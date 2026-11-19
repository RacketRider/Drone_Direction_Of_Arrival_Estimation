/**
 * Typed Telemetry and Diagnostics Contracts matching Backend FastAPI Schemas.
 */

export interface UAVState {
  x: number;
  y: number;
  z: number;
  speed: number;
  heading_deg: number;
  pitch_deg?: number;
  roll_deg?: number;
  true_azimuth_deg: number;
  true_elevation_deg: number;
  distance_m: number;
  trajectory_name: string;
  // Obstacle avoidance diagnostics
  avoidance_status?: "NOMINAL" | "AVOIDING" | "OBSTRUCTED_PAUSED";
  is_avoiding?: boolean;
  is_paused?: boolean;
  avoidance_event_count?: number;
  active_building_name?: string | null;
  min_clearance_m?: number;
  nominal_x?: number;
  nominal_y?: number;
  nominal_z?: number;
}

export interface NLOSPath {
  building_id: number;
  refl_point: [number, number, number];
  azimuth_deg: number;
  total_path_m: number;
  delay_ns: number;
  attenuation_linear: number;
  attenuation_db: number;
}

export interface RFState {
  active_freq_hz: number;
  active_freq_mhz: number;
  wavelength_m: number;
  snr_db: number;
  is_occluded: boolean;
  has_multipath: boolean;
  los_distance_m: number;
  nlos_paths: NLOSPath[];
}

export interface HardwareState {
  mode: "MODE_A_SIMULTANEOUS" | "MODE_B_SWITCHED";
  lo_freq_hz: number;
  in_band: boolean;
  phase_coherence_ok: boolean;
  snapshots_used: number;
}

export interface DSPState {
  burst_detected: boolean;
  detected_freq_hz: number;
  detected_freq_mhz: number;
  detected_baseband_khz: number;
  eigenvalues: [number, number, number, number];
  eigenvalue_ratio: number;
  gate_status: string;
  is_accepted: boolean;
  est_compensated_deg: number;
  est_static_deg: number;
  accepted_track_deg: number;
  error_comp_deg: number;
  error_static_deg: number;
  error_track_deg: number;
  tracker_state: "ACQUIRED" | "HOLDING" | "LOST";
  consecutive_rejections: number;
  total_rejections: number;
  total_bursts: number;
  // Benchmark Estimators & Advanced Tracking Diagnostics
  est_esprit_deg?: number;
  error_esprit_deg?: number;
  est_pv_deg?: number;
  error_pv_deg?: number;
  est_centroid_deg?: number;
  error_centroid_deg?: number;
  nis?: number;
  is_maneuvering?: boolean;
}

export interface MultiRadarStationReading {
  id: number;
  name: string;
  x: number;
  y: number;
  z: number;
  distance_m: number;
  true_azimuth_deg: number;
  measured_bearing_deg: number;
  tracked_bearing_deg: number;
  error_deg: number;
  tracked_error_deg: number;
  sigma_deg: number;
  effective_snr_db: number;
  active: boolean;
}

export interface MultiRadarTelemetry {
  num_active_stations: number;
  stations: MultiRadarStationReading[];
  estimated_pos_xz?: [number, number] | null;
  position_error_m?: number | null;
  solution_valid: boolean;
  condition_number: number;
  truth_xz: [number, number];
}

export interface TelemetryFrame {
  type: "telemetry";
  sim_time: number;
  frame_id: number;
  dt: number;
  uav: UAVState;
  rf: RFState;
  hardware: HardwareState;
  dsp: DSPState;
  multiradar?: MultiRadarTelemetry;
}

export interface SignalDiagnosticsFrame {
  type: "signal_diagnostics";
  sim_time: number;
  power_envelope: {
    time_us: number[];
    power_linear: number[];
    threshold: number;
    burst_start_idx: number;
    burst_end_idx: number;
  };
  fft_spectrum: {
    freqs_khz: number[];
    mag_db: number[];
    peak_freq_khz: number;
  };
  music_spectrum: {
    angles_deg: number[];
    comp_db: number[];
    static_db: number[];
    true_bearing_deg: number;
    est_comp_deg: number;
    est_static_deg: number;
  };
  raw_iq_burst: {
    time_us: number[];
    i_ch0: number[];
    q_ch0: number[];
  };
}

export interface ExperimentPreset {
  id: string;
  title: string;
  description: string;
  parameter_name: string;
  parameter_values: any[];
  num_steps: number;
}

export interface ExperimentReport {
  preset_id: string;
  title: string;
  description: string;
  parameter_name: string;
  seed: number;
  results: Array<{
    param_value: string;
    total_bursts: number;
    compensated_rmse_deg: number;
    static_rmse_deg: number;
    tracked_rmse_deg: number;
    compensated_mae_deg: number;
    static_mae_deg: number;
    tracked_mae_deg: number;
    compensated_median_deg: number;
    static_median_deg: number;
    tracked_median_deg: number;
    multipath_rejection_rate: number;
    false_rejection_rate: number;
    track_availability_pct: number;
    burst_detection_rate_pct: number;
    mean_latency_ms: number;
  }>;
}

export interface PaperBenchmarksData {
  figure3_manifold_bias: {
    freq_sweep: {
      frequencies_mhz: number[];
      worst_case_bias_deg: number[];
      rms_bias_deg: number[];
    };
    radius_sweep: {
      radius_cm: number[];
      bias_915mhz_deg: number[];
      bias_868mhz_deg: number[];
      prototype_radius_cm: number;
      spatial_ambiguity_threshold_cm: number;
    };
  };
  figure4_snr_benchmarks: {
    snr_db: number[];
    doa_rmse: {
      proposed_fine_lambda_k: number[];
      switched_no_derotation: number[];
      fft_only_derotation: number[];
      static_lambda0_baseline: number[];
      ideal_4ch_coherent: number[];
      cramer_rao_bound: number[];
    };
    frequency_offset_rmse_hz: {
      coarse_fft_peak: number[];
      lag_m_refined: number[];
    };
  };
  figure5_multipath_gate: {
    eigenvalue_ratio_vs_snr: {
      snr_db: number[];
      gamma_median: number[];
      gamma_p10: number[];
      gamma_p90: number[];
      false_rejection_rate: number[];
      gate_threshold_gamma: number;
    };
    rejection_prob_vs_correlation: {
      correlation_c: number[];
      rho_0_3_weak: number[];
      rho_0_6_moderate: number[];
      rho_0_9_strong: number[];
    };
    gate_table: Array<{
      name: string;
      rej: number;
      gam_med: number;
      MUSIC: number;
      Bartlett: number;
      Capon: number;
      "Interf-LS": number;
      MUSIC_gated: number;
      out_all: number;
      out_acc: number;
      det_big: number;
    }>;
  };
  figure6_tracking_gdop: {
    example_track: {
      time_s: number[];
      true_bearing_deg: number[];
      raw_music_deg: number[];
      circular_kf_deg: number[];
      is_accepted: boolean[];
    };
    gdop: {
      stations: number[][];
      target: number[];
      xs: number[];
      ys: number[];
      gdop_grid: number[][];
      wls_fixes: number[][];
    };
  };
}

