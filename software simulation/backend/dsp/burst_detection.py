"""
Sliding-Window Power Envelope Burst Detector.
Detects FHSS packet arrival, estimates noise floor, and slices active burst window.
"""

from typing import Tuple
import numpy as np

class BurstDetector:
    """Sliding-window energy detector with adaptive noise-floor thresholding."""

    def __init__(self, window_size: int = 16, threshold_factor: float = 2.5):
        self.window_size: int = window_size
        self.threshold_factor: float = threshold_factor
        self.kernel: np.ndarray = np.ones(window_size) / window_size

    def detect(
        self,
        iq_stream: np.ndarray,
        guard_samples: int = 100
    ) -> Tuple[bool, int, int, np.ndarray, float]:
        """
        Calculates instantaneous power P[n] = I^2[n] + Q^2[n], smooths across window,
        and identifies active burst boundaries.
        
        Args:
            iq_stream: Complex array of shape [M, N_total] or [N_total]
            guard_samples: Initial baseline samples used for noise floor estimation
            
        Returns:
            detected: True if burst detected above threshold
            start_idx: Beginning sample index of burst
            end_idx: Ending sample index of burst
            power_envelope: 1D array of smoothed power envelope
            threshold: Applied linear power threshold
        """
        # Multi-antenna average power or single channel
        if iq_stream.ndim == 2:
            inst_power = np.mean(np.abs(iq_stream) ** 2, axis=0)
        else:
            inst_power = np.abs(iq_stream) ** 2

        # Moving-average smoothing filter
        smooth_power = np.convolve(inst_power, self.kernel, mode="same")

        # Noise floor estimated from the pre-burst guard window
        guard_window = smooth_power[:max(20, min(guard_samples, len(smooth_power) // 4))]
        noise_floor = float(np.median(guard_window))
        threshold = float(self.threshold_factor * max(1e-9, noise_floor))

        # Detect active burst samples
        active_indices = np.where(smooth_power > threshold)[0]

        if len(active_indices) < self.window_size:
            # No valid burst detected above threshold
            return False, 0, 0, smooth_power, threshold

        start_idx = int(active_indices[0])
        end_idx = int(active_indices[-1])
        return True, start_idx, end_idx, smooth_power, threshold

