"""
Sample Covariance Matrix Calculator.
Computes spatial covariance R_xx = (1/N) * X * X^H with Hermitian preservation and conditioning checks.
"""

from typing import Tuple
import numpy as np

class CovarianceEstimator:
    """Computes and validates the sample spatial covariance matrix."""

    @staticmethod
    def compute_covariance(snapshots: np.ndarray) -> Tuple[np.ndarray, dict]:
        """
        Calculates R_xx = (1/N) * X * X^H from snapshot matrix X [M, N].
        
        Args:
            snapshots: Complex snapshot array [M, N]
            
        Returns:
            r_xx: Hermitian complex matrix [M, M]
            diagnostics: Numerical validation metadata
        """
        M, N = snapshots.shape
        if N < M:
            raise ValueError(f"Snapshots N={N} must be >= antenna count M={M}")

        # Unbiased spatial sample covariance
        r_xx = (snapshots @ snapshots.conj().T) / float(N)

        # Enforce exact Hermitian symmetry: R = (R + R^H) / 2
        r_xx = 0.5 * (r_xx + r_xx.conj().T)

        # Numerical diagnostics
        trace_val = float(np.real(np.trace(r_xx)))
        diag_elements = np.real(np.diag(r_xx))
        
        # Check condition number
        cond_num = float(np.linalg.cond(r_xx))

        diagnostics = {
            "matrix_dim": M,
            "snapshots_averaged": N,
            "trace_power": round(trace_val, 4),
            "diagonal_powers": [round(float(p), 4) for p in diag_elements],
            "condition_number": round(cond_num, 2),
            "is_hermitian": bool(np.allclose(r_xx, r_xx.conj().T, atol=1e-10))
        }

        return r_xx, diagnostics

