"""
Eigenvalue Spread Multipath Reliability Gate.
Evaluates the eigenvalue ratio gamma = lambda_1 / lambda_2 against threshold gamma_th.
"""

from typing import Tuple
import numpy as np

class EigenvalueGate:
    """Evaluates spatial covariance eigenvalue spread to filter multipath outliers."""

    def __init__(self, threshold: float = 8.0):
        self.threshold: float = threshold

    def evaluate(self, eigenvalues: np.ndarray) -> Tuple[bool, float, dict]:
        """
        Calculates gamma = lambda_1 / (lambda_2 + eps).
        
        Args:
            eigenvalues: Real 1D array of sorted eigenvalues [M]
            
        Returns:
            is_accepted: True if burst is reliable (LoS), False if multipath corrupted
            ratio: Computed spread ratio gamma
            diagnostics: Gate evaluation diagnostics dictionary
        """
        l1 = float(eigenvalues[0])
        l2 = float(eigenvalues[1])
        eps = 1.0e-12

        # Eigenvalue spread ratio
        ratio = float(l1 / (max(0.0, l2) + eps))
        is_accepted = bool(ratio >= self.threshold)

        reason = "ACCEPTED: Dominant single-source LoS" if is_accepted else "REJECTED: Multipath dispersion / second source detected"

        diagnostics = {
            "lambda_1": round(l1, 4),
            "lambda_2": round(l2, 4),
            "ratio": round(ratio, 2),
            "threshold": round(self.threshold, 2),
            "is_accepted": is_accepted,
            "status": "ACCEPTED" if is_accepted else "REJECTED",
            "reason": reason
        }

        return is_accepted, ratio, diagnostics

