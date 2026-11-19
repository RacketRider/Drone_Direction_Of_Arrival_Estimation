"""
UAV Trajectory Generators.
Implements Figure-Eight, S-Curve, Circular, and Waypoint flight trajectories.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np

class Trajectory(ABC):
    """Abstract base trajectory interface."""
    
    @abstractmethod
    def get_position(self, t: float) -> Tuple[float, float, float]:
        """Returns 3D position [x, y_altitude, z] in meters at simulation time t."""
        pass

    @abstractmethod
    def get_velocity(self, t: float, dt: float = 0.01) -> Tuple[float, float, float]:
        """Returns 3D velocity vector [vx, vy, vz] in m/s at time t."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Trajectory designation name."""
        pass

class FigureEightTrajectory(Trajectory):
    """
    Lemniscate of Gerono / Figure-eight trajectory.
    Gracefully traverses across both building quadrants and open space.
    """
    def __init__(self, a: float = 38.0, b: float = 28.0, altitude: float = 18.0, period: float = 24.0):
        self.a = a
        self.b = b
        self.altitude = altitude
        self.period = period

    @property
    def name(self) -> str:
        return "FIGURE_EIGHT"

    def get_position(self, t: float) -> Tuple[float, float, float]:
        omega = 2.0 * np.pi / self.period
        tau = omega * t
        x = self.a * np.sin(tau)
        z = self.b * np.sin(tau) * np.cos(tau)
        y = self.altitude + 3.0 * np.sin(0.5 * tau)
        return float(x), float(y), float(z)

    def get_velocity(self, t: float, dt: float = 0.01) -> Tuple[float, float, float]:
        p1 = self.get_position(t + dt)
        p0 = self.get_position(t - dt)
        return (
            (p1[0] - p0[0]) / (2.0 * dt),
            (p1[1] - p0[1]) / (2.0 * dt),
            (p1[2] - p0[2]) / (2.0 * dt)
        )

class SCurveTrajectory(Trajectory):
    """
    S-Curve slalom trajectory with sinusoidal sweeping.
    Passes directly into and out of building occlusion shadows.
    """
    def __init__(self, x_span: float = 42.0, z_span: float = 30.0, altitude: float = 16.0, period: float = 20.0):
        self.x_span = x_span
        self.z_span = z_span
        self.altitude = altitude
        self.period = period

    @property
    def name(self) -> str:
        return "S_CURVE"

    def get_position(self, t: float) -> Tuple[float, float, float]:
        omega = 2.0 * np.pi / self.period
        tau = omega * t
        x = self.x_span * np.cos(tau)
        z = self.z_span * np.sin(2.0 * tau) - 10.0
        y = self.altitude + 2.0 * np.cos(tau)
        return float(x), float(y), float(z)

    def get_velocity(self, t: float, dt: float = 0.01) -> Tuple[float, float, float]:
        p1 = self.get_position(t + dt)
        p0 = self.get_position(t - dt)
        return (
            (p1[0] - p0[0]) / (2.0 * dt),
            (p1[1] - p0[1]) / (2.0 * dt),
            (p1[2] - p0[2]) / (2.0 * dt)
        )

class CircularTrajectory(Trajectory):
    """
    Constant radius circular orbit around the ground station array.
    Ideal for evaluating 360-degree azimuth continuity and tracking lag.
    """
    def __init__(self, radius: float = 35.0, altitude: float = 20.0, period: float = 18.0):
        self.radius = radius
        self.altitude = altitude
        self.period = period

    @property
    def name(self) -> str:
        return "CIRCULAR_ORBIT"

    def get_position(self, t: float) -> Tuple[float, float, float]:
        omega = 2.0 * np.pi / self.period
        tau = omega * t
        x = self.radius * np.cos(tau)
        z = self.radius * np.sin(tau)
        y = self.altitude
        return float(x), float(y), float(z)

    def get_velocity(self, t: float, dt: float = 0.01) -> Tuple[float, float, float]:
        omega = 2.0 * np.pi / self.period
        tau = omega * t
        vx = -self.radius * omega * np.sin(tau)
        vz = self.radius * omega * np.cos(tau)
        return float(vx), 0.0, float(vz)

class WaypointTrajectory(Trajectory):
    """
    Smooth spline interpolation through key tactical flight waypoints.
    """
    def __init__(self, waypoints: List[Tuple[float, float, float]] = None, speed: float = 6.0):
        if waypoints is None:
            self.waypoints = [
                (-46.0, 18.0, -25.0),
                (-12.0, 18.0, -5.0),
                (0.0, 22.0, 25.0),
                (30.0, 18.0, 20.0),
                (46.0, 18.0, -22.0),
                (8.0, 15.0, -42.0),
            ]
        else:
            self.waypoints = waypoints
        self.speed = speed

    @property
    def name(self) -> str:
        return "WAYPOINT_PATH"

    def get_position(self, t: float) -> Tuple[float, float, float]:
        # Compute total path length
        pts = np.array(self.waypoints)
        n = len(pts)
        diffs = pts[(np.arange(n) + 1) % n] - pts
        seg_lens = np.linalg.norm(diffs, axis=1)
        total_len = np.sum(seg_lens)
        
        # Current distance along closed loop
        dist = (t * self.speed) % total_len
        cum_lens = np.cumsum(seg_lens)
        
        # Find active segment
        idx = int(np.searchsorted(cum_lens, dist)) % n
        prev_len = cum_lens[idx - 1] if idx > 0 else 0.0
        seg_dist = dist - prev_len
        alpha = seg_dist / max(1e-6, seg_lens[idx])
        
        p0 = pts[idx]
        p1 = pts[(idx + 1) % n]
        pos = (1.0 - alpha) * p0 + alpha * p1
        return float(pos[0]), float(pos[1]), float(pos[2])

    def get_velocity(self, t: float, dt: float = 0.01) -> Tuple[float, float, float]:
        p1 = self.get_position(t + dt)
        p0 = self.get_position(t - dt)
        return (
            (p1[0] - p0[0]) / (2.0 * dt),
            (p1[1] - p0[1]) / (2.0 * dt),
            (p1[2] - p0[2]) / (2.0 * dt)
        )

TRAJECTORY_REGISTRY = {
    "FIGURE_EIGHT": FigureEightTrajectory,
    "S_CURVE": SCurveTrajectory,
    "CIRCULAR_ORBIT": CircularTrajectory,
    "WAYPOINT_PATH": WaypointTrajectory
}

