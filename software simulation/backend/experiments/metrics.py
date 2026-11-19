"""
Statistical Metrics Calculator for Direction-Finding Experiments.
Computes Angular RMSE, MAE, Median Error, Rejection Rates, and Track Availability.
"""

from typing import List, Dict, Optional
import numpy as np
from backend.dsp.music import MUSICEstimator

class ExperimentMetricsCalculator:
    """Computes comprehensive academic performance metrics across experiment bursts."""

    @staticmethod
    def compute_metrics(
        true_bearings: List[float],
        est_comp_bearings: List[float],
        est_static_bearings: List[float],
        tracked_bearings: List[float],
        gate_decisions: List[bool],
        is_multipath_active: List[bool],
        burst_detected_flags: List[bool],
        latencies_ms: List[float],
        est_esprit_bearings: Optional[List[float]] = None,
        est_pv_bearings: Optional[List[float]] = None,
        est_centroid_bearings: Optional[List[float]] = None
    ) -> Dict:
        """
        Calculates all required research metrics across the trial dataset.
        """
        n_total = len(true_bearings)
        if n_total == 0:
            return {}

        # Circular angular errors
        errs_comp = np.array([
            MUSICEstimator.circular_angular_error(est, true)
            for est, true in zip(est_comp_bearings, true_bearings)
        ])
        errs_static = np.array([
            MUSICEstimator.circular_angular_error(est, true)
            for est, true in zip(est_static_bearings, true_bearings)
        ])
        errs_track = np.array([
            MUSICEstimator.circular_angular_error(trk, true)
            for trk, true in zip(tracked_bearings, true_bearings)
        ])

        # Angular RMSE
        rmse_comp = float(np.sqrt(np.mean(errs_comp ** 2)))
        rmse_static = float(np.sqrt(np.mean(errs_static ** 2)))
        rmse_track = float(np.sqrt(np.mean(errs_track ** 2)))

        # Mean Absolute Error (MAE)
        mae_comp = float(np.mean(np.abs(errs_comp)))
        mae_static = float(np.mean(np.abs(errs_static)))
        mae_track = float(np.mean(np.abs(errs_track)))

        # Median Absolute Error
        median_comp = float(np.median(np.abs(errs_comp)))
        median_static = float(np.median(np.abs(errs_static)))
        median_track = float(np.median(np.abs(errs_track)))

        # Optional Benchmark Estimator Metrics
        benchmark_results = {}
        if est_esprit_bearings and len(est_esprit_bearings) == n_total:
            errs_esprit = np.array([MUSICEstimator.circular_angular_error(e, t) for e, t in zip(est_esprit_bearings, true_bearings)])
            benchmark_results["esprit_rmse_deg"] = round(float(np.sqrt(np.mean(errs_esprit ** 2))), 3)
            benchmark_results["esprit_mae_deg"] = round(float(np.mean(np.abs(errs_esprit))), 3)

        if est_pv_bearings and len(est_pv_bearings) == n_total:
            errs_pv = np.array([MUSICEstimator.circular_angular_error(e, t) for e, t in zip(est_pv_bearings, true_bearings)])
            benchmark_results["pv_rmse_deg"] = round(float(np.sqrt(np.mean(errs_pv ** 2))), 3)
            benchmark_results["pv_mae_deg"] = round(float(np.mean(np.abs(errs_pv))), 3)

        if est_centroid_bearings and len(est_centroid_bearings) == n_total:
            errs_cnt = np.array([MUSICEstimator.circular_angular_error(e, t) for e, t in zip(est_centroid_bearings, true_bearings)])
            benchmark_results["centroid_rmse_deg"] = round(float(np.sqrt(np.mean(errs_cnt ** 2))), 3)
            benchmark_results["centroid_mae_deg"] = round(float(np.mean(np.abs(errs_cnt))), 3)

        # Reliability Gate Metrics
        gate_arr = np.array(gate_decisions)
        mp_arr = np.array(is_multipath_active)
        det_arr = np.array(burst_detected_flags)

        total_mp = np.sum(mp_arr)
        total_los = n_total - total_mp

        # True Rejection Rate (Sensitivity): Gate rejected when multipath was actually active
        if total_mp > 0:
            rejection_rate = float(np.sum((gate_arr == False) & (mp_arr == True)) / total_mp)
        else:
            rejection_rate = 1.0

        # False Rejection Rate (Fallout): Gate rejected when signal was clean LoS
        if total_los > 0:
            false_rejection_rate = float(np.sum((gate_arr == False) & (mp_arr == False)) / total_los)
        else:
            false_rejection_rate = 0.0

        # Track Availability: Percentage of bursts where estimator produced accepted valid bearing
        track_availability = float(np.sum(gate_arr) / n_total)

        # Burst Detection Rate
        burst_detection_rate = float(np.sum(det_arr) / n_total)

        # Mean processing latency
        mean_latency_ms = float(np.mean(latencies_ms)) if latencies_ms else 0.0

        res = {
            "total_bursts": n_total,
            "compensated_rmse_deg": round(rmse_comp, 3),
            "static_rmse_deg": round(rmse_static, 3),
            "tracked_rmse_deg": round(rmse_track, 3),
            "compensated_mae_deg": round(mae_comp, 3),
            "static_mae_deg": round(mae_static, 3),
            "tracked_mae_deg": round(mae_track, 3),
            "compensated_median_deg": round(median_comp, 3),
            "static_median_deg": round(median_static, 3),
            "tracked_median_deg": round(median_track, 3),
            "multipath_rejection_rate": round(rejection_rate * 100.0, 1),
            "false_rejection_rate": round(false_rejection_rate * 100.0, 1),
            "track_availability_pct": round(track_availability * 100.0, 1),
            "burst_detection_rate_pct": round(burst_detection_rate * 100.0, 1),
            "mean_latency_ms": round(mean_latency_ms, 2)
        }
        res.update(benchmark_results)
        return res

