"""
Unit Tests for Bearing Tracker and Gated Hold State Machine.
"""

import pytest
import numpy as np
from backend.dsp.tracker import BearingTracker

def test_tracker_gated_hold_behavior():
    """Verifies that the tracker holds the last verified bearing when gate rejects a burst."""
    tracker = BearingTracker(tracker_type="GATED_HOLD")
    
    # Burst 1: Clean LoS at 35.0 deg -> Accepted
    trk1, state1, _ = tracker.update(est_compensated_deg=35.0, est_static_deg=15.0, gate_accepted=True)
    assert trk1 == 35.0
    assert state1 == "ACQUIRED"
    
    # Burst 2: Clean LoS at 36.5 deg -> Accepted
    trk2, state2, _ = tracker.update(est_compensated_deg=36.5, est_static_deg=16.0, gate_accepted=True)
    assert trk2 == 36.5
    assert state2 == "ACQUIRED"
    
    # Burst 3: Multipath reflection / outlier at -45.0 deg -> REJECTED
    trk3, state3, diag3 = tracker.update(est_compensated_deg=-45.0, est_static_deg=-40.0, gate_accepted=False)
    # MUST HOLD 36.5 deg!
    assert trk3 == 36.5, f"Expected held track of 36.5 deg, got {trk3}"
    assert state3 == "HOLDING"
    assert diag3["consecutive_rejections"] == 1
    assert diag3["total_rejections"] == 1
    
    # Burst 4: Second consecutive rejection at -42.0 deg -> STILL HOLDING 36.5 deg
    trk4, state4, diag4 = tracker.update(est_compensated_deg=-42.0, est_static_deg=-38.0, gate_accepted=False)
    assert trk4 == 36.5
    assert state4 == "HOLDING"
    assert diag4["consecutive_rejections"] == 2

    # Burst 5: Clear signal resumes at 38.0 deg -> ACQUIRED
    trk5, state5, diag5 = tracker.update(est_compensated_deg=38.0, est_static_deg=18.0, gate_accepted=True)
    assert trk5 == 38.0
    assert state5 == "ACQUIRED"
    assert diag5["consecutive_rejections"] == 0

def test_kalman_filter_tracking_mode():
    """Verifies that Kalman filter predicts and updates smoothly across steps."""
    tracker = BearingTracker(tracker_type="KALMAN_FILTER")
    
    # Sequence of smooth updates moving at 10 deg/s
    dt = 0.1
    true_bearings = [10.0, 11.0, 12.0, 13.0, 14.0]
    for theta in true_bearings:
        trk, state, _ = tracker.update(est_compensated_deg=theta, est_static_deg=theta, gate_accepted=True, dt=dt)
        assert state == "ACQUIRED"
    
    # Next step is rejected: KF predicts forward without measurement update
    trk_pred, state_pred, _ = tracker.update(est_compensated_deg=90.0, est_static_deg=90.0, gate_accepted=False, dt=dt)
    assert state_pred == "HOLDING"
    # Predicted angle should follow velocity (around 15.0 deg, definitely not jumped to 90 deg!)
    assert 13.5 <= trk_pred <= 16.5

