"""
UAV Kinematics, Collision-Aware Flight Planning, and Ground-Truth State Tracking.
Maintains authoritative collision-free UAV position, velocity, attitude, trail history,
and true bearing calculations strictly synchronized across RF propagation and estimation.
"""

from typing import List, Optional, Tuple
import numpy as np

from backend.simulation.configuration import BuildingConfig, DEFAULT_CONFIG
from backend.simulation.collision import CollisionDetector
from backend.simulation.obstacle_avoidance import ObstacleAvoidancePlanner
from backend.simulation.trajectories import Trajectory, FigureEightTrajectory


class UAVState:
    """Rigorous ground-truth physical state of the UAV with obstacle avoidance."""

    def __init__(
        self,
        trajectory: Optional[Trajectory] = None,
        history_length: int = 300,
        buildings: Optional[List[BuildingConfig]] = None
    ):
        self.trajectory: Trajectory = trajectory if trajectory is not None else FigureEightTrajectory()
        self.history_length: int = history_length
        self.buildings: List[BuildingConfig] = buildings if buildings is not None else DEFAULT_CONFIG.buildings

        # Collision detection and avoidance planner
        self.collision_detector: CollisionDetector = CollisionDetector(
            buildings=self.buildings,
            uav_radius_m=0.8,
            safety_margin_m=2.2
        )
        self.planner: ObstacleAvoidancePlanner = ObstacleAvoidancePlanner(
            collision_detector=self.collision_detector,
            lookahead_seconds=2.5,
            max_speed_mps=12.0,
            max_accel_mps2=8.0,
            waypoint_arrival_radius_m=2.5
        )

        # Authoritative Kinematics (strictly collision-free)
        init_pos = self.trajectory.get_position(0.0)
        self.position: Tuple[float, float, float] = init_pos
        self.velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.speed: float = 0.0
        self.heading_deg: float = 0.0
        self.pitch_deg: float = 0.0
        self.roll_deg: float = 0.0

        # Nominal position (before avoidance replanning)
        self.nominal_position: Tuple[float, float, float] = init_pos

        # Ground-truth direction relative to Ground Station array at origin (0, 0, 0)
        self.true_azimuth_deg: float = 0.0
        self.true_elevation_deg: float = 0.0
        self.true_distance_m: float = 0.0

        # Latest avoidance diagnostics
        self.latest_avoidance_diag: dict = {
            "avoidance_status": "NOMINAL",
            "is_avoiding": False,
            "is_paused": False,
            "avoidance_event_count": 0,
            "active_building_name": None,
            "min_clearance_m": 99.0
        }

        # Trail history buffer for 3D visualization
        self.trail_history: List[Tuple[float, float, float]] = []

        # Initialize planner with starting position
        self.planner.reset(self.position)
        self._compute_bearings()

    def reset(self, sim_time: float = 0.0) -> None:
        """Resets UAV state and avoidance planner."""
        init_pos = self.trajectory.get_position(sim_time)
        self.position = init_pos
        self.velocity = (0.0, 0.0, 0.0)
        self.speed = 0.0
        self.nominal_position = init_pos
        self.trail_history.clear()
        self.planner.reset(init_pos)

    def set_buildings_enabled(self, enabled: bool) -> None:
        """Enables or disables building collision avoidance."""
        active_bldgs = DEFAULT_CONFIG.buildings if enabled else []
        self.collision_detector = CollisionDetector(
            buildings=active_bldgs,
            uav_radius_m=0.8,
            safety_margin_m=2.2
        )
        self.planner = ObstacleAvoidancePlanner(
            collision_detector=self.collision_detector,
            lookahead_seconds=2.5,
            max_speed_mps=12.0,
            max_accel_mps2=8.0,
            waypoint_arrival_radius_m=2.5
        )
        self.planner.reset(self.position)
        self._compute_bearings()

    def set_trajectory(self, trajectory: Trajectory, sim_time: float = 0.0) -> None:
        """Switches UAV flight path trajectory and resets avoidance controller."""
        self.trajectory = trajectory
        self.trail_history.clear()
        init_pos = self.trajectory.get_position(sim_time)
        self.nominal_position = init_pos
        self.planner.reset(init_pos)
        self.position = init_pos
        self.velocity = (0.0, 0.0, 0.0)
        self._compute_bearings()

    def update(self, sim_time: float, dt: float = 0.05) -> None:
        """
        Advances UAV state through the obstacle avoidance planner.
        Guarantees that self.position never penetrates building safety volumes.
        """
        # Save nominal trajectory position for reference
        self.nominal_position = self.trajectory.get_position(sim_time)

        # Plan next safe step
        safe_pos, safe_vel, diag = self.planner.plan_next_step(
            current_sim_time=sim_time,
            dt=dt,
            trajectory=self.trajectory
        )

        self.position = safe_pos
        self.velocity = safe_vel
        self.latest_avoidance_diag = diag

        vx, vy, vz = safe_vel
        self.speed = float(np.sqrt(vx * vx + vy * vy + vz * vz))

        # Heading in horizontal x-z plane
        if abs(vx) > 1e-4 or abs(vz) > 1e-4:
            self.heading_deg = float(np.degrees(np.arctan2(vz, vx)))

        # Bank/pitch angles from velocity
        horiz_speed = max(1e-4, np.sqrt(vx * vx + vz * vz))
        self.pitch_deg = float(np.degrees(np.arctan2(-vy, horiz_speed)))

        # Update authoritative bearings from collision-free position
        self._compute_bearings()

        # Record trail point
        self.trail_history.append(self.position)
        if len(self.trail_history) > self.history_length:
            self.trail_history.pop(0)

    def _compute_bearings(self) -> None:
        """Calculates true spherical bearing coordinates from actual UAV position to array origin (0, 0, 0)."""
        x, y, z = self.position
        ground_dist = np.sqrt(x * x + z * z)
        self.true_distance_m = float(np.sqrt(x * x + y * y + z * z))
        self.true_azimuth_deg = float(np.degrees(np.arctan2(z, x)))
        self.true_elevation_deg = float(np.degrees(np.arctan2(y, ground_dist)))

    @property
    def current_dict(self) -> dict:
        """Serializes current UAV ground-truth state and obstacle avoidance diagnostics for telemetry."""
        return {
            "x": round(self.position[0], 3),
            "y": round(self.position[1], 3),
            "z": round(self.position[2], 3),
            "speed": round(self.speed, 2),
            "heading_deg": round(self.heading_deg, 2),
            "pitch_deg": round(self.pitch_deg, 2),
            "roll_deg": round(self.roll_deg, 2),
            "true_azimuth_deg": round(self.true_azimuth_deg, 2),
            "true_elevation_deg": round(self.true_elevation_deg, 2),
            "distance_m": round(self.true_distance_m, 2),
            "trajectory_name": self.trajectory.name,
            # Obstacle Avoidance Telemetry
            "avoidance_status": self.latest_avoidance_diag.get("avoidance_status", "NOMINAL"),
            "is_avoiding": self.latest_avoidance_diag.get("is_avoiding", False),
            "is_paused": self.latest_avoidance_diag.get("is_paused", False),
            "avoidance_event_count": self.latest_avoidance_diag.get("avoidance_event_count", 0),
            "active_building_name": self.latest_avoidance_diag.get("active_building_name"),
            "min_clearance_m": self.latest_avoidance_diag.get("min_clearance_m", 99.0),
            "nominal_x": round(self.nominal_position[0], 3),
            "nominal_y": round(self.nominal_position[1], 3),
            "nominal_z": round(self.nominal_position[2], 3)
        }
