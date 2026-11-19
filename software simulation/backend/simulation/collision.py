"""
3D Building Collision Detection and Swept-Segment Intersection Engine.
Provides exact analytical AABB and swept-line segment collision checks with physical UAV safety buffers.
"""

from typing import List, Optional, Tuple
import numpy as np
from backend.simulation.configuration import BuildingConfig

class BuildingCollisionVolume:
    """Represents a physical 3D obstacle with UAV radius and safety margins."""

    def __init__(
        self,
        building: BuildingConfig,
        uav_radius_m: float = 0.8,
        safety_margin_m: float = 2.2
    ):
        self.building: BuildingConfig = building
        self.uav_radius_m: float = uav_radius_m
        self.safety_margin_m: float = safety_margin_m
        self.total_buffer_m: float = uav_radius_m + safety_margin_m

        # Raw physical bounds
        self.raw_min = np.array([building.x_min, 0.0, building.z_min], dtype=np.float64)
        self.raw_max = np.array([building.x_max, building.height, building.z_max], dtype=np.float64)

        # Expanded safety collision bounds
        self.expanded_min = np.array([
            building.x_min - self.total_buffer_m,
            0.0,
            building.z_min - self.total_buffer_m
        ], dtype=np.float64)
        self.expanded_max = np.array([
            building.x_max + self.total_buffer_m,
            building.height + self.total_buffer_m,
            building.z_max + self.total_buffer_m
        ], dtype=np.float64)

    def point_inside(self, p: Tuple[float, float, float], extra_buffer: float = 0.0) -> bool:
        """Tests whether 3D point is inside the building volume."""
        b_min = self.expanded_min - extra_buffer
        b_max = self.expanded_max + extra_buffer
        return bool(
            b_min[0] <= p[0] <= b_max[0] and
            b_min[1] <= p[1] <= b_max[1] and
            b_min[2] <= p[2] <= b_max[2]
        )

    def swept_segment_intersects(
        self,
        p0: Tuple[float, float, float],
        p1: Tuple[float, float, float],
        extra_buffer: float = 0.0
    ) -> Tuple[bool, float, float]:
        """
        Analytical 3D slab ray-box intersection for line segment [P0, P1].
        Returns: (intersects: bool, entry_t: float, exit_t: float) where t in [0, 1].
        """
        b_min = self.expanded_min - extra_buffer
        b_max = self.expanded_max + extra_buffer

        t_min = 0.0
        t_max = 1.0

        for i in range(3):
            v0 = p0[i]
            v1 = p1[i]
            d = v1 - v0

            if abs(d) < 1e-9:
                # Line is parallel to slab
                if v0 < b_min[i] or v0 > b_max[i]:
                    return False, 0.0, 0.0
            else:
                inv_d = 1.0 / d
                t1 = (b_min[i] - v0) * inv_d
                t2 = (b_max[i] - v0) * inv_d
                if t1 > t2:
                    t1, t2 = t2, t1
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                if t_min > t_max:
                    return False, 0.0, 0.0

        if t_min <= 1.0 and t_max >= 0.0:
            return True, max(0.0, t_min), min(1.0, t_max)
        return False, 0.0, 0.0

    def distance_to_point(self, p: Tuple[float, float, float]) -> float:
        """Calculates distance from point p to the building's physical surface."""
        # Clamp point to physical bounding box
        clamped_x = max(self.raw_min[0], min(p[0], self.raw_max[0]))
        clamped_y = max(self.raw_min[1], min(p[1], self.raw_max[1]))
        clamped_z = max(self.raw_min[2], min(p[2], self.raw_max[2]))

        dx = p[0] - clamped_x
        dy = p[1] - clamped_y
        dz = p[2] - clamped_z

        return float(np.sqrt(dx * dx + dy * dy + dz * dz))


class CollisionDetector:
    """Manages all arena building collision volumes and spatial queries."""

    def __init__(
        self,
        buildings: List[BuildingConfig],
        uav_radius_m: float = 0.8,
        safety_margin_m: float = 2.2
    ):
        self.uav_radius_m = uav_radius_m
        self.safety_margin_m = safety_margin_m
        self.volumes: List[BuildingCollisionVolume] = [
            BuildingCollisionVolume(b, uav_radius_m, safety_margin_m)
            for b in buildings
        ]

    def point_in_collision(
        self,
        p: Tuple[float, float, float],
        extra_buffer: float = 0.0
    ) -> Tuple[bool, Optional[BuildingConfig]]:
        """Tests whether point p violates any building safety envelope."""
        for v in self.volumes:
            if v.point_inside(p, extra_buffer):
                return True, v.building
        return False, None

    def swept_segment_in_collision(
        self,
        p0: Tuple[float, float, float],
        p1: Tuple[float, float, float],
        extra_buffer: float = 0.0
    ) -> Tuple[bool, Optional[BuildingConfig], float]:
        """
        Tests whether the motion swept segment [p0, p1] penetrates any building safety envelope.
        Returns: (in_collision: bool, building: Optional[BuildingConfig], entry_t: float)
        """
        closest_hit = 1.0
        hit_building = None
        has_hit = False

        for v in self.volumes:
            hit, t_entry, _ = v.swept_segment_intersects(p0, p1, extra_buffer)
            if hit:
                has_hit = True
                if t_entry <= closest_hit:
                    closest_hit = t_entry
                    hit_building = v.building

        return has_hit, hit_building, closest_hit

    def min_clearance_to_obstacles(self, p: Tuple[float, float, float]) -> float:
        """Returns distance in meters to the nearest building physical surface."""
        if not self.volumes:
            return 999.0
        return min(v.distance_to_point(p) for v in self.volumes)

