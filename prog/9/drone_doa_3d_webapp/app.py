from flask import Flask, jsonify, request, render_template, send_file
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Alignment
import numpy as np
import threading
from em_solver import fdtd_tmz, trace_geometry, trace_reflected_scattered_paths
from em_solver_3d import fdtd_3d
from doa_sim import (
    Systems, simulate_switched, simulate_uca, est_strongest, est_centroid,
    AngleTracker, TrackerConfig, wrap180, db
)

app = Flask(__name__)
_lock = threading.Lock()
_multi_tracks = {}  # per-radar circularly smoothed bearing tracks
_rng = np.random.default_rng(20261011)
_tracker = None
_last_n = None
_last_samples = None
_systems_cache = {}

# Reference presets for the educational RF-material model. Values are representative
# starting points near 2.4 GHz, not universal constants or laboratory measurements.
MATERIAL_FREQUENCY_HZ = 2.4e9
EPSILON_0 = 8.8541878128e-12
GROUND_MATERIALS = {
    'soil_dry':  {'label': 'Dry soil',     'epsilon_r': 4.5,  'conductivity_s_m': 0.002, 'mu_r': 1.001, 'tan_delta_e': 0.025, 'tan_delta_m': 0.00005, 'moisture_pct': 4.0},
    'soil_moist':{'label': 'Moist soil',   'epsilon_r': 14.0, 'conductivity_s_m': 0.025, 'mu_r': 1.005, 'tan_delta_e': 0.055, 'tan_delta_m': 0.00010, 'moisture_pct': 18.0},
    'rocky':     {'label': 'Rocky ground', 'epsilon_r': 7.0,  'conductivity_s_m': 0.008, 'mu_r': 1.015, 'tan_delta_e': 0.035, 'tan_delta_m': 0.00100, 'moisture_pct': 6.0},
    'soil_wet':  {'label': 'Wet soil',     'epsilon_r': 24.0, 'conductivity_s_m': 0.15,  'mu_r': 1.020, 'tan_delta_e': 0.12,  'tan_delta_m': 0.00150, 'moisture_pct': 32.0},
}


def _safe_material(raw):
    """Validate material properties arriving from the local browser."""
    raw = raw if isinstance(raw, dict) else {}
    def bounded(key, default, low, high):
        try:
            value = float(raw.get(key, default))
        except (TypeError, ValueError):
            value = float(default)
        if not np.isfinite(value):
            value = float(default)
        return float(np.clip(value, low, high))
    return {
        'label': str(raw.get('label', raw.get('name', 'Unknown object')))[:100],
        'epsilon_r': bounded('epsilon_r', 5.0, 1.0, 100.0),
        'conductivity_s_m': bounded('conductivity_s_m', 0.005, 0.0, 20.0),
        'mu_r': bounded('mu_r', 1.0, 0.9, 5.0),
        'tan_delta_e': bounded('tan_delta_e', 0.03, 0.0, 5.0),
        'tan_delta_m': bounded('tan_delta_m', 0.0001, 0.0, 5.0),
        'moisture_pct': bounded('moisture_pct', 10.0, 0.0, 100.0),
    }


def _reflection_magnitude(material):
    """Magnitude of a normal-incidence air/material Fresnel reflection estimate.

    The complex permittivity includes both the entered intrinsic dielectric loss and
    conductive loss. This is a compact approximation, not a full boundary solver.
    """
    m = _safe_material(material)
    omega = 2.0 * np.pi * MATERIAL_FREQUENCY_HZ
    eps_complex = complex(m['epsilon_r'], -(m['epsilon_r'] * m['tan_delta_e'] + m['conductivity_s_m'] / (omega * EPSILON_0)))
    mu_complex = complex(m['mu_r'], -m['mu_r'] * m['tan_delta_m'])
    impedance_ratio = np.sqrt(mu_complex / eps_complex)
    gamma = (impedance_ratio - 1.0) / (impedance_ratio + 1.0)
    return float(np.clip(abs(gamma), 0.0, 0.99))


def _object_path_weight(obj, start_xz, end_xz, drone_y):
    """Return a soft proximity weight for a 3D scene object near the X/Z path."""
    try:
        x, z = float(obj.get('x', 0.0)), float(obj.get('z', 0.0))
    except (TypeError, ValueError):
        return 0.0
    sx, sz = start_xz; ex, ez = end_xz
    vx, vz = ex - sx, ez - sz
    denom = vx * vx + vz * vz
    t = 0.0 if denom <= 1e-9 else float(np.clip(((x - sx) * vx + (z - sz) * vz) / denom, 0.0, 1.0))
    if t <= 0.02 or t >= 0.98:
        return 0.0
    px, pz = sx + t * vx, sz + t * vz
    horizontal_distance = float(np.hypot(x - px, z - pz))
    kind = str(obj.get('kind', 'unknown')).lower()
    try:
        influence = float(np.clip(float(obj.get('influence_radius', obj.get('radius', 2.0) + 4.0)), 0.5, 12.0))
    except (TypeError, ValueError):
        influence = 6.0
    if horizontal_distance >= influence:
        return 0.0
    # Objects farther from the direct path contribute less scattering.
    weight = (1.0 - horizontal_distance / influence) ** 1.35
    if kind == 'tree':
        try: height = float(np.clip(float(obj.get('height', 6.0)), 1.0, 30.0))
        except (TypeError, ValueError): height = 6.0
        path_height = 5.7 + t * (float(drone_y) - 5.7)
        # Trees above/beside the direct ray still contribute some foliage scattering.
        vertical_weight = 0.22 + 0.78 * float(np.clip((height + 1.5 - path_height) / 2.8, 0.0, 1.0))
        weight *= vertical_weight
    elif kind in ('rock', 'stone'):
        weight *= 0.65
    elif kind in ('water', 'puddle'):
        weight *= 0.8
    return float(np.clip(weight, 0.0, 1.0))


def material_path_effects(scene_materials, ground_material, rng, radar_x=0.0, radar_z=0.0, drone_x=40.0, drone_z=0.0, drone_y=17.0):
    """Calculate illustrative, property-dependent ground and nearby-object RF effects."""
    ground_key = str(ground_material or 'soil_dry').lower()
    ground = dict(GROUND_MATERIALS.get(ground_key, GROUND_MATERIALS['soil_dry']))
    ground['key'] = ground_key if ground_key in GROUND_MATERIALS else 'soil_dry'
    ground['reflection_magnitude'] = _reflection_magnitude(ground)
    gamma = ground['reflection_magnitude']
    # Effective ground loss is a teaching heuristic informed by complex impedance,
    # conduction and magnetic loss. Random spread represents unmodelled roughness.
    ground_loss_db = float(rng.uniform(0.65, 1.25) + 2.0 * gamma + 0.55 * np.log10(1.0 + ground['conductivity_s_m'] * 100.0) + 1.2 * max(0.0, ground['mu_r'] - 1.0))
    ground_sigma_deg = float(1.4 + 5.0 * gamma + 0.8 * np.log10(1.0 + ground['conductivity_s_m'] * 100.0) + 7.0 * max(0.0, ground['mu_r'] - 1.0) + 0.5 * ground['tan_delta_m'])

    safe_objects = []
    for obj in (scene_materials if isinstance(scene_materials, list) else [])[:100]:
        if not isinstance(obj, dict):
            continue
        material = _safe_material(obj.get('material', obj))
        kind = str(obj.get('kind', 'unknown')).lower()
        weight = _object_path_weight(obj, (float(radar_x), float(radar_z)), (float(drone_x), float(drone_z)), float(drone_y))
        if weight <= 0.01:
            continue
        reflectivity = _reflection_magnitude(material)
        eps = material['epsilon_r']; sigma = material['conductivity_s_m']; mu = material['mu_r']
        # Small per-object terms preserve sensitivity to each object's own εr, σ, μr
        # and losses without pretending a mesh is a calibrated full-wave scatterer.
        if kind == 'tree':
            raw_loss = 0.025 + 0.012 * np.sqrt(max(eps - 1.0, 0.0)) + 0.28 * material['tan_delta_e'] + 1.3 * sigma + 1.2 * max(0.0, mu - 1.0) + 0.03 * material['tan_delta_m']
        elif kind in ('water', 'puddle'):
            raw_loss = 0.025 + 0.010 * np.sqrt(max(eps - 1.0, 0.0)) + 0.22 * material['tan_delta_e'] + 0.55 * sigma
        else:
            raw_loss = 0.015 + 0.008 * np.sqrt(max(eps - 1.0, 0.0)) + 0.16 * material['tan_delta_e'] + 0.75 * sigma + 0.65 * max(0.0, mu - 1.0) + 0.02 * material['tan_delta_m']
        contribution = float(weight * np.clip(raw_loss, 0.0, 0.8))
        safe_objects.append({
            'id': str(obj.get('id', material['label']))[:100],
            'kind': kind, 'label': material['label'], 'weight': float(weight),
            'epsilon_r': eps, 'conductivity_s_m': sigma, 'mu_r': mu,
            'tan_delta_e': material['tan_delta_e'], 'tan_delta_m': material['tan_delta_m'],
            'moisture_pct': material['moisture_pct'], 'reflection_magnitude': reflectivity,
            'loss_contribution_db': contribution,
        })
    object_loss_db = float(min(4.0, sum(q['loss_contribution_db'] for q in safe_objects)))
    object_sigma_deg = float(np.sqrt(sum((0.45 + 1.8 * q['reflection_magnitude'] + 1.5 * q['tan_delta_e'] + 3.0 * abs(q['mu_r'] - 1.0)) ** 2 * q['weight'] for q in safe_objects)))
    return {
        'reference_frequency_mhz': MATERIAL_FREQUENCY_HZ / 1e6,
        'ground': ground, 'ground_loss_db': ground_loss_db,
        'ground_multipath_sigma_deg': ground_sigma_deg,
        'objects': safe_objects, 'object_count': len(safe_objects),
        'object_material_loss_db': object_loss_db,
        'object_multipath_sigma_deg': object_sigma_deg,
    }


def propagation_effects(environment, distance, rng, ground_material='soil_dry', scene_materials=None, radar_x=0.0, radar_z=0.0, drone_x=40.0, drone_z=0.0, drone_y=17.0):
    """Synthetic vegetation + heterogeneous material effects; not a calibrated EM solver."""
    env = str(environment or 'open').lower()
    ground = str(ground_material or 'soil_dry').lower()
    distance = max(0.0, float(distance))
    if env == 'light':
        attenuation = 0.04 * distance + float(rng.uniform(0.5, 3.0)); multipath_sigma = 3.0
    elif env == 'forest':
        attenuation = 0.13 * distance + float(rng.uniform(4.0, 14.0)); multipath_sigma = 12.0
    else:
        env = 'open'; attenuation = 0.0; multipath_sigma = 0.0
    details = material_path_effects(scene_materials, ground, rng, radar_x, radar_z, drone_x, drone_z, drone_y)
    attenuation += details['ground_loss_db'] + details['object_material_loss_db']
    sigma_total = float(np.sqrt(multipath_sigma**2 + details['ground_multipath_sigma_deg']**2 + details['object_multipath_sigma_deg']**2))
    # Complex material impedance changes reflection strength; residual angular bias is stochastic.
    angular_bias = float(rng.normal(0.0, sigma_total))
    return env, float(attenuation), angular_bias, ground, details


def reset_tracker(dt=0.45):
    global _tracker
    _tracker = AngleTracker(TrackerConfig(dt=float(np.clip(dt, 0.02, 2.0))))

reset_tracker()

@app.get('/')
def home():
    response = app.make_response(render_template('index.html'))
    # Prevent browsers from showing an older cached control panel.
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.get('/api/status')
def status():
    return jsonify({'ok': True, 'service': 'Drone DoA Lab Python backend'})

@app.post('/api/propagation-study')
def propagation_study():
    """Run bounded 2-D TMz FDTD and geometric line-of-sight tests."""
    data = request.get_json(silent=True) or {}
    try:
        source = data.get('source', [0.0, 0.0, 0.0])
        target = data.get('target', [1.0, 0.0, 0.0])
        objects = data.get('objects', [])
        if not isinstance(objects, list): objects = []
        objects = objects[:100]
        trace = trace_geometry(source, target, objects)
        path_candidates = trace_reflected_scattered_paths(source, target, objects)
        size_m = float(np.clip(float(data.get('domain_size_m', 1.5)), 0.8, 3.0))
        # Center the local FDTD patch on the source-target midpoint; object offsets are local X/Z.
        try:
            mx = (float(source[0]) + float(target[0])) / 2.0; mz = (float(source[2]) + float(target[2])) / 2.0
            fdtd_objects = [dict(o, x=float(o.get('x', 0.0))-mx, z=float(o.get('z', 0.0))-mz) for o in objects if isinstance(o, dict) and abs(float(o.get('x', 0.0))-mx) <= size_m/2 and abs(float(o.get('z', 0.0))-mz) <= size_m/2]
        except (TypeError, ValueError, IndexError): fdtd_objects = objects
        frequency = float(np.clip(float(data.get('frequency_hz', 2.4e9)), 1e8, 6e9))
        steps = int(np.clip(int(data.get('steps', 450)), 100, 900))
        field = fdtd_tmz(frequency, size_m, int(data.get('cells_per_wavelength', 10)), steps, fdtd_objects)
        return jsonify({'ok': True, 'trace': trace, 'paths': path_candidates, 'fdtd': field,
                        'validation': {'finite_field': bool(np.all(np.isfinite(np.asarray(field['field_normalized'])))),
                                       'grid_dimensions': [field['grid_nx'], field['grid_ny']],
                                       'courant_factor': 0.99,
                                       'notes': ['2D TMz only; no full 3D Maxwell claim.', 'Boundary uses lossy sponge, not CPML.', 'Scene geometry is represented by proxies unless triangle facets are supplied.', 'Local patch is wavelength-resolved; it is not the full 45 m scene.']}})
    except Exception as exc:
        app.logger.exception('Propagation study failed')
        return jsonify({'ok': False, 'error': str(exc)}), 400

@app.post('/api/propagation-study-3d')
def propagation_study_3d():
    """Run a bounded true 3-D vector Maxwell FDTD study plus existing 3-D geometry trace."""
    data = request.get_json(silent=True) or {}
    try:
        source = data.get('source', [0.0, 0.0, 0.0])
        target = data.get('target', [0.3, 0.0, 0.0])
        objects = data.get('objects', [])
        if not isinstance(objects, list): objects = []
        trace = trace_geometry(source, target, objects[:100])
        paths = trace_reflected_scattered_paths(source, target, objects[:100])
        frequency = float(np.clip(float(data.get('frequency_hz', 2.4e9)), 1e8, 6e9))
        size_m = float(np.clip(float(data.get('domain_size_m', 0.30)), 0.08, 1.0))
        steps = int(np.clip(int(data.get('steps', 80)), 20, 160))
        field = fdtd_3d(frequency_hz=frequency, size_m=size_m, steps=steps)
        return jsonify({'ok': True, 'trace': trace, 'paths': paths, 'fdtd3d': field,
          'validation': {'finite_field': field['finite_field'], 'courant_number': field['courant_number'],
            'grid_dimensions': field['dimensions'], 'courant_limit_pass': field['courant_number'] <= 1.0,
            'notes': field['notes']}})
    except Exception as exc:
        app.logger.exception('3D propagation study failed')
        return jsonify({'ok': False, 'error': str(exc)}), 400

@app.post('/api/reset')
def reset():
    data = request.get_json(silent=True) or {}
    reset_tracker(data.get('dt', 0.45))
    with _lock:
        _multi_tracks.clear()
    return jsonify({'ok': True})

@app.post('/api/multiradar')
def multiradar():
    """Independent synthetic DoA readings from each radar plus bearing-line least squares."""
    global _rng
    data = request.get_json(force=True)
    method = 'pv'
    drone_x = float(data.get('drone_x', 39.0))
    drone_z = float(data.get('drone_z', -22.0))
    n = int(np.clip(int(data.get('n', 6)), 4, 12))
    snr = float(np.clip(float(data.get('snr', 12)), -20, 40))
    samples = int(np.clip(int(data.get('samples', 64)), 8, 2048))
    k_db = float(np.clip(float(data.get('rician_k', 8)), -20, 40))
    interference = bool(data.get('interference', False))
    environment = str(data.get('environment', 'open'))
    ground_material = str(data.get('ground_material', 'soil_dry'))
    scene_materials_by_radar = data.get('scene_materials_by_radar', {})
    drone_y = float(np.clip(float(data.get('drone_y', 17.0)), 0.0, 500.0))
    sir = float(np.clip(float(data.get('sir', 0)), -30, 30))
    radars = data.get('radars', [])
    if not isinstance(radars, list) or len(radars) < 1:
        return jsonify({'error': 'At least one radar position is required'}), 400
    radars = radars[:6]
    readings = []
    bearing_lines = []
    with _lock:
        cache_key = (n, samples)
        systems = _systems_cache.get(cache_key)
        if systems is None:
            systems = Systems(n=n, L=samples, K=n * samples)
            _systems_cache[cache_key] = systems
        for item in radars:
            rx = float(item.get('x', 0.0)); rz = float(item.get('z', 0.0))
            rid = int(item.get('id', len(readings) + 1))
            dx, dz = drone_x - rx, drone_z - rz
            distance = max(0.1, float(np.hypot(dx, dz)))
            az = float(np.degrees(np.arctan2(dx, dz)) % 360.0)
            # Each radar gets a path-specific vegetation loss and multipath bias.
            path_objects = scene_materials_by_radar.get(str(rid), []) if isinstance(scene_materials_by_radar, dict) else []
            env_name, vegetation_loss_db, multipath_bias_deg, ground_material, material_details = propagation_effects(
                environment, distance, _rng, ground_material, path_objects, rx, rz, drone_x, drone_z, drone_y)
            effective_snr = float(np.clip(snr - 20.0 * np.log10(distance / 45.0) - vegetation_loss_db, -20, 40))
            apparent_az = (az + multipath_bias_deg) % 360.0
            theta = np.array([apparent_az], dtype=float)
            snr_arr = np.array([effective_snr], dtype=float)
            int_kwargs = {}
            if interference:
                int_kwargs = {'int_theta': np.array([(az + 73.0) % 360]), 'sir_db': np.array([sir])}
            sigma = 12.0
            beam_powers = None
            beam_angles = None
            if method in ('strongest', 'centroid', 'pv'):
                powers, _ = simulate_switched(systems.arr, theta, snr_arr, _rng, L=samples, k_db=k_db, **int_kwargs)
                beam_powers = np.asarray(powers[0], dtype=float).tolist()
                beam_angles = np.asarray(systems.arr.boresights, dtype=float).tolist()
                if method == 'strongest':
                    est = float(est_strongest(powers, systems.arr)[0]); sigma = 360.0 / n / np.sqrt(12.0)
                elif method == 'centroid':
                    est = float(est_centroid(powers, systems.arr)[0]); sigma = 360.0 / n / 3.0
                else:
                    result = systems.pv.estimate(powers, samples)
                    est = float(result['theta'][0]); sigma = float(result['sigma'][0])
            elif method in ('music', 'esprit'):
                x = simulate_uca(systems.uca, theta, snr_arr, _rng, systems.K, **int_kwargs)
                if method == 'music':
                    result = systems.music.estimate(x); est = float(result['theta'][0]); sigma = float(result['sigma'][0])
                else:
                    est = float(systems.esprit.estimate(x)[0]); sigma = max(2.0, 180.0 / n)
            else:
                return jsonify({'error': f'Unknown method: {method}'}), 400
            # Keep an independent circular EMA track for every radar ID. This avoids
            # angle-wrap problems (e.g. smoothing 359° and 1° toward 180°).
            previous_track = _multi_tracks.get(rid)
            if previous_track is None:
                tracked = est % 360.0
            else:
                tracked = (previous_track + 0.28 * float(wrap180(est - previous_track))) % 360.0
            _multi_tracks[rid] = tracked
            # An omnidirectional transmitter reaches each site; this simplified link-budget model
            # uses a material-aware illustrative loss term, not a calibrated field link budget.
            received_power_db = 30.0 - 20.0 * np.log10(distance) - vegetation_loss_db
            received = effective_snr > -18.0
            readings.append({'id': rid, 'x': rx, 'z': rz, 'range_m': distance,
                             'true_azimuth': az, 'estimate': est, 'tracked': float(tracked), 'error_deg': float(wrap180(est-az)),
                             'environment': env_name, 'vegetation_loss_db': vegetation_loss_db, 'multipath_bias_deg': multipath_bias_deg,
                             'sigma_deg': float(sigma), 'received_power_db': float(received_power_db),
                             'received': bool(received), 'effective_snr_db': effective_snr,
                             'beam_powers': beam_powers, 'beam_angles': beam_angles,
                             'material_effects': material_details})
            if received:
                a = np.radians(est)
                direction = np.array([np.sin(a), np.cos(a)])
                origin = np.array([rx, rz])
                # Projector perpendicular to a bearing line.
                projector = np.eye(2) - np.outer(direction, direction)
                weight = 1.0 / max(sigma, 2.0) ** 2
                bearing_lines.append((projector, origin, weight))
    estimated_x = estimated_z = None
    valid = False
    if len(bearing_lines) >= 2:
        matrix = sum((projector * weight for projector, _, weight in bearing_lines), np.zeros((2, 2)))
        vector = sum((projector @ origin * weight for projector, origin, weight in bearing_lines), np.zeros(2))
        if np.linalg.det(matrix) > 1e-8 and np.linalg.cond(matrix) < 1e6:
            estimate_xy = np.linalg.solve(matrix, vector)
            estimated_x, estimated_z = float(estimate_xy[0]), float(estimate_xy[1])
            valid = bool(np.isfinite(estimated_x) and np.isfinite(estimated_z))
    return jsonify({'ok': True, 'readings': readings, 'estimated_x': estimated_x,
                    'estimated_z': estimated_z, 'valid': valid,
                    'received_count': sum(1 for q in readings if q['received']),
                    'method': method, 'environment': environment, 'truth_x': drone_x, 'truth_z': drone_z})


@app.post('/api/export.xlsx')
def export_xlsx():
    """Build an Excel workbook containing one row per active radar measurement."""
    data = request.get_json(silent=True) or {}
    rows = data.get('rows', [])
    if not isinstance(rows, list) or not rows:
        return jsonify({'error': 'No measurement rows to export'}), 400
    columns = [
        ('time', 'Timestamp'), ('radar_id', 'Radar ID'),
        ('radar_x_m', 'Radar X (m)'), ('radar_z_m', 'Radar Z (m)'),
        ('drone_x_m', 'Drone X (m)'), ('drone_y_m', 'Drone Y / altitude (m)'),
        ('drone_z_m', 'Drone Z (m)'), ('true_azimuth_deg', 'True azimuth (deg)'),
        ('raw_estimate_deg', 'Raw DoA estimate (deg)'), ('raw_angle_error_deg', 'Raw angle error (deg)'),
        ('tracked_bearing_deg', 'Tracked bearing (deg)'), ('tracked_angle_error_deg', 'Tracked angle error (deg)'),
        ('range_m', 'Range (m)'), ('received_power_db', 'Received power (dB)'),
        ('effective_snr_db', 'Effective SNR (dB)'), ('propagation_environment', 'Propagation environment'),
        ('vegetation_loss_db', 'Total illustrative propagation loss (dB)'), ('multipath_bias_deg', 'Simulated multipath bias (deg)'),
        ('material_reference_frequency_mhz', 'Material model reference frequency (MHz)'),
        ('ground_relative_permittivity', 'Ground relative permittivity εr'),
        ('ground_conductivity_s_m', 'Ground conductivity (S/m)'),
        ('ground_relative_permeability', 'Ground relative permeability μr'),
        ('objects_on_path', 'Nearby material objects on path'),
        ('object_material_loss_db', 'Nearby object material loss (dB)'),
        ('estimated_drone_x_m', 'Estimated drone X (m)'),
        ('estimated_drone_z_m', 'Estimated drone Z (m)'), ('horizontal_position_error_m', 'Horizontal position error (m)'),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = 'Radar Measurements'
    ws.append([label for _, label in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='17324D')
        cell.alignment = Alignment(horizontal='center')
    # Explicit column whitelist excludes track_state, received, location_solution_valid,
    # method, samples, and interference as requested.
    for row in rows[-30000:]:
        if isinstance(row, dict):
            ws.append([row.get(key) for key, _ in columns])
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    widths = [26, 12, 13, 13, 13, 20, 13, 20, 22, 21, 21, 22, 13, 20, 17, 30, 18, 23, 23, 20, 22, 20, 18, 24, 21, 21, 27]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='drone_doa_measurements.xlsx')


@app.post('/api/estimate')
def estimate():
    global _rng, _tracker, _last_n, _last_samples
    data = request.get_json(force=True)
    method = 'pv'
    az = float(data.get('azimuth', 120.0)) % 360.0
    elevation = float(data.get('elevation', 18.0))
    distance = max(1.0, float(data.get('range', 45.0)))
    n = int(np.clip(int(data.get('n', 6)), 4, 12))
    snr = float(np.clip(float(data.get('snr', 12)), -20, 40))
    samples = int(np.clip(int(data.get('samples', 64)), 8, 2048))
    k_db = float(np.clip(float(data.get('rician_k', 8)), -20, 40))
    interference = bool(data.get('interference', False))
    environment = str(data.get('environment', 'open'))
    ground_material = str(data.get('ground_material', 'soil_dry'))
    scene_materials = data.get('scene_materials', [])
    radar_x = float(np.clip(float(data.get('radar_x', 0.0)), -10000.0, 10000.0))
    radar_z = float(np.clip(float(data.get('radar_z', 0.0)), -10000.0, 10000.0))
    drone_x = float(np.clip(float(data.get('drone_x', radar_x + distance * np.sin(np.radians(az)))), -10000.0, 10000.0))
    drone_z = float(np.clip(float(data.get('drone_z', radar_z + distance * np.cos(np.radians(az)))), -10000.0, 10000.0))
    drone_y = float(np.clip(float(data.get('drone_y', 17.0)), 0.0, 500.0))
    env_name, vegetation_loss_db, multipath_bias_deg, ground_material, material_details = propagation_effects(
        environment, distance, _rng, ground_material, scene_materials, radar_x, radar_z, drone_x, drone_z, drone_y)
    effective_snr = float(np.clip(snr - 20.0 * np.log10(distance / 45.0) - vegetation_loss_db, -20, 40))
    sir = float(np.clip(float(data.get('sir', 0)), -30, 30))
    dt = float(np.clip(float(data.get('dt', 0.45)), 0.02, 2.0))
    with _lock:
        if _tracker is None or n != _last_n or samples != _last_samples:
            reset_tracker(dt)
            _last_n, _last_samples = n, samples
        cache_key = (n, samples)
        systems = _systems_cache.get(cache_key)
        if systems is None:
            systems = Systems(n=n, L=samples, K=n * samples)
            _systems_cache[cache_key] = systems
        theta = np.array([(az + multipath_bias_deg) % 360.0], dtype=float)
        snr_arr = np.array([effective_snr], dtype=float)
        int_kwargs = {}
        if interference:
            int_kwargs = {'int_theta': np.array([(az + 73.0) % 360]), 'sir_db': np.array([sir])}
        beam_powers = None
        beam_angles = None
        sigma = None
        fit_deviance = None
        snr_est_db = None
        if method in ('strongest', 'centroid', 'pv'):
            p, _ = simulate_switched(systems.arr, theta, snr_arr, _rng, L=samples,
                                     k_db=k_db, **int_kwargs)
            beam_powers = p[0].tolist()
            beam_angles = systems.arr.boresights.tolist()
            if method == 'strongest':
                est = float(est_strongest(p, systems.arr)[0])
                sigma = 360.0 / n / np.sqrt(12.0)
                snr_est_db = snr
            elif method == 'centroid':
                est = float(est_centroid(p, systems.arr)[0])
                sigma = 360.0 / n / 3.0
                snr_est_db = snr
            else:
                result = systems.pv.estimate(p, samples)
                est = float(result['theta'][0])
                sigma = float(result['sigma'][0])
                fit_deviance = float(result['red_dev'][0])
                snr_est_db = float(result['snr_db'][0])
        elif method in ('music', 'esprit'):
            x = simulate_uca(systems.uca, theta, snr_arr, _rng, systems.K, **int_kwargs)
            if method == 'music':
                result = systems.music.estimate(x)
                est = float(result['theta'][0])
                sigma = float(result['sigma'][0])
                snr_est_db = float(result['snr_db'][0])
            else:
                est = float(systems.esprit.estimate(x)[0])
                sigma = max(2.0, 180.0 / max(n, 1))
                snr_est_db = snr
        else:
            return jsonify({'error': f'Unknown method: {method}'}), 400
        error = float(wrap180(est - az))
        tracked, omega, post_sigma, track_status, confidence = _tracker.step(est, float(sigma or 10.0))
        status_names = {0: 'COAST', 1: 'ACCEPT', 2: 'REJECT', 3: 'REACQ'}
        gain = float(10.0 * np.log10(max(float(systems.arr.g0), 1e-12)))
        # Approximate range loss for the interface's SNR display. The core estimator still receives
        # the user-controlled SNR, so this does not claim a calibrated propagation channel.
        range_snr = effective_snr
        return jsonify({
            'ok': True, 'method': method, 'true_azimuth': az, 'estimate': est,
            'error': error, 'tracked': float(tracked), 'tracked_error': float(wrap180(tracked-az)),
            'omega': float(omega), 'sigma': float(sigma), 'confidence': float(confidence),
            'track_state': status_names.get(int(track_status), 'UNKNOWN'),
            'snr_db': float(range_snr), 'snr_est_db': None if snr_est_db is None else float(snr_est_db),
            'antenna_gain_dbi': gain, 'beamwidth_deg': float(systems.arr.bw_deg),
            'fit_deviance': fit_deviance, 'beam_powers': beam_powers, 'beam_angles': beam_angles,
            'range_m': distance, 'elevation_deg': elevation, 'interference': interference,
            'environment': env_name, 'vegetation_loss_db': float(vegetation_loss_db), 'multipath_bias_deg': float(multipath_bias_deg),
            'material_effects': material_details,
            'n': n, 'samples': samples
        })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
