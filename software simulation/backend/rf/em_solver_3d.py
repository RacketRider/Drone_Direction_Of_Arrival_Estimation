"""
Bounded 3-D Vector Maxwell Yee-Grid FDTD Simulation.
Calculates full 3-D Cartesian vector electrodynamics for Ex, Ey, Ez and Hx, Hy, Hz
on a localized voxel domain with dielectric inclusions and boundary absorbing sponge.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
import numpy as np

C0: float = 299792458.0
EPS0: float = 8.8541878128e-12
MU0: float = 4.0e-7 * np.pi


def fdtd_3d(
    frequency_hz: float = 433.0e6,
    size_m: float = 0.50,
    steps: int = 70,
    shape: Tuple[int, int, int] = (24, 24, 24)
) -> dict:
    """
    3-D Cartesian vector Yee-grid time-domain update.
    Returns central Ez field slice and electrodynamic stability diagnostics.
    """
    f = float(np.clip(frequency_hz, 1.0e7, 6.0e9))
    size_m = float(np.clip(size_m, 0.1, 2.0))
    nx, ny, nz = (int(np.clip(v, 12, 36)) for v in shape)
    steps = int(np.clip(steps, 20, 140))

    dx = size_m / (max(nx, ny, nz) - 1)
    dy = dx
    dz = dx

    # 3-D Courant stability limit with safety margin
    courant_dt_limit = 1.0 / (C0 * math.sqrt(dx**-2 + dy**-2 + dz**-2))
    dt = 0.95 * courant_dt_limit
    courant_number = float(C0 * dt * math.sqrt(dx**-2 + dy**-2 + dz**-2))

    epsr = np.ones((nx, ny, nz), dtype=np.float32)
    sigma = np.zeros_like(epsr)

    # Concrete slab inclusion at the base (y <= ny // 5)
    epsr[:, :max(2, ny // 5), :] = 5.5
    sigma[:, :max(2, ny // 5), :] = 0.02

    # Concrete building block voxel obstacle
    xx, yy, zz = np.indices((nx, ny, nz))
    bldg_mask = (
        (xx >= nx * 0.4) & (xx <= nx * 0.75) &
        (yy <= ny * 0.7) &
        (zz >= nz * 0.35) & (zz <= nz * 0.75)
    )
    epsr[bldg_mask] = 5.5
    sigma[bldg_mask] = 0.02

    Ex = np.zeros_like(epsr)
    Ey = np.zeros_like(epsr)
    Ez = np.zeros_like(epsr)
    Hx = np.zeros_like(epsr)
    Hy = np.zeros_like(epsr)
    Hz = np.zeros_like(epsr)

    # 3D absorbing boundary sponge
    edge = np.minimum.reduce(
        np.broadcast_arrays(xx, nx - 1 - xx, yy, ny - 1 - yy, zz, nz - 1 - zz)
    ).astype(np.float32)
    sponge = np.exp(-0.12 * np.maximum(0, 4 - edge)**2).astype(np.float32)

    ce = (1.0 - sigma * dt / (2.0 * EPS0 * epsr)) / (1.0 + sigma * dt / (2.0 * EPS0 * epsr))
    ch = (dt / (EPS0 * epsr)) / (1.0 + sigma * dt / (2.0 * EPS0 * epsr))
    ch = ch.astype(np.float32)
    c_curl_h = float(dt / MU0)

    # Soft Gaussian-modulated Ez dipole source
    sx, sy, sz = nx // 4, ny // 2, nz // 2
    t0 = 16.0
    spread = 5.0
    omega = 2.0 * np.pi * f

    for n in range(steps):
        # H-field update: H <- H - dt/mu * curl(E)
        dEz_dy = (np.roll(Ez, -1, axis=1) - Ez) / dy
        dEy_dz = (np.roll(Ey, -1, axis=2) - Ey) / dz
        dEx_dz = (np.roll(Ex, -1, axis=2) - Ex) / dz
        dEz_dx = (np.roll(Ez, -1, axis=0) - Ez) / dx
        dEy_dx = (np.roll(Ey, -1, axis=0) - Ey) / dx
        dEx_dy = (np.roll(Ex, -1, axis=1) - Ex) / dy

        Hx = (Hx - c_curl_h * (dEz_dy - dEy_dz)) * sponge
        Hy = (Hy - c_curl_h * (dEx_dz - dEz_dx)) * sponge
        Hz = (Hz - c_curl_h * (dEy_dx - dEx_dy)) * sponge

        # E-field update: E <- E + dt/eps * curl(H)
        dHz_dy = (Hz - np.roll(Hz, 1, axis=1)) / dy
        dHy_dz = (Hy - np.roll(Hy, 1, axis=2)) / dz
        dHx_dz = (Hx - np.roll(Hx, 1, axis=2)) / dz
        dHz_dx = (Hz - np.roll(Hz, 1, axis=0)) / dx
        dHy_dx = (Hy - np.roll(Hy, 1, axis=0)) / dx
        dHx_dy = (Hx - np.roll(Hx, 1, axis=1)) / dy

        Ex = ce * Ex + ch * (dHz_dy - dHy_dz)
        Ey = ce * Ey + ch * (dHx_dz - dHz_dx)
        Ez = ce * Ez + ch * (dHy_dx - dHx_dy)

        # Inject source
        pulse = math.exp(-0.5 * ((n - t0) / spread)**2) * math.sin(omega * n * dt)
        Ez[sx, sy, sz] += float(pulse)

        # Apply sponge
        Ex *= sponge
        Ey *= sponge
        Ez *= sponge

    # Central Z-slice through 3D domain for 2D visualization
    sl = np.abs(Ez[:, :, nz // 2]).astype(float)
    peak = float(sl.max()) if float(sl.max()) > 1e-12 else 1.0
    normalized_slice = (sl / peak).tolist()

    return {
        "solver": "3D Vector Maxwell Yee-Grid FDTD",
        "dimensions": [nx, ny, nz],
        "steps": steps,
        "frequency_hz": f,
        "wavelength_m": round(C0 / f, 4),
        "dx_m": round(dx, 5),
        "dt_s": float(dt),
        "courant_number": round(courant_number, 3),
        "courant_limit_pass": bool(courant_number <= 1.0),
        "field_component": "|Ez| central z-slice",
        "field_normalized": normalized_slice,
        "peak_field_amplitude": round(peak, 5),
        "finite_field": bool(np.all(np.isfinite(Ez)) and np.all(np.isfinite(Hx))),
        "material_voxels": {
            "air_epsr": 1.0,
            "concrete_epsr": 5.5,
            "conductivity_s_m": 0.02
        }
    }
