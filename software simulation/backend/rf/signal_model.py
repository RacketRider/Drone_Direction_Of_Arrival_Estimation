"""
Complex Baseband Signal Generator.
Synthesizes baseband IQ packet bursts with carrier offsets, modulation envelopes, and phase terms.
"""

from typing import Tuple
import numpy as np

class SignalModel:
    """Generates analytical complex baseband burst signals."""

    @staticmethod
    def generate_burst_waveform(
        carrier_freq_hz: float,
        receiver_lo_hz: float,
        num_samples: int,
        sample_rate: float,
        carrier_phase_rad: float = 0.0,
        ramp_samples: int = 8
    ) -> Tuple[np.ndarray, float]:
        """
        Synthesizes a complex baseband telemetry packet burst.
        
        Args:
            carrier_freq_hz: True active RF hop carrier frequency (e.g. 915.0 MHz)
            receiver_lo_hz: Receiver Local Oscillator tuning frequency (e.g. 914.85 MHz)
            num_samples: Length of burst in snapshots (e.g. 256)
            sample_rate: SDR baseband sample rate in S/s (e.g. 2 MS/s)
            carrier_phase_rad: Initial carrier phase
            ramp_samples: Power amplifier ramp-up/down samples
            
        Returns:
            s_burst: Complex ndarray of shape [1, num_samples]
            f_baseband: Effective baseband frequency offset in Hz
        """
        # True complex downconversion: f_bb = f_RF - f_LO
        f_baseband = carrier_freq_hz - receiver_lo_hz
        
        t = np.arange(num_samples) / sample_rate
        phase = 2.0 * np.pi * f_baseband * t + carrier_phase_rad
        carrier = np.exp(1j * phase)

        # Smooth raised-cosine ramp to prevent artificial spectral leakage at burst edges
        envelope = np.ones(num_samples)
        if ramp_samples > 0 and ramp_samples * 2 < num_samples:
            ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(ramp_samples) / ramp_samples))
            envelope[:ramp_samples] = ramp
            envelope[-ramp_samples:] = ramp[::-1]

        s_burst = (envelope * carrier).reshape(1, -1)
        return s_burst, f_baseband

