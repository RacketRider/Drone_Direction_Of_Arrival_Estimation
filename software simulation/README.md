# EC261 — Frequency-Hopping-Aware Direction Finding for UAV Telemetry
### High-Fidelity RF Digital Twin & Interactive DSP Simulation Suite
**Affiliation:** IIIT Vadodara – International Campus Diu (IIITV-ICD)  
**Course Project:** EC261 — RF and Digital Signal Processing Systems  
**Authors:** Abhijit Prasad Mallick, Ayush Gupta, Mansi, Nihal Prakash, Ojaswi Shrivastava  

---

## 1. Overview & Research Motivation

Small unmanned aerial vehicles (UAVs) commonly employ Frequency-Hopping Spread Spectrum (FHSS) telemetry protocols—such as **ExpressLRS (ELRS)** and **TBS Crossfire**—operating across sub-GHz ISM bands:
- **433 MHz** (Telemetry Band)
- **868 MHz** (European ISM)
- **902–928 MHz** (North American ISM, 915 MHz center)

Conventional radio direction-finding (DF) systems rely on array steering vectors calibrated at a single static design frequency ($f_{ref} = 433$ MHz). When the drone hops between carrier frequencies, static estimators exhibit severe spatial manifold mismatch, resulting in significant angular bias and false bearings. Furthermore, deploying four synchronized, phase-coherent SDR receivers is cost-prohibitive. Instead, practical ground stations utilize a single RTL-SDR receiver ($2.0$ MS/s) coupled with a high-speed solid-state RF switch (**Analog Devices HMC241 SP4T**), controlled by an **ESP32 microcontroller**.

Because physical SDR and RF hardware are currently unavailable, this project implements a **pure software simulation**: a mathematically rigorous, physically informed interactive digital twin of the entire RF direction-finding system.

---

## 2. Key System Capabilities

- **3D Physical World Engine (Three.js / React Three Fiber):**
  - 120m × 120m tactical arena with ground station at $(0, 0, 0)$.
  - 4 UAV flight trajectories: Figure-Eight (Lemniscate), S-Curve Slalom, Circular 360° Orbit, Waypoint Path.
  - **Analytical 3D Swept-Segment Obstacle Avoidance:** Enforces a strict 3.0m clearance buffer around concrete buildings (Building Alpha & Beta) via continuous Cyrus-Beck/slab tests and visibility-graph waypoint replanning with critically damped 2nd-order dynamic tracking.
  - Realistic concrete buildings with line-of-sight (LOS) occlusion checks and Image Source Method specular multipath ray tracing.
  - Expanding frequency-coded spherical RF wavefronts (433 MHz cyan, 868 MHz amber, 915 MHz emerald).
- **High-Performance Python DSP Engine & Comparative Estimators:**
  - Sliding-window power envelope burst detector ($P[n] = I^2[n] + Q^2[n]$).
  - Radix-2 FFT hop identifier with differential phase fine-tuning ($< 10$ Hz precision).
  - Proposed A2 Dynamic Frequency-Compensated Array Manifold $a(f_k, \theta)$ vs Static Legacy 433 MHz baseline.
  - Hermitian sample covariance matrix $R_{xx} = \frac{1}{N} X X^H$.
  - Hermitian Eigenvalue Decomposition (EVD) with descending eigenvalue sort.
  - Multipath Reliability Gate: $\gamma = \lambda_1 / \lambda_2 \ge \gamma_{th} = 8.0 \implies$ `ACCEPT` / `REJECT` / `HOLD LAST VERIFIED TRACK`.
  - Vectorized Circular MUSIC pseudospectrum across $[-180^\circ, +180^\circ]$.
  - **Beamspace Phase-Mode UCA-ESPRIT:** Bessel mode harmonic transformation $j^m J_m(kr)$ synthesizing virtual shift-invariant linear array manifolds.
  - **Switched-Beam Power-Vector ML Estimator:** Maximum-likelihood direction finding and power-weighted centroid from sequential dwell vectors.
  - **Adaptive Kalman Filter:** Continuous acceleration process noise covariance $Q(q, \Delta t)$, $\chi^2$ Normalized Innovation Squared (NIS) gating, and automatic $4.0\times Q$ maneuver detection.
- **Electromagnetic Wave Propagation & Multi-Radar Triangulation Lab:**
  - **2D TMz Yee-Grid FDTD:** Conductive dielectric wave scattering with absorbing boundary conditions and HTML5 canvas field map visualization.
  - **3D Vector Maxwell FDTD:** Computes all 6 coupled field components ($E_x, E_y, E_z, H_x, H_y, H_z$) with verified Courant stability ($C \le 0.95$).
  - **Complex Material Impedance Model:** Realistic concrete permittivity ($\varepsilon_r = 5.50$), conductivity ($\sigma = 0.020$ S/m), loss tangent ($0.030$), intrinsic impedance ($\eta = 160.6\ \Omega$), and Fresnel reflection ($|\Gamma| = 40.8\%$).
  - **Multi-Radar Ground Station Triangulation:** Orthogonal projection least squares solving multi-bearing intersections with GDOP condition analysis.
- **Virtual Switched-SDR Hardware Simulation:**
  - **Mode A:** Ideal simultaneous 4-channel coherent receiver (baseline ground truth).
  - **Mode B:** Single RTL-SDR sequential switched receiver (HMC241 SP4T + ESP32 schedule, settling transients, temporal carrier phase de-rotation $e^{-j 2\pi f_{BB} \Delta t_m}$, and phase coherence validation).
- **Interactive Aerospace Web Dashboard (Next.js 14 + Tailwind CSS):**
  - **3D Mission Control:** 65% Interactive 3D Viewport with safety envelope wireframes, collision indicators, and 35% Telemetry, 360° Azimuth Compass Rose, and Mission Control.
  - **Signal Analysis Panel:** IQ waveforms, power envelope, FFT spectrum, MUSIC overlays, eigenvalues.
  - **EM & Multi-Radar Lab:** Interactive 2D wavefield canvas, 3D Vector Maxwell status, complex material impedance metrics, and live multi-station triangulation solver.
  - **Automated Experiment Laboratory:** Presets A through H, parameter sweeps, CSV/JSON reporting, and one-click OpenPyXL styled `.xlsx` flight workbook export.

---

## 3. Architecture & Tech Stack

```
ec261-uav-simulation/
├── backend/
│   ├── simulation/     # Clock, UAV dynamics, trajectories, arena environment, collision, obstacle_avoidance, multiradar
│   ├── rf/             # FHSS hopping, baseband signals, path loss, multipath, AWGN, em_solver (2D FDTD), em_solver_3d
│   ├── hardware/       # 4-element UCA, HMC241 SP4T switch, RTL-SDR tuner, sampling
│   ├── dsp/            # Burst detection, FFT hop ID, steering, covariance, EVD, gate, MUSIC, esprit, power_vector, tracker
│   ├── experiments/    # Presets A-H, batch runner, metrics calculation, CSV/JSON export
│   ├── validation/     # Benchmarks and numerical tests
│   └── api/            # FastAPI REST & WebSocket server, export_excel
├── frontend/
│   ├── src/app/        # Next.js App Router (Mission Control, Analysis, Experiment Lab, EM & Multi-Radar Lab)
│   ├── src/components/ # React Three Fiber 3D Scene, Telemetry panels, Controls, Recharts, EMMaxwellLabPanel
│   └── src/hooks/      # WebSocket client bridge
├── docs/               # In-depth technical specifications and mathematical documentation
└── tests/              # 38 automated unit and integration tests (Pytest)
```

---

## 4. Quick Start & Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Node.js 18+ and npm

### Step 1: Backend Setup & Launch
```bash
# In project root:
# 1. Activate virtual environment
.venv\Scripts\activate   # On Windows
# source .venv/bin/activate # On Linux/macOS

# 2. Run backend test suite (38 automated tests)
pytest -v

# 3. Start FastAPI server with live WebSocket broker
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API is now running at `http://localhost:8000` with interactive Swagger docs at `http://localhost:8000/docs`.

### Step 2: Frontend Setup & Launch
```bash
# In a separate terminal, navigate to frontend:
cd frontend

# Start Next.js development server
npm run dev
```
Open your browser to `http://localhost:3000` to access the interactive Mission Control Suite!

