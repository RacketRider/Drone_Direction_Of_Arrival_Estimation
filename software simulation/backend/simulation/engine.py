"""
Master Simulation Engine.
Coordinates UAV dynamics, RF propagation, switched SDR sampling, and complete DSP estimation chain.
"""

from typing import Dict, Optional, Tuple
import numpy as np

from backend.simulation.configuration import SystemConfiguration, DEFAULT_CONFIG
from backend.simulation.clock import SimulationClock
from backend.simulation.trajectories import TRAJECTORY_REGISTRY, FigureEightTrajectory
from backend.simulation.uav import UAVState
from backend.simulation.environment import PhysicalEnvironment

from backend.hardware.uca import UniformCircularArray
from backend.hardware.sdr import RTLSDRReceiver
from backend.hardware.sampling import SamplingSubsystem

from backend.rf.fhss import FHSSTransmitter
from backend.rf.propagation import RFPropagationEngine

from backend.dsp.burst_detection import BurstDetector
from backend.dsp.frequency_estimation import FrequencyEstimator
from backend.dsp.steering import SteeringVectorProvider
from backend.dsp.covariance import CovarianceEstimator
from backend.dsp.eigendecomposition import SubspaceDecomposition
from backend.dsp.eigenvalue_gate import EigenvalueGate
from backend.dsp.music import MUSICEstimator
from backend.dsp.tracker import BearingTracker
from backend.dsp.esprit import UCAESPRITEstimator
from backend.dsp.power_vector import PowerVectorMLEstimator, est_power_centroid, est_strongest_beam
from backend.simulation.multiradar import MultiRadarNetwork

class SimulationEngine:
    """Integrated master digital twin and DSP direction-finding simulation engine."""

    def __init__(self, config: Optional[SystemConfiguration] = None):
        self.config: SystemConfiguration = config or DEFAULT_CONFIG
        
        # 1. Clock
        self.clock: SimulationClock = SimulationClock(
            dt=self.config.simulation_dt,
            speed_multiplier=self.config.uav_speed_multiplier,
            seed=self.config.seed
        )

        # 2. Physics & Environment
        self.environment: PhysicalEnvironment = PhysicalEnvironment(self.config.buildings)
        self.uav: UAVState = UAVState(FigureEightTrajectory(), buildings=self.config.buildings)

        # 3. Hardware Subsystems
        self.uca: UniformCircularArray = UniformCircularArray(self.config.array)
        self.sdr: RTLSDRReceiver = RTLSDRReceiver(self.config.sdr)
        self.sampler: SamplingSubsystem = SamplingSubsystem(self.config.sdr, self.sdr)

        # 4. RF Generation
        self.transmitter: FHSSTransmitter = FHSSTransmitter(
            hop_frequencies_hz=self.config.rf.hop_frequencies_hz,
            tx_power_dbm=self.config.rf.tx_power_dbm,
            seed=self.config.seed
        )
        self.propagation: RFPropagationEngine = RFPropagationEngine(
            uca=self.uca,
            environment=self.environment,
            config=self.config.rf,
            seed=self.config.seed
        )

        # 5. DSP Pipeline Modules
        self.burst_detector: BurstDetector = BurstDetector(
            window_size=self.config.dsp.power_envelope_window,
            threshold_factor=self.config.dsp.power_trigger_threshold_factor
        )
        self.freq_estimator: FrequencyEstimator = FrequencyEstimator(
            sample_rate=self.config.rf.sample_rate,
            fft_size=self.config.dsp.fft_size
        )
        self.steering_provider: SteeringVectorProvider = SteeringVectorProvider(
            uca=self.uca,
            reference_frequency_hz=self.config.rf.reference_frequency_hz,
            grid_min_deg=self.config.dsp.angle_grid_min_deg,
            grid_max_deg=self.config.dsp.angle_grid_max_deg,
            grid_resolution_deg=self.config.dsp.angle_grid_resolution_deg
        )
        self.gate: EigenvalueGate = EigenvalueGate(
            threshold=self.config.dsp.eigenvalue_gate_threshold
        )
        self.tracker: BearingTracker = BearingTracker(
            tracker_type=self.config.dsp.tracker_type
        )
        self.esprit_estimator: UCAESPRITEstimator = UCAESPRITEstimator(self.uca)
        self.pv_estimator: PowerVectorMLEstimator = PowerVectorMLEstimator(
            boresights_deg=self.config.array.element_angles_deg,
            beamwidth_deg=90.0
        )
        self.multiradar: MultiRadarNetwork = MultiRadarNetwork()
        self.foliage_density: float = 0.0

        # Cached latest frames and rolling history buffer
        self.latest_telemetry: Optional[dict] = None
        self.latest_diagnostics: Optional[dict] = None
        self.telemetry_history: list = []

    def set_station_active(self, station_id: int, active: bool) -> None:
        """Enables or disables an active radar station in the distributed network."""
        self.multiradar.set_station_active(station_id, active)

    def set_foliage_density(self, density: float) -> None:
        """Sets the vegetation foliage density (0.0 to 1.0) for ITU-R P.833 attenuation."""
        self.foliage_density = float(np.clip(density, 0.0, 1.0))

    def set_trajectory(self, trajectory_name: str) -> None:
        """Changes the UAV flight trajectory."""
        if trajectory_name in TRAJECTORY_REGISTRY:
            traj_cls = TRAJECTORY_REGISTRY[trajectory_name]
            self.uav.set_trajectory(traj_cls(), sim_time=self.clock.sim_time)
            self.clock.log_event("TRAJECTORY_CHANGE", f"Switched trajectory to {trajectory_name}")

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Resets the simulation clock, UAV position, and tracking filters."""
        self.clock.reset(new_seed=new_seed)
        self.uav.reset(0.0)
        self.tracker.reset()
        self.multiradar.reset()
        self.latest_telemetry = None
        self.latest_diagnostics = None
        self.telemetry_history.clear()

    def set_snr(self, snr_db: float) -> None:
        """Dynamically adjusts RF Signal-to-Noise Ratio."""
        self.config.rf.nominal_snr_db = max(-10.0, min(40.0, snr_db))

    def set_receiver_mode(self, mode_str: str) -> None:
        """Switches between MODE_A_SIMULTANEOUS and MODE_B_SWITCHED."""
        if mode_str in ["MODE_A_SIMULTANEOUS", "MODE_B_SWITCHED"]:
            self.config.sdr.receiver_mode = mode_str
            self.sampler.config.receiver_mode = mode_str

    def set_buildings_enabled(self, enabled: bool) -> None:
        """Enables or disables buildings in physical environment and UAV flight planning."""
        self.environment.set_buildings_enabled(enabled)
        self.uav.set_buildings_enabled(enabled)

    def step(self) -> Tuple[dict, dict]:
        """
        Executes one discrete simulation and DSP pipeline cycle.
        Returns: (telemetry_dict, diagnostics_dict)
        """
        sim_time = self.clock.sim_time

        # 1. Advance UAV Kinematics
        self.uav.update(sim_time, dt=self.clock.dt)
        uav_pos = self.uav.position
        true_az = self.uav.true_azimuth_deg

        # 2. Advance FHSS Transmitter Hop
        active_freq = self.transmitter.hop()
        wavelength = self.transmitter.current_wavelength

        # 3. Update SDR LO Tuning
        receiver_lo = self.sdr.update_lo_for_expected_hop(active_freq)
        in_band, f_bb_nominal, filter_att = self.sdr.evaluate_acquisition(active_freq)

        # 4. Generate Multi-Antenna RF Field & Stream
        stream, burst_slice, rf_meta = self.propagation.simulate_burst_stream(
            uav_pos=uav_pos,
            active_freq_hz=active_freq,
            receiver_lo_hz=receiver_lo,
            snr_db=self.config.rf.nominal_snr_db,
            foliage_density=self.foliage_density
        )

        # Apply RF front-end bandpass attenuation if out of band
        if not in_band:
            stream *= filter_att
            burst_slice *= filter_att

        # 5. DSP Stage A: Power Envelope Burst Detection
        detected, b_start, b_end, power_env, p_th = self.burst_detector.detect(stream)

        # If burst detection fails (e.g. low SNR or out-of-band), use fallback slice
        active_burst = burst_slice if detected else burst_slice * 0.1

        # 6. DSP Stage B: FFT Frequency & Wavelength Estimation
        (
            det_freq_rf,
            det_f_bb,
            det_lambda,
            fft_freqs_khz,
            fft_mag_db
        ) = self.freq_estimator.estimate_frequency(active_burst, receiver_lo)

        # 7. Hardware Capture: Mode A Simultaneous vs Mode B Switched
        snapshots, coherence_ok, sampling_meta = self.sampler.capture_burst(
            active_burst, det_f_bb
        )

        # 8. DSP Stage C: Covariance Matrix R_xx
        r_xx, cov_meta = CovarianceEstimator.compute_covariance(snapshots)

        # 9. DSP Stage D: Hermitian Eigenvalue Decomposition
        eigvals, eigvecs, e_noise, p_noise = SubspaceDecomposition.decompose(r_xx)

        # 10. DSP Stage E: Multipath Reliability Gate
        gate_ok, eig_ratio, gate_meta = self.gate.evaluate(eigvals)

        # If phase coherence failed in switched mode, reject burst
        if not coherence_ok:
            gate_ok = False
            gate_meta["status"] = "REJECTED (Phase Incoherent)"

        # 11. DSP Stage F: Proposed Frequency-Compensated MUSIC Spectrum
        angle_grid = self.steering_provider.get_angle_grid()
        a_comp_mat = self.steering_provider.get_compensated_steering_matrix(det_freq_rf)
        p_comp_lin, p_comp_db = MUSICEstimator.evaluate_pseudospectrum(a_comp_mat, p_noise)
        est_comp_deg = MUSICEstimator.extract_peak_bearing(p_comp_db, angle_grid)

        # 12. DSP Stage G: Static Uncompensated Reference MUSIC Spectrum (433 MHz)
        a_static_mat = self.steering_provider.get_static_steering_matrix()
        p_static_lin, p_static_db = MUSICEstimator.evaluate_pseudospectrum(a_static_mat, p_noise)
        est_static_deg = MUSICEstimator.extract_peak_bearing(p_static_db, angle_grid)

        # 13. Tracking & Gated Hold Update
        active_track_deg, track_state, tracker_meta = self.tracker.update(
            est_compensated_deg=est_comp_deg,
            est_static_deg=est_static_deg,
            gate_accepted=gate_ok,
            dt=self.clock.dt
        )

        # 14. Benchmark Estimators
        est_esprit_deg = self.esprit_estimator.estimate(r_xx, det_freq_rf)
        err_esprit = MUSICEstimator.circular_angular_error(est_esprit_deg, true_az)

        elem_powers = np.mean(np.abs(snapshots)**2, axis=1)
        est_centroid_deg = est_power_centroid(elem_powers, np.array(self.config.array.element_angles_deg))
        err_centroid = MUSICEstimator.circular_angular_error(est_centroid_deg, true_az)

        pv_res = self.pv_estimator.estimate(elem_powers, noise_variance=1.0, dwell_samples=snapshots.shape[1])
        est_pv_deg = pv_res["estimated_bearing_deg"]
        err_pv = MUSICEstimator.circular_angular_error(est_pv_deg, true_az)

        # 15. Error Metrics
        err_comp = MUSICEstimator.circular_angular_error(est_comp_deg, true_az)
        err_static = MUSICEstimator.circular_angular_error(est_static_deg, true_az)
        err_track = MUSICEstimator.circular_angular_error(active_track_deg, true_az)

        # 16. Multi-Station Radar Network Triangulation
        multiradar_data = self.multiradar.update(
            uav_position=uav_pos,
            active_frequency_hz=active_freq,
            nominal_snr_db=self.config.rf.nominal_snr_db,
            seed=int(self.clock.seed + self.clock.frame_count)
        )

        # 17. Formulate Telemetry Payload
        telemetry = {
            "type": "telemetry",
            "sim_time": round(sim_time, 3),
            "frame_id": self.clock.frame_count,
            "dt": round(self.clock.dt, 4),
            "uav": self.uav.current_dict,
            "multiradar": multiradar_data,
            "rf": {
                "active_freq_hz": float(active_freq),
                "active_freq_mhz": round(active_freq / 1.0e6, 2),
                "wavelength_m": round(wavelength, 4),
                "snr_db": round(self.config.rf.nominal_snr_db, 1),
                "is_occluded": rf_meta["is_occluded"],
                "has_multipath": rf_meta["has_multipath"],
                "los_distance_m": round(rf_meta["los_distance_m"], 2),
                "nlos_paths": rf_meta["nlos_paths"]
            },
            "hardware": {
                "mode": self.config.sdr.receiver_mode,
                "lo_freq_hz": float(receiver_lo),
                "in_band": bool(in_band),
                "phase_coherence_ok": bool(coherence_ok),
                "snapshots_used": sampling_meta["snapshots_used"],
                "elem_powers_db": [round(float(10.0 * np.log10(max(1e-4, p))), 2) for p in elem_powers]
            },
            "dsp": {
                "burst_detected": bool(detected),
                "detected_freq_hz": float(det_freq_rf),
                "detected_freq_mhz": round(det_freq_rf / 1.0e6, 2),
                "detected_baseband_khz": round(det_f_bb / 1.0e3, 2),
                "eigenvalues": [round(float(v), 4) for v in eigvals],
                "eigenvalue_ratio": round(eig_ratio, 2),
                "gate_status": gate_meta["status"],
                "is_accepted": bool(gate_ok),
                "est_compensated_deg": round(est_comp_deg, 2),
                "est_static_deg": round(est_static_deg, 2),
                "accepted_track_deg": round(active_track_deg, 2),
                "error_comp_deg": round(err_comp, 2),
                "error_static_deg": round(err_static, 2),
                "error_track_deg": round(err_track, 2),
                # Benchmark algorithms
                "est_esprit_deg": round(est_esprit_deg, 2),
                "error_esprit_deg": round(err_esprit, 2),
                "est_pv_deg": round(est_pv_deg, 2),
                "error_pv_deg": round(err_pv, 2),
                "est_centroid_deg": round(est_centroid_deg, 2),
                "error_centroid_deg": round(err_centroid, 2),
                # Tracker diagnostics
                "tracker_state": track_state,
                "consecutive_rejections": tracker_meta["consecutive_rejections"],
                "total_rejections": tracker_meta["total_rejections"],
                "total_bursts": tracker_meta["total_bursts"],
                "nis": tracker_meta.get("nis", 0.0),
                "is_maneuvering": tracker_meta.get("is_maneuvering", False)
            }
        }

        # 16. Formulate Detailed Signal Diagnostics Payload (for Analysis tab)
        # Downsample signals slightly if needed to keep payload clean
        step_samp = max(1, len(power_env) // 150)
        diagnostics = {
            "type": "signal_diagnostics",
            "sim_time": round(sim_time, 3),
            "power_envelope": {
                "time_us": [round(float(t * 1e6 / self.config.rf.sample_rate), 1) for t in range(0, len(power_env), step_samp)],
                "power_linear": [round(float(p), 5) for p in power_env[::step_samp]],
                "threshold": round(float(p_th), 5),
                "burst_start_idx": b_start,
                "burst_end_idx": b_end
            },
            "fft_spectrum": {
                "freqs_khz": [round(float(f), 1) for f in fft_freqs_khz],
                "mag_db": [round(float(m), 2) for m in fft_mag_db],
                "peak_freq_khz": round(float(det_f_bb / 1.0e3), 2)
            },
            "music_spectrum": {
                "angles_deg": [round(float(a), 1) for a in angle_grid],
                "comp_db": [round(float(s), 2) for s in p_comp_db],
                "static_db": [round(float(s), 2) for s in p_static_db],
                "true_bearing_deg": round(true_az, 2),
                "est_comp_deg": round(est_comp_deg, 2),
                "est_static_deg": round(est_static_deg, 2)
            },
            "raw_iq_burst": {
                "time_us": [round(float(n * 1e6 / self.config.rf.sample_rate), 1) for n in range(0, min(128, active_burst.shape[1]))],
                "i_ch0": [round(float(np.real(active_burst[0, n])), 4) for n in range(0, min(128, active_burst.shape[1]))],
                "q_ch0": [round(float(np.imag(active_burst[0, n])), 4) for n in range(0, min(128, active_burst.shape[1]))]
            }
        }

        self.latest_telemetry = telemetry
        self.latest_diagnostics = diagnostics
        self.telemetry_history.append(telemetry)
        if len(self.telemetry_history) > 2000:
            self.telemetry_history.pop(0)
        return telemetry, diagnostics

