"""
Switched-Beam Power-Vector Maximum-Likelihood and Baseline Direction-Finding Estimators.
Implements Fisher-scoring ML pattern fitting, power-weighted centroid, and strongest-beam selection.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np


def wrap180(deg: float | np.ndarray) -> float | np.ndarray:
    """Wraps angle to [-180, +180) degrees."""
    return (np.asarray(deg, dtype=float) + 180.0) % 360.0 - 180.0


def wrap360(deg: float | np.ndarray) -> float | np.ndarray:
    """Wraps angle to [0, 360) degrees."""
    return np.asarray(deg, dtype=float) % 360.0


def est_strongest_beam(
    beam_powers: np.ndarray,
    boresights_deg: np.ndarray
) -> float:
    """Returns the boresight angle of the antenna beam with maximum received power."""
    idx = int(np.argmax(beam_powers))
    return float(wrap180(boresights_deg[idx]))


def est_power_centroid(
    beam_powers: np.ndarray,
    boresights_deg: np.ndarray,
    noise_floor: float = 1.0
) -> float:
    """
    Computes power-weighted vector centroid of beam boresights with noise-floor subtraction:
    z = sum_i max(0, p_i - sigma^2) * exp(j * theta_i)
    """
    weights = np.maximum(beam_powers - noise_floor, 0.0)
    if np.sum(weights) < 1e-9:
        return float(est_strongest_beam(beam_powers, boresights_deg))

    z = np.sum(weights * np.exp(1j * np.deg2rad(boresights_deg)))
    angle_deg = float(np.degrees(np.angle(z)))
    return float(wrap180(angle_deg))


class PowerVectorMLEstimator:
    """
    Maximum-Likelihood Estimator for Switched Directional Antenna Arrays.
    Profiles out unknown source power and optimizes azimuth angle via Fisher scoring.
    """

    def __init__(
        self,
        boresights_deg: List[float] = [0.0, 90.0, 180.0, 270.0],
        beamwidth_deg: float = 90.0,
        sidelobe_db: float = 20.0,
        grid_step_deg: float = 1.0
    ):
        self.boresights_deg = np.array(boresights_deg, dtype=float)
        self.N = len(boresights_deg)
        self.beamwidth_deg = beamwidth_deg
        self.sidelobe_db = sidelobe_db
        self.step_deg = grid_step_deg

        self.angle_grid = np.arange(-180.0, 180.0, grid_step_deg)
        self.G_table = self.evaluate_beam_gains(self.angle_grid)  # [T, N]

    def evaluate_beam_gains(self, angles_deg: np.ndarray) -> np.ndarray:
        """Evaluates linear directional gain of all N beams across candidate angles."""
        th = np.asarray(angles_deg, dtype=float)
        if th.ndim == 1:
            th = th[:, None]
        delta_deg = wrap180(th - self.boresights_deg)
        atten_db = -np.minimum(12.0 * (delta_deg / self.beamwidth_deg)**2, self.sidelobe_db)
        return 10.0 ** (atten_db / 10.0)

    def estimate(
        self,
        beam_powers: np.ndarray,
        noise_variance: float = 1.0,
        dwell_samples: int = 64
    ) -> Dict:
        """
        Executes ML profile fit over measured beam powers.
        Returns:
            estimated_bearing_deg: float
            sigma_deg: float (angular uncertainty)
            reduced_deviance: float (goodness-of-fit statistic)
            estimated_snr_db: float
        """
        p = np.asarray(beam_powers, dtype=float).reshape(1, -1)
        G = self.G_table  # [T, N]
        T = len(self.angle_grid)

        # 1. Profile NLL over source power `a`
        ph = np.maximum(p - noise_variance, 0.0)
        a_init = (ph * G).sum(-1) / np.maximum((G * G).sum(-1), 1e-6)
        floor_a = 1e-4 * noise_variance
        a = np.maximum(a_init, floor_a)

        # 2. Fisher scoring iterations
        for _ in range(4):
            m = a[..., None] * G + noise_variance
            grad = (G * (m - p) / (m**2)).sum(-1)
            fish = (G**2 / (m**2)).sum(-1)
            a = np.maximum(a - grad / np.maximum(fish, 1e-6), floor_a)

        m = a[..., None] * G + noise_variance
        nll = dwell_samples * (np.log(m) + p / m).sum(-1)

        # 3. Best grid minimum
        best_idx = int(np.argmin(nll))
        best_angle = self.angle_grid[best_idx]

        # 4. Parabolic fine interpolation
        prev_idx = (best_idx - 1) % T
        next_idx = (best_idx + 1) % T
        y0 = nll[prev_idx]
        y1 = nll[best_idx]
        y2 = nll[next_idx]

        den = y0 - 2.0 * y1 + y2
        delta = 0.0
        if den > 1e-12:
            delta = float(np.clip(0.5 * (y0 - y2) / den, -1.0, 1.0))

        refined_angle = wrap180(best_angle + delta * self.step_deg)

        # 5. Goodness-of-fit reduced deviance and variance
        a_hat = float(a[best_idx])
        m_best = a_hat * G[best_idx] + noise_variance
        ratio = p[0] / m_best
        red_dev = float(2.0 * dwell_samples * np.sum(ratio - 1.0 - np.log(np.maximum(1e-6, ratio))) / max(1, self.N - 2))

        curv = den / (self.step_deg**2)
        sig_crb = float(1.0 / np.sqrt(max(curv, 1e-6))) if curv > 1e-6 else 45.0
        sigma_inflated = float(np.clip(sig_crb * np.sqrt(max(1.0, red_dev)), 0.1, 90.0))
        snr_db = float(10.0 * np.log10(max(1e-3, a_hat / noise_variance)))

        return {
            "estimated_bearing_deg": round(float(refined_angle), 2),
            "sigma_deg": round(sigma_inflated, 2),
            "reduced_deviance": round(red_dev, 2),
            "estimated_snr_db": round(snr_db, 1)
        }
