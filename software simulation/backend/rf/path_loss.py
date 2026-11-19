"""
RF Path Loss and Attenuation Models.
Implements Friis Free-Space Path Loss (FSPL) and distance-dependent phase delay.
"""

import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT

class PathLossModel:
    """Calculates physical path loss and geometric propagation delay."""

    @staticmethod
    def free_space_path_loss_db(distance_m: float, frequency_hz: float) -> float:
        """
        Calculates Free-Space Path Loss in dB via Friis transmission equation.
        FSPL_dB = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)
        """
        d = max(1.0, distance_m)
        wavelength = SPEED_OF_LIGHT / frequency_hz
        fspl_linear = (4.0 * np.pi * d / wavelength) ** 2
        return float(10.0 * np.log10(fspl_linear))

    @staticmethod
    def propagation_delay_seconds(distance_m: float) -> float:
        """Calculates propagation time of flight tau = d / c."""
        return float(distance_m / SPEED_OF_LIGHT)

    @staticmethod
    def carrier_phase_rad(distance_m: float, frequency_hz: float) -> float:
        """Calculates carrier phase shift accumulated over distance d: phi = -2*pi*f*d/c."""
        phase = -2.0 * np.pi * frequency_hz * (distance_m / SPEED_OF_LIGHT)
        return float(np.mod(phase, 2.0 * np.pi))

    @staticmethod
    def relative_amplitude(distance_m: float, ref_distance_m: float = 10.0) -> float:
        """
        Calculates normalized relative amplitude (1/d envelope) relative to ref_distance.
        """
        d = max(1.0, distance_m)
        return float(ref_distance_m / d)

