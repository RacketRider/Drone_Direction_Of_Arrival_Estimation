"""
Unit Tests for Switched-Interferometric SDR Array (HMC241 SP4T + RTL-SDR).
Verifies sequential switching, settling transients, temporal de-rotation, and LO acquisition.
"""

import pytest
import numpy as np

from backend.simulation.configuration import SwitchedSDRConfig
from backend.hardware.rf_switch import HMC241RFSwitch
from backend.hardware.sdr import RTLSDRReceiver
from backend.hardware.sampling import SamplingSubsystem
from backend.hardware.uca import UniformCircularArray
from backend.dsp.covariance import CovarianceEstimator
from backend.dsp.eigendecomposition import SubspaceDecomposition
from backend.dsp.steering import SteeringVectorProvider
from backend.dsp.music import MUSICEstimator

def test_hmc241_port_schedule_and_settling():
    """Verifies that HMC241 sequences through ports 0, 1, 2, 3 with initial settling samples flagged."""
    switch = HMC241RFSwitch(settling_samples=4, dwell_samples=64)
    
    # First slot: samples 0..63 are port 0
    port, is_settle = switch.get_port_for_sample(0)
    assert port == 0 and is_settle is True
    
    port, is_settle = switch.get_port_for_sample(3)
    assert port == 0 and is_settle is True
    
    port, is_settle = switch.get_port_for_sample(4)
    assert port == 0 and is_settle is False
    
    # Second slot: samples 64..127 are port 1
    port, is_settle = switch.get_port_for_sample(64)
    assert port == 1 and is_settle is True
    
    port, is_settle = switch.get_port_for_sample(68)
    assert port == 1 and is_settle is False

def test_sdr_tuning_and_out_of_band_rejection():
    """Verifies that signals outside the 2 MS/s baseband filter are rejected."""
    cfg = SwitchedSDRConfig(lo_tuning_mode="STATIC_LO", lo_frequency_hz=915.0e6, baseband_bandwidth_hz=2.0e6)
    sdr = RTLSDRReceiver(cfg)
    
    # 915.2 MHz is in-band (offset = +200 kHz <= 1.0 MHz)
    in_band, f_bb, att = sdr.evaluate_acquisition(915.2e6)
    assert in_band is True
    assert pytest.approx(f_bb, abs=1e-3) == 200.0e3
    assert att == 1.0
    
    # 433.0 MHz is out-of-band (> 400 MHz away!)
    in_band_oob, f_bb_oob, att_oob = sdr.evaluate_acquisition(433.0e6)
    assert in_band_oob is False
    assert att_oob <= 1e-3

def test_mode_b_temporal_phase_derotation_reconstructs_doa():
    """
    Rigorously verifies that in Mode B (single-SDR switched),
    temporal phase de-rotation successfully reconstructs the spatial snapshot and DoA peak!
    """
    uca = UniformCircularArray()
    provider = SteeringVectorProvider(uca, reference_frequency_hz=433.0e6, grid_resolution_deg=0.5)
    angle_grid = provider.get_angle_grid()
    
    f_rf = 915.0e6
    true_theta = 40.0
    n_burst = 256
    fs = 2.0e6
    f_bb = 150.0e3
    
    t = np.arange(n_burst) / fs
    s_burst = np.exp(1j * 2.0 * np.pi * f_bb * t).reshape(1, -1)
    a_true = uca.steering_vector(f_rf, true_theta)
    x_multichannel = a_true @ s_burst  # Clean multi-channel field [4, 256]
    
    # 1. Mode B WITH de-rotation enabled
    cfg_with_derot = SwitchedSDRConfig(
        receiver_mode="MODE_B_SWITCHED",
        phase_de_rotation_enabled=True,
        dwell_samples_per_antenna=64,
        switch_settling_samples=4
    )
    sdr = RTLSDRReceiver(cfg_with_derot)
    sampler_derot = SamplingSubsystem(cfg_with_derot, sdr)
    x_recon, coh_ok, _ = sampler_derot.capture_burst(x_multichannel, detected_f_bb_hz=f_bb)
    
    r_xx, _ = CovarianceEstimator.compute_covariance(x_recon)
    _, _, _, p_noise = SubspaceDecomposition.decompose(r_xx)
    a_comp = provider.get_compensated_steering_matrix(f_rf)
    _, p_db = MUSICEstimator.evaluate_pseudospectrum(a_comp, p_noise)
    est_derot = MUSICEstimator.extract_peak_bearing(p_db, angle_grid)
    
    err_derot = abs(MUSICEstimator.circular_angular_error(est_derot, true_theta))
    assert err_derot <= 1.0, f"Mode B with de-rotation must be accurate: got {est_derot} deg, err={err_derot} deg"
    
    # 2. Mode B WITHOUT de-rotation (simulates naive sequential sampling failure)
    cfg_no_derot = SwitchedSDRConfig(
        receiver_mode="MODE_B_SWITCHED",
        phase_de_rotation_enabled=False,
        dwell_samples_per_antenna=64,
        switch_settling_samples=4
    )
    sampler_noderot = SamplingSubsystem(cfg_no_derot, sdr)
    x_recon_bad, _, _ = sampler_noderot.capture_burst(x_multichannel, detected_f_bb_hz=f_bb)
    
    r_xx_bad, _ = CovarianceEstimator.compute_covariance(x_recon_bad)
    _, _, _, p_noise_bad = SubspaceDecomposition.decompose(r_xx_bad)
    _, p_db_bad = MUSICEstimator.evaluate_pseudospectrum(a_comp, p_noise_bad)
    est_noderot = MUSICEstimator.extract_peak_bearing(p_db_bad, angle_grid)
    
    err_noderot = abs(MUSICEstimator.circular_angular_error(est_noderot, true_theta))
    assert err_noderot > 5.0, f"Without de-rotation, sequential sampling must exhibit high error, got {err_noderot} deg"

