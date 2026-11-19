"""
Automated Experiment Runner.
Executes reproducible parameter sweeps, collects burst telemetry, and generates benchmark metrics.
"""

import time
from typing import Dict, List, Optional
import numpy as np

from backend.simulation.configuration import SystemConfiguration
from backend.simulation.engine import SimulationEngine
from backend.experiments.metrics import ExperimentMetricsCalculator
from backend.experiments.scenarios import EXPERIMENT_PRESETS

class ExperimentRunner:
    """Manages batch execution of reproducible experiments."""

    @staticmethod
    def run_preset(preset_key: str, seed: int = 42) -> Dict:
        """
        Executes a pre-defined experiment preset.
        Accepts either full preset key (e.g. PRESET_A_FREQUENCY_HOPPING) or short ID (e.g. PRESET_A).
        """
        target_key = preset_key
        if target_key not in EXPERIMENT_PRESETS:
            for k, p in EXPERIMENT_PRESETS.items():
                if p.get("id") == preset_key or k.startswith(preset_key):
                    target_key = k
                    break

        if target_key not in EXPERIMENT_PRESETS:
            raise ValueError(f"Unknown preset {preset_key}. Available: {list(EXPERIMENT_PRESETS.keys())}")

        preset = EXPERIMENT_PRESETS[target_key]
        results_by_param: List[Dict] = []

        for val in preset["parameter_values"]:
            # Clone clean configuration with deterministic seed
            cfg = SystemConfiguration(seed=seed)
            
            # Apply parameter modification
            param_name = preset["parameter_name"]
            if param_name == "active_frequency_mhz":
                if val == "DYNAMIC_FHSS":
                    cfg.rf.hop_frequencies_hz = [433e6, 868e6, 915e6, 920e6, 928e6]
                else:
                    freq_hz = float(val) * 1.0e6
                    cfg.rf.hop_frequencies_hz = [freq_hz]
            elif param_name == "snr_db":
                cfg.rf.nominal_snr_db = float(val)
            elif param_name == "multipath_strength":
                cfg.rf.multipath_strength_factor = float(val)
                cfg.rf.multipath_enabled = (val > 0.0)
            elif param_name == "phase_offset_deg":
                cfg.array.phase_offsets_deg = [0.0, float(val), -float(val), float(val)*0.5]
            elif param_name == "speed_multiplier":
                cfg.uav_speed_multiplier = float(val)
            elif param_name == "receiver_sampling_mode":
                if val == "MODE_A_SIMULTANEOUS":
                    cfg.sdr.receiver_mode = "MODE_A_SIMULTANEOUS"
                elif val == "MODE_B_DEROTATED":
                    cfg.sdr.receiver_mode = "MODE_B_SWITCHED"
                    cfg.sdr.phase_de_rotation_enabled = True
                elif val == "MODE_B_UNCOMPENSATED":
                    cfg.sdr.receiver_mode = "MODE_B_SWITCHED"
                    cfg.sdr.phase_de_rotation_enabled = False
            elif param_name == "lo_tuning_mode":
                cfg.sdr.lo_tuning_mode = val
                cfg.sdr.lo_frequency_hz = 915.0e6
            elif param_name == "array_radius_m":
                cfg.array.radius = float(val)
            elif param_name == "snr_db_fine_freq":
                cfg.rf.nominal_snr_db = float(val)
            elif param_name == "multipath_coherence_c":
                cfg.rf.multipath_strength_factor = 0.6
                cfg.rf.multipath_enabled = True

            # Instantiate engine
            engine = SimulationEngine(cfg)
            if param_name == "trajectory":
                engine.set_trajectory(str(val))
            if param_name == "active_frequency_mhz" and val != "DYNAMIC_FHSS":
                engine.transmitter.set_mode("FIXED", fixed_freq_hz=float(val)*1e6)

            engine.clock.play()

            # Execute run
            true_bearings: List[float] = []
            comp_bearings: List[float] = []
            static_bearings: List[float] = []
            track_bearings: List[float] = []
            esprit_bearings: List[float] = []
            pv_bearings: List[float] = []
            centroid_bearings: List[float] = []
            gate_decisions: List[bool] = []
            mp_active_flags: List[bool] = []
            det_flags: List[bool] = []
            latencies_ms: List[float] = []

            n_steps = preset["num_steps"]
            for step_idx in range(n_steps):
                engine.clock.tick()
                t_start = time.perf_counter()
                telem, _ = engine.step()
                t_elapsed_ms = (time.perf_counter() - t_start) * 1.0e3

                uav = telem["uav"]
                rf = telem["rf"]
                dsp = telem["dsp"]

                true_bearings.append(uav["true_azimuth_deg"])
                comp_bearings.append(dsp["est_compensated_deg"])
                static_bearings.append(dsp["est_static_deg"])
                track_bearings.append(dsp["accepted_track_deg"])
                esprit_bearings.append(dsp.get("est_esprit_deg", dsp["est_compensated_deg"]))
                pv_bearings.append(dsp.get("est_pv_deg", dsp["est_compensated_deg"]))
                centroid_bearings.append(dsp.get("est_centroid_deg", dsp["est_compensated_deg"]))
                gate_decisions.append(dsp["is_accepted"])
                mp_active_flags.append(rf["has_multipath"] or rf["is_occluded"])
                det_flags.append(dsp["burst_detected"])
                latencies_ms.append(t_elapsed_ms)

            # Compute statistics
            metrics = ExperimentMetricsCalculator.compute_metrics(
                true_bearings=true_bearings,
                est_comp_bearings=comp_bearings,
                est_static_bearings=static_bearings,
                tracked_bearings=track_bearings,
                gate_decisions=gate_decisions,
                is_multipath_active=mp_active_flags,
                burst_detected_flags=det_flags,
                latencies_ms=latencies_ms,
                est_esprit_bearings=esprit_bearings,
                est_pv_bearings=pv_bearings,
                est_centroid_bearings=centroid_bearings
            )

            metrics["param_value"] = str(val)
            results_by_param.append(metrics)

        return {
            "preset_id": preset["id"],
            "title": preset["title"],
            "description": preset["description"],
            "parameter_name": preset["parameter_name"],
            "seed": seed,
            "results": results_by_param
        }

