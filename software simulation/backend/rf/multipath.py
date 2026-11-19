"""
Multipath Propagation and Reflection Physics.
Calculates multipath delay, attenuation, dispersive wall scattering, and multipath array responses.
"""

from typing import List, Tuple
import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT
from backend.simulation.environment import PhysicalEnvironment, SpecularReflectionRay
from backend.hardware.uca import UniformCircularArray

class MultipathChannel:
    """Simulates physical multipath reflections from concrete buildings."""

    def __init__(self, uca: UniformCircularArray, environment: PhysicalEnvironment):
        self.uca: UniformCircularArray = uca
        self.environment: PhysicalEnvironment = environment

    def synthesize_multipath_contributions(
        self,
        uav_pos: Tuple[float, float, float],
        active_freq_hz: float,
        s_burst: np.ndarray,
        sample_rate: float,
        los_distance_m: float,
        alpha_multiplier: float = 0.85
    ) -> Tuple[np.ndarray, List[dict]]:
        """
        Calculates the combined multipath signal array contribution:
        X_NLOS = sum_p a(f_k, theta_p) * s_NLOS,p(t)
        
        Returns:
            x_nlos: Complex ndarray of shape [M, N_samples]
            path_diagnostics: List of dicts describing active multipath paths
        """
        num_samples = s_burst.shape[1]
        x_nlos = np.zeros((self.uca.M, num_samples), dtype=np.complex128)
        
        refl_rays = self.environment.compute_specular_reflections(uav_pos)
        diagnostics = []

        t_axis = np.arange(num_samples) / sample_rate

        for ray in refl_rays:
            # Additional path delay relative to LOS
            delta_path = ray.total_path_m - los_distance_m
            delta_tau = delta_path / SPEED_OF_LIGHT  # seconds
            
            # Additional carrier phase accumulation + reflection boundary phase flip
            phase_accum = 2.0 * np.pi * active_freq_hz * delta_tau + ray.phase_shift_rad
            
            # Amplitude attenuation (relative path length and wall loss)
            path_attenuation = (los_distance_m / max(1.0, ray.total_path_m)) * ray.attenuation_linear * alpha_multiplier
            
            # Dispersive concrete wall scatter phase modulation across burst samples
            scatter_phase = np.exp(1j * (phase_accum + np.linspace(0.0, 3.8 * np.pi, num_samples)))
            
            # Reflected baseband waveform
            s_refl = path_attenuation * s_burst * scatter_phase.reshape(1, -1)
            
            # Multipath array response vector a(f_k, theta_refl)
            a_refl = self.uca.steering_vector(active_freq_hz, ray.azimuth_deg, apply_impairments=True)
            
            x_nlos += a_refl @ s_refl
            
            diagnostics.append({
                "building_id": ray.building_id,
                "refl_point": [round(c, 2) for c in ray.refl_point],
                "azimuth_deg": round(ray.azimuth_deg, 2),
                "total_path_m": round(ray.total_path_m, 2),
                "delay_ns": round(delta_tau * 1.0e9, 2),
                "attenuation_linear": round(path_attenuation, 3),
                "attenuation_db": round(20.0 * np.log10(max(1e-6, path_attenuation)), 2)
            })

        return x_nlos, diagnostics

