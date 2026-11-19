"""
Unit Tests for RF Propagation, Building Occlusion, and Specular Multipath.
"""

import pytest
import numpy as np

from backend.simulation.configuration import RFPropagationConfig, BuildingConfig
from backend.simulation.environment import PhysicalEnvironment
from backend.hardware.uca import UniformCircularArray
from backend.rf.propagation import RFPropagationEngine
from backend.rf.path_loss import PathLossModel

def test_los_occlusion_behind_building():
    """Verifies that line-of-sight is detected as occluded when UAV flies behind Building Alpha."""
    env = PhysicalEnvironment()
    
    # Building Alpha: x in [-38, -18], z in [-35, -15], height = 16m
    # Point directly behind Building Alpha along ray from origin (0, 0, 0):
    # E.g. x = -50, z = -50, altitude = 12m (below 16m)
    uav_occluded = (-50.0, 12.0, -50.0)
    is_occ, b_id = env.check_los_occlusion(uav_occluded)
    assert is_occ is True
    assert b_id == 0  # Building Alpha
    
    # Point high above building (altitude = 35m) -> unoccluded
    uav_high = (-50.0, 35.0, -50.0)
    is_occ_high, _ = env.check_los_occlusion(uav_high)
    assert is_occ_high is False
    
    # Point in clear open quadrant -> unoccluded
    uav_clear = (0.0, 15.0, 40.0)
    is_occ_clear, _ = env.check_los_occlusion(uav_clear)
    assert is_occ_clear is False

def test_specular_reflection_point_calculation():
    """Verifies Image Source Method specular reflection calculation off building wall."""
    env = PhysicalEnvironment()
    # UAV placed where specular reflection off South face of Building Alpha or Beta occurs
    uav_pos = (15.0, 10.0, -5.0)
    reflections = env.compute_specular_reflections(uav_pos)
    
    # Must compute valid specular rays
    assert isinstance(reflections, list)
    for ray in reflections:
        assert ray.total_path_m > 0
        assert 0.0 <= ray.refl_point[1] <= 20.0  # Wall height bound
        assert -180.0 <= ray.azimuth_deg <= 180.0

def test_free_space_path_loss_monotonically_increases_with_distance():
    """Verifies that FSPL increases with distance and frequency."""
    f = 915.0e6
    fspl_10m = PathLossModel.free_space_path_loss_db(10.0, f)
    fspl_50m = PathLossModel.free_space_path_loss_db(50.0, f)
    fspl_100m = PathLossModel.free_space_path_loss_db(100.0, f)
    
    assert fspl_50m > fspl_10m
    assert fspl_100m > fspl_50m
    # 20 dB per decade of distance
    assert pytest.approx(fspl_100m - fspl_10m, abs=0.5) == 20.0

def test_dynamic_specular_point_and_forest_disable():
    """Verifies that specular reflection point moves dynamically with UAV and disables in forest mode."""
    env = PhysicalEnvironment()
    
    # 1. As UAV moves along South face of Building Alpha, reflection point moves dynamically
    pos1 = (-60.0, 15.0, 10.0)
    pos2 = (-70.0, 15.0, 10.0)
    refl1 = env.compute_specular_reflections(pos1)
    refl2 = env.compute_specular_reflections(pos2)
    assert len(refl1) > 0
    assert len(refl2) > 0
    # Reflection point must move dynamically along X axis (NOT a single fixed line!)
    assert refl1[0].refl_point[0] != refl2[0].refl_point[0]
    
    # 2. When buildings are disabled (e.g. Forest environment preset)
    env.set_buildings_enabled(False)
    assert env.compute_specular_reflections(pos1) == []
    assert env.compute_specular_reflections(pos2) == []
    is_occ, _ = env.check_los_occlusion((-28.0, 5.0, -25.0))
    assert is_occ is False
    
    # 3. Re-enabling restores buildings
    env.set_buildings_enabled(True)
    assert len(env.compute_specular_reflections(pos1)) > 0

