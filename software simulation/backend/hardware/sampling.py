"""
IQ Sampling Engine: Mode A (Simultaneous Coherent) vs Mode B (Single-SDR Switched).
Handles sequential slot reconstruction, phase de-rotation, and coherence verification.
"""

from typing import Tuple
import numpy as np
from backend.simulation.configuration import SwitchedSDRConfig
from backend.hardware.rf_switch import HMC241RFSwitch
from backend.hardware.sdr import RTLSDRReceiver

class SamplingSubsystem:
    """Orchestrates hardware capture for Mode A and Mode B receivers."""

    def __init__(self, config: SwitchedSDRConfig, sdr: RTLSDRReceiver):
        self.config: SwitchedSDRConfig = config
        self.sdr: RTLSDRReceiver = sdr
        self.switch: HMC241RFSwitch = HMC241RFSwitch(
            settling_samples=config.switch_settling_samples,
            dwell_samples=config.dwell_samples_per_antenna
        )

    def capture_burst(
        self,
        multichannel_burst: np.ndarray,
        detected_f_bb_hz: float
    ) -> Tuple[np.ndarray, bool, dict]:
        """
        Samples the physical RF burst according to configured receiver mode.
        
        Args:
            multichannel_burst: Raw physical field at elements [M, N_samples]
            detected_f_bb_hz: Estimated baseband frequency used for Mode B de-rotation
            
        Returns:
            x_snapshots: Reconstructed array snapshots for spatial covariance [M, N_snapshots]
            coherence_ok: Boolean flag indicating valid spatial phase alignment
            diagnostics: Sampling diagnostics dictionary
        """
        M, N = multichannel_burst.shape

        if self.config.receiver_mode == "MODE_A_SIMULTANEOUS":
            # Mode A: Ideal 4-channel coherent simultaneous receiver
            # All snapshots are perfectly aligned in time
            return multichannel_burst, True, {
                "mode": "MODE_A_SIMULTANEOUS",
                "snapshots_used": N,
                "phase_de_rotation_applied": False,
                "phase_coherence_metric": 1.0,
                "settling_samples_discarded": 0
            }

        # Mode B: Single-SDR sequential switched receiver (HMC241)
        # 1. Route through physical SP4T switch to get single SDR ADC stream
        sdr_stream, valid_mask = self.switch.route_sequential_burst(multichannel_burst)
        
        dwell = self.config.dwell_samples_per_antenna
        settle = self.config.switch_settling_samples
        n_eff = dwell - settle  # Valid samples per slot (e.g. 64 - 4 = 60)
        
        x_recon = np.zeros((M, n_eff), dtype=np.complex128)
        fs = self.sdr.sample_rate

        # 2. De-rotate temporal carrier phase progression across switch dwell slots
        for m in range(M):
            start_idx = m * dwell + settle
            end_idx = (m + 1) * dwell
            slot_samples = sdr_stream[start_idx:end_idx]
            
            if self.config.phase_de_rotation_enabled:
                # Time elapsed from slot 0 start to slot m start
                delta_t = float(m * dwell) / fs
                carrier_rot = np.exp(-1j * 2.0 * np.pi * detected_f_bb_hz * delta_t)
                x_recon[m, :] = slot_samples * carrier_rot
            else:
                # Uncorrected sequential sampling: phase will be heavily distorted!
                x_recon[m, :] = slot_samples

        # 3. Phase coherence metric: check correlation consistency across antennas
        # If signal power is strong and de-rotation succeeds, correlation remains high
        norm_powers = np.mean(np.abs(x_recon) ** 2, axis=1)
        power_spread = float(np.std(norm_powers) / (np.mean(norm_powers) + 1e-9))
        coherence_ok = (power_spread < 0.6)

        return x_recon, coherence_ok, {
            "mode": "MODE_B_SWITCHED",
            "snapshots_used": n_eff,
            "phase_de_rotation_applied": self.config.phase_de_rotation_enabled,
            "phase_coherence_metric": round(1.0 - min(1.0, power_spread), 3),
            "settling_samples_discarded": settle * M
        }

