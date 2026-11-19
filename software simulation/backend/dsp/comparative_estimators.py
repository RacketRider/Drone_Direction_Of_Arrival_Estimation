"""
Comparative Direction-of-Arrival (DoA) Benchmark Algorithms.
Implements:
1. Power-Vector Maximum Likelihood (PV-ML) with Fisher scoring & parabolic profile interpolation.
2. Power-Weighted Beam Centroid (vector sum of boresights).
3. Strongest Beam (coarse sector argmax).
4. Uniform Circular Array ESPRIT (UCA-ESPRIT in phase-mode beamspace).
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import scipy.special as sp

from backend.simulation.configuration import SPEED_OF_LIGHT
from backend.hardware.uca import UniformCircularArray


def wrap180(angles_deg: np.ndarray) -> np.ndarray:
    """Wraps angles to [-180, +180] degrees."""
    return (np.asarray(angles_deg, dtype=float) + 180.0) % 360.0 - 180.0


def wrap360(angles_deg: np.ndarray) -> np.ndarray:
    """Wraps angles to [0, 360) degrees."""
    return np.asarray(angles_deg, dtype=float) % 360.0


def parabolic_interpolation(y0: float, y1: float, y2: float) -> Tuple[float, float]:
    """
    Fits parabola y(x) through (-1, y0), (0, y1), (+1, y2).
    Returns: (delta_x, curvature_second_difference)
    """
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-12:
        return 0.0, 0.0
    delta = np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0)
    return float(delta), float(denom)


class PowerVectorMLEstimator:
    """
    Maximum-Likelihood fit of switched-beam measured power vector to known directional antenna patterns.
    Applies Fisher scoring to profile out source amplitude, followed by coarse-to-fine parabolic NLL refinement.
    """

    def __init__(
        self,
        num_beams: int = 4,
        beamwidth_deg: float = 100.0,
        sidelobe_floor_db: float = 20.0,
        grid_step_deg: float = 1.0
    ):
        self.num_beams = num_beams
        self.beamwidth_deg = beamwidth_deg
        self.sidelobe_floor_db = sidelobe_floor_db
        self.grid_step_deg = grid_step_deg

        self.boresights_deg = (360.0 / num_beams) * np.arange(num_beams)
        self.grid_angles = np.arange(0.0, 360.0, grid_step_deg)
        self.gain_table = self._compute_gain_table(self.grid_angles)  # [T, N_beams]

    def _compute_gain_table(self, angles_deg: np.ndarray) -> np.ndarray:
        """Evaluates linear directional gain for all beams across given azimuth angles."""
        th = np.asarray(angles_deg, dtype=float)[:, None]
        d = wrap180(th - self.boresights_deg[None, :])
        # 3GPP parabolic main-lobe approximation with flat sidelobe floor
        a_db = -np.minimum(12.0 * (d / self.beamwidth_deg) ** 2, self.sidelobe_floor_db)
        return 10.0 ** (a_db / 10.0)

    def estimate(
        self,
        measured_powers: np.ndarray,
        dwell_samples: int = 64,
        noise_variance: float = 1.0
    ) -> Dict:
        """
        Estimates DoA from measured beam powers.
        
        Args:
            measured_powers: 1D array of measured power per beam [N_beams]
            dwell_samples: Number of samples L averaged per beam dwell
            noise_variance: Calibrated receiver noise power sigma^2
            
        Returns:
            Dict containing estimated angle (deg), CRB uncertainty sigma (deg),
            reduced deviance chi^2, and estimated SNR (dB).
        """
        p = np.maximum(1e-6, np.asarray(measured_powers, dtype=float))
        T = len(self.grid_angles)
        G = self.gain_table
        L = dwell_samples
        sigma2 = noise_variance

        # 1. Initial amplitude estimate via linear projection
        p_excess = np.maximum(p - sigma2, 0.0)
        a_init = (p_excess * G).sum(axis=-1) / np.maximum(1e-6, (G * G).sum(axis=-1))
        a_floor = 1e-4 * sigma2
        a = np.maximum(a_init, a_floor)

        # 2. Fisher scoring optimization over source amplitude a
        for _ in range(5):
            m = a[:, None] * G + sigma2
            grad = (G * (m - p[None, :]) / (m ** 2)).sum(axis=-1)
            fish = (G ** 2 / (m ** 2)).sum(axis=-1)
            a = np.maximum(a - grad / np.maximum(1e-9, fish), a_floor)

        # 3. Profile Negative Log-Likelihood (NLL) for Gamma distribution
        m = a[:, None] * G + sigma2
        nll = L * (np.log(m) + p[None, :] / m).sum(axis=-1)

        # 4. Grid search minimum
        k_min = int(np.argmin(nll))
        k_prev = (k_min - 1) % T
        k_next = (k_min + 1) % T

        # 5. Coarse parabolic refinement
        delta, den = parabolic_interpolation(nll[k_prev], nll[k_min], nll[k_next])
        th_coarse = self.grid_angles[k_min] + delta * self.grid_step_deg

        # 6. Fine parabolic interpolation on 4x finer local grid
        d_fine = self.grid_step_deg / 4.0
        cand_angles = th_coarse + d_fine * np.array([-1.0, 0.0, 1.0])
        G_fine = self._compute_gain_table(cand_angles)
        
        # Profile on fine candidate angles
        a_fine = a[k_min]
        m_fine = a_fine * G_fine + sigma2
        nll_fine = L * (np.log(m_fine) + p[None, :] / m_fine).sum(axis=-1)
        delta2, _ = parabolic_interpolation(nll_fine[0], nll_fine[1], nll_fine[2])
        est_theta = float(wrap360(th_coarse + delta2 * d_fine))

        # 7. Uncertainty estimation (Cramer-Rao bound curvature + reduced deviance)
        curvature = den / (self.grid_step_deg ** 2)
        sig_crb = 1.0 / np.sqrt(max(1e-6, curvature)) if curvature > 1e-6 else 45.0

        # Goodness-of-fit: Gamma reduced deviance
        m_best = a[k_min] * G[k_min] + sigma2
        r = p / m_best
        red_dev = float(2.0 * L * np.sum(r - 1.0 - np.log(np.maximum(1e-12, r))) / max(1, self.num_beams - 2))
        est_sigma = float(np.clip(sig_crb * np.sqrt(max(1.0, red_dev)), 0.1, 90.0))

        # Estimated SNR
        snr_est_db = float(10.0 * np.log10(max(1e-3, a[k_min] / sigma2)))

        return {
            "method": "POWER_VECTOR_ML",
            "est_azimuth_deg": round(est_theta, 2),
            "sigma_deg": round(est_sigma, 2),
            "reduced_deviance": round(red_dev, 2),
            "estimated_snr_db": round(snr_est_db, 1)
        }


class BeamCentroidEstimator:
    """
    Calculates power-weighted circular vector centroid of the beam boresights.
    Fast, non-iterative, and robust at moderate-to-high SNR.
    """

    @staticmethod
    def estimate(
        measured_powers: np.ndarray,
        boresights_deg: np.ndarray,
        noise_variance: float = 1.0
    ) -> float:
        weights = np.maximum(0.0, np.asarray(measured_powers, dtype=float) - noise_variance)
        if np.sum(weights) < 1e-9:
            return float(boresights_deg[np.argmax(measured_powers)])

        rad = np.radians(boresights_deg)
        z = np.sum(weights * np.exp(1j * rad))
        return float(wrap360(np.degrees(np.angle(z))))


class StrongestBeamEstimator:
    """Coarse sector selector pointing directly along the boresight with maximum received power."""

    @staticmethod
    def estimate(measured_powers: np.ndarray, boresights_deg: np.ndarray) -> float:
        best_idx = int(np.argmax(measured_powers))
        return float(boresights_deg[best_idx])


class UcaEspritEstimator:
    """
    Uniform Circular Array ESPRIT (UCA-ESPRIT) in phase-mode beamspace.
    Eliminates angular grid search by converting circular manifold into a virtual shift-invariant Vandermonde manifold.
    """

    def __init__(self, uca: UniformCircularArray, mode_count_m: Optional[int] = None):
        self.uca = uca
        self.N = uca.M
        self.radius_m = uca.radius
        self.element_angles_rad = uca.element_angles_rad

        # Maximum spatial mode index M <= (N-1)//2
        self.M = mode_count_m if mode_count_m is not None else max(1, (self.N - 1) // 2)

    def estimate(self, covariance_matrix: np.ndarray, frequency_hz: float) -> Dict:
        """
        Estimates DoA using beamspace UCA-ESPRIT.
        
        Args:
            covariance_matrix: Sample covariance matrix R_xx [N, N]
            frequency_hz: Operating RF frequency
            
        Returns:
            Dict containing estimated azimuth (deg) and status.
        """
        R_xx = np.asarray(covariance_matrix, dtype=complex)
        wavelength = SPEED_OF_LIGHT / frequency_hz
        k0 = 2.0 * np.pi / wavelength
        kr = k0 * self.radius_m

        m_indices = np.arange(-self.M, self.M + 1)
        dim = len(m_indices)  # 2M + 1

        # Phase-mode transform matrix F: F_mn = (1/N) * exp(-j * m * gamma_n)
        F = np.exp(-1j * np.outer(m_indices, self.element_angles_rad)) / self.N

        # Bessel function normalization weights: J_m(kr) * j^m
        bessel_weights = sp.jv(m_indices, kr) * (1j ** m_indices)
        # Avoid division by zero
        bessel_weights = np.where(np.abs(bessel_weights) > 1e-12, bessel_weights, 1e-12)

        # Beamspace covariance matrix R_bm = F @ R_xx @ F^H
        R_bm = F @ R_xx @ F.conj().T

        # Eigendecomposition in beamspace
        eigvals, eigvecs = np.linalg.eigh(R_bm)

        # Principal signal subspace eigenvector (largest eigenvalue)
        e_signal = eigvecs[:, -1]

        # Normalize signal subspace by Bessel weights to recover shift-invariant Vandermonde structure
        u_vector = (e_signal / np.linalg.norm(e_signal)) / bessel_weights

        # Sub-matrices U1 and U2 representing delay shift
        u1 = u_vector[:-1]
        u2 = u_vector[1:]

        # Shift invariance rotation operator: psi = (U1^H * U2) / (U1^H * U1)
        psi = np.vdot(u1, u2) / max(1e-12, np.vdot(u1, u1))
        phase_rad = float(np.angle(psi))

        # DoA in horizontal plane
        est_deg = float(wrap360(-np.degrees(phase_rad)))

        return {
            "method": "UCA_ESPRIT",
            "est_azimuth_deg": round(est_deg, 2),
            "phase_rad": round(phase_rad, 4),
            "mode_count": self.M
        }
