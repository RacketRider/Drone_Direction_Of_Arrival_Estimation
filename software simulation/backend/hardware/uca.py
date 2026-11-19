"""
Uniform Circular Array (UCA) Hardware Model.
Implements 4-element circular interferometer geometry, steering vector manifold, and hardware impairments.
"""

from typing import List, Optional, Tuple
import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT, ArrayGeometryConfig

class UniformCircularArray:
    """
    4-element Uniform Circular Array (UCA) with radius r = 0.072 m (7.2 cm).
    Elements located at phi_m = 0, 90, 180, 270 degrees in the horizontal ground plane.
    """

    def __init__(self, config: Optional[ArrayGeometryConfig] = None):
        self.config: ArrayGeometryConfig = config or ArrayGeometryConfig()
        self.M: int = self.config.num_elements
        self.radius: float = self.config.radius
        self.element_angles_rad: np.ndarray = np.radians(self.config.element_angles_deg)
        
        # Nominal 2D horizontal coordinates of elements relative to array center [M, 2]
        self.nominal_positions: np.ndarray = np.zeros((self.M, 2))
        for m in range(self.M):
            self.nominal_positions[m, 0] = self.radius * np.cos(self.element_angles_rad[m])
            self.nominal_positions[m, 1] = self.radius * np.sin(self.element_angles_rad[m])

        # Hardware calibration impairments
        self.position_errors: np.ndarray = np.array(self.config.position_errors_m)
        self.phase_offsets_rad: np.ndarray = np.radians(self.config.phase_offsets_deg)
        self.amplitude_gains: np.ndarray = 10.0 ** (np.array(self.config.amplitude_mismatch_db) / 20.0)

    @property
    def effective_positions(self) -> np.ndarray:
        """Returns physical element coordinates including manufacturing position errors."""
        return self.nominal_positions + self.position_errors

    def steering_vector(
        self,
        frequency_hz: float,
        azimuth_deg: float,
        apply_impairments: bool = False
    ) -> np.ndarray:
        """
        Computes the theoretical complex steering vector a(f, theta) for the 4-element UCA.
        Shape: [M, 1]
        
        Mathematical definition:
        a_m(f, theta) = exp(j * 2*pi * f * r / c * cos(theta - phi_m))
        """
        theta_rad = np.radians(azimuth_deg)
        k_wave = 2.0 * np.pi * frequency_hz / SPEED_OF_LIGHT
        
        if not apply_impairments:
            # Clean analytical circular array manifold
            cos_diff = np.cos(theta_rad - self.element_angles_rad)
            phase = k_wave * self.radius * cos_diff
            return np.exp(1j * phase).reshape(-1, 1)
        else:
            # Impaired manifold with position perturbation, gain & phase mismatch
            u_wave = np.array([np.cos(theta_rad), np.sin(theta_rad)])
            eff_pos = self.effective_positions
            geom_phase = k_wave * (eff_pos @ u_wave)
            total_phase = geom_phase + self.phase_offsets_rad
            manifold = self.amplitude_gains * np.exp(1j * total_phase)
            return manifold.reshape(-1, 1)

    def steering_matrix(
        self,
        frequency_hz: float,
        azimuth_grid_deg: np.ndarray
    ) -> np.ndarray:
        """
        Vectorized computation of steering vectors across a 1D grid of azimuth angles.
        Returns matrix A of shape [M, num_angles].
        """
        k_wave = 2.0 * np.pi * frequency_hz / SPEED_OF_LIGHT
        theta_rad = np.radians(azimuth_grid_deg).reshape(1, -1)  # [1, N_angles]
        phi_m = self.element_angles_rad.reshape(-1, 1)          # [M, 1]
        
        # cos(theta - phi_m) broadcasted to [M, N_angles]
        cos_diff = np.cos(theta_rad - phi_m)
        phase = k_wave * self.radius * cos_diff
        return np.exp(1j * phase)

    def check_spatial_aliasing(self, max_frequency_hz: float = 928.0e6) -> dict:
        """
        Rigorously verifies whether the UCA geometry satisfies the spatial Nyquist criterion
        to prevent grating lobes and spatial phase ambiguities across [-180 deg, +180 deg].
        """
        wavelength_min = SPEED_OF_LIGHT / max_frequency_hz
        max_baseline = 2.0 * self.radius  # Diametric opposite elements (0 and 2, 1 and 3)
        adjacent_baseline = np.sqrt(2.0) * self.radius
        
        d_max_over_lambda = max_baseline / wavelength_min
        d_adj_over_lambda = adjacent_baseline / wavelength_min
        
        # Condition: diametric baseline < 0.5 * lambda guarantees no grating lobes
        is_aliasing_free = (d_max_over_lambda < 0.5)
        
        return {
            "max_frequency_hz": max_frequency_hz,
            "min_wavelength_m": round(wavelength_min, 4),
            "array_diameter_m": round(max_baseline, 4),
            "diameter_over_lambda": round(d_max_over_lambda, 4),
            "adjacent_chord_over_lambda": round(d_adj_over_lambda, 4),
            "is_aliasing_free": bool(is_aliasing_free)
        }

