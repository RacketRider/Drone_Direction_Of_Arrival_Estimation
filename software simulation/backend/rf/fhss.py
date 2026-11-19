"""
Frequency-Hopping Spread Spectrum (FHSS) Transmitter Model.
Simulates ExpressLRS / Sub-GHz telemetry transmitter hopping schedules across ISM bands.
"""

from typing import List, Literal, Optional
import numpy as np

class FHSSTransmitter:
    """Simulates an ExpressLRS sub-GHz FHSS telemetry transmitter."""
    
    def __init__(
        self,
        hop_frequencies_hz: Optional[List[float]] = None,
        mode: Literal["PSEUDORANDOM", "RANDOM", "FIXED"] = "PSEUDORANDOM",
        fixed_freq_hz: Optional[float] = None,
        tx_power_dbm: float = 20.0,
        seed: int = 42
    ):
        self.frequencies: List[float] = (
            hop_frequencies_hz
            if hop_frequencies_hz is not None
            else [433.0e6, 868.0e6, 915.0e6, 920.0e6, 928.0e6]
        )
        self.mode: str = mode
        self.fixed_freq_hz: float = fixed_freq_hz or self.frequencies[min(2, len(self.frequencies) - 1)]
        self.tx_power_dbm: float = tx_power_dbm
        self.seed: int = seed
        self._rng: np.random.Generator = np.random.default_rng(seed)
        
        # State
        self.hop_index: int = 0
        self.active_freq_hz: float = self.frequencies[0]
        self.hop_counter: int = 0
        
        # Precomputed pseudo-random hop table (ELRS 16-hop permutation)
        self._prng_table = [2, 0, 3, 1, 4, 2, 4, 1, 0, 3, 2, 1, 4, 0, 3, 2]

    def set_mode(self, mode: Literal["PSEUDORANDOM", "RANDOM", "FIXED"], fixed_freq_hz: Optional[float] = None) -> None:
        """Configures hopping mode."""
        self.mode = mode
        if fixed_freq_hz is not None:
            self.fixed_freq_hz = fixed_freq_hz

    def hop(self) -> float:
        """Selects the next RF carrier frequency according to hopping mode."""
        if self.mode == "FIXED":
            self.active_freq_hz = self.fixed_freq_hz
        elif self.mode == "PSEUDORANDOM":
            table_idx = self.hop_counter % len(self._prng_table)
            pool_idx = self._prng_table[table_idx] % len(self.frequencies)
            self.active_freq_hz = self.frequencies[pool_idx]
        elif self.mode == "RANDOM":
            self.active_freq_hz = float(self._rng.choice(self.frequencies))
        
        self.hop_counter += 1
        return self.active_freq_hz

    @property
    def current_frequency(self) -> float:
        """Returns the active transmission carrier frequency in Hz."""
        return self.active_freq_hz

    @property
    def current_wavelength(self) -> float:
        """Returns active carrier wavelength in meters."""
        from backend.simulation.configuration import SPEED_OF_LIGHT
        return SPEED_OF_LIGHT / self.active_freq_hz
