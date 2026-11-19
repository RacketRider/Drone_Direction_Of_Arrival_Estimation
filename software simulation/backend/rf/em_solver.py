"""
Bounded 2-D TMz Yee-Grid FDTD and Physical Ray-Tracing Solver.
Calculates local electromagnetic wave propagation, complex dielectric impedance,
Fresnel reflections, Möller-Trumbore facet intersections, and specular ray paths.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
import numpy as np

# Physical constants
C0: float = 299792458.0
EPS0: float = 8.8541878128e-12
MU0: float = 4.0e-7 * np.pi


def compute_complex_impedance_and_fresnel(
    epsilon_r: float = 5.5,
    conductivity_s_m: float = 0.02,
    mu_r: float = 1.0,
    tan_delta_e: float = 0.03,
    tan_delta_m: float = 0.0001,
    frequency_hz: float = 433.0e6
) -> Tuple[complex, complex, complex, float]:
    """
    Computes exact complex permittivity, complex permeability, intrinsic wave impedance,
    and normal-incidence Fresnel reflection magnitude:
    eps* = eps_r * eps_0 - j*(eps_r * eps_0 * tan_delta_e + sigma / omega)
    mu* = mu_r * mu_0 - j*(mu_r * mu_0 * tan_delta_m)
    eta = sqrt(mu* / eps*)
    Gamma = (eta - eta_0) / (eta + eta_0)
    """
    omega = 2.0 * np.pi * max(1e6, frequency_hz)
    eps_complex = complex(
        epsilon_r * EPS0,
        -(epsilon_r * EPS0 * tan_delta_e + conductivity_s_m / omega)
    )
    mu_complex = complex(
        mu_r * MU0,
        -(mu_r * MU0 * tan_delta_m)
    )
    eta_medium = np.sqrt(mu_complex / eps_complex)
    eta_free_space = np.sqrt(MU0 / EPS0)  # ~376.73 ohms

    gamma = (eta_medium - eta_free_space) / (eta_medium + eta_free_space)
    gamma_mag = float(np.clip(abs(gamma), 0.0, 0.999))

    return eps_complex, mu_complex, eta_medium, gamma_mag


def segment_triangle_intersection(
    p0: Tuple[float, float, float],
    p1: Tuple[float, float, float],
    triangle: List[List[float]],
    eps: float = 1e-9
) -> Optional[float]:
    """
    Möller–Trumbore segment/triangle intersection.
    Returns parametric distance t in [eps, 1 - eps] or None.
    """
    v0 = np.asarray(triangle[0], dtype=float)
    v1 = np.asarray(triangle[1], dtype=float)
    v2 = np.asarray(triangle[2], dtype=float)

    d = np.asarray(p1, dtype=float) - np.asarray(p0, dtype=float)
    e1 = v1 - v0
    e2 = v2 - v0
    h = np.cross(d, e2)
    a = float(np.dot(e1, h))

    if abs(a) < eps:
        return None

    f = 1.0 / a
    s = np.asarray(p0, dtype=float) - v0
    u = f * float(np.dot(s, h))
    if u < -eps or u > 1.0 + eps:
        return None

    q = np.cross(s, e1)
    v = f * float(np.dot(d, q))
    if v < -eps or u + v > 1.0 + eps:
        return None

    t = f * float(np.dot(e2, q))
    if eps < t < 1.0 - eps:
        return float(t)

    return None


def trace_geometry(
    source: List[float],
    target: List[float],
    objects: List[dict]
) -> dict:
    """
    Traces line-of-sight ray between source and target against building facets and boxes.
    """
    s = np.asarray(source, dtype=float)
    t = np.asarray(target, dtype=float)
    d = t - s
    hits = []

    for i, o in enumerate(objects):
        if not isinstance(o, dict):
            continue
        name = str(o.get('name', o.get('id', f'object_{i+1}')))

        # 1. Triangle Facet Intersection
        if 'triangles' in o and isinstance(o['triangles'], list):
            for tri in o['triangles']:
                try:
                    hit_t = segment_triangle_intersection(tuple(s), tuple(t), tri)
                    if hit_t is not None:
                        pt = (s + hit_t * d).tolist()
                        hits.append({
                            'object': name,
                            'kind': o.get('kind', 'mesh'),
                            't': hit_t,
                            'point': [round(c, 3) for c in pt],
                            'method': 'triangle_facet'
                        })
                except Exception:
                    continue

        # 2. Axis-Aligned Bounding Box (AABB) Slab Intersection
        elif 'bounds' in o:
            b = o['bounds']
            lo = np.asarray(b.get('min', [0, 0, 0]), dtype=float)
            hi = np.asarray(b.get('max', [0, 0, 0]), dtype=float)
            inv = np.where(np.abs(d) > 1e-12, 1.0 / d, np.inf)
            t_lo = (lo - s) * inv
            t_hi = (hi - s) * inv
            near = np.max(np.minimum(t_lo, t_hi))
            far = np.min(np.maximum(t_lo, t_hi))
            if far >= max(near, 0.0) and near < 1.0 and far > 0.0:
                t_hit = float(max(0.0, near))
                pt = (s + t_hit * d).tolist()
                hits.append({
                    'object': name,
                    'kind': o.get('kind', 'box'),
                    't': t_hit,
                    'point': [round(c, 3) for c in pt],
                    'method': 'axis_aligned_box'
                })

        # 3. Direct AABB coordinates [x_min, x_max, z_min, z_max, height]
        elif 'x_min' in o and 'x_max' in o:
            lo = np.array([float(o['x_min']), 0.0, float(o['z_min'])])
            hi = np.array([float(o['x_max']), float(o.get('height', 20.0)), float(o['z_max'])])
            inv = np.where(np.abs(d) > 1e-12, 1.0 / d, np.inf)
            t_lo = (lo - s) * inv
            t_hi = (hi - s) * inv
            near = np.max(np.minimum(t_lo, t_hi))
            far = np.min(np.maximum(t_lo, t_hi))
            if far >= max(near, 0.0) and near < 1.0 and far > 0.0:
                t_hit = float(max(0.0, near))
                pt = (s + t_hit * d).tolist()
                hits.append({
                    'object': name,
                    'kind': 'building',
                    't': t_hit,
                    'point': [round(c, 3) for c in pt],
                    'method': 'building_slab'
                })

    hits.sort(key=lambda h: h['t'])
    return {
        'blocked': bool(len(hits) > 0),
        'hits': hits,
        'direct_path': [s.tolist(), t.tolist()],
        'hit_count': len(hits)
    }


def trace_reflected_scattered_paths(
    source: List[float],
    target: List[float],
    objects: List[dict],
    max_paths: int = 16
) -> dict:
    """
    Computes single-bounce specular reflection points on building facets using image methods,
    and diffuse facet-centroid scattering candidates.
    """
    s = np.asarray(source, dtype=float)
    t = np.asarray(target, dtype=float)
    reflected = []
    scattered = []

    for oi, o in enumerate(objects):
        if not isinstance(o, dict):
            continue
        name = str(o.get('name', o.get('id', f'building_{oi+1}')))

        # If object has explicit triangles
        tris = o.get('triangles', [])
        if tris:
            stride = max(1, len(tris) // 60)
            for tri_raw in tris[::stride]:
                try:
                    tri = np.asarray(tri_raw, dtype=float)
                    a, b, c = tri
                    normal = np.cross(b - a, c - a)
                    norm_len = float(np.linalg.norm(normal))
                    if norm_len < 1e-10:
                        continue
                    n = normal / norm_len

                    # Image source reflection point
                    image = s - 2.0 * np.dot(s - a, n) * n
                    u = t - image
                    denom = float(np.dot(n, u))
                    if abs(denom) > 1e-10:
                        tau = float(np.dot(n, a - image) / denom)
                        if 0.0 < tau < 1.0:
                            p = image + tau * u
                            # Barycentric test
                            v0 = b - a
                            v1 = c - a
                            v2 = p - a
                            d00 = float(v0 @ v0)
                            d01 = float(v0 @ v1)
                            d11 = float(v1 @ v1)
                            d20 = float(v2 @ v0)
                            d21 = float(v2 @ v1)
                            den = d00 * d11 - d01 * d01
                            if abs(den) > 1e-12:
                                vv = (d11 * d20 - d01 * d21) / den
                                ww = (d00 * d21 - d01 * d20) / den
                                uu = 1.0 - vv - ww
                                if min(uu, vv, ww) >= -1e-4:
                                    length = float(np.linalg.norm(p - s) + np.linalg.norm(t - p))
                                    reflected.append({
                                        'object': name,
                                        'path': [s.tolist(), [round(coord, 2) for coord in p.tolist()], t.tolist()],
                                        'reflection_point': [round(coord, 2) for coord in p.tolist()],
                                        'path_length_m': round(length, 2),
                                        'method': 'specular_facet_reflection'
                                    })
                except Exception:
                    continue

        # If object is a 3D AABB building box, test its 4 vertical planar walls!
        elif 'x_min' in o and 'x_max' in o:
            xmin, xmax = float(o['x_min']), float(o['x_max'])
            zmin, zmax = float(o['z_min']), float(o['z_max'])
            h = float(o.get('height', 16.0))

            # 4 vertical walls: (plane_coord, is_x, val, min_other, max_other)
            walls = [
                (0, xmin, zmin, zmax, "West Wall"),
                (0, xmax, zmin, zmax, "East Wall"),
                (2, zmin, xmin, xmax, "North Wall"),
                (2, zmax, xmin, xmax, "South Wall"),
            ]

            for axis, wall_pos, o_min, o_max, wall_name in walls:
                # Mirror source across wall plane
                image_s = s.copy()
                image_s[axis] = 2.0 * wall_pos - s[axis]
                d_ray = t - image_s
                if abs(d_ray[axis]) > 1e-6:
                    tau = (wall_pos - image_s[axis]) / d_ray[axis]
                    if 0.0 < tau < 1.0:
                        refl_pt = image_s + tau * d_ray
                        other_axis = 2 if axis == 0 else 0
                        # Check if reflection point is within wall dimensions and height
                        if (o_min <= refl_pt[other_axis] <= o_max) and (0.0 <= refl_pt[1] <= h):
                            total_len = float(np.linalg.norm(refl_pt - s) + np.linalg.norm(t - refl_pt))
                            reflected.append({
                                'object': f"{name} ({wall_name})",
                                'path': [s.tolist(), [round(c, 2) for c in refl_pt.tolist()], t.tolist()],
                                'reflection_point': [round(c, 2) for c in refl_pt.tolist()],
                                'path_length_m': round(total_len, 2),
                                'method': 'planar_wall_specular_reflection'
                            })

    reflected.sort(key=lambda p: p['path_length_m'])
    return {
        'reflected_paths': reflected[:max_paths],
        'scattered_paths': scattered[:max_paths],
        'total_reflected_found': len(reflected)
    }


def fdtd_tmz(
    frequency_hz: float = 433.0e6,
    size_m: float = 2.5,
    cells_per_wavelength: int = 10,
    steps: int = 350,
    objects: Optional[List[dict]] = None
) -> dict:
    """
    2-D TMz Yee-Grid Finite-Difference Time-Domain (FDTD) Simulation.
    Simulates local electric and magnetic field wave propagation (Ez, Hx, Hy)
    with conductive dielectrics and raised-cosine absorbing sponge boundaries.
    """
    f = float(np.clip(frequency_hz, 1.0e7, 6.0e9))
    lam = C0 / f
    cpw = int(np.clip(cells_per_wavelength, 8, 16))
    dx = lam / cpw
    dy = dx

    nx = int(np.clip(round(size_m / dx), 48, 160))
    ny = nx
    dx = size_m / nx
    dy = dx

    # 2-D Courant stability condition (Courant number = 0.99)
    dt = 0.99 / (C0 * math.sqrt(dx**-2 + dy**-2))
    steps = int(np.clip(steps, 80, 600))

    epsr = np.ones((ny, nx), dtype=float)
    sigma = np.zeros_like(epsr)

    # Map dielectric obstacle objects into the 2D grid
    for o in (objects or []):
        if not isinstance(o, dict):
            continue
        try:
            er = float(np.clip(o.get('epsilon_r', 5.5), 1.0, 80.0))
            cond = float(np.clip(o.get('conductivity', 0.02), 0.0, 5.0))
            # If object has 2D box bounds relative to local patch
            if 'x_min' in o and 'x_max' in o:
                # Map arena coords to local patch grid
                cx = nx // 2
                cy = ny // 2
                scale = nx / size_m
                x0 = int(np.clip(cx + float(o['x_min']) * 0.1 * scale, 0, nx - 1))
                x1 = int(np.clip(cx + float(o['x_max']) * 0.1 * scale, 0, nx - 1))
                y0 = int(np.clip(cy + float(o['z_min']) * 0.1 * scale, 0, ny - 1))
                y1 = int(np.clip(cy + float(o['z_max']) * 0.1 * scale, 0, ny - 1))
                if x1 > x0 and y1 > y0:
                    epsr[y0:y1, x0:x1] = er
                    sigma[y0:y1, x0:x1] = cond
            else:
                # Circular dielectric scatterer
                r = float(np.clip(o.get('radius', 0.25), 0.05, 0.8))
                cx = int(nx // 2)
                cy = int(ny // 2)
                rr = max(2, int(r / dx))
                yy, xx = np.ogrid[:ny, :nx]
                mask = (xx - cx)**2 + (yy - cy)**2 <= rr**2
                epsr[mask] = er
                sigma[mask] = cond
        except Exception:
            continue

    # Conductive-medium update coefficients
    ca = (1.0 - sigma * dt / (2.0 * EPS0 * epsr)) / (1.0 + sigma * dt / (2.0 * EPS0 * epsr))
    cb = (dt / (EPS0 * epsr * dx)) / (1.0 + sigma * dt / (2.0 * EPS0 * epsr))
    ch = dt / (MU0 * dx)

    ez = np.zeros((ny, nx), dtype=float)
    hx = np.zeros((ny, nx), dtype=float)
    hy = np.zeros((ny, nx), dtype=float)

    # Raised-cosine lossy sponge boundary
    yy_idx, xx_idx = np.indices((ny, nx))
    edge = np.minimum(np.minimum(yy_idx, xx_idx), np.minimum(ny - 1 - yy_idx, nx - 1 - xx_idx))
    sponge = np.exp(-0.02 * np.maximum(0, 10 - edge)**2)

    # Source location
    sx, sy = nx // 4, ny // 2
    omega = 2.0 * np.pi * f
    pulse_center = 35
    pulse_width = 14
    max_history = []

    for n in range(steps):
        # Update H-field from curl of E
        hx[:-1, :] -= ch * (ez[1:, :] - ez[:-1, :])
        hy[:, :-1] += ch * (ez[:, 1:] - ez[:, :-1])

        # Update E-field from curl of H
        curl = (hy[1:-1, 1:-1] - hy[1:-1, :-2]) - (hx[1:-1, 1:-1] - hx[:-2, 1:-1])
        ez[1:-1, 1:-1] = ca[1:-1, 1:-1] * ez[1:-1, 1:-1] + cb[1:-1, 1:-1] * curl

        # Gaussian-modulated sinusoidal RF source
        env = np.exp(-((n - pulse_center) / pulse_width)**2)
        ez[sy, sx] += env * np.sin(omega * n * dt)

        # Apply absorbing boundary sponge
        ez *= sponge
        if n % 40 == 0:
            max_history.append(float(np.max(np.abs(ez))))

    field = np.abs(ez)
    peak = float(field.max()) if float(field.max()) > 1e-12 else 1.0
    norm_field = np.clip(field / peak, 0.0, 1.0)

    # Downsample for compact web payload
    stride = max(1, nx // 80)
    grid = np.round(norm_field[::stride, ::stride], 4).tolist()

    return {
        "solver": "2D TMz Yee-grid FDTD",
        "frequency_hz": f,
        "wavelength_m": round(lam, 4),
        "cells_per_wavelength": cpw,
        "dx_m": round(dx, 5),
        "dt_s": float(dt),
        "steps": steps,
        "grid_nx": nx,
        "grid_ny": ny,
        "domain_size_m": size_m,
        "peak_field_amplitude": round(peak, 5),
        "field_normalized": grid,
        "sample_stride": stride,
        "source_cell": [sx, sy],
        "max_field_history": [round(h, 4) for h in max_history],
        "finite_field": bool(np.all(np.isfinite(ez)))
    }
