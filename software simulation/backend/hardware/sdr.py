"""
RTL-SDR Receiver Hardware and Acquisition Model.
Simulates tuner Local Oscillator (LO), front-end bandwidth filtering, and carrier downconversion.
"""

from typing import Literal, Tuple
import numpy as np
from backend.simulation.configuration import SwitchedSDRConfig

class RTLSDRReceiver:
    """
    RTL2832U + R820T2 Software Defined Radio receiver model.
    Sampling rate: 2.0 MS/s.
    Complex baseband bandwidth: 2.0 MHz (-1.0 MHz to +1.0 MHz).
    """

    def __init__(self, config: SwitchedSDRConfig):
        self.config: SwitchedSDRConfig = config
        self.sample_rate: float = config.baseband_bandwidth_hz  # 2.0 MS/s
        self.bandwidth: float = config.baseband_bandwidth_hz    # 2.0 MHz
        self.lo_freq_hz: float = config.lo_frequency_hz
        self.nominal_if_hz: float = 150.0e3  # 150 kHz intermediate frequency

    def update_lo_for_expected_hop(self, expected_freq_hz: float) -> float:
        """
        In SYNCHRONOUS hopping mode, tunes the SDR LO to track the transmitter hop schedule
        with a nominal 150 kHz IF offset.
        """
        if self.config.lo_tuning_mode == "SYNCHRONOUS":
            self.lo_freq_hz = expected_freq_hz - self.nominal_if_hz
        elif self.config.lo_tuning_mode == "WIDEBAND":
            self.lo_freq_hz = expected_freq_hz - self.nominal_if_hz
        # STATIC_LO retains its configured fixed frequency
        return self.lo_freq_hz

    def evaluate_acquisition(self, incoming_freq_hz: float) -> Tuple[bool, float, float]:
        """
        Checks whether incoming carrier frequency is within the SDR baseband passband.
        
        Returns:
            in_band: True if incoming signal passes the RF front-end filter
            f_baseband: Resulting complex baseband frequency in Hz
            filter_attenuation_linear: Transmission coefficient (1.0 in band, ~1e-3 out of band)
        """
        if self.config.lo_tuning_mode == "WIDEBAND":
            return True, self.nominal_if_hz, 1.0

        f_baseband = incoming_freq_hz - self.lo_freq_hz
        half_bw = 0.5 * self.bandwidth

        if abs(f_baseband) <= half_bw:
            # Signal is cleanly inside the 2 MS/s baseband window
            return True, f_baseband, 1.0
        else:
            # Out-of-band: heavily attenuated by RF front-end SAW/tuner filter
            attenuation = 1.0e-3  # -60 dB rejection
            return False, f_baseband, attenuation

