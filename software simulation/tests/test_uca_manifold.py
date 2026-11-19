"""
Unit Tests for 4-Element Uniform Circular Array (UCA) Geometry and Manifold.
"""

import pytest
import numpy as np
from backend.simulation.configuration import SPEED_OF_LIGHT, ArrayGeometryConfig
from backend.hardware.uca import UniformCircularArray

def test_antenna_positions():
    """Verifies that the 4 antenna elements are placed at r=0.072m with 90-degree spacing."""
    uca = UniformCircularArray()
    assert uca.M == 4
    assert pytest.approx(uca.radius, rel=1e-5) == 0.072
    
    pos = uca.nominal_positions
    # Ant 0 (0 deg): (r, 0)
    assert pytest.approx(pos[0, 0], abs=1e-6) == 0.072
    assert pytest.approx(pos[0, 1], abs=1e-6) == 0.0
    
    # Ant 1 (90 deg): (0, r)
    assert pytest.approx(pos[1, 0], abs=1e-6) == 0.0
    assert pytest.approx(pos[1, 1], abs=1e-6) == 0.072
    
    # Ant 2 (180 deg): (-r, 0)
    assert pytest.approx(pos[2, 0], abs=1e-6) == -0.072
    assert pytest.approx(pos[2, 1], abs=1e-6) == 0.0
    
    # Ant 3 (270 deg): (0, -r)
    assert pytest.approx(pos[3, 0], abs=1e-6) == 0.0
    assert pytest.approx(pos[3, 1], abs=1e-6) == -0.072

def test_wavelength_and_spatial_aliasing():
    """Verifies that at the highest hop frequency (928 MHz), 2*r < 0.5 * lambda."""
    uca = UniformCircularArray()
    res = uca.check_spatial_aliasing(928.0e6)
    
    expected_lambda = SPEED_OF_LIGHT / 928.0e6
    assert pytest.approx(res["min_wavelength_m"], rel=1e-3) == expected_lambda
    assert res["is_aliasing_free"] is True
    assert res["diameter_over_lambda"] < 0.5

def test_steering_vector_magnitude_and_phase():
    """Verifies that steering vector elements have unit magnitude and correct phase shifts."""
    uca = UniformCircularArray()
    f_test = 915.0e6
    theta_test = 45.0  # 45 degrees
    
    a = uca.steering_vector(f_test, theta_test)
    assert a.shape == (4, 1)
    
    # Magnitudes must all be exactly 1.0 (pure phase shifts)
    mags = np.abs(a)
    np.testing.assert_allclose(mags, 1.0, atol=1e-7)
    
    # Phase calculation check: phi_m = 2*pi*f*r/c * cos(theta - phi_m)
    k = 2.0 * np.pi * f_test * uca.radius / SPEED_OF_LIGHT
    expected_phases = k * np.cos(np.radians(theta_test) - uca.element_angles_rad)
    actual_phases = np.angle(a.flatten())
    
    # Wrap difference to [-pi, pi]
    diff = np.angle(np.exp(1j * (actual_phases - expected_phases)))
    np.testing.assert_allclose(diff, 0.0, atol=1e-6)

