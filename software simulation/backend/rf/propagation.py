"""
Composite RF Propagation Pipeline.
Calculates direct LOS, building occlusion, multipath reflections, and AWGN at the antenna array.
"""

from typing import Dict, List, Tuple
import numpy as np
from backend.simulation.configuration import RFPropagationConfig, SPEED_OF_LIGHT
from backend.simulation.environment import PhysicalEnvironment
from backend.hardware.uca import UniformCircularArray
from backend.rf.signal_model import SignalModel
from backend.rf.multipath import MultipathChannel
from backend.rf.noise import ComplexAWGNGenerator
from backend.rf.path_loss import PathLossModel

class RFPropagationEngine:
    """End-to-end multi-channel RF field simulation at the 4-element UCA."""

    def __init__(
        self,
        uca: UniformCircularArray,
        environment: PhysicalEnvironment,
        config: RFPropagationConfig,
        seed: int = 42
    ):
        self.uca: UniformCircularArray = uca
        self.environment: PhysicalEnvironment = environment
        self.config: RFPropagationConfig = config
        self.multipath_channel = MultipathChannel(uca, environment)
        self.noise_gen = ComplexAWGNGenerator(seed=seed)

    def simulate_burst_stream(
        self,
        uav_pos: Tuple[float, float, float],
        active_freq_hz: float,
        receiver_lo_hz: float,
        snr_db: float,
        carrier_phase_rad: float = 0.0,
        foliage_density: float = 0.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Simulates the entire multi-antenna IQ stream across time:
        X_stream: [M, N_total] containing noise guard and burst window.
        X_burst: [M, N_burst] sliced active burst for spatial analysis.
        
        Returns:
            stream: Complex ndarray [M, N_total]
            burst_slice: Complex ndarray [M, N_burst]
            metadata: Propagation diagnostics dictionary
        """
        M = self.uca.M
        n_total = self.config.total_stream_samples
        n_burst = self.config.burst_samples
        b_start = self.config.burst_start_sample
        b_end = b_start + n_burst

        # 1. Base AWGN noise background across entire stream
        stream = self.noise_gen.generate_noise((M, n_total), snr_db=snr_db, signal_power=1.0)

        # 2. Check Line-of-Sight (LOS) occlusion by buildings
        is_occluded, occluding_bldg_id = self.environment.check_los_occlusion(uav_pos)

        # 3. Ground-truth distance and azimuth
        ux, uy, uz = uav_pos
        los_dist = float(np.sqrt(ux * ux + uy * uy + uz * uz))
        true_az = float(np.degrees(np.arctan2(uz, ux)))

        # 4. Generate baseband packet burst waveform
        s_burst, f_bb = SignalModel.generate_burst_waveform(
            carrier_freq_hz=active_freq_hz,
            receiver_lo_hz=receiver_lo_hz,
            num_samples=n_burst,
            sample_rate=self.config.sample_rate,
            carrier_phase_rad=carrier_phase_rad
        )

        # 5. Direct Line-of-Sight (LOS) array response
        # Direct ray steering vector
        a_direct = self.uca.steering_vector(active_freq_hz, true_az, apply_impairments=True)
        
        # Path delay phase and attenuation
        prop_phase = PathLossModel.carrier_phase_rad(los_dist, active_freq_hz)
        los_attenuation = 1.0
        foliage_loss_db = 0.0
        if is_occluded:
            # Heavy attenuation through concrete structure (25 dB loss)
            los_attenuation = 0.056  # 10^(-25/20)
        elif foliage_density > 0.05:
            # ITU-R P.833 vegetation attenuation through tree foliage
            f_mhz = active_freq_hz / 1e6
            foliage_loss_db = float(0.18 * (f_mhz ** 0.3) * (foliage_density * min(los_dist, 35.0)) ** 0.5)
            los_attenuation = float(10.0 ** (-foliage_loss_db / 20.0))

        s_direct = (los_attenuation * np.exp(1j * prop_phase)) * s_burst
        x_direct = a_direct @ s_direct  # Shape: [M, N_burst]

        # 6. Multipath reflection contribution
        x_nlos = np.zeros_like(x_direct)
        nlos_diagnostics: List[dict] = []
        if self.config.multipath_enabled:
            x_nlos, nlos_diagnostics = self.multipath_channel.synthesize_multipath_contributions(
                uav_pos=uav_pos,
                active_freq_hz=active_freq_hz,
                s_burst=s_burst,
                sample_rate=self.config.sample_rate,
                los_distance_m=los_dist,
                alpha_multiplier=self.config.multipath_strength_factor
            )

        # 7. Composite RF burst at antenna elements
        x_burst_clean = x_direct + x_nlos
        
        # Inject burst into stream window
        stream[:, b_start:b_end] += x_burst_clean
        burst_slice = stream[:, b_start:b_end]

        metadata = {
            "active_freq_hz": active_freq_hz,
            "f_baseband_hz": f_bb,
            "true_azimuth_deg": true_az,
            "los_distance_m": los_dist,
            "is_occluded": is_occluded,
            "occluding_building_id": occluding_bldg_id,
            "foliage_loss_db": foliage_loss_db,
            "foliage_density": foliage_density,
            "has_multipath": len(nlos_diagnostics) > 0,
            "nlos_paths": nlos_diagnostics,
            "snr_db": snr_db
        }

        return stream, burst_slice, metadata

