# Drone Direction of Arrival (DoA) Estimation Digital Twin & Research Suite

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14.2-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688.svg)](https://fastapi.tiangolo.com/)
[![Three.js](https://img.shields.io/badge/Three.js-r164-orange.svg)](https://threejs.org/)
[![Tests Passing](https://img.shields.io/badge/Tests-40%20Passed-brightgreen.svg)]()
[![Paper PDF](https://img.shields.io/badge/Paper-IEEE%20Format-red.svg)](paper_source_and_simulation_code/latex_source/main.pdf)

> **A Switched-Interferometric Receiver Architecture with Frequency-Compensated Subspace Processing for Direction Finding of Sub-GHz Frequency-Hopping UAV Telemetry**  
> *Abhijit Mallick, Dr. J. S. Bhat*  
> **Indian Institute of Information Technology Vadodara – International Campus Diu (IIITV-ICD)**  
> *Target Publication: IEEE Transactions on Aerospace and Electronic Systems*

---

## 📖 Comprehensive Documentation Links

- 📄 **[Research Paper PDF (`main.pdf`)](paper_source_and_simulation_code/latex_source/main.pdf)**: Complete 7-page IEEE journal manuscript.
- 📑 **[Page-by-Page Paper Guide & Walkthrough (`RESEARCH_PAPER_PAGE_BY_PAGE_GUIDE.md`)](RESEARCH_PAPER_PAGE_BY_PAGE_GUIDE.md)**: Exhaustive breakdown of what is on every page (Pages 1 to 7), mathematical intuition for every equation, figures, tables, and embedded ARM Cortex-A72 execution profile.
- 💻 **[Digital Twin Web Dashboard](software%20simulation/)**: Interactive 3D Mission Control, Signal Diagnostics, Experiment Lab, and EM & Multi-Radar Localization Lab.

---

## 🎯 Executive Overview

Modern commercial and custom uncrewed aerial vehicles (UAVs / drones) predominantly utilize long-range Command and Control (C2) and telemetry links operating under **ExpressLRS (ELRS)**, **Crossfire (CRSF)**, or **LoRa**. These links hop rapidly across sub-GHz industrial bands (**433 MHz, 868 MHz, 915 MHz, 928 MHz**) at rates up to 500 hops/second.

Traditional Direction of Arrival (DoA) systems rely on multi-channel phase-coherent receivers (e.g. USRP X310, KerberosSDR) costing over $2,000, requiring significant size, weight, and power (SWaP), and demanding continuous inter-channel calibration.

This project introduces a **single-channel switched-interferometric direction finding architecture** powered by an inexpensive **RTL-SDR v4** ($<\$35$) and a high-speed **GaAs SP4T RF switch (HMC241)** connected to a 4-element Uniform Circular Array (UCA, $r = 7.2$ cm).

```
                      +------------------------------------------------+
                      |       4-Element UCA Antenna Array (r=7.2 cm)   |
                      |          (1)       (2)       (3)       (4)     |
                      +-----------+---------+---------+---------+------+
                                  |         |         |         |
                                  v         v         v         v
                      +------------------------------------------------+
                      |         HMC241 GaAs SP4T RF Switch (fsw=62.5 kHz)|
                      +-----------------------+------------------------+
                                              | (Single RF Channel)
                                              v
                      +------------------------------------------------+
                      |       Single-Channel RTL-SDR v4 (Fs = 2.0 MS/s)|
                      +-----------------------+------------------------+
                                              | Raw I/Q Stream
                                              v
                      +------------------------------------------------+
                      | Moving-Average Energy Burst Detection (Eq. 3)  |
                      +-----------------------+------------------------+
                                              | Burst Slices
                                              v
                      +------------------------------------------------+
                      | Coarse 512-pt FFT + Lag-M Refinement (Eq. 5)   |
                      +-----------------------+------------------------+
                                              | Fine Offset \hat{f}_\Delta
                                              v
                      +------------------------------------------------+
                      | Baseband Inter-Element Phase De-rotation (Eq.6)|
                      +-----------------------+------------------------+
                                              | Synthetic Snapshots X
                                              v
                      +------------------------------------------------+
                      | Sample Covariance R_xx (Eq. 9) & Jacobi EVD    |
                      +-----------------------+------------------------+
                                              | Ordered Eigenvalues \lambda_i
                                              v
                             [ Multipath Gate: \gamma = \lambda_1/\lambda_2 >= 8.0? ]
                                    /                           \
                              YES  /                             \  NO (Multipath Flagged)
                                  v                               v
            +------------------------------------+   +------------------------------------+
            | A2 Frequency-Compensated MUSIC     |   | Discard Corrupted Measurement      |
            | P_MUSIC(\theta, \lambda_k) (Eq. 12)|   | Coast Tracker via Prior State      |
            +-----------------+------------------+   +-----------------+------------------+
                              \                                       /
                               \                                     /
                                v                                   v
                      +------------------------------------------------+
                      | Circular Kalman Filter on S^1 Manifold (Eq.14) |
                      +-----------------------+------------------------+
                                              | Smooth Azimuth Track \hat{\theta}_k
                                              v
                      +------------------------------------------------+
                      | Multi-Station Triangulation (WLS) & 2D GDOP    |
                      +------------------------------------------------+
```

---

## ⚡ Key Research Discoveries & Benchmark Results

1. **Elimination of Frequency Mismatch**:
   - Static steering manifolds calibrated at 433 MHz exhibit up to $0.85^\circ$ angular bias when evaluated at 915 MHz.
   - Proposed **A2 dynamic manifold steering ($\lambda_k = c/f_k$)** achieves **$0.17^\circ - 0.18^\circ$ RMSE** across all sub-GHz hopping bands.
2. **Lag-$M$ Fine Frequency Refinement**:
   - Coarse FFT bin resolution ($\sim 3.9$ kHz) creates an unacceptable residual phase drift.
   - Lag-$M$ differential phase estimation across full switching cycles cancels spatial steering and resolves carrier offset to **$< 50$ Hz** (34 Hz at 30 dB SNR).
3. **Array Radius & Spatial Ambiguity Threshold**:
   - Optimal performance achieved at prototype radius **$r = 7.2$ cm** ($d/\lambda_0 = 0.31$).
   - **Catastrophic Failure Boundary**: Exceeding **$r \ge 12$ cm** ($d/\lambda \ge 0.52$) causes spatial aliasing and severe multi-lobe ambiguity ($>60^\circ$ error).
4. **Subspace Multipath Mitigation**:
   - Eigenvalue ratio gate ($\gamma = \lambda_1/\lambda_2 \ge 8.0$) detects and rejects partially correlated multipath with **$>95\%$ probability**.
   - Gated Circular Kalman Filter reduces dynamic bearing tracking RMSE from **$14.2^\circ$ down to $0.42^\circ$** with **$0.0\%$ outliers**.
5. **Embedded Real-Time Execution**:
   - Complete 8-stage DSP pipeline executes in **$345\ \mu\text{s}$ (0.35 ms)** per burst on an embedded **ARM Cortex-A72 (Raspberry Pi 4B)**, consuming only **17.3% of a single core** at a 500 Hz telemetry rate.

---

## 📂 Repository Directory Layout

```
Drone_Direction_Of_Arrival_Estimation/
├── .gitignore                                      # Clean repository exclusions
├── README.md                                       # Primary repository manual & architecture
├── RESEARCH_PAPER_PAGE_BY_PAGE_GUIDE.md            # Comprehensive page-by-page research paper guide
├── run_simulation.bat                              # One-click Windows launch script
│
├── paper_source_and_simulation_code/
│   ├── latex_source/
│   │   ├── IEEEtran.cls                            # Official IEEE Transactions LaTeX class
│   │   ├── main.tex                                # 7-page authoritative IEEE manuscript source
│   │   ├── main.pdf                                # Compiled 7-page PDF with boxed equations
│   │   ├── nums.tex                                # Centralized publication metrics
│   │   ├── tab_gate.tex, tab_hops.tex, tab_track.tex # LaTeX table source files
│   │   └── figs/                                   # High-resolution vector PDF and raster figures
│   │       ├── fig_bias.pdf                        # Fig 3: Manifold mismatch & radius aliasing
│   │       ├── fig_dashboard.png                   # Fig 2: Digital twin simulation UI
│   │       ├── fig_rmse.pdf                        # Fig 4: Multi-receiver RMSE & freq error vs SNR
│   │       ├── fig_gate.pdf                        # Fig 5: Eigenvalue gate & coherence sweep
│   │       └── fig_trkgdop.pdf                     # Fig 6: Bearing tracking & 2D GDOP map
│   │
│   └── simulation_code/
│       ├── sim_core.py                             # Core DSP routines (MUSIC, Jacobi, Lag-M)
│       ├── run_main.py, run_more.py, run_track.py  # Reproduction batch runners
│       ├── make_figs.py, gen_tables.py             # Publication figure and table generators
│       └── res_main.json, res_more.json            # Publication datasets
│
└── software simulation/
    ├── backend/
    │   ├── api/
    │   │   ├── main.py                             # FastAPI REST & WebSocket server
    │   │   ├── schemas.py                          # Pydantic schemas
    │   │   └── export_excel.py                     # Styled multi-sheet Excel generator
    │   ├── dsp/
    │   │   ├── music.py                            # Spectral MUSIC & spatial pseudospectrum
    │   │   ├── eigenvalue_gate.py                  # \gamma = \lambda_1/\lambda_2 decision logic
    │   │   ├── frequency_estimation.py             # FFT + Lag-M differential phase refinement
    │   │   └── tracker.py                          # Circular Kalman Filter on S^1
    │   ├── rf/
    │   │   ├── em_solver.py, em_solver_3d.py       # FDTD Yee-grid Maxwell solvers & ray-tracer
    │   │   └── materials.py                        # ITU-R P.833 / complex permittivity library
    │   ├── simulation/
    │   │   ├── engine.py, multiradar.py            # Authoritative simulation loop & 3-station WLS
    │   │   └── configuration.py                    # Physical parameters (UCA, HMC241, RTL-SDR)
    │   └── experiments/
    │       ├── scenarios.py                        # Presets A through K (including Fig 3-5 sweeps)
    │       ├── runner.py, metrics.py               # Batch Monte Carlo execution engine
    │       └── data/paper_benchmarks.json          # Precomputed IEEE paper benchmark dataset
    │
    ├── frontend/
    │   ├── src/
    │   │   ├── app/page.tsx, layout.tsx            # Next.js 14 App Router UI
    │   │   ├── components/scene/                   # Three.js / React Three Fiber 3D viewport
    │   │   │   ├── SceneViewport.tsx, AntennaArray3D.tsx, Quadcopter3D.tsx, ForestTrees3D.tsx
    │   │   ├── components/panels/                  # Aerospace telemetry panels
    │   │   │   ├── ExperimentLabPanel.tsx          # Dual-mode publication & batch simulator
    │   │   │   ├── SignalAnalysisPanel.tsx         # Real-time IQ, FFT, MUSIC pseudospectrum
    │   │   │   └── EMMaxwellLabPanel.tsx           # FDTD fields, 2D GDOP, and multi-radar fixes
    │   │   └── hooks/useSimulationWebSocket.ts     # Resilient 20 Hz WebSocket hook
    │   ├── package.json, tsconfig.json             # TypeScript & Tailwind configurations
    │   └── tailwind.config.ts
    │
    └── tests/                                      # Automated test suite (40 Pytest suites)
        ├── test_dsp_pipeline.py, test_uca_manifold.py, test_switched_sdr.py
        ├── test_em_solvers.py, test_api_endpoints.py, test_experiment_runner.py
        └── test_multiradar_and_export.py
```

---

## 🚀 Quick Start Guide

### Option 1: One-Click Startup (Windows)
Double-click `run_simulation.bat` in the repository root, or open PowerShell:
```powershell
.\run_simulation.bat
```
This automatically starts:
- **Backend API**: `http://localhost:8000` (FastAPI + WebSocket)
- **Frontend Dashboard**: `http://localhost:3000` (Next.js Aerospace UI)

---

### Option 2: Manual Terminal Startup

#### 1. Start the Python Backend
```bash
cd "software simulation"
# Activate your virtual environment (or create one: python -m venv .venv)
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Start the Next.js Frontend
```bash
cd "software simulation/frontend"
npm install
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

### Option 3: Running Automated Test Suites
Run the exhaustive unit and integration test suite:
```bash
cd "software simulation"
.\.venv\Scripts\activate
pytest tests/ -v
```
*Result: 40 tests passed covering DSP algorithms, circular phase wrapping, FDTD solvers, and REST endpoints.*

---

## 📊 Reproducing Research Paper Figures & Tables

To regenerate all numerical results, tables, and publication figures from scratch:
```bash
cd "paper_source_and_simulation_code/simulation_code"
python run_main.py      # Computes Table I and Fig 4 SNR curves
python run_more.py      # Computes Fig 3 manifold sweeps and Fig 5 gate breakdown
python run_track.py     # Generates Fig 6 dynamic tracking and GDOP contours
python make_figs.py     # Renders vector PDFs in latex_source/figs/
python gen_tables.py    # Generates formatted LaTeX tables
```

To recompile the research paper PDF:
```bash
cd "paper_source_and_simulation_code/latex_source"
pdflatex main.tex
pdflatex main.tex
```

---

## 📜 Citation & Academic Attribution

If you use this work, the digital twin simulation suite, or the mathematical derivations in your research, please cite:

```bibtex
@article{mallick2026switched,
  title={A Switched-Interferometric Receiver Architecture with Frequency-Compensated Subspace Processing for Direction Finding of Sub-GHz Frequency-Hopping UAV Telemetry},
  author={Mallick, Abhijit and Bhat, J. S.},
  journal={IEEE Transactions on Aerospace and Electronic Systems},
  year={2026},
  note={Under review}
}
```

---

## ⚖️ License & Acknowledgements
- Developed at the **Indian Institute of Information Technology Vadodara – International Campus Diu**.
- Dedicated to advancing open-source counter-UAS (C-UAS) radio direction finding and spectral safety.
