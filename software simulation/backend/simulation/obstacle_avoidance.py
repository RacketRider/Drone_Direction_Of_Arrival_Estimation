"""
Obstacle-Aware Local Trajectory Planner and Flight Controller.
Detects impending building collisions, computes optimal visibility-graph bypass waypoints,
prevents oscillation, and rejoins nominal trajectories seamlessly.
"""

from typing import List, Literal, Optional, Tuple
import heapq
import numpy as np

from backend.simulation.configuration import BuildingConfig
from backend.simulation.collision import CollisionDetector
from backend.simulation.trajectories import Trajectory


def plan_visibility_bypass(
    detector: CollisionDetector,
    curr_pos: Tuple[float, float, float],
    exit_pos: Tuple[float, float, float],
    altitude: float,
    margin_m: float = 2.5
) -> Optional[List[Tuple[float, float, float]]]:
    """
    Computes the shortest collision-free polygonal path around obstacles
    using an analytical visibility graph on expanded obstacle vertices.
    """
    corners: List[Tuple[float, float, float]] = []
    for vol in detector.volumes:
        b_min = vol.expanded_min
        b_max = vol.expanded_max
        corners.extend([
            (float(b_min[0] - margin_m), altitude, float(b_max[2] + margin_m)),  # SW
            (float(b_max[0] + margin_m), altitude, float(b_max[2] + margin_m)),  # SE
            (float(b_max[0] + margin_m), altitude, float(b_min[2] - margin_m)),  # NE
            (float(b_min[0] - margin_m), altitude, float(b_min[2] - margin_m)),  # NW
        ])

    nodes = [curr_pos] + corners + [exit_pos]
    num_nodes = len(nodes)
    adj = {i: [] for i in range(num_nodes)}

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            hit, _, _ = detector.swept_segment_in_collision(nodes[i], nodes[j], extra_buffer=0.0)
            if not hit:
                dist_ij = float(np.linalg.norm(np.array(nodes[i]) - np.array(nodes[j])))
                adj[i].append((j, dist_ij))
                adj[j].append((i, dist_ij))

    dist = {i: float('inf') for i in range(num_nodes)}
    dist[0] = 0.0
    prev = {i: None for i in range(num_nodes)}
    pq = [(0.0, 0)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == num_nodes - 1:
            break
        for v, weight in adj[u]:
            if dist[u] + weight < dist[v]:
                dist[v] = dist[u] + weight
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))

    if dist[num_nodes - 1] == float('inf'):
        return None

    path = []
    curr = num_nodes - 1
    while curr is not None:
        path.append(nodes[curr])
        curr = prev[curr]
    path.reverse()

    # Drop starting node (current_pos)
    return path[1:] if len(path) > 1 else None


class ObstacleAvoidancePlanner:
    """
    Autonomous trajectory replanner with predictive swept collision detection,
    optimal visibility-graph bypass waypoint generation, and smooth continuous dynamics.
    """

    def __init__(
        self,
        collision_detector: CollisionDetector,
        lookahead_seconds: float = 2.5,
        max_speed_mps: float = 12.0,
        max_accel_mps2: float = 8.0,
        waypoint_arrival_radius_m: float = 2.5
    ):
        self.detector: CollisionDetector = collision_detector
        self.lookahead_seconds: float = lookahead_seconds
        self.max_speed_mps: float = max_speed_mps
        self.max_accel_mps2: float = max_accel_mps2
        self.waypoint_arrival_radius_m: float = waypoint_arrival_radius_m

        # State machine: "NOMINAL", "AVOIDING", "OBSTRUCTED_PAUSED"
        self.status: Literal["NOMINAL", "AVOIDING", "OBSTRUCTED_PAUSED"] = "NOMINAL"
        self.avoidance_event_count: int = 0
        self.active_building: Optional[BuildingConfig] = None

        # Planned avoidance waypoint queue [ [x, y, z], ... ]
        self.avoidance_waypoints: List[Tuple[float, float, float]] = []

        # Last confirmed safe position & velocity
        self.current_pos: Tuple[float, float, float] = (0.0, 18.0, 0.0)
        self.current_vel: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def reset(self, initial_pos: Tuple[float, float, float]) -> None:
        """Resets planner state on simulation reset or trajectory switch."""
        self.status = "NOMINAL"
        self.avoidance_event_count = 0
        self.active_building = None
        self.avoidance_waypoints.clear()
        self.current_pos = initial_pos
        self.current_vel = (0.0, 0.0, 0.0)

    def plan_next_step(
        self,
        current_sim_time: float,
        dt: float,
        trajectory: Trajectory
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], dict]:
        """
        Executes one discrete planning step.
        Returns: (final_pos, final_vel, diagnostics_dict)
        """
        nominal_pos = trajectory.get_position(current_sim_time)
        nominal_vel = trajectory.get_velocity(current_sim_time, dt=dt)

        # 1. Predictive Lookahead Collision Check along nominal path
        impending_collision = False
        collision_bldg: Optional[BuildingConfig] = None

        # Check future nominal trajectory over lookahead horizon
        lookahead_steps = 15
        for t_fut in np.linspace(current_sim_time, current_sim_time + self.lookahead_seconds, lookahead_steps):
            p_fut = trajectory.get_position(float(t_fut))
            hit, b_hit, _ = self.detector.swept_segment_in_collision(self.current_pos, p_fut)
            if hit:
                impending_collision = True
                collision_bldg = b_hit
                break

        # Also check direct swept segment from current position to nominal target
        hit_direct, bldg_direct, _ = self.detector.swept_segment_in_collision(self.current_pos, nominal_pos)
        if hit_direct:
            impending_collision = True
            if collision_bldg is None:
                collision_bldg = bldg_direct

        # 2. State Machine Transitions
        if self.status == "NOMINAL":
            if impending_collision:
                # Find exit point on nominal trajectory past obstacle
                exit_pos = None
                for t_ex in np.linspace(current_sim_time + 1.5, current_sim_time + 10.0, 30):
                    p_candidate = trajectory.get_position(float(t_ex))
                    in_col, _ = self.detector.point_in_collision(p_candidate, extra_buffer=0.5)
                    if not in_col:
                        exit_pos = p_candidate
                        break

                if exit_pos is None:
                    exit_pos = trajectory.get_position(current_sim_time + 6.0)

                path = plan_visibility_bypass(
                    self.detector,
                    self.current_pos,
                    exit_pos,
                    self.current_pos[1],
                    margin_m=2.5
                )

                if path:
                    self.status = "AVOIDING"
                    self.active_building = collision_bldg
                    self.avoidance_waypoints = path
                    self.avoidance_event_count += 1
                else:
                    self.status = "OBSTRUCTED_PAUSED"
                    self.active_building = collision_bldg

        elif self.status == "AVOIDING":
            # Check if line of sight to current nominal position is completely clear and no impending collision
            hit_nom, _, _ = self.detector.swept_segment_in_collision(self.current_pos, nominal_pos)
            if not hit_nom and not impending_collision:
                self.status = "NOMINAL"
                self.active_building = None
                self.avoidance_waypoints.clear()

        elif self.status == "OBSTRUCTED_PAUSED":
            # Attempt recovery: check if nominal pos is clear
            hit_nom, _, _ = self.detector.swept_segment_in_collision(self.current_pos, nominal_pos)
            if not hit_nom and not impending_collision:
                self.status = "NOMINAL"
                self.active_building = None
            else:
                # Try bypass to nominal position
                recovery_path = plan_visibility_bypass(
                    self.detector,
                    self.current_pos,
                    nominal_pos,
                    self.current_pos[1],
                    margin_m=2.5
                )
                if recovery_path:
                    self.status = "AVOIDING"
                    self.avoidance_waypoints = recovery_path

        # 3. Target Position & Velocity Determination
        if self.status == "NOMINAL":
            target_pos = nominal_pos
            target_vel = nominal_vel

        elif self.status == "AVOIDING":
            if self.avoidance_waypoints:
                target_wp = self.avoidance_waypoints[0]
                dist_to_wp = float(np.linalg.norm(np.array(target_wp) - np.array(self.current_pos)))

                if dist_to_wp < self.waypoint_arrival_radius_m:
                    self.avoidance_waypoints.pop(0)
                    if self.avoidance_waypoints:
                        target_wp = self.avoidance_waypoints[0]
                    else:
                        # Reached end of bypass waypoints
                        hit_rejoin, _, _ = self.detector.swept_segment_in_collision(self.current_pos, nominal_pos)
                        if not hit_rejoin:
                            self.status = "NOMINAL"
                            self.active_building = None
                            target_wp = nominal_pos
                        else:
                            rejoin_path = plan_visibility_bypass(
                                self.detector,
                                self.current_pos,
                                nominal_pos,
                                self.current_pos[1],
                                margin_m=2.5
                            )
                            if rejoin_path:
                                self.avoidance_waypoints = rejoin_path
                                target_wp = self.avoidance_waypoints[0]
                            else:
                                target_wp = self.current_pos
                                self.status = "OBSTRUCTED_PAUSED"

                target_pos = target_wp
                dir_vec = np.array(target_pos) - np.array(self.current_pos)
                norm_d = float(np.linalg.norm(dir_vec))
                if norm_d > 1e-4:
                    target_vel = tuple((dir_vec / norm_d) * min(self.max_speed_mps, norm_d / max(0.05, dt)))
                else:
                    target_vel = (0.0, 0.0, 0.0)
            else:
                self.status = "NOMINAL"
                target_pos = nominal_pos
                target_vel = nominal_vel

        else:  # OBSTRUCTED_PAUSED
            target_pos = self.current_pos
            target_vel = (0.0, 0.0, 0.0)

        # 4. Smooth Dynamical Tracking (Critically Damped Second-Order Filter)
        pos_err = np.array(target_pos) - np.array(self.current_pos)
        vel_err = np.array(target_vel) - np.array(self.current_vel)

        kp = 4.0
        kd = 2.0 * np.sqrt(kp)  # Critical damping ratio = 1.0

        accel_cmd = kp * pos_err + kd * vel_err
        accel_mag = float(np.linalg.norm(accel_cmd))
        if accel_mag > self.max_accel_mps2:
            accel_cmd = (accel_cmd / accel_mag) * self.max_accel_mps2

        new_vel = np.array(self.current_vel) + accel_cmd * dt
        speed = float(np.linalg.norm(new_vel))
        if speed > self.max_speed_mps:
            new_vel = (new_vel / speed) * self.max_speed_mps

        proposed_pos = np.array(self.current_pos) + new_vel * dt

        # 5. ABSOLUTE SAFETY HARD SWEPT-SEGMENT CHECK:
        # Swept-segment test between current_pos and proposed_pos against building envelopes
        is_hit, hit_bldg, _ = self.detector.swept_segment_in_collision(
            self.current_pos,
            (float(proposed_pos[0]), float(proposed_pos[1]), float(proposed_pos[2])),
            extra_buffer=0.0
        )

        if is_hit:
            # Emergency braking: halt immediately without penetrating boundary
            self.status = "OBSTRUCTED_PAUSED"
            self.active_building = hit_bldg
            final_pos = self.current_pos
            final_vel = (0.0, 0.0, 0.0)
        else:
            final_pos = (float(proposed_pos[0]), float(proposed_pos[1]), float(proposed_pos[2]))
            final_vel = (float(new_vel[0]), float(new_vel[1]), float(new_vel[2]))

        self.current_pos = final_pos
        self.current_vel = final_vel

        clearance = self.detector.min_clearance_to_obstacles(final_pos)

        diagnostics = {
            "avoidance_status": self.status,
            "is_avoiding": self.status == "AVOIDING",
            "is_paused": self.status == "OBSTRUCTED_PAUSED",
            "avoidance_event_count": self.avoidance_event_count,
            "active_building_name": self.active_building.name if self.active_building else None,
            "min_clearance_m": round(clearance, 2),
            "nominal_pos": [round(float(c), 2) for c in nominal_pos],
            "actual_pos": [round(float(c), 2) for c in final_pos]
        }

        return final_pos, final_vel, diagnostics
