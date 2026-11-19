"""
Excel Flight Telemetry and Direction-Finding Data Exporter.
Builds formatted, styled OpenPyXL workbooks for scientific data analysis and paper reporting.
"""

from io import BytesIO
from typing import Dict, List, Optional
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def build_telemetry_excel(rows: List[Dict]) -> BytesIO:
    """
    Builds an academic-grade Excel workbook containing one row per simulation telemetry cycle.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "UAV RF DF Telemetry"

    columns = [
        ("sim_time", "Sim Time (s)"),
        ("frame_id", "Frame ID"),
        ("uav_x", "UAV X (m)"),
        ("uav_y", "UAV Altitude (m)"),
        ("uav_z", "UAV Z (m)"),
        ("true_azimuth_deg", "True Azimuth (deg)"),
        ("true_elevation_deg", "True Elevation (deg)"),
        ("los_distance_m", "LOS Distance (m)"),
        ("active_freq_mhz", "Hopping Frequency (MHz)"),
        ("est_compensated_deg", "Compensated MUSIC (deg)"),
        ("est_static_deg", "Static MUSIC (deg)"),
        ("accepted_track_deg", "Accepted Track (deg)"),
        ("error_comp_deg", "Compensated Error (deg)"),
        ("error_static_deg", "Static Error (deg)"),
        ("error_track_deg", "Track Error (deg)"),
        ("gate_status", "Gate Decision"),
        ("eigenvalue_ratio", "EVD Ratio (L1/L2)"),
        ("is_occluded", "LOS Occluded"),
        ("has_multipath", "Multipath Active"),
        ("avoidance_status", "Obstacle Avoidance"),
        ("min_clearance_m", "Building Clearance (m)")
    ]

    # Header Row
    ws.append([label for _, label in columns])

    # Header Styling
    header_fill = PatternFill("solid", fgColor="17324D")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    # Data Rows
    for row in rows[:20000]:
        if not isinstance(row, dict):
            continue

        # Extract nested values gracefully if raw telemetry dictionary is passed
        uav = row.get("uav", {})
        rf = row.get("rf", {})
        dsp = row.get("dsp", {})

        row_data = [
            row.get("sim_time", 0.0),
            row.get("frame_id", 0),
            uav.get("x", row.get("uav_x", 0.0)),
            uav.get("y", row.get("uav_y", 0.0)),
            uav.get("z", row.get("uav_z", 0.0)),
            uav.get("true_azimuth_deg", row.get("true_azimuth_deg", 0.0)),
            uav.get("true_elevation_deg", row.get("true_elevation_deg", 0.0)),
            rf.get("los_distance_m", row.get("los_distance_m", 0.0)),
            rf.get("active_freq_mhz", row.get("active_freq_mhz", 0.0)),
            dsp.get("est_compensated_deg", row.get("est_compensated_deg", 0.0)),
            dsp.get("est_static_deg", row.get("est_static_deg", 0.0)),
            dsp.get("accepted_track_deg", row.get("accepted_track_deg", 0.0)),
            dsp.get("error_comp_deg", row.get("error_comp_deg", 0.0)),
            dsp.get("error_static_deg", row.get("error_static_deg", 0.0)),
            dsp.get("error_track_deg", row.get("error_track_deg", 0.0)),
            dsp.get("gate_status", row.get("gate_status", "UNKNOWN")),
            dsp.get("eigenvalue_ratio", row.get("eigenvalue_ratio", 0.0)),
            bool(rf.get("is_occluded", row.get("is_occluded", False))),
            bool(rf.get("has_multipath", row.get("has_multipath", False))),
            uav.get("avoidance_status", row.get("avoidance_status", "NOMINAL")),
            uav.get("min_clearance_m", row.get("min_clearance_m", 99.0))
        ]
        ws.append(row_data)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
