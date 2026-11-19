"""
FFT Hop Frequency Identifier and Wavelength Calculation.
Estimates baseband offset frequency via FFT and recovers the active RF carrier frequency.
"""

from typing import Tuple
import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT

class FrequencyEstimator:
    """Radix-2 FFT spectral peak estimator for FHSS carrier identification."""

    def __init__(self, sample_rate: float = 2.0e6, fft_size: int = 256):
        self.sample_rate: float = sample_rate
        self.fft_size: int = fft_size
        self.bin_resolution_hz: float = sample_rate / fft_size  # 2.0 MHz / 256 = 7812.5 Hz

    def estimate_frequency(
        self,
        burst_samples: np.ndarray,
        receiver_lo_hz: float
    ) -> Tuple[float, float, float, np.ndarray, np.ndarray]:
        """
        Computes FFT of antenna 0 samples, identifies peak baseband bin, and recovers RF carrier.
        
        Args:
            burst_samples: Complex array [M, N] or [N]
            receiver_lo_hz: Known SDR tuner LO frequency in Hz
f
        Returns:
            detected_rf_freq_hz: Recovered RF carrier frequency in Hz
            detected_baseband_hz: Baseband frequency offset in Hz
            wavelength_m: Estimated RF wavelength c / f_RF in meters
            fft_freqs_khz: Frequency bin axis in kHz
            fft_mag_db: Normalized FFT magnitude spectrum in dB
        """
        # Use first antenna channel for frequency identification
        sig = burst_samples[0, :] if burst_samples.ndim == 2 else burst_samples
        n = min(len(sig), self.fft_size)
        sig_windowed = sig[:n] * np.hanning(n)
        # Compute FFT and shift zero-frequency to center
        fft_vals = np.fft.fftshift(np.fft.fft(sig_windowed, n=self.fft_size))
        fft_freqs = np.fft.fftshift(np.fft.fftfreq(self.fft_size, d=1.0 / self.sample_rate))
        mag = np.abs(fft_vals)
        peak_idx = int(np.argmax(mag))
        coarse_baseband_hz = float(fft_freqs[peak_idx])
        # Fine frequency refinement via differential phase (Kay / Fitz estimator)
        # Prevents temporal de-rotation phase drift across sequential dwell slots in switched Mode B
        diff_prod = np.mean(sig[1:n] * sig[:n-1].conj())
        if abs(diff_prod) > 1e-9:
            fine_baseband_hz = float(np.angle(diff_prod) * self.sample_rate / (2.0 * np.pi))
            if abs(fine_baseband_hz - coarse_baseband_hz) < self.bin_resolution_hz * 1.5:
                detected_baseband_hz = fine_baseband_hz
            else:
                detected_baseband_hz = coarse_baseband_hz
        else:
            detected_baseband_hz = coarse_baseband_hz
        # True RF carrier reconstruction: f_RF = f_LO + f_BB
        detected_rf_freq_hz = receiver_lo_hz + detected_baseband_hz
        wavelength_m = SPEED_OF_LIGHT / max(1e6, detected_rf_freq_hz)
        # Normalized dB spectrum for frontend visualization
        fft_mag_db = 20.0 * np.log10(mag / max(1e-9, np.max(mag)))
        fft_freqs_khz = fft_freqs / 1.0e3
        return (
            detected_rf_freq_hz,
            detected_baseband_hz,
            wavelength_m,
            fft_freqs_khz,
            fft_mag_db
        )