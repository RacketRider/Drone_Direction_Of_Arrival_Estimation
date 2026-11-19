"""
Unit Tests for Automated Experiment Runner and Data Export.
"""

import os
import pytest
from backend.experiments.runner import ExperimentRunner
from backend.experiments.export import ExperimentExporter

def test_run_preset_a_frequency_hopping():
    """Verifies that Preset A runs without errors and produces valid metrics across parameter values."""
    res = ExperimentRunner.run_preset("PRESET_A_FREQUENCY_HOPPING", seed=42)
    
    assert res["preset_id"] == "PRESET_A"
    assert len(res["results"]) == 5  # 433, 868, 915, 928, DYNAMIC_FHSS
    
    for r in res["results"]:
        assert "compensated_rmse_deg" in r
        assert "static_rmse_deg" in r
        assert r["total_bursts"] == 30
        assert r["track_availability_pct"] >= 0.0

def test_export_json_and_csv(tmp_path):
    """Verifies that experiment reports can be exported to JSON and CSV."""
    res = ExperimentRunner.run_preset("PRESET_E_SWITCHED_COHERENCE", seed=42)
    
    json_file = str(tmp_path / "exp_e.json")
    csv_file = str(tmp_path / "exp_e.csv")
    
    ExperimentExporter.to_json(res, json_file)
    ExperimentExporter.to_csv(res, csv_file)
    
    assert os.path.exists(json_file)
    assert os.path.exists(csv_file)
    assert os.path.getsize(json_file) > 100
    assert os.path.getsize(csv_file) > 50

