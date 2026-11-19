# Academic Experiment Protocols & Benchmark Scenarios
## EC261: Validation and Verification of Research Presets

### 1. Overview of Automated Presets

The simulation suite includes 8 pre-configured experiment presets designed for reproducible research and viva demonstration:

| Preset | Title | Independent Variable | Tested Values | Primary Research Question |
|:---|:---|:---|:---|:---|
| **A** | **Frequency Hopping Comparison** | Carrier Frequency $f_k$ | 433, 868, 915, 928 MHz, Dynamic FHSS | Does Proposed A2 dynamic compensation eliminate frequency-dependent DoA error compared to static 433 MHz baseline? |
| **B** | **SNR Sensitivity Sweep** | Signal-to-Noise Ratio (dB) | -5, 0, 5, 10, 15, 20, 30 dB | What is the threshold SNR where burst detection breaks down and eigenvalue spread collapses? |
| **C** | **Building Occlusion Transition** | UAV Flight Path | S-Curve Slalom vs Figure-Eight | How effectively does the system maintain tracking continuity during sudden building blockage? |
| **D** | **Multipath Reflection Severity** | Reflection Factor $\alpha$ | 0.0, 0.2, 0.4, 0.6, 0.85, 1.0 | At what reflection strength does the Reliability Gate ($\gamma \ge 8.0$) transition from ACCEPT to REJECT? |
| **E** | **Antenna Switching Coherence** | Receiver Mode | Mode A (Simultaneous), Mode B (De-rotated), Mode B (Uncompensated) | How much angular RMSE degradation occurs when transitioning from ideal 4-channel to single-SDR switched? |
| **F** | **Array Calibration Impairments** | Phase Mismatch $\Delta\psi$ | 0°, 5°, 10°, 15°, 20° | How sensitive is the 4-element circular manifold to uncalibrated RF cable lengths and phase drift? |
| **G** | **UAV Speed & Tracking Lag** | Flight Speed Multiplier | 0.5x, 1.0x, 2.0x, 3.0x | Does a Circular Kalman Filter provide lower tracking lag than a standard Gated Hold state machine? |
| **H** | **Receiver Acquisition Failure** | SDR LO Tuning Mode | SYNCHRONOUS vs STATIC_LO | Demonstrates physical out-of-band rejection when a narrowband SDR fails to retune to the active hop. |

---

### 2. Evaluated Metrics
For each trial, the following research metrics are computed:
1. **Angular RMSE (Root Mean Square Error):**
   $$\text{RMSE} = \sqrt{\frac{1}{N_{bursts}} \sum_{i=1}^{N_{bursts}} (\Delta\theta_i)^2}$$
2. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{N_{bursts}} \sum_{i=1}^{N_{bursts}} |\Delta\theta_i|$$
3. **Median Angular Error:** Robust against extreme outliers.
4. **Multipath Rejection Rate (Sensitivity):** Percentage of multipath-corrupted bursts correctly rejected by the gate ($\gamma < 8.0$).
5. **False Rejection Rate (Fallout):** Percentage of clean LoS bursts falsely rejected due to noise or low SNR.
6. **Track Availability (%):** Fraction of bursts where the receiver maintains an active, verified track.
7. **Processing Latency (ms):** Mean DSP computation time per burst.

---

### 3. Data Exporting & Reproducibility
- All experiments record the deterministic PRNG seed (default `42`).
- Results can be exported directly from the browser UI or CLI to formatted JSON and CSV files.
- **Scientific OpenPyXL Telemetry Workbook (`.xlsx`):** A dedicated endpoint `/api/export.xlsx` allows one-click export of rolling telemetry frames, comparative estimator readouts (MUSIC, ESPRIT, Power ML, Centroid), Kalman innovations, and avoidance event logs with frozen headers and auto-filters.

