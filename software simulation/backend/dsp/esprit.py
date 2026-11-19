"""
Beamspace Phase-Mode UCA-ESPRIT Direction-of-Arrival Estimator.
Transforms circular array manifold into virtual uniform linear array via Bessel phase-modes,
and extracts DoA algebraically through shift-invariance without search grids.
"""

from __future__ import annotations
from typing import Optional, Tuple
import numpy as np
from scipy.special import jv

from backend.hardware.uca import UniformCircularArray
from backend.simulation.configuration import SPEED_OF_LIGHT


class UCAESPRITEstimator:
    """
    Uniform Circular Array ESPRIT using Beamspace Phase-Mode Excitation.
    Serves as an analytical super-resolution benchmark for comparison against MUSIC.
    """

    def __init__(self, uca: UniformCircularArray, M: Optional[int] = None):
        self.uca: UniformCircularArray = uca
        self.N: int = uca.M
        self.radius_m: float = uca.config.radius

        # Element azimuth angles in radians
        self.gamma_rad: np.ndarray = np.deg2rad(np.array(uca.config.element_angles_deg, dtype=float))

        # Select mode order M: default max mode M <= (N - 1) // 2
        self.M: int = M if M is not None else max(1, (self.N - 1) // 2)

        # Mode indices m in [-M, ..., +M]
        self.m_modes: np.ndarray = np.arange(-self.M, self.M + 1)
        self.num_modes: int = len(self.m_modes)

        # Phase-mode transformation matrix F of shape [2M+1, N]
        self.F: np.ndarray = np.exp(-1j * np.outer(self.m_modes, self.gamma_rad)) / self.N

    def estimate(
        self,
        covariance_matrix: np.ndarray,
        carrier_freq_hz: float,
        num_signals: int = 1
    ) -> float:
        """
        Estimates DoA angle in degrees using beamspace phase-mode UCA-ESPRIT.
        """
        wavelength = SPEED_OF_LIGHT / carrier_freq_hz
        kr = 2.0 * np.pi * (self.radius_m / wavelength)

        # Bessel mode scaling coefficients j^m * J_m(kr)
        bessel_coeff = np.exp(1j * (np.pi / 2.0) * self.m_modes) * jv(self.m_modes, kr)

        # Protect against division by zero at Bessel nulls
        safe_bessel = np.where(np.abs(bessel_coeff) > 1e-6, bessel_coeff, 1e-6)

        # 1. Transform covariance into beamspace: R_beam = F * R_xx * F^H
        r_beam = self.F @ covariance_matrix @ self.F.conj().T

        # 2. Hermitian Eigendecomposition of transformed covariance
        eigvals, eigvecs = np.linalg.eigh(r_beam)

        # Signal subspace vector (dominant eigenvector)
        v_sig = eigvecs[:, -1]

        # 3. Undo Bessel weighting on the subspace: U = v / bessel_coeff
        u = v_sig / safe_bessel
        u_norm = np.linalg.norm(u)
        if u_norm > 1e-12:
            u = u / u_norm

        # 4. Shift-invariance sub-arrays: U1 = U[:-1], U2 = U[1:]
        u1 = u[:-1]
        u2 = u[1:]

        denom = float(np.sum(np.abs(u1)**2))
        if denom < 1e-12:
            return 0.0

        z = np.sum(u1.conj() * u2) / denom
        angle_rad = -np.angle(z)
        angle_deg = float(np.degrees(angle_rad) % 360.0)

        # Map to [-180, +180] convention
        angle_wrapped = float(((angle_deg + 180.0) % 360.0) - 180.0)
        return angle_wrapped
