"""
FastAPI Server Entrypoint and Live WebSocket Simulation Service.
Runs the authoritative simulation loop and exposes HTTP/WebSocket endpoints for the digital twin.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.simulation.configuration import SystemConfiguration, DEFAULT_CONFIG
from backend.simulation.engine import SimulationEngine
from backend.api.schemas import ControlCommand, StatusResponse, ExperimentRunRequest, ExperimentRunResponse
from backend.api.websocket import ws_manager
from backend.experiments.scenarios import EXPERIMENT_PRESETS
from backend.experiments.runner import ExperimentRunner
from backend.rf.em_solver import fdtd_tmz, trace_geometry, trace_reflected_scattered_paths, compute_complex_impedance_and_fresnel
from backend.rf.em_solver_3d import fdtd_3d
from backend.simulation.multiradar import MultiRadarLocalization
from backend.api.export_excel import build_telemetry_excel
from backend.rf.materials import MATERIAL_DATABASE, ElectromagneticsEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EC261-Simulation-Server")

# Global master engine instance
engine = SimulationEngine()
sim_loop_task: asyncio.Task = None

async def simulation_background_loop():
    """
    Continuous background loop advancing simulation time when unpaused
    and broadcasting telemetry to connected frontend clients at ~20 Hz.
    """
    logger.info("Simulation background loop started.")
    diagnostics_counter = 0

    while True:
        try:
            if not engine.clock.is_paused or engine.clock.single_step_requested:
                stepped = engine.clock.tick()
                if stepped:
                    telem, diag = engine.step()
                    # Broadcast high-rate telemetry
                    await ws_manager.broadcast_json(telem)

                    # Broadcast detailed diagnostics at 4 Hz (every 5 steps)
                    diagnostics_counter += 1
                    if diagnostics_counter % 5 == 0:
                        await ws_manager.broadcast_json(diag)

            await asyncio.sleep(engine.clock.dt)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in simulation loop: {e}", exc_info=True)
            await asyncio.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager starting and stopping the background simulation loop."""
    global sim_loop_task
    sim_loop_task = asyncio.create_task(simulation_background_loop())
    yield
    if sim_loop_task:
        sim_loop_task.cancel()
        try:
            await sim_loop_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="EC261 — UAV Direction Finding Simulation Suite API",
    description="Academic Digital Twin API for Switched-Interferometric SDR Arrays",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "project": "EC261 — Direction Finding for UAV Telemetry",
        "institution": "IIIT Vadodara – International Campus Diu",
        "status": "RUNNING",
        "version": "2.0.0"
    }

@app.get("/api/status")
def get_status():
    """Returns current state of the simulation engine."""
    telem = engine.latest_telemetry
    if telem is None:
        telem, _ = engine.step()

    return {
        "sim_time": round(engine.clock.sim_time, 3),
        "frame_count": engine.clock.frame_count,
        "is_paused": engine.clock.is_paused,
        "speed_multiplier": engine.clock.speed_multiplier,
        "snr_db": engine.config.rf.nominal_snr_db,
        "receiver_mode": engine.config.sdr.receiver_mode,
        "active_trajectory": engine.uav.trajectory.name,
        "active_frequency_mhz": telem["rf"]["active_freq_mhz"],
        "true_azimuth_deg": telem["uav"]["true_azimuth_deg"],
        "accepted_track_deg": telem["dsp"]["accepted_track_deg"],
        "gate_status": telem["dsp"]["gate_status"]
    }

@app.post("/api/control")
def execute_control(cmd: ControlCommand):
    """Executes a simulation playback or parameter control action."""
    action = cmd.action
    if action == "PLAY":
        engine.clock.play()
    elif action == "PAUSE":
        engine.clock.pause()
    elif action == "STEP":
        engine.clock.step()
        telem, _ = engine.step()
    elif action == "RESET":
        engine.reset(new_seed=cmd.seed)
    elif action == "SET_SPEED" and cmd.speed_multiplier is not None:
        engine.clock.set_speed(cmd.speed_multiplier)
    elif action == "SET_SNR" and cmd.snr_db is not None:
        engine.set_snr(cmd.snr_db)
    elif action == "SET_TRAJECTORY" and cmd.trajectory is not None:
        engine.set_trajectory(cmd.trajectory)
    elif action == "SET_RECEIVER_MODE" and cmd.receiver_mode is not None:
        engine.set_receiver_mode(cmd.receiver_mode)
    elif action == "SET_TRACKER_TYPE" and cmd.tracker_type is not None:
        engine.config.dsp.tracker_type = cmd.tracker_type
        engine.tracker.tracker_type = cmd.tracker_type
    elif action == "SET_GATE_THRESHOLD" and cmd.gate_threshold is not None:
        engine.config.dsp.eigenvalue_gate_threshold = cmd.gate_threshold
        engine.gate.threshold = cmd.gate_threshold
    elif action == "SET_FOLIAGE_DENSITY" and cmd.foliage_density is not None:
        engine.set_foliage_density(cmd.foliage_density)
    elif action == "SET_ENVIRONMENT":
        bldgs_on = cmd.buildings_enabled if cmd.buildings_enabled is not None else (cmd.preset != "FOREST")
        engine.set_buildings_enabled(bldgs_on)
        if cmd.foliage_density is not None:
            engine.set_foliage_density(cmd.foliage_density)
        else:
            engine.set_foliage_density(0.85 if cmd.preset == "FOREST" else (0.45 if cmd.preset == "WOODLAND_URBAN" else 0.0))
    elif action == "SET_BUILDINGS_ENABLED" and cmd.buildings_enabled is not None:
        engine.set_buildings_enabled(cmd.buildings_enabled)

    return {"status": "SUCCESS", "action": action}

@app.get("/api/diagnostics")
def get_diagnostics():
    """Returns the most recent detailed signal analysis frame (IQ, FFT, MUSIC, EVD)."""
    if engine.latest_diagnostics is None:
        _, diag = engine.step()
        return diag
    return engine.latest_diagnostics

@app.get("/api/experiments/presets")
def get_experiment_presets():
    """Lists all available automated experiment presets."""
    return list(EXPERIMENT_PRESETS.values())

@app.get("/api/experiments/paper-benchmarks")
def get_paper_benchmarks():
    """
    Returns the comprehensive research paper benchmarks (IEEE Trans. publication dataset):
    - Fig 3: Manifold mismatch (frequency bias & aperture radius breakdown).
    - Fig 4: Multi-receiver DoA RMSE vs SNR & Frequency offset refinement error.
    - Fig 5: Multipath eigenvalue gate distribution & coherence sweep.
    - Fig 6: Bearing tracking & GDOP contour data.
    """
    import os
    benchmark_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "experiments",
        "data",
        "paper_benchmarks.json"
    )
    if not os.path.exists(benchmark_file):
        raise HTTPException(status_code=404, detail="Paper benchmark dataset not found.")
    
    with open(benchmark_file, "r") as f:
        data = json.load(f)
    return data

@app.post("/api/experiments/run")
def run_experiment(req: ExperimentRunRequest):
    """Executes a reproducible batch experiment preset."""
    # Resolve preset ID or full key
    resolved_key = None
    if req.preset_id in EXPERIMENT_PRESETS:
        resolved_key = req.preset_id
    else:
        for k, p in EXPERIMENT_PRESETS.items():
            if p.get("id") == req.preset_id or k.startswith(req.preset_id):
                resolved_key = k
                break

    if resolved_key is None:
        raise HTTPException(status_code=404, detail=f"Preset {req.preset_id} not found")

    try:
        report = ExperimentRunner.run_preset(resolved_key, seed=req.seed)
        return report
    except Exception as e:
        logger.error(f"Experiment execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/propagation-study")
def run_propagation_study(payload: Dict = None):
    """
    Executes bounded 2-D TMz Yee-grid FDTD simulation and physical ray-tracing.
    """
    data = payload or {}
    source = data.get("source", [0.0, 0.0, 0.0])
    target = data.get("target", list(engine.uav.position))
    objects = data.get("objects", [b.model_dump() for b in engine.config.buildings])

    trace = trace_geometry(source, target, objects)
    paths = trace_reflected_scattered_paths(source, target, objects)
    freq = float(data.get("frequency_hz", engine.transmitter.current_frequency))
    size_m = float(data.get("domain_size_m", 2.5))
    steps = int(data.get("steps", 250))

    fdtd = fdtd_tmz(frequency_hz=freq, size_m=size_m, steps=steps, objects=objects)
    return {
        "ok": True,
        "trace": trace,
        "paths": paths,
        "fdtd": fdtd
    }


@app.post("/api/propagation-study-3d")
def run_propagation_study_3d(payload: Dict = None):
    """
    Executes bounded true 3-D vector Maxwell Yee-grid FDTD simulation.
    """
    data = payload or {}
    freq = float(data.get("frequency_hz", engine.transmitter.current_frequency))
    size_m = float(data.get("domain_size_m", 0.45))
    steps = int(data.get("steps", 60))

    fdtd3d = fdtd_3d(frequency_hz=freq, size_m=size_m, steps=steps)
    return {
        "ok": True,
        "fdtd3d": fdtd3d
    }


@app.post("/api/multiradar")
def run_multiradar(payload: Dict = None):
    """
    Multi-radar direction finding and position triangulation.
    """
    data = payload or {}
    uav_pos = engine.uav.position

    radars = data.get("radars")
    if not radars:
        # Default 3 distributed tactical DF stations
        stations_xy = [
            (0.0, 0.0, "Ground Station Central (Array 0)"),
            (-35.0, 25.0, "Tactical DF Outpost West (Array 1)"),
            (35.0, 25.0, "Tactical DF Outpost East (Array 2)")
        ]
        radars = []
        for i, (sx, sz, sname) in enumerate(stations_xy):
            dx = uav_pos[0] - sx
            dz = uav_pos[2] - sz
            az_true = float(np.degrees(np.arctan2(dz, dx)))
            # Add synthetic estimation noise
            az_meas = az_true + float(np.random.normal(0.0, 1.2))
            radars.append({
                "id": i + 1,
                "name": sname,
                "x": sx,
                "z": sz,
                "azimuth_deg": round(az_meas, 2),
                "sigma_deg": 1.5
            })

    result = MultiRadarLocalization.solve_position_from_bearings(
        radar_stations=radars,
        drone_true_pos=uav_pos
    )
    result["drone_true_pos"] = [round(c, 2) for c in uav_pos]
    return {"ok": True, "triangulation": result}


@app.get("/api/export.xlsx")
@app.post("/api/export.xlsx")
def export_telemetry_excel(payload: Dict = None):
    """
    Generates and downloads a styled Excel workbook of simulation telemetry history.
    """
    rows = []
    if payload and "rows" in payload and isinstance(payload["rows"], list):
        rows = payload["rows"]
    elif engine.telemetry_history:
        rows = engine.telemetry_history
    else:
        # If no history yet, generate a frame
        telem, _ = engine.step()
        rows = [telem]

    excel_stream = build_telemetry_excel(rows)
    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=ec261_uav_telemetry.xlsx"
        }
    )


@app.get("/api/materials")
def get_materials_catalog():
    """Returns the electromagnetic materials library with RF constitutive parameters."""
    catalog = {}
    for mat_id, mat in MATERIAL_DATABASE.items():
        catalog[mat_id] = {
            "name": mat.name,
            "epsilon_r": mat.epsilon_r,
            "conductivity_s_m": mat.conductivity_s_m,
            "mu_r": mat.mu_r,
            "tan_delta_e": mat.tan_delta_e,
            "moisture_pct": mat.moisture_pct,
            "rf_915mhz": ElectromagneticsEngine.propagation_parameters(mat, 915e6)
        }
    return catalog


@app.post("/api/multiradar/station")
def toggle_radar_station(payload: Dict):
    """Activates or deactivates a specific distributed radar station."""
    station_id = int(payload.get("station_id", 1))
    active = bool(payload.get("active", True))
    engine.set_station_active(station_id, active)
    return {"ok": True, "station_id": station_id, "active": active}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming and interactive control.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial telemetry snapshot on connection
        if engine.latest_telemetry is not None:
            await websocket.send_json(engine.latest_telemetry)
        if engine.latest_diagnostics is not None:
            await websocket.send_json(engine.latest_diagnostics)

        while True:
            # Receive inbound commands from frontend
            msg_text = await websocket.receive_text()
            try:
                data = json.loads(msg_text)
                cmd = ControlCommand(**data)
                execute_control(cmd)
            except Exception as e:
                logger.warning(f"Invalid WebSocket command received: {e}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket client error: {e}")
        ws_manager.disconnect(websocket)

