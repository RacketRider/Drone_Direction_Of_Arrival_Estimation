"""
Integration Tests for FastAPI Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "sim_time" in data
    assert "receiver_mode" in data

def test_api_control():
    # Play
    r_play = client.post("/api/control", json={"action": "PLAY"})
    assert r_play.status_code == 200
    
    # Step
    r_step = client.post("/api/control", json={"action": "STEP"})
    assert r_step.status_code == 200
    
    # Set SNR
    r_snr = client.post("/api/control", json={"action": "SET_SNR", "snr_db": 25.0})
    assert r_snr.status_code == 200
    
    # Pause
    r_pause = client.post("/api/control", json={"action": "PAUSE"})
    assert r_pause.status_code == 200

def test_api_diagnostics():
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "signal_diagnostics"
    assert "fft_spectrum" in data
    assert "music_spectrum" in data

def test_api_experiment_presets():
    response = client.get("/api/experiments/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 11

def test_api_paper_benchmarks():
    response = client.get("/api/experiments/paper-benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert "figure3_manifold_bias" in data
    assert "figure4_snr_benchmarks" in data
    assert "figure5_multipath_gate" in data
    assert "figure6_tracking_gdop" in data


