"""
Experiment Scenario Presets.
Configures Presets A through H for automated parametric benchmarking.
"""

from typing import Dict, List
from backend.simulation.configuration import SystemConfiguration

EXPERIMENT_PRESETS: Dict[str, dict] = {
    "PRESET_A_FREQUENCY_HOPPING": {
        "id": "PRESET_A",
        "title": "Frequency Hopping Comparison",
        "description": "Compares Proposed A2 Frequency-Compensated MUSIC vs Static 433 MHz baseline across individual hop frequencies and dynamic hopping.",
        "parameter_name": "active_frequency_mhz",
        "parameter_values": [433.0, 868.0, 915.0, 928.0, "DYNAMIC_FHSS"],
        "num_steps": 30
    },
    "PRESET_B_SNR_SENSITIVITY": {
        "id": "PRESET_B",
        "title": "SNR Sensitivity Sweep",
        "description": "Sweeps Signal-to-Noise Ratio from -5 dB to +30 dB to evaluate threshold breakdown, burst detection, and subspace estimation limits.",
        "parameter_name": "snr_db",
        "parameter_values": [-5.0, 0.0, 5.0, 10.0, 15.0, 20.0, 30.0],
        "num_steps": 30
    },
    "PRESET_C_BUILDING_OCCLUSION": {
        "id": "PRESET_C",
        "title": "Building Occlusion Transition",
        "description": "Evaluates UAV traversing behind concrete buildings on S-Curve path, triggering LOS blockage and concrete reflections.",
        "parameter_name": "trajectory",
        "parameter_values": ["S_CURVE", "FIGURE_EIGHT"],
        "num_steps": 40
    },
    "PRESET_D_MULTIPATH_SEVERITY": {
        "id": "PRESET_D",
        "title": "Multipath Reflection Severity",
        "description": "Sweeps building reflection coefficient alpha from 0.0 (open field) to 1.0 (strong metallic/dense concrete reflector) to assess eigenvalue gate rejection.",
        "parameter_name": "multipath_strength",
        "parameter_values": [0.0, 0.2, 0.4, 0.6, 0.85, 1.0],
        "num_steps": 30
    },
    "PRESET_E_SWITCHED_COHERENCE": {
        "id": "PRESET_E",
        "title": "Antenna Switching Coherence",
        "description": "Compares Mode A (Simultaneous Coherent) against Mode B (HMC241 switched) with and without baseband phase de-rotation.",
        "parameter_name": "receiver_sampling_mode",
        "parameter_values": ["MODE_A_SIMULTANEOUS", "MODE_B_DEROTATED", "MODE_B_UNCOMPENSATED"],
        "num_steps": 30
    },
    "PRESET_F_CALIBRATION_ERRORS": {
        "id": "PRESET_F",
        "title": "Array Calibration Impairments",
        "description": "Evaluates robustness against RF manufacturing tolerances: phase offsets up to 20 deg and amplitude imbalances up to 2 dB.",
        "parameter_name": "phase_offset_deg",
        "parameter_values": [0.0, 5.0, 10.0, 15.0, 20.0],
        "num_steps": 30
    },
    "PRESET_G_UAV_SPEED_TRACKING": {
        "id": "PRESET_G",
        "title": "UAV Dynamics and Tracking Filters",
        "description": "Tests tracking lag and availability across UAV speed multipliers (0.5x to 3.0x), comparing Gated Hold vs Kalman Filter.",
        "parameter_name": "speed_multiplier",
        "parameter_values": [0.5, 1.0, 2.0, 3.0],
        "num_steps": 40
    },
    "PRESET_H_ACQUISITION_FAILURE": {
        "id": "PRESET_H",
        "title": "Receiver LO Acquisition Behavior",
        "description": "Demonstrates burst acquisition failure when SDR LO is fixed to 915 MHz while drone hops across other sub-GHz channels.",
        "parameter_name": "lo_tuning_mode",
        "parameter_values": ["SYNCHRONOUS", "STATIC_LO"],
        "num_steps": 30
    },
    "PRESET_I_APERTURE_RADIUS_SWEEP": {
        "id": "PRESET_I",
        "title": "Aperture Radius & Spatial Ambiguity (Fig 3b)",
        "description": "Sweeps UCA radius r from 5 cm to 35 cm at 915 MHz to demonstrate prototype optimality at r=7.2 cm (d/lambda=0.31) and spatial aliasing breakdown above 12 cm.",
        "parameter_name": "array_radius_m",
        "parameter_values": [0.05, 0.072, 0.10, 0.12, 0.15, 0.20, 0.30],
        "num_steps": 30
    },
    "PRESET_J_FREQUENCY_REFINEMENT_SNR": {
        "id": "PRESET_J",
        "title": "Fine Frequency Recovery vs SNR (Fig 4b)",
        "description": "Sweeps SNR (-10 dB to +30 dB) to evaluate Coarse FFT peak resolution vs Lag-M differential phase refinement error down to sub-100 Hz.",
        "parameter_name": "snr_db_fine_freq",
        "parameter_values": [-10.0, -5.0, 0.0, 5.0, 10.0, 15.0, 20.0, 30.0],
        "num_steps": 30
    },
    "PRESET_K_MULTIPATH_COHERENCE_SWEEP": {
        "id": "PRESET_K",
        "title": "Multipath Coherence & Gate Rejection (Fig 5b)",
        "description": "Sweeps direct-to-reflected path correlation coefficient |c| from 0.0 to 1.0 across reflection levels rho to evaluate eigenvalue gate rejection probability.",
        "parameter_name": "multipath_coherence_c",
        "parameter_values": [0.0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0],
        "num_steps": 30
    }
}

