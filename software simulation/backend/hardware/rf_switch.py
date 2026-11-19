"""
HMC241 SP4T RF Switch Model.
Simulates GaAs solid-state switch controlled by ESP32 GPIO pins, switching transients, and dwell scheduling.
"""

from typing import List, Tuple
import numpy as np

class HMC241RFSwitch:
    """
    Simulates the Analog Devices / Hittite HMC241 SP4T non-reflective RF switch.
    Features 4 RF input ports (Ant 0..3) routed to 1 common output port.
    Controlled via 2-bit digital logic (ESP32 GPIO pins A, B).
    """

    def __init__(self, settling_samples: int = 4, dwell_samples: int = 64):
        self.settling_samples: int = settling_samples
        self.dwell_samples: int = dwell_samples
        self.num_ports: int = 4
        self.current_port: int = 0
        self.switching_log: List[dict] = []

    def get_port_for_sample(self, sample_idx: int) -> Tuple[int, bool]:
        """
        Determines active switch input port (0..3) and whether sample is in settling transient.
        Returns: (port_index: int, is_settling: bool)
        """
        slot = (sample_idx // self.dwell_samples) % self.num_ports
        sample_in_slot = sample_idx % self.dwell_samples
        is_settling = (sample_in_slot < self.settling_samples)
        return slot, is_settling

    def route_sequential_burst(self, multichannel_iq: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Routes the 4-channel multi-antenna burst stream into a single sequential SDR input stream.
        
        Args:
            multichannel_iq: Complex ndarray of shape [M, N_samples]
            
        Returns:
            sdr_stream: 1D complex ndarray of length N_samples
            valid_mask: Boolean 1D array indicating valid non-transient samples
        """
        M, N = multichannel_iq.shape
        sdr_stream = np.zeros(N, dtype=np.complex128)
        valid_mask = np.ones(N, dtype=bool)

        for n in range(N):
            port, is_settling = self.get_port_for_sample(n)
            if is_settling:
                # RF transient: attenuated / corrupted sample during switch actuation
                sdr_stream[n] = 0.1 * multichannel_iq[port, n]
                valid_mask[n] = False
            else:
                sdr_stream[n] = multichannel_iq[port, n]

        return sdr_stream, valid_mask

