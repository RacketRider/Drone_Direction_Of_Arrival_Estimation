"""
Frequency-Compensated and Static Steering Vector Generators.
Implements:
1. Proposed A2 Dynamic Frequency-Compensated Manifold a(f_k, theta)
2. Exact Physical Static Manifold a(f_ref, theta) [r=7.2cm circular at 433 MHz]
3. Midsem Slide Baseline Model (Simulates legacy linear/scaled frequency mismatch)
"""

from typing import Literal, Tuple
import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT
from backend.hardware.uca import UniformCircularArray

class SteeringVectorProvider:
    """Provides dynamic frequency-compensated and static baseline steering manifolds."""

    def __init__(
        self,
        uca: UniformCircularArray,
        reference_frequency_hz: float = 433.0e6,
        grid_min_deg: float = -180.0,
        grid_max_deg: float = 180.0,
        grid_resolution_deg: float = 0.5,
        static_baseline_model: Literal["CIRCULAR_FREF", "SLIDE_MISMATCH"] = "CIRCULAR_FREF"
    ):
        self.uca: UniformCircularArray = uca
        self.reference_frequency_hz: float = reference_frequency_hz
        self.static_baseline_model: str = static_baseline_model
        self.angle_grid_deg: np.ndarray = np.arange(
            grid_min_deg, grid_max_deg + 1e-4, grid_resolution_deg
        )

    def get_compensated_steering_matrix(self, detected_freq_hz: float) -> np.ndarray:
        """
        Proposed A2 Method: Dynamic steering manifold tailored to active hop frequency f_k.
        Shape: [M, num_angles]
        """
        return self.uca.steering_matrix(detected_freq_hz, self.angle_grid_deg)

    def get_static_steering_matrix(self, active_freq_hz: float = 915.0e6) -> np.ndarray:
        """
        Static Baseline Method:
        - CIRCULAR_FREF: Exact physical circular array manifold evaluated at f_ref (433 MHz).
        - SLIDE_MISMATCH: Matches the team's Slide 8 prototype formula:
          f_mismatch = f_k * (f_k / f_ref), generating the classic synthetic angular bias.
        """
        if self.static_baseline_model == "SLIDE_MISMATCH":
            # Midsem Slide 8 model: synthetic scaled frequency mismatch
            f_mismatch = active_freq_hz * (active_freq_hz / self.reference_frequency_hz)
            theta_rad = np.radians(self.angle_grid_deg).reshape(1, -1)
            m_idx = np.arange(self.uca.M).reshape(-1, 1)
            # Distorted linear/circular phase mismatch
            phase = -1j * 2.0 * np.pi * self.uca.radius * f_mismatch * np.sin(theta_rad) / SPEED_OF_LIGHT * m_idx
            return np.exp(phase)
        else:
            # Physical static circular manifold at f_ref (433 MHz)
            return self.uca.steering_matrix(self.reference_frequency_hz, self.angle_grid_deg)

    def get_angle_grid(self) -> np.ndarray:
        """Returns the 1D search grid in degrees."""
        return self.angle_grid_deg
