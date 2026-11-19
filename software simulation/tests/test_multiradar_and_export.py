"""
Tests for Multi-Radar Triangulation and Excel Flight Data Export.
"""

from io import BytesIO
import numpy as np
import pytest
from backend.simulation.multiradar import MultiRadarLocalization
from backend.api.export_excel import build_telemetry_excel
from backend.simulation.engine import SimulationEngine


def test_multiradar_localization_intersection():
    """Validates multi-station bearing line intersection solving for true (x, z)."""
    true_drone_pos = (-20.0, 18.0, 15.0)
    tx, _, tz = true_drone_pos

    stations = [
        {"id": "radar_1", "x": 0.0, "z": 0.0},
        {"id": "radar_2", "x": -40.0, "z": 30.0},
        {"id": "radar_3", "x": 40.0, "z": 30.0}
    ]

    for st in stations:
        dx = tx - st["x"]
        dz = tz - st["z"]
        st["azimuth_deg"] = float(np.degrees(np.arctan2(dz, dx)))
        st["sigma_deg"] = 1.0

    res = MultiRadarLocalization.solve_position_from_bearings(stations, drone_true_pos=true_drone_pos)
    assert res["valid"] is True
    assert abs(res["estimated_x"] - tx) < 0.1
    assert abs(res["estimated_z"] - tz) < 0.1
    assert res["position_error_m"] < 0.15


def test_excel_export_generation():
    """Validates generation of valid OpenPyXL workbook from simulation telemetry."""
    engine = SimulationEngine()
    telem, _ = engine.step()

    buf = build_telemetry_excel([telem, telem])
    assert isinstance(buf, BytesIO)
    data = buf.getvalue()
    assert len(data) > 1000
    # Check PK zip header for valid xlsx format
    assert data[:2] == b"PK"
