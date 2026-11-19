# Comprehensive Page-by-Page Guide & Mathematical Walkthrough
## *A Switched-Interferometric Receiver Architecture with Frequency-Compensated Subspace Processing for Direction Finding of Sub-GHz Frequency-Hopping UAV Telemetry*

**Authors:** Abhijit Mallick, Dr. J. S. Bhat  
**Institution:** Indian Institute of Information Technology Vadodara – International Campus Diu (IIITV-ICD)  
**Publication Target:** IEEE Transactions on Aerospace and Electronic Systems  
**Associated Repository:** [Drone_Direction_Of_Arrival_Estimation](https://github.com/RacketRider/Drone_Direction_Of_Arrival_Estimation.git)  
**Document Reference:** [`latex_source/main.pdf`](file:///c:/Users/Abhij/OneDrive/Documents/ec261/paper_source_and_simulation_code/latex_source/main.pdf) (7 pages, IEEE standard two-column format)

---

## Executive Summary & Core Engineering Breakthrough

Uncrewed Aerial Vehicles (UAVs / drones) operating rogue or unauthorized flights predominantly utilize open-source, long-range Command and Control (C2) links such as **ExpressLRS (ELRS)**, **Crossfire (CRSF)**, or **LoRa**. These protocols operate in license-exempt sub-GHz bands (**433 MHz, 868 MHz, 915 MHz**) and employ rapid **Frequency-Hopping Spread Spectrum (FHSS)** agility (up to 500 hops/second).

Traditional Direction of Arrival (DoA) radio direction finding systems require:
1. **$M$-channel coherent receivers** (e.g., USRP X310, KerberosSDR) with $M$ synchronized tuners, mixers, and ADCs.
2. High cost ($>\$2,000$), substantial size, weight, and power (SWaP), and cumbersome continuous phase/gain calibration hardware.

**Our Proposed Solution:**
A **single-channel switched-interferometric receiver** utilizing a standard **RTL-SDR v4** ($<\$35$) coupled to a 4-element Uniform Circular Array (UCA, radius $r = 7.2$ cm) through an ultra-fast **GaAs SP4T RF switch (HMC241)**. By switching sequentially through antenna elements during each incoming packet burst, the system reconstructs a synthetic spatial covariance matrix. 

The paper develops three fundamental innovations to overcome the physical limitations of switched SDR direction finding:
1. **Lag-$M$ Fine Frequency Refinement & Phase De-Rotation**: Eliminates inter-element switching phase skew without requiring external RF reference generators.
2. **Frequency-Agile Manifold Steering ($\lambda_k$-Compensation)**: Dynamically recalculates the array steering vector at every hop frequency $f_k \in [430, 928]$ MHz, preventing manifold mismatch bias.
3. **Subspace Multipath Eigenvalue Gate ($\gamma = \lambda_1/\lambda_2$)**: Exploits the rank inflation of the spatial covariance matrix to detect and reject non-line-of-sight (NLoS) multipath reflections before feeding clean bearings into a Circular Kalman Filter.

---

## Detailed Page-by-Page Breakdown

```
+---------------------------------------------------------------------------------------------------+
| PAGE 1: Foundations & Architecture                                                                |
| - Header & Abstract | Section I: Intro & Challenges | Section II: Switched Array Signal Model     |
+---------------------------------------------------------------------------------------------------+
| PAGE 2: Hardware Topology & Frequency Recovery                                                    |
| - Section II-B: GaAs Switch & Timing | Section III-A: Coarse FFT + Lag-M Differential Refinement  |
+---------------------------------------------------------------------------------------------------+
| PAGE 3: The Mathematical Engine                                                                   |
| - Section III-B: Dynamic Manifold | III-C: Sample Covariance | III-D: Eigenvalue Gate             |
| - Section III-E: A2 MUSIC Pseudospectrum | Section III-F: Circular Kalman Filter on S¹           |
+---------------------------------------------------------------------------------------------------+
| PAGE 4: Digital Twin & Frequency Hopping Performance                                              |
| - Figure 2: Full Simulation Dashboard | Section IV-A: Setup | Table I: 5-Band Hopping Benchmark   |
+---------------------------------------------------------------------------------------------------+
| PAGE 5: Spatial Ambiguity Breakdown & SNR Benchmarks                                              |
| - Section IV-B: Radius Aliasing (Fig 3) | Section IV-C: 6-Receiver DoA RMSE & Freq Error (Fig 4)   |
+---------------------------------------------------------------------------------------------------+
| PAGE 6: Multipath Mitigation & Empirical Regimes                                                  |
| - Section IV-D: Gate Dynamics (Fig 5) | Table II: 6 Multipath Regimes | Table III: Tracking Table |
+---------------------------------------------------------------------------------------------------+
| PAGE 7: Dynamic Tracking, GDOP Triangulation & Real-Time DSP                                      |
| - Figure 6: Tracking Shadow & 2D GDOP Map | Section V: ARM Cortex-A72 Budget | References [1-11]  |
+---------------------------------------------------------------------------------------------------+
```

---

### Page 1: Problem Formulation, Switched Array Model & The Mathematical Foundation

#### 1. Title, Abstract & Index Terms (Top of Page 1)
- **Title**: Establishes the exact scope: switched interferometry, frequency compensation across sub-GHz hopping channels, and UAV direction finding.
- **Abstract**: Outlines the core quantitative achievements:
  - Sub-0.20° angular RMSE achieved across 433–928 MHz hopping channels at 15 dB SNR.
  - $\sim 1.9$ kHz coarse FFT error reduced to $< 50$ Hz using lag-$M$ differential phase estimation.
  - Multipath mitigation via eigenvalue ratio gate ($\gamma_{th} = 8.0$) discarding corrupted bursts ($P_{rej} > 95\%$).
  - Full execution completed in $345\ \mu\text{s}$ per burst on an embedded ARM Cortex-A72.

#### 2. Section I: Introduction & Motivation
- **The Threat Landscape**: Consumer and custom-built drones utilizing frequency-hopping telemetry (ELRS/LoRa) evade fixed-frequency radio scanners.
- **The Hardware Dilemma**: Traditional multi-channel SDRs (e.g. USRP, KrakenSDR) are expensive, bulky, and require continuous inter-channel phase alignment.
- **Why Switched SDRs Fail Conventionally**:
  1. *Time-Displaced Phase Modulation*: Switching sequentially between antennas at rate $f_{sw}$ imparts an artificial linear phase ramp onto the incoming signal.
  2. *Manifold Mismatch*: If steering vectors calibrated at a single reference frequency (e.g., $\lambda_0 = 433$ MHz) are evaluated during high-frequency hops (e.g., $915$ MHz), severe angular bias occurs.
  3. *Multipath Reflections*: Concrete walls and trees create coherent reflections that corrupt single-snapshot bearings.
- **Five Specific Contributions**: Enumerates the architecture, lag-$M$ algorithm, manifold compensation, eigenvalue gate, and embedded benchmarks.

#### 3. Section II: Switched-Interferometric System Architecture
- **Array Geometry**: $M=4$ element Uniform Circular Array (UCA) arranged at radius $r = 7.2$ cm:
  $$\psi_m = \frac{2\pi(m-1)}{M}, \quad m \in \{1, 2, 3, 4\} \implies [0^\circ, 90^\circ, 180^\circ, 270^\circ]$$
- **Equation (1) — Antenna Switching State Function**:
  $$\boxed{s(t) = \sum_{k=0}^{\infty} \sum_{m=1}^{M} \mathbf{e}_m \, \Pi\left(\frac{t - (k M + m - 1) T_{\text{dw}}}{T_{\text{dw}}}\right)}$$
  *What it means*: At any given microsecond $t$, exactly one antenna element $m$ is connected to the single RF receiver for duration $T_{dw} = 16\ \mu\text{s}$.
- **Equation (2) — Received RF Signal Model**:
  $$\boxed{x(t) = \sum_{m=1}^{M} s_m(t) \left[ a_m(\theta, \phi, f_k) u(t) e^{j(2\pi f_k t + \Delta\omega t + \phi_0)} + w_m(t) \right]}$$
  *What it means*: The receiver observes the transmitted complex envelope $u(t)$ modulated by the spatial phase delay $a_m(\theta, \phi, f_k)$ of antenna $m$, plus carrier frequency offset $\Delta\omega$, initial phase $\phi_0$, and AWGN $w_m(t)$.

---

### Page 2: Hardware Topology & Frequency-Offset Recovery

#### 1. Section II-B: Hardware Topology & Timing Synchronization
- **RF Switching Hardware**: Analog Devices **HMC241** non-reflective GaAs SP4T switch:
  - 20 ns switching time (negligible inter-dwell transient).
  - $> 40$ dB isolation up to 1 GHz (prevents RF bleed-through from adjacent antennas).
- **Sampling Parameters**:
  - Sample rate $F_s = 2.0$ MS/s ($T_s = 0.5\ \mu\text{s}$).
  - Dwell time $T_{dw} = 16\ \mu\text{s} \implies L = 32$ samples per antenna dwell.
  - Round-robin cycle $T_{cycle} = M \times T_{dw} = 64\ \mu\text{s}$ (128 samples per 4-antenna sweep).
  - An ExpressLRS telemetry burst ($T_b \in [1.0, 4.0]$ ms) provides $N_{cyc} \ge 15$ full array cycles.
- **Equation (3) — Moving-Average Burst Detection**:
  Energy detector computes running power $P[n] = \frac{1}{L} \sum_{i=0}^{L-1} |y[n-i]|^2$ against noise threshold $\eta = \sigma_w^2 (1 + \beta/\sqrt{L})$.

#### 2. Section III: Frequency-Compensated DSP Pipeline
- **Section III-A: Frequency Estimation & De-Rotation**:
  Because the switch alternates through elements every $16\ \mu\text{s}$, any frequency error between the drone's transmitter and the receiver local oscillator (LO) creates a progressive phase shift across antennas that masquerades as an artificial angle of arrival!
- **Coarse Frequency Search**: A 512-point FFT on the first dwell gives coarse frequency peak $\hat{f}_c$ with bin resolution $F_s / N_{FFT} \approx 3.9$ kHz.
- **Equation (5) — Lag-$M$ Differential Phase Refinement**:
  $$\boxed{\hat{f}_\Delta = \frac{1}{2\pi M T_s} \arg\left( \sum_{n=0}^{N_{\text{burst}} - M - 1} y^*[n] \, y[n + M] \right)}$$
  *Why this is brilliant*: By taking pairs of samples separated by exactly one full switching cycle ($M = 4$ dwells = 128 samples), the spatial steering vector $\mathbf{a}(\theta)$ is identical in both samples! Thus, the spatial phase cancels out completely, leaving *only* the pure carrier frequency drift:
  $$y^*[n] y[n + M] \propto \exp(j 2\pi \Delta f \cdot M T_s)$$
  This estimates the true frequency offset to within $< 50$ Hz without needing an expensive external reference.
- **Equation (6) — Baseband Phase De-Rotation**:
  $$\boxed{\tilde{y}[n] = y[n] \exp\left(-j 2\pi (f_k + \hat{f}_\Delta) n T_s\right)}$$
  Multiplying the raw I/Q samples by this complex phasor unwraps the linear phase ramp and aligns all time-displaced dwells into a coherent baseband snapshot.

---

### Page 3: Spatial Manifold, Eigenvalue Gate & Circular Kalman Filter

#### 1. Section III-B: Dynamic Array Manifold Steering Vector
- **Equation (7) — UCA Steering Vector at Hop Frequency $f_k$**:
  $$\boxed{[\mathbf{a}(\theta, f_k)]_m = \exp\left( j \frac{2\pi r f_k}{c} \cos\left(\theta - \psi_m\right) \sin\phi \right)}$$
  Where $r=7.2$ cm, $c = 3 \times 10^8$ m/s, $\theta$ is azimuth, $\phi$ is elevation, and $\psi_m$ is element angle.
- **Equation (8) — Theoretical Steering Phase Error of Static Baseline**:
  $$\boxed{\Delta\phi_m(f_k, f_0) = \frac{2\pi r}{c} (f_k - f_0) \cos(\theta - \psi_m) \sin\phi}$$
  *What it reveals*: When a drone hops from $f_0 = 433$ MHz to $f_k = 915$ MHz, $(f_k - f_0) = 482$ MHz. For $r = 7.2$ cm, this creates a phase error of $\Delta\phi \approx 125^\circ$, causing classical uncompensated MUSIC to suffer up to $0.85^\circ$ of systematic angular bias.

#### 2. Section III-C: Sample Covariance & Spatial Subspace Decomposition
- Synthetic snapshots $\mathbf{X} \in \mathbb{C}^{M \times N_{snap}}$ are constructed from the de-rotated samples.
- **Equation (9) — Sample Covariance Matrix**:
  $$\boxed{\hat{\mathbf{R}}_{xx} = \frac{1}{N_{\text{snap}}} \mathbf{X} \mathbf{X}^H}$$
- **Cyclic Jacobi Eigenvalue Decomposition (EVD)**:
  Decomposes $\hat{\mathbf{R}}_{xx}$ into orthogonal eigenvectors and ordered eigenvalues $\lambda_1 \ge \lambda_2 \ge \lambda_3 \ge \lambda_4$.

#### 3. Section III-D: Subspace Multipath Eigenvalue Ratio Gate
- Under clean Line-of-Sight (LoS), the signal subspace is strictly rank-1:
  $$\lambda_1 = N_{\text{snap}} P_{sig} + \sigma_w^2, \quad \lambda_2 \approx \lambda_3 \approx \lambda_4 \approx \sigma_w^2 \implies \frac{\lambda_1}{\lambda_2} \gg 1$$
- Under multipath reflections (from concrete walls or trees), energy leaks into the second eigenvalue, causing $\lambda_2$ to jump upwards!
- **Equation (10) — The Eigenvalue Gate**:
  $$\boxed{\gamma = \frac{\lambda_1}{\lambda_2} \ge \gamma_{\text{th}} = 8.0}$$
  Bursts failing this condition ($\gamma < 8.0$) are rejected as multipath-contaminated before they can pollute the tracker.

#### 4. Section III-E: Frequency-Compensated Spectral MUSIC (A2 Algorithm)
- Noise subspace matrix $\mathbf{E}_n = [\mathbf{v}_2, \mathbf{v}_3, \mathbf{v}_4]$.
- **Equation (12) — Pseudospectrum with Active Hop $\lambda_k$**:
  $$\boxed{P_{\text{MUSIC}}(\theta, f_k) = \frac{1}{\mathbf{a}^H(\theta, f_k) \mathbf{E}_n \mathbf{E}_n^H \mathbf{a}(\theta, f_k)}}$$
  The peak location gives the direct Line-of-Sight bearing: $\hat{\theta} = \arg\max_\theta P_{\text{MUSIC}}(\theta, f_k)$.

#### 5. Section III-F: Circular Kalman Filter on the $S^1$ Manifold
Because bearing angles wrap around at $360^\circ \equiv 0^\circ$, traditional linear Kalman filters experience catastrophic discontinuity when a drone crosses due North.
- **Equation (13) — Circular State Prediction**:
  $$\boxed{\hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1|k-1}, \quad \mathbf{P}_{k|k-1} = \mathbf{F} \mathbf{P}_{k-1|k-1} \mathbf{F}^T + \mathbf{Q}}$$
- **Equation (14) — Circular Innovation / Residual**:
  $$\boxed{\tilde{y}_k = \text{wrap}\left(\theta_{\text{meas}, k} - \mathbf{H} \hat{\mathbf{x}}_{k|k-1}\right) = \left(\left(\theta_{\text{meas}, k} - \hat{\theta}_{k|k-1} + \pi\right) \pmod{2\pi}\right) - \pi}$$
- **Equation (15) & (16) — Kalman Gain and State Update**:
  Updates bearing and angular velocity smoothly across the $0^\circ / 360^\circ$ boundary.

---

### Page 4: Digital Twin Simulation Dashboard & Frequency Hopping Benchmark

#### 1. Figure 2: Simulation Environment & Real-Time DSP Dashboard
Spanning the full text width across both columns, Figure 2 shows the live digital twin in operation:
- **(a) Dynamic Flight Tracking**: 60 consecutive ELRS hops. The Proposed A2 Filter (blue) tracks the true trajectory (black), while the Static 433 Baseline (red) shows constant angular bias.
- **(b) Instantaneous MUSIC Spatial Spectrum @ 915 MHz Hop**: A sharp, distinct peak at true bearing $\theta = 35^\circ$ with side-lobe suppression $> 22$ dB.
- **(c) Monte Carlo Angular RMSE vs SNR**: 280 simulated packet bursts verifying sub-0.2° accuracy.
- **(d) Multipath Eigenvalue Ratio Gate**: Demonstrates clean LoS bursts passing well above the $\gamma_{th} = 8.0$ threshold line.

#### 2. Section IV: Experimental Evaluation Setup
- Simulated 3D RF arena ($120 \times 120 \times 60$ m) featuring:
  - 4-element UCA ground station ($r=7.2$ cm).
  - Quadcopter UAV traversing realistic trajectories at $12$ m/s.
  - Concrete buildings with dielectric constant $\epsilon_r = 7.0$ and conductivity $\sigma = 0.015$ S/m.
- **Table I — Performance Across Sub-GHz Frequency Hopping Channels**:
  Demonstrates empirical accuracy across 600 bursts per band at 15 dB SNR:
  - **433 MHz**: Static Baseline RMSE $0.34^\circ$ vs Proposed $0.34^\circ$ (Zero mismatch).
  - **868 MHz**: Static Baseline degrades to $0.68^\circ$ (Bias $-0.61^\circ$) vs Proposed **$0.18^\circ$**.
  - **915 MHz**: Static Baseline degrades to $0.76^\circ$ (Bias $-0.69^\circ$) vs Proposed **$0.17^\circ$**.
  - **928 MHz**: Static Baseline degrades to $0.79^\circ$ (Bias $-0.71^\circ$) vs Proposed **$0.17^\circ$**.
  *Core Takeaway*: Frequency-compensated steering completely eliminates the frequency-dependent bias floor.

---

### Page 5: Spatial Aliasing Breakdown & Multi-Receiver Benchmarks

#### 1. Figure 3: Array Manifold Mismatch & Spatial Ambiguity Breakdown
- **Fig 3(a) — Static Bias vs Hop Frequency**:
  Plots worst-case bias $|bias(\theta)|$ and RMS bias from 430 to 930 MHz. Confirms that uncompensated static steering exhibits monotonic error growth up to $0.85^\circ$.
- **Fig 3(b) — 95th-Percentile Bias vs UCA Radius $r$**:
  Sweeps array radius $r$ from 4 cm to 40 cm.
  - Highlights prototype optimality at $r = 7.2$ cm ($d/\lambda_0 = 0.31$).
  - **Critical Discovery**: Above $r \ge 12$ cm ($d/\lambda \ge 0.52$), spatial phase wrapping occurs ($kd > \pi$), causing catastrophic multi-lobe collapse with angular errors exceeding $60^\circ$!
- **Fig 3(c) — Pseudospectrum Comparison**:
  Shows why uncompensated switching fails: raw switched samples create false pseudo-peaks across the horizon, whereas fine de-rotation produces a single pristine peak.

#### 2. Figure 4: DoA Estimation Accuracy & Frequency Recovery vs SNR
- **Fig 4(a) — 6-Receiver DoA RMSE Benchmark**:
  Compares 6 systems from $-10$ dB to $+30$ dB SNR:
  1. *Switched, No De-rotation* (Red): Fails completely with RMSE $> 20^\circ$.
  2. *FFT-Only De-rotation* (Magenta): Error floor at $\sim 1.5^\circ$ due to residual FFT bin quantization.
  3. *Static $\lambda_0$ Baseline* (Blue): Biased error floor at $\sim 0.65^\circ$.
  4. *Proposed Fine De-rotation + $\lambda_k$* (Black): Reaches **$0.18^\circ$** at 30 dB.
  5. *Ideal 4-Channel Coherent* (Green dashed): $0.12^\circ$ (theoretical upper bound).
  6. *Cramér-Rao Bound (CRB)* (Black dotted): $0.08^\circ$ (fundamental physical bound).
- **Fig 4(b) — Frequency-Offset Estimation Error**:
  Demonstrates that coarse FFT has an error floor of $\sim 1.9$ kHz, while the lag-$M$ differential estimator suppresses carrier error down to **34 Hz** at 30 dB.

---

### Page 6: Multipath Mitigation & Empirical Propagation Regimes

#### 1. Figure 5: Multipath Eigenvalue Gate Dynamics
- **Fig 5(a) — $\gamma = \lambda_1/\lambda_2$ Distribution vs SNR**:
  Under clean Line-of-Sight, median $\gamma$ rises from 12 at 0 dB SNR to $> 150$ at 25 dB SNR. Even at 10 dB SNR, the 10th-percentile curve remains above $\gamma_{th} = 8.0$, ensuring a false rejection rate $< 0.5\%$.
- **Fig 5(b) — Rejection Probability vs Correlation $|c|$**:
  Sweeps reflection correlation $|c| \in [0, 1]$ across weak ($\rho=0.3$), moderate ($\rho=0.6$), and strong ($\rho=0.9$) reflections.
  - For decorrelated or partially correlated multipath ($|c| \le 0.8$), the eigenvalue gate rejects corrupted bursts with $> 95\%$ probability.
  - **Physical Insight**: For fully coherent multipath ($|c| \to 1.0$, e.g., zero Doppler difference), the composite signal collapses to rank-1, which explains the theoretical limitation of single-array eigenvalue gating.

#### 2. Table II: Direction Finding Performance Across 6 Multipath Regimes
Evaluates 1,000 Monte Carlo bursts under each condition:
- *LoS Only*: Gate rejection $0.0\%$, Raw MUSIC RMSE $0.19^\circ$, Gated MUSIC $0.19^\circ$.
- *Weak Reflection ($-10.5$ dB)*: Rejection $88.2\%$, Raw RMSE $1.42^\circ$, Gated RMSE **$0.24^\circ$**.
- *Moderate Reflection, Decorrelated*: Rejection $99.8\%$, Raw RMSE $4.85^\circ$, Gated RMSE **$0.21^\circ$**.
- *Moderate Reflection, Partially Coherent*: Rejection $96.4\%$, Raw RMSE $5.12^\circ$, Gated RMSE **$0.28^\circ$**.
- *Strong Reflection ($-0.9$ dB)*: Rejection $98.1\%$, Raw RMSE $8.74^\circ$, Gated RMSE **$0.31^\circ$**.
- *Fully Coherent Reflection*: Rejection $12.4\%$ (coherent rank-1 collapse), outlier detector engages.

#### 3. Table III: End-to-End Tracking Performance in Urban Shadow Multipath
- Raw MUSIC exhibits RMSE of $14.2^\circ$ with $18.2\%$ outliers.
- Gated + Circular Kalman Filter achieves RMSE of **$0.42^\circ$** with **$0.0\%$ outliers**, proving seamless coasting through building shadow intervals.

---

### Page 7: Tracking Trajectories, GDOP Triangulation & Real-Time Embedded DSP

#### 1. Figure 6: Dynamic Bearing Tracking & Multi-Station GDOP
- **Fig 6(a) — Bearing Tracking Over Time**:
  Tracks a UAV through two severe urban building shadow intervals ($t \in [15, 25]$ s and $t \in [40, 48]$ s). Rejected bursts (red markers) are safely isolated while the Circular KF smoothly coasts along the true trajectory.
- **Fig 6(b) — 2D GDOP Contour Map & WLS Triangulation**:
  Shows a 3-station DF network covering a $120 \times 120$ m tactical perimeter:
  - Station coordinates: $S_1(20, 20)$, $S_2(100, 25)$, $S_3(60, 105)$.
  - Weighted Least Squares (WLS) target fixes (blue dots) cluster tightly around the true drone position.
  - 95% confidence error ellipse ($a = 3.8$ m, $b = 1.9$ m) demonstrates sub-2 meter localization accuracy.

#### 2. Section V: Real-Time Embedded Profiling (Table IV)
Benchmarked on an embedded **Raspberry Pi 4B** (Broadcom BCM2711, Quad-core ARM Cortex-A72 @ 1.5 GHz, NEON SIMD enabled):

| Execution Phase | Computational Primitive | CPU Latency ($\mu\text{s}$) |
| :--- | :--- | :---: |
| Burst Detection & Slicing | Vector Energy Window | $12\ \mu\text{s}$ |
| Fine Freq. & De-rotation | Lag-$M$ Dot-Product + Phase Vector | $48\ \mu\text{s}$ |
| Covariance Matrix $\hat{\mathbf{R}}_{xx}$ | Complex Outer Product ($4 \times 4$) | $31\ \mu\text{s}$ |
| Subspace Decomposition | 6-Sweep Cyclic Jacobi EVD | $42\ \mu\text{s}$ |
| Multipath Eigenvalue Gate | Ratio Comparison ($\lambda_1/\lambda_2$) | $4\ \mu\text{s}$ |
| 1-D Coarse MUSIC Scan | Vectorized Subspace Projection ($1^\circ$ grid) | $185\ \mu\text{s}$ |
| Fine Peak Refinement | 3-Point Parabolic Interpolation | $8\ \mu\text{s}$ |
| Circular Kalman Filter | 2-State Circular Innovation & Covariance | $15\ \mu\text{s}$ |
| **Total Pipeline Latency** | **End-to-End per Packet Burst** | **$345\ \mu\text{s}$ (0.35 ms)** |

*Significance*: The entire DSP chain executes in $0.35$ ms. Since ExpressLRS packets arrive at most every $2.0$ ms (at 500 Hz), the processor utilizes only **$17.3\%$ of a single CPU core**, leaving ample headroom for multi-radar networking and UI telemetry streaming.

#### 3. Section VI: Conclusion & References
- Summarizes the validation of low-cost switched interferometric direction finding.
- Concludes with 11 balanced, authoritative IEEE citations covering array signal processing, drone telemetry, and subspace algorithms.

---

## Quick Reference: Key Formulas Cheat Sheet

| Formula | Equation # | Physical / Engineering Purpose |
| :--- | :---: | :--- |
| **$s(t) = \sum \Pi(...)$** | Eq. (1) | GaAs switch round-robin sampling state function ($16\ \mu\text{s}$ dwell). |
| **$\hat{f}_\Delta = \frac{1}{2\pi M T_s} \arg(...) $** | Eq. (5) | Lag-$M$ differential carrier frequency estimator (removes phase skew). |
| **$\tilde{y}[n] = y[n] e^{-j 2\pi (...) n T_s}$** | Eq. (6) | Baseband de-rotation phasor un-wrapping the time-displaced dwells. |
| **$[\mathbf{a}(\theta, f_k)]_m = e^{j \frac{2\pi r f_k}{c} \cos(\theta - \psi_m) \sin\phi}$** | Eq. (7) | Frequency-agile UCA array manifold at instantaneous hop $f_k$. |
| **$\Delta\phi = \frac{2\pi r}{c}(f_k - f_0)\cos(...)$** | Eq. (8) | Theoretical angular phase bias of uncompensated static manifolds. |
| **$\hat{\mathbf{R}}_{xx} = \frac{1}{N} \mathbf{X} \mathbf{X}^H$** | Eq. (9) | Spatial sample covariance matrix across synthetic snapshots. |
| **$\gamma = \lambda_1 / \lambda_2 \ge 8.0$** | Eq. (10) | Multipath subspace eigenvalue gate detecting NLoS reflections. |
| **$P_{\text{MUSIC}} = \frac{1}{\mathbf{a}^H \mathbf{E}_n \mathbf{E}_n^H \mathbf{a}}$** | Eq. (12) | A2 frequency-compensated spatial pseudospectrum. |
| **$\tilde{y}_k = \text{wrap}(\theta_{\text{meas}} - \mathbf{H}\hat{\mathbf{x}})$** | Eq. (14) | Circular modular innovation preventing $0^\circ/360^\circ$ jump singularities. |

---

*Document compiled and verified against the authoritative LaTeX source and digital twin simulation suite.*
