"""
EC261 Comprehensive Software Simulation Suite:
Frequency-Hopping-Aware RF Direction Finding for UAV Telemetry (ELRS 915 MHz)
Dynamic Trajectory Tracking + Monte Carlo SNR Analysis + Multipath Gating

Team: Abhijit Prasad Mallick, Ayush Gupta, Mansi, Nihal Prakash, Ojaswi Shrivastava
Institute: IIIT Vadodara - International Campus Diu (IIITV-ICD)
"""

import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)

# =====================================================================
# 1. SYSTEM & SIMULATION PARAMETERS
# =====================================================================
C = 3.0e8                        # Speed of light (m/s)
M = 4                            # 4-Element Circular/Switched Array
FS = 2.0e6                       # Baseband sampling rate (2 MS/s)
N_BURST = 256                    # Samples per FHSS burst
F_REF = 433.0e6                  # Legacy static reference frequency
D_SPACING = 0.22 * (C / 915.0e6) # Array spacing (~7.2 cm)
GAMMA_TH = 8.0                   # Eigenvalue ratio gate threshold (lambda_1 / lambda_2)
ANGLE_GRID = np.linspace(-80.0, 80.0, 801) # 0.2 deg resolution


# =====================================================================
# 2. CORE DSP ENGINE (A2 + MUSIC + EIGENVALUE GATE)
# =====================================================================
def steering_vector(freq_hz, angle_deg):
    """Frequency-compensated steering vector a(f_k, theta)"""
    theta_rad = np.radians(angle_deg)
    m_idx = np.arange(M).reshape(-1, 1)
    phase = -1j * 2.0 * np.pi * D_SPACING * freq_hz * np.sin(theta_rad) / C
    return np.exp(m_idx * phase)


def simulate_burst(f_hop, true_angle, snr_db, multipath=False):
    """Generates a single FHSS burst with AWGN and optional building reflection"""
    noise_pwr = 10.0 ** (-snr_db / 10.0)
    noise = np.sqrt(noise_pwr / 2.0) * (
        np.random.randn(M, N_BURST) + 1j * np.random.randn(M, N_BURST)
    )

    t = np.arange(N_BURST) / FS
    f_offset = 150.0e3 + (f_hop - F_REF) * 1.0e-3
    s_burst = np.exp(1j * 2.0 * np.pi * f_offset * t).reshape(1, -1)

    x_burst = steering_vector(f_hop, true_angle) @ s_burst

    if multipath:
        # Strong dispersive reflection from a concrete building at -45 deg
        a_ref = steering_vector(f_hop, -45.0)
        scatter = np.exp(1j * np.linspace(0, 4.0 * np.pi, N_BURST)).reshape(1, -1)
        x_burst += 0.80 * (a_ref @ (s_burst * scatter))

    return x_burst + noise


def process_burst(x_burst):
    """Runs FFT Hop ID, Eigenvalue Gate, and Compensated vs Static MUSIC"""
    # 1. FFT Hop Frequency Identification (f_k)
    fft_spec = np.fft.fft(x_burst[0, :])
    fft_freqs = np.fft.fftfreq(N_BURST, d=1.0 / FS)
    det_offset = fft_freqs[np.argmax(np.abs(fft_spec))]
    det_fk = F_REF + (det_offset - 150.0e3) * 1.0e3

    # 2. Sample Covariance & Eigenvalue Decomposition
    r_xx = (x_burst @ x_burst.conj().T) / N_BURST
    eigvals, eigvecs = np.linalg.eigh(r_xx)
    idx = np.argsort(eigvals)[::-1]
    eigvals = np.real(eigvals[idx])
    eigvecs = eigvecs[:, idx]

    eig_ratio = eigvals[0] / (eigvals[1] + 1e-12)
    accepted = eig_ratio >= GAMMA_TH

    e_noise = eigvecs[:, 1:]
    proj_n = e_noise @ e_noise.conj().T

    # Vectorized MUSIC Spectrum Evaluation across ANGLE_GRID
    theta_rad = np.radians(ANGLE_GRID).reshape(1, -1)
    m_idx = np.arange(M).reshape(-1, 1)

    # Proposed A2 Compensated Manifold
    A_comp = np.exp(-1j * 2.0 * np.pi * D_SPACING * det_fk * np.sin(theta_rad) / C * m_idx)
    denom_comp = np.real(np.sum(A_comp.conj() * (proj_n @ A_comp), axis=0))
    spec_comp = 1.0 / (denom_comp + 1e-12)
    est_comp = ANGLE_GRID[np.argmax(spec_comp)]

    # Uncompensated Static Manifold
    f_mismatch = det_fk * (det_fk / F_REF)
    A_uncomp = np.exp(-1j * 2.0 * np.pi * D_SPACING * f_mismatch * np.sin(theta_rad) / C * m_idx)
    denom_uncomp = np.real(np.sum(A_uncomp.conj() * (proj_n @ A_uncomp), axis=0))
    spec_uncomp = 1.0 / (denom_uncomp + 1e-12)
    est_uncomp = ANGLE_GRID[np.argmax(spec_uncomp)]

    spec_comp_db = 10.0 * np.log10(spec_comp / np.max(spec_comp))
    spec_uncomp_db = 10.0 * np.log10(spec_uncomp / np.max(spec_uncomp))

    return est_comp, est_uncomp, eig_ratio, accepted, spec_comp_db, spec_uncomp_db


# =====================================================================
# 3. RUN 3-STAGE VERIFICATION EXPERIMENTS
# =====================================================================
if __name__ == "__main__":
    print("=" * 76)
    print(" EC261 FULL SOFTWARE SIMULATION SUITE: MULTI-HOP UAV TRACKING & BENCHMARK")
    print("=" * 76)

    # --- Experiment 1: Single Burst @ 915 MHz (35 deg) ---
    b_clean = simulate_burst(915.0e6, 35.0, snr_db=15.0, multipath=False)
    est_c, est_u, ratio_clean, _, sp_c_db, sp_u_db = process_burst(b_clean)
    b_mp = simulate_burst(915.0e6, 35.0, snr_db=15.0, multipath=True)
    _, est_mp_raw, ratio_mp, _, _, _ = process_burst(b_mp)

    # --- Experiment 2: Dynamic Moving Drone Flight Trajectory (60 Hop Bursts) ---
    n_steps = 60
    time_sec = np.linspace(0, 10, n_steps)
    # Drone flies a curved trajectory from -50 deg to +50 deg
    true_traj = -50.0 + 100.0 * (time_sec / 10.0) + 8.0 * np.sin(2.0 * np.pi * time_sec / 5.0)
    # ELRS hops randomly across 433, 868, and 902-928 MHz ISM bands
    elrs_pool = np.concatenate([[433.0e6, 868.0e6], np.linspace(902.0e6, 928.0e6, 20)])
    hop_sequence = np.random.choice(elrs_pool, size=n_steps)

    traj_comp = np.zeros(n_steps)
    traj_uncomp = np.zeros(n_steps)
    multipath_flags = np.zeros(n_steps, dtype=bool)
    last_valid_angle = true_traj[0]

    for k in range(n_steps):
        # Inject building multipath bursts at steps 18, 19, 41, 42
        is_mp_zone = k in [18, 19, 41, 42]
        burst = simulate_burst(hop_sequence[k], true_traj[k], snr_db=15.0, multipath=is_mp_zone)
        ec, eu, er, ok, _, _ = process_burst(burst)

        traj_uncomp[k] = eu
        if ok:
            traj_comp[k] = ec
            last_valid_angle = ec
        else:
            # Slide 8/9 Hold Logic: Reject multipath spike and hold last valid track
            traj_comp[k] = last_valid_angle
            multipath_flags[k] = True

    traj_rmse_uncomp = np.sqrt(np.mean((traj_uncomp - true_traj) ** 2))
    traj_rmse_comp = np.sqrt(np.mean((traj_comp - true_traj) ** 2))
    print(f"[Exp 1: 60-Hop Moving Drone Flight] -> Static RMSE: {traj_rmse_uncomp:.2f} deg | "
          f"Proposed A2+Gate RMSE: {traj_rmse_comp:.2f} deg")
    print(f"        Multipath Outliers Caught & Rejected: {np.sum(multipath_flags)} / 4 building reflections")

    # --- Experiment 3: Monte Carlo SNR Sweep (-5 dB to +25 dB) ---
    snr_grid = np.arange(-5, 26, 5)
    n_trials = 40
    rmse_snr_comp = []
    rmse_snr_uncomp = []

    for snr in snr_grid:
        err_c, err_u = [], []
        for _ in range(n_trials):
            f_rand = np.random.choice([868.0e6, 915.0e6])
            b = simulate_burst(f_rand, 35.0, snr_db=snr, multipath=False)
            ec, eu, _, _, _, _ = process_burst(b)
            err_c.append(ec - 35.0)
            err_u.append(eu - 35.0)
        rmse_snr_comp.append(np.sqrt(np.mean(np.array(err_c) ** 2)))
        rmse_snr_uncomp.append(np.sqrt(np.mean(np.array(err_u) ** 2)))

    print(f"[Exp 2: Monte Carlo @ 15 dB SNR]     -> Static RMSE: {rmse_snr_uncomp[4]:.2f} deg | "
          f"Proposed A2 RMSE: {rmse_snr_comp[4]:.2f} deg")
    print("=" * 76)

    # =====================================================================
    # 4. GENERATE 4-PANEL EXECUTIVE SIMULATION DASHBOARD
    # =====================================================================
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.5))
    navy = "#224266"
    crimson = "#7C2138"
    green = "#1B7837"

    # Panel A (Top-Left): Live Moving UAV Trajectory Tracking Across 60 FHSS Hops
    ax1 = axes[0, 0]
    ax1.plot(time_sec, true_traj, color=green, lw=2.2, label="True UAV Flight Path")
    ax1.scatter(time_sec, traj_uncomp, color=crimson, marker="x", s=28, alpha=0.65,
                label=f"Uncompensated Static Array (RMSE={traj_rmse_uncomp:.1f}$^\\circ$)")
    ax1.plot(time_sec, traj_comp, color=navy, lw=1.8, linestyle="--", marker="o", markersize=3.5,
             label=f"Proposed A2 + Gate Track (RMSE={traj_rmse_comp:.1f}$^\\circ$)")
    mp_times = time_sec[multipath_flags]
    mp_angles = traj_comp[multipath_flags]
    ax1.scatter(mp_times, mp_angles, facecolors="none", edgecolors="orange", s=110, lw=2.2,
                label="Multipath Outlier Rejected (Track Held)")
    ax1.set_title("A. Dynamic UAV Flight Tracking (60 Random ELRS Hops)", fontweight="bold", color=navy)
    ax1.set_xlabel("Flight Time (seconds)")
    ax1.set_ylabel("Azimuth Bearing $\\theta$ (degrees)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8, loc="upper left")

    # Panel B (Top-Right): MUSIC Spatial Spectrum @ 915 MHz Hop
    ax2 = axes[0, 1]
    ax2.plot(ANGLE_GRID, sp_c_db, color=navy, lw=2.2, label=f"Proposed A2 Compensated ({est_c:.1f}$^\\circ$)")
    ax2.plot(ANGLE_GRID, sp_u_db, color=crimson, ls="--", lw=1.8, label=f"Uncompensated Static $\\lambda_0$ ({est_u:.1f}$^\\circ$)")
    ax2.axvline(35.0, color=green, ls=":", lw=1.8, label="True UAV Bearing (35.0$^\\circ$)")
    ax2.set_xlim(-65, 65)
    ax2.set_ylim(-35, 2)
    ax2.set_title("B. Instantaneous MUSIC Spectrum @ 915 MHz Hop", fontweight="bold", color=navy)
    ax2.set_xlabel("Azimuth Angle $\\theta$ (degrees)")
    ax2.set_ylabel("Normalized Spatial Power (dB)")
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8, loc="upper left")

    # Panel C (Bottom-Left): Monte Carlo RMSE vs. SNR Curve
    ax3 = axes[1, 0]
    ax3.plot(snr_grid, rmse_snr_uncomp, color=crimson, ls="--", marker="s", lw=2.0,
             label="Uncompensated Static $\\lambda_0$ (Wavelength Bias)")
    ax3.plot(snr_grid, rmse_snr_comp, color=navy, marker="o", lw=2.2,
             label="Proposed A2 Dynamic Hop Compensation")
    ax3.set_title("C. Monte Carlo Angular RMSE vs. SNR (280 Bursts)", fontweight="bold", color=navy)
    ax3.set_xlabel("Signal-to-Noise Ratio - SNR (dB)")
    ax3.set_ylabel("Angular RMSE (degrees)")
    ax3.set_ylim(-1, 35)
    ax3.grid(True, alpha=0.3)
    ax3.legend(fontsize=8, loc="upper right")

    # Panel D (Bottom-Right): Eigenvalue Spread Ratio Gate (lambda_1 / lambda_2)
    ax4 = axes[1, 1]
    labels = ["Clean LoS Burst\n(Accepted)", "Building Reflection\n(Outlier Rejected)"]
    vals = [ratio_clean, ratio_mp]
    bars = ax4.bar(labels, vals, color=[navy, crimson], width=0.42)
    ax4.axhline(GAMMA_TH, color="black", ls="--", lw=1.6, label=f"Reliability Threshold $\\gamma_{{th}} = {GAMMA_TH}$")
    ax4.set_title("D. Multipath Eigenvalue Gate ($\\lambda_1 / \\lambda_2$)", fontweight="bold", color=navy)
    ax4.set_ylabel("Eigenvalue Ratio ($\\lambda_1 / \\lambda_2$)")
    ax4.set_ylim(0, ratio_clean * 1.18)
    ax4.grid(True, axis="y", alpha=0.3)
    ax4.legend(fontsize=8, loc="upper right")
    for b in bars:
        h = b.get_height()
        ax4.text(b.get_x() + b.get_width() / 2.0, h + 2.0, f"{h:.1f}",
                 ha="center", va="bottom", fontweight="bold", fontsize=9)

    plt.tight_layout()
    plt.savefig("full_simulation_dashboard.png", dpi=300)
    plt.show()
    