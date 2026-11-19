"""
Unit Tests for the Digital Signal Processing (DSP) Pipeline.
Verifies FFT, Covariance, EVD, Gate, and MUSIC Direction of Arrival estimation.
"""

import pytest
import numpy as np

from backend.simulation.configuration import SPEED_OF_LIGHT
from backend.hardware.uca import UniformCircularArray
from backend.dsp.burst_detection import BurstDetector
from backend.dsp.frequency_estimation import FrequencyEstimator
from backend.dsp.steering import SteeringVectorProvider
from backend.dsp.covariance import CovarianceEstimator
from backend.dsp.eigendecomposition import SubspaceDecomposition
from backend.dsp.eigenvalue_gate import EigenvalueGate
from backend.dsp.music import MUSICEstimator

def test_circular_angular_error():
    """Verifies circular distance calculation modulo 360 degrees."""
    # Simple small differences
    assert pytest.approx(MUSICEstimator.circular_angular_error(35.0, 30.0), abs=1e-5) == 5.0
    assert pytest.approx(MUSICEstimator.circular_angular_error(30.0, 35.0), abs=1e-5) == -5.0
    
    # Boundary crossing between +179 and -179 degrees
    # True is -179, est is +179 -> shortest path is -2 degrees
    err = MUSICEstimator.circular_angular_error(179.0, -179.0)
    assert pytest.approx(err, abs=1e-5) == -2.0
    
    # Opposite direction: True is +179, est is -179 -> shortest path is +2 degrees
    err2 = MUSICEstimator.circular_angular_error(-179.0, 179.0)
    assert pytest.approx(err2, abs=1e-5) == 2.0

def test_fft_frequency_estimation():
    """Verifies FFT peak identification of baseband offset and RF carrier reconstruction."""
    fs = 2.0e6
    n_burst = 256
    t = np.arange(n_burst) / fs
    f_offset = 125.0e3  # 125 kHz tone
    lo_freq = 915.0e6
    
    # Clean baseband tone
    sig = np.exp(1j * 2.0 * np.pi * f_offset * t).reshape(1, -1)
    
    estimator = FrequencyEstimator(sample_rate=fs, fft_size=n_burst)
    det_rf, det_bb, wavelength, freqs, mag_db = estimator.estimate_frequency(sig, lo_freq)
    
    # Bin resolution is 2.0e6 / 256 = 7812.5 Hz. Detected frequency must be within 1 bin!
    assert abs(det_bb - f_offset) <= estimator.bin_resolution_hz
    assert abs(det_rf - (lo_freq + f_offset)) <= estimator.bin_resolution_hz
    assert pytest.approx(wavelength, rel=1e-3) == (SPEED_OF_LIGHT / det_rf)

def test_covariance_hermitian_and_positive_semidefinite():
    """Verifies that R_xx is Hermitian and all eigenvalues are non-negative."""
    uca = UniformCircularArray()
    n_samples = 256
    
    # Generate random complex snapshots
    x = np.random.randn(4, n_samples) + 1j * np.random.randn(4, n_samples)
    r_xx, meta = CovarianceEstimator.compute_covariance(x)
    
    assert meta["is_hermitian"] is True
    np.testing.assert_allclose(r_xx, r_xx.conj().T, atol=1e-12)
    
    eigvals, _, _, _ = SubspaceDecomposition.decompose(r_xx)
    # Sorted descending
    assert eigvals[0] >= eigvals[1] >= eigvals[2] >= eigvals[3]
    # All non-negative
    assert np.all(eigvals >= -1e-10)

def test_multipath_reliability_gate():
    """Verifies that clean single-source gives high gamma, while two strong sources trigger rejection."""
    gate = EigenvalueGate(threshold=8.0)
    
    # Clean single-source case: lambda_1 dominant, lambda_2..4 at noise floor
    clean_eigvals = np.array([12.5, 0.4, 0.38, 0.35])
    accepted, ratio, diag = gate.evaluate(clean_eigvals)
    assert accepted is True
    assert ratio > 8.0
    assert diag["status"] == "ACCEPTED"
    
    # Multipath / two-source case: lambda_1 and lambda_2 both large
    multipath_eigvals = np.array([8.0, 5.5, 0.5, 0.4])
    accepted_mp, ratio_mp, diag_mp = gate.evaluate(multipath_eigvals)
    assert accepted_mp is False
    assert ratio_mp < 8.0
    assert diag_mp["status"] == "REJECTED"

def test_clean_music_direction_finding_accuracy():
    """
    Rigorously verifies that Frequency-Compensated MUSIC recovers the true DoA
    within 1.0 degree tolerance across multiple ground-truth bearings.
    """
    uca = UniformCircularArray()
    provider = SteeringVectorProvider(uca, reference_frequency_hz=433.0e6, grid_resolution_deg=0.5)
    angle_grid = provider.get_angle_grid()
    
    test_frequencies = [433.0e6, 868.0e6, 915.0e6]
    test_bearings = [35.0, -45.0, 70.0, -120.0]
    n_samples = 256
    fs = 2.0e6
    t = np.arange(n_samples) / fs
    
    for f_rf in test_frequencies:
        a_mat = provider.get_compensated_steering_matrix(f_rf)
        
        for true_theta in test_bearings:
            # Generate clean signal without noise
            s = np.exp(1j * 2.0 * np.pi * 150e3 * t).reshape(1, -1)
            a_true = uca.steering_vector(f_rf, true_theta)
            x_clean = a_true @ s
            
            # Add minor AWGN (30 dB SNR)
            noise = 0.02 * (np.random.randn(4, n_samples) + 1j * np.random.randn(4, n_samples))
            x_recv = x_clean + noise
            
            r_xx, _ = CovarianceEstimator.compute_covariance(x_recv)
            _, _, _, p_noise = SubspaceDecomposition.decompose(r_xx)
            
            _, p_db = MUSICEstimator.evaluate_pseudospectrum(a_mat, p_noise)
            est_angle = MUSICEstimator.extract_peak_bearing(p_db, angle_grid)
            
            err = abs(MUSICEstimator.circular_angular_error(est_angle, true_theta))
            assert err <= 1.0, f"Failed at f={f_rf/1e6} MHz, true={true_theta} deg: est={est_angle} deg (err={err} deg)"

def test_static_slide_model_bias():
    """
    Verifies that the midsem slide mismatch model (Slide 8) exhibits substantial angular bias
    when the hop frequency moves to 915 MHz away from 433 MHz reference.
    """
    uca = UniformCircularArray()
    provider = SteeringVectorProvider(
        uca,
        reference_frequency_hz=433.0e6,
        grid_resolution_deg=0.5,
        static_baseline_model="SLIDE_MISMATCH"
    )
    angle_grid = provider.get_angle_grid()
    
    f_rf = 915.0e6
    true_theta = 35.0
    n_samples = 256
    fs = 2.0e6
    t = np.arange(n_samples) / fs
    
    s = np.exp(1j * 2.0 * np.pi * 150e3 * t).reshape(1, -1)
    a_true = uca.steering_vector(f_rf, true_theta)
    x = a_true @ s + 0.05 * (np.random.randn(4, n_samples) + 1j * np.random.randn(4, n_samples))
    
    r_xx, _ = CovarianceEstimator.compute_covariance(x)
    _, _, _, p_noise = SubspaceDecomposition.decompose(r_xx)
    
    # 1. Proposed Compensated Manifold
    a_comp = provider.get_compensated_steering_matrix(f_rf)
    _, p_comp_db = MUSICEstimator.evaluate_pseudospectrum(a_comp, p_noise)
    est_comp = MUSICEstimator.extract_peak_bearing(p_comp_db, angle_grid)
    err_comp = abs(MUSICEstimator.circular_angular_error(est_comp, true_theta))
    
    # 2. Slide 8 Baseline Model
    a_static = provider.get_static_steering_matrix(active_freq_hz=f_rf)
    _, p_static_db = MUSICEstimator.evaluate_pseudospectrum(a_static, p_noise)
    est_static = MUSICEstimator.extract_peak_bearing(p_static_db, angle_grid)
    err_static = abs(MUSICEstimator.circular_angular_error(est_static, true_theta))
    
    assert err_comp <= 1.0, f"Compensated error too high: {err_comp} deg"
    assert err_static > 10.0, f"Slide model should exhibit noticeable bias (>10 deg), got {err_static} deg"

def test_physical_static_peak_broadening():
    """
    Verifies that the exact physical static circular manifold at 433 MHz suffers
    severe peak flattening (much lower linear peak magnitude) compared to compensated MUSIC.
    """
    uca = UniformCircularArray()
    provider = SteeringVectorProvider(
        uca,
        reference_frequency_hz=433.0e6,
        grid_resolution_deg=0.5,
        static_baseline_model="CIRCULAR_FREF"
    )
    
    f_rf = 915.0e6
    true_theta = 35.0
    n_samples = 256
    fs = 2.0e6
    t = np.arange(n_samples) / fs
    
    s = np.exp(1j * 2.0 * np.pi * 150e3 * t).reshape(1, -1)
    a_true = uca.steering_vector(f_rf, true_theta)
    x = a_true @ s + 0.01 * (np.random.randn(4, n_samples) + 1j * np.random.randn(4, n_samples))
    
    r_xx, _ = CovarianceEstimator.compute_covariance(x)
    _, _, _, p_noise = SubspaceDecomposition.decompose(r_xx)
    
    a_comp = provider.get_compensated_steering_matrix(f_rf)
    p_comp_lin, _ = MUSICEstimator.evaluate_pseudospectrum(a_comp, p_noise)
    
    a_static = provider.get_static_steering_matrix(active_freq_hz=f_rf)
    p_static_lin, _ = MUSICEstimator.evaluate_pseudospectrum(a_static, p_noise)
    
    peak_comp = np.max(p_comp_lin)
    peak_static = np.max(p_static_lin)
    
    # Compensated peak should be at least 10x (10 dB) sharper/higher than uncompensated
    assert peak_comp > 10.0 * peak_static, f"Compensated peak ({peak_comp}) should dominate static ({peak_static})"
