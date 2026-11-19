"""
Direction-Finding Tracking Engine.
Implements Track State Machine (Gated Hold) and Adaptive Circular Kalman Filter
with continuous acceleration process noise, innovation chi-squared gating,
maneuver detection, and re-acquisition logic.
"""

from typing import Literal, Optional, Tuple
import numpy as np
from scipy.stats import chi2
from backend.dsp.music import MUSICEstimator


class BearingTracker:
    """
    Maintains continuous estimated bearing trajectory.
    When reliability gate rejects a multipath outlier, retains HOLD_LAST_VERIFIED_BEARING
    or propagates kinematic state predictions.
    """

    def __init__(
        self,
        tracker_type: Literal["GATED_HOLD", "KALMAN_FILTER"] = "GATED_HOLD",
        max_hold_bursts: int = 20,
        q_accel_psd: float = 80.0,       # Acceleration power spectral density deg^2/s^3
        r_meas_var: float = 0.8,         # Default measurement variance deg^2
        gate_probability: float = 0.999   # Chi-square gating confidence
    ):
        self.tracker_type: str = tracker_type
        self.max_hold_bursts: int = max_hold_bursts
        self.q_accel_psd: float = q_accel_psd
        self.r_meas: float = r_meas_var

        # Chi-square threshold for 1 degree-of-freedom measurement innovation
        self.gate_threshold: float = float(chi2.ppf(gate_probability, df=1))
        self.soft_gate_nis: float = 16.0  # Normalized Innovation Squared threshold for maneuvers

        # Track state
        self.raw_compensated_deg: float = 0.0
        self.raw_static_deg: float = 0.0
        self.accepted_track_deg: float = 0.0
        self.previous_accepted_deg: float = 0.0
        self.state: Literal["ACQUIRED", "HOLDING", "LOST"] = "HOLDING"

        # Counters
        self.consecutive_rejections: int = 0
        self.total_rejections: int = 0
        self.total_bursts: int = 0

        # Recent rejected measurements buffer for re-acquisition
        self.rejected_history: list = []

        # 2-State Kalman Filter: [theta_deg, omega_deg_per_s]
        self.kf_state: np.ndarray = np.zeros(2)
        self.kf_cov: np.ndarray = np.diag([9.0, 16.0])

    def _compute_process_noise_q(self, dt: float, is_maneuvering: bool = False) -> np.ndarray:
        """
        Continuous white noise acceleration model Q matrix:
        Q = q * [[dt^3 / 3, dt^2 / 2], [dt^2 / 2, dt]]
        """
        q = self.q_accel_psd * (4.0 if is_maneuvering else 1.0)
        dt2 = dt * dt
        dt3 = dt2 * dt
        return q * np.array([
            [dt3 / 3.0, dt2 / 2.0],
            [dt2 / 2.0, dt]
        ])

    def update(
        self,
        est_compensated_deg: float,
        est_static_deg: float,
        gate_accepted: bool,
        dt: float = 0.05,
        est_uncertainty_deg: Optional[float] = None
    ) -> Tuple[float, str, dict]:
        """
        Updates bearing track with newest burst estimates and gate decision.
        """
        self.total_bursts += 1
        self.raw_compensated_deg = est_compensated_deg
        self.raw_static_deg = est_static_deg

        nis = 0.0
        is_maneuver = False

        if self.tracker_type == "GATED_HOLD":
            if gate_accepted:
                self.previous_accepted_deg = self.accepted_track_deg
                self.accepted_track_deg = est_compensated_deg
                self.consecutive_rejections = 0
                self.state = "ACQUIRED"
                self.rejected_history.clear()
            else:
                self.consecutive_rejections += 1
                self.total_rejections += 1
                if self.consecutive_rejections > self.max_hold_bursts:
                    self.state = "LOST"
                else:
                    self.state = "HOLDING"

            active_track = self.accepted_track_deg

        else:
            # KALMAN FILTER MODE
            # 1. Measurement initialization on first valid bursts
            if self.total_bursts == 1 and gate_accepted:
                self.kf_state[0] = est_compensated_deg
                self.kf_state[1] = 0.0
                self.accepted_track_deg = est_compensated_deg
                self.previous_accepted_deg = est_compensated_deg
                self.state = "ACQUIRED"
                return self.accepted_track_deg, self.state, {
                    "tracker_type": self.tracker_type,
                    "state": self.state,
                    "accepted_track_deg": round(est_compensated_deg, 2),
                    "raw_compensated_deg": round(est_compensated_deg, 2),
                    "raw_static_deg": round(est_static_deg, 2),
                    "consecutive_rejections": 0,
                    "total_rejections": 0,
                    "total_bursts": 1,
                    "nis": 0.0
                }
            elif self.total_bursts == 2 and gate_accepted:
                d_theta = MUSICEstimator.circular_angular_error(est_compensated_deg, self.previous_accepted_deg)
                self.kf_state[1] = d_theta / max(1e-4, dt)

            # 2. State Prediction: theta_k|k-1 = theta_k-1 + omega * dt
            f_mat = np.array([[1.0, dt], [0.0, 1.0]])
            pred_state = f_mat @ self.kf_state
            pred_state[0] = ((pred_state[0] + 180.0) % 360.0) - 180.0

            # 3. Innovation and Gating Evaluation
            innov = MUSICEstimator.circular_angular_error(est_compensated_deg, pred_state[0])
            h_mat = np.array([1.0, 0.0])

            # Adaptive measurement variance if estimator provides uncertainty
            r_effective = (est_uncertainty_deg**2) if est_uncertainty_deg is not None else self.r_meas
            r_effective = float(np.clip(r_effective, 0.2, 50.0))

            # Initial process noise covariance for prediction
            q_mat = self._compute_process_noise_q(dt, is_maneuvering=False)
            pred_cov = f_mat @ self.kf_cov @ f_mat.T + q_mat

            s_innov = float(h_mat @ pred_cov @ h_mat.T + r_effective)
            nis = float((innov * innov) / max(1e-6, s_innov))

            # Detect rapid maneuver: if NIS is elevated but not extreme, inflate Q
            if nis > self.soft_gate_nis and nis < self.gate_threshold * 2.5:
                is_maneuver = True
                q_mat = self._compute_process_noise_q(dt, is_maneuvering=True)
                pred_cov = f_mat @ self.kf_cov @ f_mat.T + q_mat
                s_innov = float(h_mat @ pred_cov @ h_mat.T + r_effective)
                nis = float((innov * innov) / max(1e-6, s_innov))

            # Kinematic innovation gate check
            passes_kinematic_gate = (nis <= self.gate_threshold) or is_maneuver

            # Re-acquisition check: if sustained rejections have occurred, check if recent measurements cluster
            reacquired = False
            if not gate_accepted or not passes_kinematic_gate:
                self.rejected_history.append(est_compensated_deg)
                if len(self.rejected_history) > 4:
                    self.rejected_history.pop(0)
                    # If last 4 rejected measurements are within 8 deg of each other, re-acquire!
                    spread = max(self.rejected_history) - min(self.rejected_history)
                    if spread < 8.0 and gate_accepted:
                        reacquired = True
                        pred_state[0] = float(np.mean(self.rejected_history))
                        pred_state[1] = 0.0
                        pred_cov = np.diag([4.0, 9.0])
                        self.rejected_history.clear()

            if (gate_accepted and passes_kinematic_gate) or reacquired:
                # 4. Measurement Update
                k_gain = (pred_cov @ h_mat) / s_innov
                self.kf_state = pred_state + k_gain * innov
                self.kf_state[0] = ((self.kf_state[0] + 180.0) % 360.0) - 180.0
                self.kf_cov = (np.eye(2) - np.outer(k_gain, h_mat)) @ pred_cov

                self.previous_accepted_deg = self.accepted_track_deg
                self.accepted_track_deg = float(self.kf_state[0])
                self.consecutive_rejections = 0
                self.state = "ACQUIRED"
                self.rejected_history.clear()
            else:
                # 5. Gate or NIS rejected: Propagate prediction only
                self.kf_state = pred_state
                self.kf_cov = pred_cov
                self.consecutive_rejections += 1
                self.total_rejections += 1
                self.state = "HOLDING" if self.consecutive_rejections <= self.max_hold_bursts else "LOST"
                self.accepted_track_deg = float(self.kf_state[0])

            active_track = self.accepted_track_deg

        diagnostics = {
            "tracker_type": self.tracker_type,
            "state": self.state,
            "accepted_track_deg": round(active_track, 2),
            "raw_compensated_deg": round(est_compensated_deg, 2),
            "raw_static_deg": round(est_static_deg, 2),
            "consecutive_rejections": self.consecutive_rejections,
            "total_rejections": self.total_rejections,
            "total_bursts": self.total_bursts,
            "nis": round(nis, 2),
            "is_maneuvering": is_maneuver
        }

        return active_track, self.state, diagnostics

    def reset(self) -> None:
        """Resets tracker state, Kalman filter, and counters."""
        self.raw_compensated_deg = 0.0
        self.raw_static_deg = 0.0
        self.accepted_track_deg = 0.0
        self.previous_accepted_deg = 0.0
        self.state = "HOLDING"
        self.consecutive_rejections = 0
        self.total_rejections = 0
        self.total_bursts = 0
        self.rejected_history.clear()
        self.kf_state = np.zeros(2)
        self.kf_cov = np.diag([9.0, 16.0])
