"""
Tests for Electromagnetic Wave Solvers and Ray-Tracing Modules.
Validates 2D TMz FDTD, 3D Vector Maxwell FDTD, Fresnel reflection, and Möller-Trumbore ray tracing.
"""

import numpy as np
import pytest
from backend.rf.em_solver import (
    compute_complex_impedance_and_fresnel,
    segment_triangle_intersection,
    trace_geometry,
    trace_reflected_scattered_paths,
    fdtd_tmz
)
from backend.rf.em_solver_3d import fdtd_3d


def test_fresnel_complex_impedance():
    """Validates complex dielectric permittivity, intrinsic impedance, and reflection magnitude."""
    eps_c, mu_c, eta, gamma_mag = compute_complex_impedance_and_fresnel(
        epsilon_r=5.5,
        conductivity_s_m=0.02,
        frequency_hz=433.0e6
    )
    # Real part of permittivity should be ~5.5 * eps0
    assert eps_c.real > 0.0
    assert eps_c.imag < 0.0  # Lossy conduction
    assert 0.0 < gamma_mag < 1.0


def test_segment_triangle_intersection():
    """Validates 3D Möller-Trumbore ray-triangle intersection."""
    triangle = [
        [-5.0, 0.0, -5.0],
        [5.0, 0.0, -5.0],
        [0.0, 10.0, -5.0]
    ]
    # Piercing ray
    p0 = [0.0, 2.0, 5.0]
    p1 = [0.0, 2.0, -10.0]
    t = segment_triangle_intersection(p0, p1, triangle)
    assert t is not None
    assert 0.0 < t < 1.0

    # Missing ray
    p_miss0 = [20.0, 20.0, 5.0]
    p_miss1 = [20.0, 20.0, -10.0]
    t_miss = segment_triangle_intersection(p_miss0, p_miss1, triangle)
    assert t_miss is None


def test_fdtd_2d_wave_propagation():
    """Validates 2D TMz FDTD time-domain field update and stability."""
    res = fdtd_tmz(frequency_hz=433.0e6, size_m=1.8, steps=70)
    assert res["finite_field"] is True
    assert len(res["field_normalized"]) > 10
    assert res["peak_field_amplitude"] > 0.0


def test_fdtd_3d_vector_maxwell():
    """Validates 3D Cartesian vector Maxwell FDTD update, Courant limit, and slice normalization."""
    res = fdtd_3d(frequency_hz=433.0e6, size_m=0.35, steps=35)
    assert res["finite_field"] is True
    assert res["courant_limit_pass"] is True
    assert res["courant_number"] <= 1.0
    assert len(res["field_normalized"]) > 5
