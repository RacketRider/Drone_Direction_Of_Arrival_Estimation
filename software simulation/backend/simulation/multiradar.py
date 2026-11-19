"""
Multi-Station Radar Network and 2D UAV Localization Engine.
Simulates a distributed network of direction-finding ground stations, computes independent
DoA bearings, and performs weighted least-squares line-of-bearing intersection to estimate
the 2D (x, z) horizontal position of the UAV in the arena.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.simulation.configuration import ArrayGeometryConfig, SystemConfiguration
from backend.hardware.uca import UniformCircularArray
from backend.dsp.comparative_estimators import wrap180, wrap360


class RadarStationConfig(BaseModel):
    """Configuration for a single direction-finding ground station."""
    id: int
    name: str
    position: Tuple[float, float, float] = Field(..., description="Ground station (x, y, z) position in meters")
    active: bool = True
    array_radius_m: float = 0.072
    num_elements: int = 4


DEFAULT_RADAR_STATIONS: List[RadarStationConfig] = [
    RadarStationConfig(
        id=1,
        name="Station Alpha (Center Array)",
        position=(0.0, 0.0, 0.0),
        active=True
    ),
    RadarStationConfig(
        id=2,
        name="Station Bravo (East Array)",
        position=(32.0, 0.0, 22.0),
        active=True
    ),
    RadarStationConfig(
        id=3,
        name="Station Charlie (West Array)",
        position=(-32.0, 0.0, 18.0),
        active=True
    ),
    RadarStationConfig(
        id=4,
        name="Station Delta (North Array)",
        position=(0.0, 0.0, -48.0),
        active=False
    ),
]


class MultiStationLocalizer:
    """
    Solves for the horizontal 2D position (x, z) of the UAV by intersecting bearing lines
    from multiple ground stations via weighted least-squares minimization.
    """

    @staticmethod
    def triangulate_position(
        station_positions: List[Tuple[float, float]],
        measured_bearings_deg: List[float],
        bearing_sigmas_deg: Optional[List[float]] = None
    ) -> Tuple[Optional[Tuple[float, float]], bool, float]:
        """
        Intersects bearing lines using the projection matrix formulation:
        For line i with origin r_i and unit vector u_i:
        Distance from point x to line is ||(I - u_i * u_i^T) * (x - r_i)||^2.
        Summing over all stations weighted by w_i = 1 / sigma_i^2 gives:
        A * x = b, where A = sum(w_i * P_i) and b = sum(w_i * P_i * r_i).
        
        Returns:
            ((est_x, est_z) or None, is_valid: bool, condition_number: float)
        """
        N = len(station_positions)
        if N < 2:
            return None, False, float('inf')

        sigmas = bearing_sigmas_deg if bearing_sigmas_deg is not None else [4.0] * N
        matrix_a = np.zeros((2, 2), dtype=np.float64)
        vector_b = np.zeros(2, dtype=np.float64)

        for i in range(N):
            rx, rz = station_positions[i]
            theta_deg = measured_bearings_deg[i]
            theta_rad = np.radians(theta_deg)

            # In our arena coordinate system, azimuth theta is from East (x) toward North (z)
            # or in bearing geometry u = [cos(theta), sin(theta)] (or [sin, cos] depending on convention)
            # Let's align with arctan2(z, x): x = r*cos(theta), z = r*sin(theta)
            u = np.array([np.cos(theta_rad), np.sin(theta_rad)], dtype=np.float64)
            r = np.array([rx, rz], dtype=np.float64)

            # Normal projection operator P_i = I - u * u^T
            projector = np.eye(2) - np.outer(u, u)

            # Weight inversely proportional to angular variance
            weight = 1.0 / max(1.0, sigmas[i] ** 2)

            matrix_a += weight * projector
            vector_b += weight * (projector @ r)

        det_a = float(np.linalg.det(matrix_a))
        cond_a = float(np.linalg.cond(matrix_a))

        if det_a > 1e-8 and cond_a < 1e5:
            sol = np.linalg.solve(matrix_a, vector_b)
            est_x = float(sol[0])
            est_z = float(sol[1])
            if np.isfinite(est_x) and np.isfinite(est_z) and abs(est_x) < 200.0 and abs(est_z) < 200.0:
                return (round(est_x, 3), round(est_z, 3)), True, round(cond_a, 2)

        return None, False, round(cond_a, 2)


class RadarStationTracker:
    """Maintains independent smoothed bearing track for an individual radar station."""

    def __init__(self, station_id: int, alpha: float = 0.25):
        self.station_id = station_id
        self.alpha = alpha
        self.current_track_deg: Optional[float] = None

    def update(self, raw_bearing_deg: float) -> float:
        raw = float(raw_bearing_deg) % 360.0
        if self.current_track_deg is None:
            self.current_track_deg = raw
        else:
            diff = wrap180(raw - self.current_track_deg)
            self.current_track_deg = wrap360(self.current_track_deg + self.alpha * diff)
        return float(self.current_track_deg)

    def reset(self) -> None:
        self.current_track_deg = None


class MultiRadarNetwork:
    """Manages the distributed radar network and real-time drone localization."""

    def __init__(self, stations: Optional[List[RadarStationConfig]] = None):
        self.stations: List[RadarStationConfig] = stations or list(DEFAULT_RADAR_STATIONS)
        self.trackers: Dict[int, RadarStationTracker] = {
            s.id: RadarStationTracker(s.id) for s in self.stations
        }
        self.localizer = MultiStationLocalizer()

    def set_station_active(self, station_id: int, active: bool) -> None:
        for s in self.stations:
            if s.id == station_id:
                s.active = active

    def reset(self) -> None:
        for t in self.trackers.values():
            t.reset()

    def update(
        self,
        uav_position: Tuple[float, float, float],
        active_frequency_hz: float,
        nominal_snr_db: float,
        seed: int = 42
    ) -> Dict:
        """
        Computes synthetic DoA measurements at all active radar stations, applies
        individual noise/propagation, and triangulates 2D drone position.
        """
        rng = np.random.default_rng(seed)
        ux, uy, uz = uav_position

        active_stations = [s for s in self.stations if s.active]
        station_positions = []
        measured_bearings = []
        tracked_bearings = []
        sigmas = []
        station_readings = []

        for st in active_stations:
            sx, sy, sz = st.position
            dx = ux - sx
            dy = uy - sy
            dz = uz - sz
            dist_3d = float(np.sqrt(dx * dx + dy * dy + dz * dz))
            dist_2d = float(np.sqrt(dx * dx + dz * dz))

            # Ground truth azimuth relative to this station's coordinates
            true_az = float(wrap360(np.degrees(np.arctan2(dz, dx))))

            # Distance-dependent SNR attenuation
            path_loss_snr = nominal_snr_db - 20.0 * np.log10(max(1.0, dist_3d / 20.0))
            eff_snr = float(np.clip(path_loss_snr, -15.0, 40.0))

            # Measurement noise sigma based on SNR
            sigma_deg = float(np.clip(18.0 / (10.0 ** (max(0.0, eff_snr) / 20.0)), 0.3, 25.0))
            meas_az = float(wrap360(true_az + rng.normal(0.0, sigma_deg)))

            # Update tracker
            track_az = self.trackers[st.id].update(meas_az)

            station_positions.append((sx, sz))
            measured_bearings.append(meas_az)
            tracked_bearings.append(track_az)
            sigmas.append(sigma_deg)

            err_meas = float(wrap180(meas_az - true_az))
            err_track = float(wrap180(track_az - true_az))

            station_readings.append({
                "id": st.id,
                "name": st.name,
                "x": round(sx, 2),
                "y": round(sy, 2),
                "z": round(sz, 2),
                "distance_m": round(dist_3d, 2),
                "true_azimuth_deg": round(true_az, 2),
                "measured_bearing_deg": round(meas_az, 2),
                "tracked_bearing_deg": round(track_az, 2),
                "error_deg": round(err_meas, 2),
                "tracked_error_deg": round(err_track, 2),
                "sigma_deg": round(sigma_deg, 2),
                "effective_snr_db": round(eff_snr, 1),
                "active": True
            })

        # Multi-station triangulation
        est_pos, valid_solution, cond_num = self.localizer.triangulate_position(
            station_positions=station_positions,
            measured_bearings_deg=tracked_bearings,
            bearing_sigmas_deg=sigmas
        )

        position_error_m = None
        if est_pos is not None:
            ex, ez = est_pos
            position_error_m = round(float(np.sqrt((ux - ex) ** 2 + (uz - ez) ** 2)), 2)

        return {
            "num_active_stations": len(active_stations),
            "stations": station_readings,
            "estimated_pos_xz": est_pos,
            "position_error_m": position_error_m,
            "solution_valid": valid_solution,
            "condition_number": cond_num,
            "truth_xz": (round(ux, 2), round(uz, 2))
        }


class MultiRadarLocalization:
    """Compatibility interface for API multi-radar localization solver."""

    @classmethod
    def solve_position_from_bearings(
        cls,
        radar_stations: List[Dict],
        drone_true_pos: Tuple[float, float, float]
    ) -> Dict:
        station_positions = [(float(s["x"]), float(s["z"])) for s in radar_stations]
        bearings = [float(s.get("azimuth_deg", s.get("measured_bearing_deg", 0.0))) for s in radar_stations]
        sigmas = [float(s.get("sigma_deg", 2.0)) for s in radar_stations]

        est_pos, valid, cond = MultiStationLocalizer.triangulate_position(
            station_positions=station_positions,
            measured_bearings_deg=bearings,
            bearing_sigmas_deg=sigmas
        )

        pos_err = None
        est_x = est_z = None
        if est_pos is not None:
            est_x, est_z = est_pos
            ux, _, uz = drone_true_pos
            pos_err = round(float(np.sqrt((ux - est_x) ** 2 + (uz - est_z) ** 2)), 2)

        return {
            "estimated_x": est_x,
            "estimated_z": est_z,
            "position_error_m": pos_err,
            "condition_number": cond,
            "valid": valid,
            "stations": radar_stations
        }
