"""
Tests for Benchmark Direction-Finding Estimators: UCA-ESPRIT, Power-Vector ML, and Centroid.
"""

import numpy as np
import pytest
from backend.hardware.uca import UniformCircularArray
from backend.simulation.configuration import ArrayGeometryConfig
from backend.dsp.esprit import UCAESPRITEstimator
from backend.dsp.power_vector import (
    PowerVectorMLEstimator,
    est_power_centroid,
    est_strongest_beam
)
from backend.dsp.covariance import CovarianceEstimator
from backend.dsp.music import MUSICEstimator


def test_uca_esprit_single_source():
    """Validates beamspace phase-mode UCA-ESPRIT bearing estimation accuracy."""
    uca = UniformCircularArray(ArrayGeometryConfig())
    esprit = UCAESPRITEstimator(uca)
    carrier_freq = 433.0e6

    for true_az in [-120.0, -45.0, 30.0, 75.0, 150.0]:
        a = uca.steering_vector(carrier_freq, true_az)
        s = np.random.randn(1, 300) + 1j * np.random.randn(1, 300)
        noise = (np.random.randn(4, 300) + 1j * np.random.randn(4, 300)) * 0.05
        x = a @ s + noise

        r_xx, _ = CovarianceEstimator.compute_covariance(x)
        est_az = esprit.estimate(r_xx, carrier_freq)
        error = MUSICEstimator.circular_angular_error(est_az, true_az)
        assert error < 3.5, f"ESPRIT error too high at {true_az} deg: {error} deg"


def test_power_vector_ml_and_centroid():
    """Validates switched-beam power vector ML and centroid estimators."""
    boresights = [0.0, 90.0, 180.0, 270.0]
    pv = PowerVectorMLEstimator(boresights_deg=boresights, beamwidth_deg=90.0)

    # Synthetic signal from 45.0 degrees
    true_az = 45.0
    gains = pv.evaluate_beam_gains(np.array([true_az]))[0]
    powers = gains * 8.0 + 1.0  # High SNR

    # 1. Centroid
    cent = est_power_centroid(powers, np.array(boresights))
    assert abs(cent - true_az) < 1.0

    # 2. Power-Vector ML
    ml_res = pv.estimate(powers)
    assert abs(ml_res["estimated_bearing_deg"] - true_az) < 1.0
    assert ml_res["estimated_snr_db"] > 5.0
