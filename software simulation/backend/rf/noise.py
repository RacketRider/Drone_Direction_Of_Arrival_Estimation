"""
Complex Additive White Gaussian Noise (AWGN) Generator.
Strictly calibrated to SNR (dB) conventions for complex baseband IQ signals.
"""

from typing import Optional, Tuple
import numpy as np

class ComplexAWGNGenerator:
    """Generates complex Gaussian noise with exact SNR power calibration."""

    def __init__(self, seed: Optional[int] = 42):
        self._rng = np.random.default_rng(seed)

    def set_seed(self, seed: int) -> None:
        """Resets RNG seed for deterministic reproducibility."""
        self._rng = np.random.default_rng(seed)

    def generate_noise(
        self,
        shape: Tuple[int, ...],
        snr_db: float,
        signal_power: float = 1.0
    ) -> np.ndarray:
        """
        Generates complex zero-mean AWGN where E[|n|^2] = sigma^2 = P_signal * 10^(-SNR_dB / 10).
        Each real and imaginary component has variance sigma^2 / 2.
        """
        noise_power = signal_power * (10.0 ** (-snr_db / 10.0))
        sigma_per_channel = np.sqrt(noise_power / 2.0)
        
        noise_i = self._rng.normal(0.0, sigma_per_channel, size=shape)
        noise_q = self._rng.normal(0.0, sigma_per_channel, size=shape)
        
        return noise_i + 1j * noise_q

