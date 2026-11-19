"""
2D TMz Yee-Grid Finite-Difference Time-Domain (FDTD) Maxwell Wave Solver.
Simulates electromagnetic wave propagation, scattering, diffraction, and dielectric penetration
around arena structures on a Yee grid with graded lossy absorbing boundary conditions.
"""

from typing import Dict, List, Optional, Tuple
import math
import numpy as np

from backend.simulation.configuration import SPEED_OF_LIGHT

EPSILON_0 = 8.8541878128e-12
MU_0 = 4.0 * np.pi * 1e-7


class FDTDWaveSolver:
    """
    Solves 2D TMz Maxwell's equations:
    dH_x/dt = -(1/mu) * dE_z/dy
    dH_y/dt =  (1/mu) * dE_z/dx
    dE_z/dt =  (1/eps) * (dH_y/dx - dH_x/dy - sigma * E_z)
    """

    @staticmethod
    def simulate(
        frequency_hz: float = 915.0e6,
        domain_size_m: float = 3.0,
        cells_per_wavelength: int = 12,
        time_steps: int = 250,
        obstacle_type: str = "CONCRETE_WALL",
        source_offset: Tuple[float, float] = (-0.8, 0.0)
    ) -> Dict:
        """
        Executes a 2D TMz FDTD wave simulation.
        
        Args:
            frequency_hz: Source frequency (e.g. 433 MHz, 915 MHz, 2.4 GHz)
            domain_size_m: Square computational domain width in meters (e.g. 3.0 m)
            cells_per_wavelength: Spatial resolution CPW (default 12 cells / lambda)
            time_steps: Number of Yee time updates
            obstacle_type: 'CONCRETE_WALL', 'ROCKY_PILLAR', 'METALLIC_PLATE', 'CLEAR'
            source_offset: (x, y) source coordinate relative to center in meters
            
        Returns:
            Dictionary containing 2D field grid, peak amplitude, and numerical parameters.
        """
        f = float(np.clip(frequency_hz, 100.0e6, 6.0e9))
        wavelength = SPEED_OF_LIGHT / f
        cpw = int(np.clip(cells_per_wavelength, 8, 16))

        # Spatial step dx = dy
        dx = wavelength / cpw
        nx = int(np.clip(round(domain_size_m / dx), 64, 160))
        ny = nx
        dx = domain_size_m / nx
        dy = dx

        # Courant-Friedrichs-Lewy (CFL) stability criterion: dt <= dx / (c * sqrt(2))
        dt = 0.99 / (SPEED_OF_LIGHT * math.sqrt(dx ** -2 + dy ** -2))
        steps = int(np.clip(time_steps, 80, 500))

        # Constitutive property maps
        eps_r = np.ones((ny, nx), dtype=np.float32)
        sigma = np.zeros((ny, nx), dtype=np.float32)

        # Center indices
        cx = nx // 2
        cy = ny // 2

        # Inset obstacle dielectric slab or cylinder
        yy, xx = np.ogrid[:ny, :nx]
        if obstacle_type == "CONCRETE_WALL":
            # Rectangular concrete slab (eps_r = 5.5, sigma = 0.025 S/m)
            slab_width_cells = max(3, int(0.35 / dx))
            slab_height_cells = max(10, int(1.4 / dy))
            mask = (np.abs(xx - (cx + 10)) <= slab_width_cells // 2) & (np.abs(yy - cy) <= slab_height_cells // 2)
            eps_r[mask] = 5.5
            sigma[mask] = 0.025

        elif obstacle_type == "METALLIC_PLATE":
            # Thin highly reflective sheet
            plate_width_cells = max(2, int(0.1 / dx))
            plate_height_cells = max(12, int(1.6 / dy))
            mask = (np.abs(xx - (cx + 8)) <= plate_width_cells // 2) & (np.abs(yy - cy) <= plate_height_cells // 2)
            eps_r[mask] = 1.0
            sigma[mask] = 50.0

        elif obstacle_type == "ROCKY_PILLAR":
            # Circular granite pillar
            pillar_radius_cells = max(4, int(0.4 / dx))
            mask = ((xx - (cx + 10)) ** 2 + (yy - cy) ** 2) <= pillar_radius_cells ** 2
            eps_r[mask] = 7.0
            sigma[mask] = 0.015

        # Update coefficients for conductive medium
        denom = 1.0 + (sigma * dt) / (2.0 * EPSILON_0 * eps_r)
        ca = (1.0 - (sigma * dt) / (2.0 * EPSILON_0 * eps_r)) / denom
        cb = (dt / (EPSILON_0 * eps_r * dx)) / denom
        ch = float(dt / (MU_0 * dx))

        # Field component grids
        Ez = np.zeros((ny, nx), dtype=np.float32)
        Hx = np.zeros((ny, nx), dtype=np.float32)
        Hy = np.zeros((ny, nx), dtype=np.float32)

        # Graded raised-cosine lossy sponge boundary
        yy_idx, xx_idx = np.indices((ny, nx))
        dist_to_edge = np.minimum(
            np.minimum(yy_idx, xx_idx),
            np.minimum(ny - 1 - yy_idx, nx - 1 - xx_idx)
        )
        sponge_depth = max(6, int(0.12 * nx))
        sponge = np.exp(-0.025 * np.maximum(0, sponge_depth - dist_to_edge) ** 2).astype(np.float32)

        # Source cell location
        src_x = int(np.clip(cx + int(source_offset[0] / dx), 4, nx - 5))
        src_y = int(np.clip(cy + int(source_offset[1] / dy), 4, ny - 5))

        omega = 2.0 * np.pi * f
        pulse_center = 40
        pulse_width = 14

        for n in range(steps):
            # 1. Update Magnetic Field H
            Hx[:-1, :] -= ch * (Ez[1:, :] - Ez[:-1, :])
            Hy[:, :-1] += ch * (Ez[:, 1:] - Ez[:, :-1])

            # Apply boundary absorption on H
            Hx *= sponge
            Hy *= sponge

            # 2. Update Electric Field Ez
            curl_h = (Hy[1:-1, 1:-1] - Hy[1:-1, :-2]) - (Hx[1:-1, 1:-1] - Hx[:-2, 1:-1])
            Ez[1:-1, 1:-1] = ca[1:-1, 1:-1] * Ez[1:-1, 1:-1] + cb[1:-1, 1:-1] * curl_h

            # Soft sinusoidal Gaussian-modulated pulse injection
            envelope = math.exp(-((n - pulse_center) / pulse_width) ** 2) if n < pulse_center * 2 else 0.8
            Ez[src_y, src_x] += float(envelope * math.sin(omega * n * dt))

            # Apply boundary absorption on Ez
            Ez *= sponge

        field_mag = np.abs(Ez)
        peak = float(field_mag.max()) or 1.0
        normalized = np.clip(field_mag / peak, 0.0, 1.0)

        # Downsample grid for efficient JSON payload (target ~80x80 cells)
        stride = max(1, nx // 80)
        field_downsampled = np.round(normalized[::stride, ::stride], 3).tolist()

        return {
            "solver": "2D TMz Yee-Grid FDTD",
            "frequency_mhz": round(f / 1.0e6, 1),
            "wavelength_m": round(wavelength, 4),
            "domain_size_m": round(domain_size_m, 2),
            "grid_cells": [nx, ny],
            "dx_m": round(dx, 4),
            "dt_ns": round(dt * 1e9, 4),
            "steps": steps,
            "obstacle_type": obstacle_type,
            "peak_amplitude": round(peak, 4),
            "field_matrix": field_downsampled,
            "source_coords": [round(source_offset[0], 2), round(source_offset[1], 2)]
        }

