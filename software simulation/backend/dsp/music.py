"""
Vectorized MUSIC Pseudospectrum and Direction of Arrival Estimator.
Computes frequency-compensated vs static spatial pseudospectra and extracts DOA peaks.
"""

from typing import Tuple
import numpy as np

class MUSICEstimator:
    """Vectorized Circular MUSIC algorithm for DoA estimation."""

    @staticmethod
    def evaluate_pseudospectrum(
        steering_matrix: np.ndarray,
        noise_projector: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes P_MUSIC(theta) = 1 / (a(theta)^H * P_n * a(theta)) across all grid angles.
        
        Args:
            steering_matrix: Array manifold matrix A of shape [M, N_angles]
            noise_projector: Noise subspace projection operator P_n of shape [M, M]
            
        Returns:
            spectrum_linear: Linear pseudospectrum values [N_angles]
            spectrum_db: Normalized pseudospectrum in dB [N_angles]
        """
        # Vectorized denominator computation:
        # P_n @ A has shape [M, N_angles]
        proj_a = noise_projector @ steering_matrix
        
        # Elementwise conjugate multiply and sum over antenna axis:
        # denom = sum_m (A_m^* * (P_n A)_m)
        denom = np.real(np.sum(steering_matrix.conj() * proj_a, axis=0))
        denom = np.maximum(1e-12, denom)

        spectrum_linear = 1.0 / denom
        max_val = max(1e-12, np.max(spectrum_linear))
        spectrum_db = 10.0 * np.log10(spectrum_linear / max_val)

        return spectrum_linear, spectrum_db

    @staticmethod
    def extract_peak_bearing(
        spectrum_db: np.ndarray,
        angle_grid_deg: np.ndarray
    ) -> float:
        """Finds azimuth angle corresponding to the maximum spectral peak."""
        peak_idx = int(np.argmax(spectrum_db))
        return float(angle_grid_deg[peak_idx])

    @staticmethod
    def circular_angular_error(est_deg: float, true_deg: float) -> float:
        """
        Computes shortest circular angular distance modulo 360 degrees:
        error = ((est - true + 180) % 360) - 180 in [-180, +180] degrees.
        """
        diff = est_deg - true_deg
        return float(((diff + 180.0) % 360.0) - 180.0)

