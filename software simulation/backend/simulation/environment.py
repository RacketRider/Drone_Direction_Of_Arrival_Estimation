"""
3D Physical Environment and Ray-Tracing Geometry.
Implements 120m x 120m arena, concrete buildings, LOS occlusion, and specular reflection points.
"""

from typing import List, Optional, Tuple
import numpy as np
from backend.simulation.configuration import BuildingConfig

class SpecularReflectionRay:
    """Represents a specular reflection ray from UAV to building wall to Ground Station."""
    def __init__(
        self,
        building_id: int,
        refl_point: Tuple[float, float, float],
        total_path_m: float,
        azimuth_deg: float,
        attenuation_linear: float,
        phase_shift_rad: float
    ):
        self.building_id: int = building_id
        self.refl_point: Tuple[float, float, float] = refl_point
        self.total_path_m: float = total_path_m
        self.azimuth_deg: float = azimuth_deg
        self.attenuation_linear: float = attenuation_linear
        self.phase_shift_rad: float = phase_shift_rad

class PhysicalEnvironment:
    """Arena geometry, obstacle collision, and ray-intersection queries."""
    
    def __init__(self, buildings: List[BuildingConfig] = None):
        if buildings is None:
            # Default to Building Alpha and Beta
            from backend.simulation.configuration import DEFAULT_CONFIG
            self.buildings = DEFAULT_CONFIG.buildings
        else:
            self.buildings = buildings
        self.all_buildings = list(self.buildings)
        self.buildings_enabled = True
        self.ground_station_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def set_buildings_enabled(self, enabled: bool) -> None:
        """Enables or disables buildings in physical environment."""
        self.buildings_enabled = enabled
        if enabled:
            self.buildings = list(self.all_buildings)
        else:
            self.buildings = []

    @staticmethod
    def _segment_intersects_aabb_2d(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        box_min: Tuple[float, float],
        box_max: Tuple[float, float]
    ) -> bool:
        """Slab test for 2D line segment intersection with axis-aligned bounding box."""
        x0, z0 = p0
        x1, z1 = p1
        xmin, zmin = box_min
        xmax, zmax = box_max

        dx = x1 - x0
        dz = z1 - z0

        tmin = 0.0
        tmax = 1.0

        # X slab
        if abs(dx) < 1e-9:
            if x0 < xmin or x0 > xmax:
                return False
        else:
            inv_dx = 1.0 / dx
            t1 = (xmin - x0) * inv_dx
            t2 = (xmax - x0) * inv_dx
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return False

        # Z slab
        if abs(dz) < 1e-9:
            if z0 < zmin or z0 > zmax:
                return False
        else:
            inv_dz = 1.0 / dz
            t1 = (zmin - z0) * inv_dz
            t2 = (zmax - z0) * inv_dz
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return False

        return True

    def check_los_occlusion(self, uav_pos: Tuple[float, float, float]) -> Tuple[bool, Optional[int]]:
        """
        Determines whether the Direct Line-of-Sight (LOS) path between
        Ground Station and UAV is occluded by any building.
        Returns: (is_occluded: bool, occluding_building_id: Optional[int])
        """
        gs_x, gs_y, gs_z = self.ground_station_pos
        u_x, u_y, u_z = uav_pos

        for bldg in self.buildings:
            # 2D footprint check
            hit_2d = self._segment_intersects_aabb_2d(
                (gs_x, gs_z), (u_x, u_z),
                (bldg.x_min, bldg.z_min), (bldg.x_max, bldg.z_max)
            )
            if hit_2d:
                # Height check: does ray penetrate below building rooftop?
                # Simple linear interpolation of height along the ray path
                # For GS at y=0, if UAV is at y=u_y, ray height at center of building
                d_total = np.sqrt((u_x - gs_x)**2 + (u_z - gs_z)**2)
                if d_total > 1e-3:
                    # Building center
                    bc_x = 0.5 * (bldg.x_min + bldg.x_max)
                    bc_z = 0.5 * (bldg.z_min + bldg.z_max)
                    d_bldg = np.sqrt(bc_x**2 + bc_z**2)
                    ray_height_at_bldg = (d_bldg / d_total) * u_y
                    if ray_height_at_bldg < bldg.height:
                        return True, bldg.id
        return False, None

    def compute_specular_reflections(
        self, uav_pos: Tuple[float, float, float]
    ) -> List[SpecularReflectionRay]:
        """
        Computes specular reflection rays from UAV to building faces to Ground Station
        using the Image Source Method.
        """
        reflections: List[SpecularReflectionRay] = []
        if not self.buildings:
            return reflections

        gs_x, gs_y, gs_z = self.ground_station_pos
        ux, uy, uz = uav_pos

        for bldg in self.buildings:
            # 4 vertical walls of the building:
            # (normal_x, normal_z, pt_x, pt_z, is_x_wall, span_min, span_max)
            faces = [
                # 1. East face:  x = x_max, outward normal [1, 0, 0]
                (1.0, 0.0, bldg.x_max, bldg.z_min, True, bldg.z_min, bldg.z_max),
                # 2. West face:  x = x_min, outward normal [-1, 0, 0]
                (-1.0, 0.0, bldg.x_min, bldg.z_min, True, bldg.z_min, bldg.z_max),
                # 3. South face: z = z_max, outward normal [0, 0, 1]
                (0.0, 1.0, bldg.x_min, bldg.z_max, False, bldg.x_min, bldg.x_max),
                # 4. North face: z = z_min, outward normal [0, 0, -1]
                (0.0, -1.0, bldg.x_min, bldg.z_min, False, bldg.x_min, bldg.x_max),
            ]

            for nx, nz, ptx, ptz, is_x_wall, span_min, span_max in faces:
                # Perpendicular distance from UAV (T) and Ground Station (R) to the face plane
                dT = nx * (ux - ptx) + nz * (uz - ptz)
                dR = nx * (gs_x - ptx) + nz * (gs_z - ptz)

                # Both UAV and Ground Station must be in front of the wall (d > 0)
                if dT <= 1e-4 or dR <= 1e-4:
                    continue

                # Virtual image of UAV across the wall plane: T_img = T - 2 * dT * n
                img_x = ux - 2.0 * dT * nx
                img_z = uz - 2.0 * dT * nz
                img_y = uy

                # Parameter s along line segment from T_img to Ground Station
                # At s = dT / (dT + dR), the point lies exactly on the face plane
                s = dT / (dT + dR)
                rx = img_x + s * (gs_x - img_x)
                rz = img_z + s * (gs_z - img_z)
                ry = img_y + s * (gs_y - img_y)

                # Check if reflection point falls within physical wall boundaries
                span_coord = rz if is_x_wall else rx
                if span_min <= span_coord <= span_max and 0.0 <= ry <= bldg.height:
                    d1 = float(np.sqrt((ux - rx)**2 + (uy - ry)**2 + (uz - rz)**2))
                    d2 = float(np.sqrt((rx - gs_x)**2 + (ry - gs_y)**2 + (rz - gs_z)**2))
                    total_dist = d1 + d2

                    # Angle of incidence (cos theta_i = dR / d2)
                    cos_theta = max(0.01, min(1.0, dR / max(1e-4, d2)))
                    sin_theta = float(np.sqrt(max(0.0, 1.0 - cos_theta**2)))

                    # Concrete Fresnel reflection coefficient (dielectric_constant = 6.0)
                    er = float(getattr(bldg, "dielectric_constant", 6.0))
                    radicand = max(0.01, er - sin_theta**2)
                    sqrt_rad = float(np.sqrt(radicand))
                    gamma_te = abs((cos_theta - sqrt_rad) / (cos_theta + sqrt_rad))
                    gamma_tm = abs((er * cos_theta - sqrt_rad) / (er * cos_theta + sqrt_rad))
                    gamma_avg = float(np.sqrt(0.5 * (gamma_te**2 + gamma_tm**2)))

                    # Direction of arrival at Ground Station (from GS to reflection point)
                    refl_az = float(np.degrees(np.arctan2(rz - gs_z, rx - gs_x)))

                    reflections.append(
                        SpecularReflectionRay(
                            building_id=bldg.id,
                            refl_point=(float(rx), float(ry), float(rz)),
                            total_path_m=total_dist,
                            azimuth_deg=refl_az,
                            attenuation_linear=gamma_avg,
                            phase_shift_rad=np.pi
                        )
                    )

        return reflections

