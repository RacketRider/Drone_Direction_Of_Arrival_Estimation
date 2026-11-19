"""
Comprehensive Verification Test Suite for 3D Building Collision Detection and Obstacle Avoidance.
Tests swept-segment collision math, anti-tunneling, continuous multi-trajectory flight,
obstacle clearance, RF synchronization, and recovery dynamics.
"""

import numpy as np
import pytest

from backend.simulation.configuration import DEFAULT_CONFIG
from backend.simulation.collision import CollisionDetector, BuildingCollisionVolume
from backend.simulation.trajectories import (
    FigureEightTrajectory,
    SCurveTrajectory,
    CircularTrajectory,
    WaypointTrajectory
)
from backend.simulation.obstacle_avoidance import ObstacleAvoidancePlanner
from backend.simulation.uav import UAVState
from backend.simulation.engine import SimulationEngine


def test_analytical_swept_segment_collision_detection():
    """Validates exact 3D slab ray-box intersection against building bounds."""
    bldg = DEFAULT_CONFIG.buildings[0] # Building Alpha [-38, -18], y in [0, 16], [-35, -15]
    vol = BuildingCollisionVolume(bldg, uav_radius_m=0.8, safety_margin_m=2.2)

    # 1. Direct hit piercing through center of building
    p_start = (-60.0, 10.0, -25.0)
    p_end = (0.0, 10.0, -25.0)
    hit, t_entry, t_exit = vol.swept_segment_intersects(p_start, p_end)
    assert hit is True
    assert 0.0 < t_entry < t_exit < 1.0

    # 2. Complete miss well clear of building
    p_miss0 = (0.0, 10.0, 0.0)
    p_miss1 = (10.0, 10.0, 10.0)
    hit_miss, _, _ = vol.swept_segment_intersects(p_miss0, p_miss1)
    assert hit_miss is False

    # 3. Flight above roof beyond safety buffer
    p_above0 = (-28.0, 25.0, -25.0)
    p_above1 = (-28.0, 25.0, -10.0)
    hit_above, _, _ = vol.swept_segment_intersects(p_above0, p_above1)
    assert hit_above is False

    # 4. Flight clipping buffer zone (grazing ray)
    # Building edge is x = -18, buffer extends to x = -15
    p_graze0 = (-16.0, 8.0, -40.0)
    p_graze1 = (-16.0, 8.0, -10.0)
    hit_graze, _, _ = vol.swept_segment_intersects(p_graze0, p_graze1)
    assert hit_graze is True


def test_uav_zero_penetration_all_trajectories():
    """
    Simulates UAV across all 4 trajectories for 600 steps (30 seconds each).
    Verifies that swept segment penetration is zero and minimum clearance >= 3.0m.
    """
    detector = CollisionDetector(DEFAULT_CONFIG.buildings, uav_radius_m=0.8, safety_margin_m=2.2)
    trajectories = [
        FigureEightTrajectory(),
        SCurveTrajectory(),
        CircularTrajectory(),
        WaypointTrajectory()
    ]

    dt = 0.05
    steps = 600

    for traj in trajectories:
        uav = UAVState(trajectory=traj, buildings=DEFAULT_CONFIG.buildings)
        p_prev = uav.position
        min_clearance = 999.0

        for step in range(steps):
            t = step * dt
            uav.update(t, dt=dt)
            p_curr = uav.position

            # Verify no swept segment entered physical building or violated bounds
            hit, bldg_hit, _ = detector.swept_segment_in_collision(p_prev, p_curr, extra_buffer=0.0)
            assert not hit, f"Collision detected in trajectory {traj.name} at t={t:.2f}s with {bldg_hit.name if bldg_hit else ''}"

            clr = detector.min_clearance_to_obstacles(p_curr)
            min_clearance = min(min_clearance, clr)

            # Ensure coordinates are physically finite
            assert not np.isnan(p_curr[0]) and not np.isinf(p_curr[0])
            assert not np.isnan(p_curr[1]) and not np.isinf(p_curr[1])
            assert not np.isnan(p_curr[2]) and not np.isinf(p_curr[2])

            p_prev = p_curr

        # Verify clearance is maintained (>= buffer of 3.0m within numerical tolerance)
        assert min_clearance >= 2.95, f"Clearance violated in {traj.name}: {min_clearance:.2f}m < 3.0m"


def test_high_speed_swept_collision_prevention():
    """
    Verifies anti-tunneling at high speed multipliers (e.g. 4.0x speed).
    """
    detector = CollisionDetector(DEFAULT_CONFIG.buildings, uav_radius_m=0.8, safety_margin_m=2.2)
    traj = FigureEightTrajectory()
    planner = ObstacleAvoidancePlanner(detector, max_speed_mps=15.0, max_accel_mps2=10.0)
    planner.reset(traj.get_position(0.0))

    dt = 0.20  # 4x larger time step simulating fast warp
    p_prev = planner.current_pos

    for step in range(150):
        t = step * dt
        pos, vel, diag = planner.plan_next_step(t, dt, traj)
        hit, _, _ = detector.swept_segment_in_collision(p_prev, pos, extra_buffer=0.0)
        assert not hit, f"High-speed tunneling occurred at t={t:.2f}s! pos={pos}"
        p_prev = pos


def test_rf_synchronization_with_avoided_position():
    """
    Verifies that RF propagation, ground truth azimuth, and telemetry strictly
    use the actual collision-avoided position and not nominal trajectory coordinates.
    """
    engine = SimulationEngine()
    engine.set_trajectory("FIGURE_EIGHT")
    engine.clock.play()

    found_avoiding_frame = False

    for _ in range(300):
        engine.clock.tick()
        telemetry, diag = engine.step()
        uav_state = telemetry["uav"]

        # 1. Authoritative unrounded position ground truth check
        uav_pos = engine.uav.position
        expected_az = float(np.degrees(np.arctan2(uav_pos[2], uav_pos[0])))
        assert abs(engine.uav.true_azimuth_deg - expected_az) < 1e-6

        # 2. Telemetry bearing check (quantized to mm and degrees)
        x = uav_state["x"]
        y = uav_state["y"]
        z = uav_state["z"]
        computed_az = float(np.degrees(np.arctan2(z, x)))
        assert abs(uav_state["true_azimuth_deg"] - round(computed_az, 2)) < 0.6

        # 3. LOS distance must match 3D distance of actual UAV position
        computed_dist = float(np.sqrt(x * x + y * y + z * z))
        assert abs(telemetry["rf"]["los_distance_m"] - round(computed_dist, 2)) < 0.15

        if uav_state["is_avoiding"]:
            found_avoiding_frame = True
            # When avoiding, actual position should diverge safely from nominal position
            nom_x = uav_state["nominal_x"]
            nom_z = uav_state["nominal_z"]
            dist_divergence = np.sqrt((x - nom_x)**2 + (z - nom_z)**2)
            assert dist_divergence > 0.05, "UAV should diverge from nominal path during avoidance"

    assert found_avoiding_frame, "Expected at least one avoidance event in 300 steps of FigureEight"


def test_avoidance_status_and_recovery():
    """
    Verifies state transitions, event counting, and reset dynamics.
    """
    engine = SimulationEngine()
    engine.set_trajectory("S_CURVE")
    engine.clock.play()

    initial_telem, _ = engine.step()
    assert initial_telem["uav"]["avoidance_status"] in ["NOMINAL", "AVOIDING"]

    # Step through simulation and verify avoidance event counter
    max_events = 0
    for _ in range(400):
        engine.clock.tick()
        telem, _ = engine.step()
        ev_count = telem["uav"]["avoidance_event_count"]
        if ev_count > max_events:
            max_events = ev_count

    assert max_events > 0, "Avoidance event counter should have incremented"

    # Test reset behavior
    engine.reset()
    assert engine.clock.sim_time == 0.0
    reset_telem, _ = engine.step()
    assert reset_telem["uav"]["avoidance_status"] in ["NOMINAL", "AVOIDING"]
