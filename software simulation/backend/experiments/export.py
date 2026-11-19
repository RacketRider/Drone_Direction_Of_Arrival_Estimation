"""
Experiment Data Export Utilities.
Exports experiment benchmark results to structured JSON, CSV, and professional multi-sheet Excel (.xlsx) files.
"""

import csv
import io
import json
import os
from typing import Dict, List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExperimentExporter:
    """Serializes experiment trial data to disk and in-memory byte buffers."""

    @staticmethod
    def to_json(experiment_data: Dict, output_path: str) -> str:
        """Saves experiment results to a formatted JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(experiment_data, f, indent=2)
        return output_path

    @staticmethod
    def to_csv(experiment_data: Dict, output_path: str) -> str:
        """Saves experiment results table to a standard CSV file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        results = experiment_data.get("results", [])
        if not results:
            return output_path

        fieldnames = ["param_value"] + [k for k in results[0].keys() if k != "param_value"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        return output_path

    @staticmethod
    def generate_xlsx_bytes(
        experiment_data: Dict,
        multiradar_measurements: Optional[List[Dict]] = None
    ) -> bytes:
        """
        Builds a multi-sheet formatted Excel workbook (.xlsx) and returns raw bytes.
        Sheets:
        1. 'Executive Summary': Metadata, parameters, system configuration.
        2. 'Parametric Benchmark': Numerical results per sweep point (RMSE, MAE, Rejection rate).
        3. 'Multi-Radar Localization': Distributed station bearings and 2D triangulated coordinates.
        """
        wb = openpyxl.Workbook()

        # Styles
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        sub_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="00E5FF")
        title_font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
        bold_font = Font(name="Segoe UI", size=10, bold=True)
        regular_font = Font(name="Segoe UI", size=10)
        thin_border = Border(
            left=Side(style='thin', color="CBD5E1"),
            right=Side(style='thin', color="CBD5E1"),
            top=Side(style='thin', color="CBD5E1"),
            bottom=Side(style='thin', color="CBD5E1")
        )

        # -----------------------------------------------------------------
        # Sheet 1: Executive Summary
        # -----------------------------------------------------------------
        ws_summary = wb.active
        ws_summary.title = "Executive Summary"
        ws_summary.views.sheetView[0].showGridLines = True

        ws_summary["A1"] = "EC261 — UAV Direction Finding Digital Twin Report"
        ws_summary["A1"].font = title_font

        ws_summary["A3"] = "Experiment ID:"
        ws_summary["B3"] = experiment_data.get("preset_id", "N/A")
        ws_summary["A4"] = "Title:"
        ws_summary["B4"] = experiment_data.get("title", "Parametric Evaluation")
        ws_summary["A5"] = "Description:"
        ws_summary["B5"] = experiment_data.get("description", "")
        ws_summary["A6"] = "Swept Parameter:"
        ws_summary["B6"] = experiment_data.get("parameter_name", "N/A")
        ws_summary["A7"] = "Execution Timestamp:"
        ws_summary["B7"] = str(experiment_data.get("timestamp", ""))

        for row in range(3, 8):
            ws_summary[f"A{row}"].font = bold_font
            ws_summary[f"B{row}"].font = regular_font

        # -----------------------------------------------------------------
        # Sheet 2: Parametric Benchmark
        # -----------------------------------------------------------------
        ws_results = wb.create_sheet(title="Parametric Benchmark")
        ws_results.views.sheetView[0].showGridLines = True

        results = experiment_data.get("results", [])
        if results:
            keys = ["param_value"] + [k for k in results[0].keys() if k != "param_value"]
            for col_idx, key in enumerate(keys, start=1):
                cell = ws_results.cell(row=1, column=col_idx, value=key.replace("_", " ").title())
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for row_idx, r in enumerate(results, start=2):
                for col_idx, key in enumerate(keys, start=1):
                    val = r.get(key)
                    cell = ws_results.cell(row=row_idx, column=col_idx, value=val)
                    cell.font = regular_font
                    cell.border = thin_border
                    if isinstance(val, (int, float)):
                        cell.alignment = Alignment(horizontal="right")

        # -----------------------------------------------------------------
        # Sheet 3: Multi-Radar Localization (if provided)
        # -----------------------------------------------------------------
        if multiradar_measurements:
            ws_radar = wb.create_sheet(title="Multi-Station Localization")
            ws_radar.views.sheetView[0].showGridLines = True
            radar_cols = [
                "Time (s)", "Station ID", "Station Name", "Station X (m)", "Station Z (m)",
                "True Azimuth (°)", "Measured Bearing (°)", "Tracked Bearing (°)",
                "Error (°)", "Distance (m)", "SNR (dB)",
                "True UAV X (m)", "True UAV Z (m)", "Est UAV X (m)", "Est UAV Z (m)",
                "2D Position Error (m)"
            ]
            for col_idx, col_name in enumerate(radar_cols, start=1):
                cell = ws_radar.cell(row=1, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for row_idx, r in enumerate(multiradar_measurements, start=2):
                row_vals = [
                    r.get("sim_time", 0.0),
                    r.get("station_id", 1),
                    r.get("station_name", "Primary Station"),
                    r.get("station_x", 0.0),
                    r.get("station_z", 0.0),
                    r.get("true_azimuth_deg", 0.0),
                    r.get("measured_bearing_deg", 0.0),
                    r.get("tracked_bearing_deg", 0.0),
                    r.get("error_deg", 0.0),
                    r.get("distance_m", 0.0),
                    r.get("effective_snr_db", 0.0),
                    r.get("truth_x", 0.0),
                    r.get("truth_z", 0.0),
                    r.get("estimated_x", 0.0),
                    r.get("estimated_z", 0.0),
                    r.get("position_error_m", 0.0)
                ]
                for col_idx, val in enumerate(row_vals, start=1):
                    cell = ws_radar.cell(row=row_idx, column=col_idx, value=val)
                    cell.font = regular_font
                    cell.border = thin_border
                    if isinstance(val, (int, float)):
                        cell.alignment = Alignment(horizontal="right")

        # Auto-fit column widths across all sheets
        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max(12, min(50, max_len + 3))

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    @classmethod
    def to_xlsx(cls, experiment_data: Dict, output_path: str, multiradar_measurements: Optional[List[Dict]] = None) -> str:
        """Saves formatted Excel report to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        xlsx_bytes = cls.generate_xlsx_bytes(experiment_data, multiradar_measurements)
        with open(output_path, "wb") as f:
            f.write(xlsx_bytes)
        return output_path
