# Digital Signal Processing Pipeline
## EC261: End-to-End Subspace Direction Finding Architecture

```mermaid
flowchart TD
    In[Received Baseband IQ Stream] --> Step1[Step 1: Sliding-Window Power Trigger P[n] = I² + Q²]
    Step1 --> Step2[Step 2: Radix-2 FFT + Fine Differential Frequency Estimator]
    Step2 --> Step3[Step 3: Dynamic Steering Vector a(f_k, theta) & Wavelength Update]
    In --> Step4[Step 4: Sample Spatial Covariance R_xx = 1/N * X * X^H]
    Step4 --> Step5[Step 5: Hermitian Eigenvalue Decomposition R_xx = V * Lambda * V^H]
    Step5 --> Step6[Step 6: Multipath Reliability Gate gamma = lambda_1 / lambda_2 >= 8.0]
    Step5 --> Step7[Step 7: Noise Subspace Projector P_n = E_n * E_n^H]
    Step3 --> Step8[Step 8: Vectorized Circular MUSIC Spectrum P(theta) = 1 / a^H P_n a]
    Step7 --> Step8
    Step8 --> Step9[Step 9: Spectral Peak Extraction theta_est]
    Step6 --> Step10[Step 10: Tracking Engine Gated Hold / Kalman Filter]
    Step9 --> Step10
```

---

### Step 1: Sliding-Window Power Envelope Burst Trigger
Instantaneous power across the multi-channel stream:
$$P[n] = \frac{1}{M} \sum_{m=0}^{M-1} (|I_m[n]|^2 + |Q_m[n]|^2)$$
The raw power stream is convolved with a moving-average kernel ($W=16$ samples):
$$\bar{P}[n] = \frac{1}{W} \sum_{k=0}^{W-1} P[n - k]$$
Baseline noise floor $P_{noise}$ is estimated from the pre-burst guard window. The adaptive trigger threshold is:
$$\eta = \kappa \cdot P_{noise}, \quad \kappa = 2.5$$
Burst start and end indices are identified when $\bar{P}[n] > \eta$.

---

### Step 2: FFT Hop Identification & Fine Differential Tuning
At 2 MS/s sampling rate, $N=256$ samples correspond to a $128 \mu s$ snapshot window.
1. **Coarse Peak Search:**
   $$X[k] = \sum_{n=0}^{N-1} x_0[n] w[n] e^{-j 2\pi k n / N}$$
   Peak bin index $k_{peak} = \arg\max_k |X[k]|$ identifies coarse baseband offset $f_{BB, coarse}$.
2. **Sub-Bin Differential Phase Refinement:**
   To prevent temporal phase drift accumulation during sequential switching in Mode B, fine frequency tuning uses the Kay/Fitz differential estimator:
   $$\Delta\psi = \arg\left( \frac{1}{N-1} \sum_{n=0}^{N-2} x_0[n+1] \cdot x_0^*[n] \right)$$
   $$\hat{f}_{BB} = \frac{F_s}{2\pi} \Delta\psi$$
3. **RF Carrier Reconstruction:**
   $$\hat{f}_k = f_{LO} + \hat{f}_{BB}, \quad \hat{\lambda}_k = \frac{c}{\hat{f}_k}$$

---

### Step 3: Spatial Covariance Matrix Estimation
From the reconstructed snapshot matrix $X = [x_0, x_1, x_2, x_3]^T \in \mathbb{C}^{4 \times N_{eff}}$:
$$R_{xx} = \frac{1}{N_{eff}} X X^H$$
To eliminate floating-point numerical asymmetry, Hermitian symmetry is enforced:
$$R_{xx} = \frac{1}{2}(R_{xx} + R_{xx}^H)$$

---

### Step 4: Hermitian Eigenvalue Decomposition (EVD)
Because $R_{xx}$ is Hermitian positive semi-definite, its eigenvalues are real and non-negative:
$$R_{xx} = \sum_{m=1}^4 \lambda_m \vec{v}_m \vec{v}_m^H$$
Eigenvalues are sorted in descending order:
$$\lambda_1 \ge \lambda_2 \ge \lambda_3 \ge \lambda_4 \ge 0$$
- Dominant eigenvector $\vec{v}_1$ spans the signal subspace $E_s = [\vec{v}_1]$.
- Remaining orthogonal eigenvectors span the noise subspace $E_n = [\vec{v}_2, \vec{v}_3, \vec{v}_4]$.
- The noise subspace projection operator is:
  $$P_n = E_n E_n^H \in \mathbb{C}^{4 \times 4}$$

---

### Step 5: Multipath Reliability Gate
The eigenvalue spread ratio is computed as:
$$\gamma = \frac{\lambda_1}{\lambda_2 + \epsilon}$$
- **Clean Single-Source LoS:** Covariance rank is approximately 1 (plus white noise floor $\sigma^2$). $\lambda_1 \approx M P_{sig} + \sigma^2$ and $\lambda_2 \approx \sigma^2 \implies \gamma \gg 8.0 \implies$ **ACCEPTED**.
- **Multipath Corrupted / Dual Source:** When a reflected ray arrives from an obstacle, the signal subspace rank expands to 2. $\lambda_2$ rises significantly $\implies \gamma < 8.0 \implies$ **REJECTED**.

---

### Step 6: Vectorized Circular MUSIC Pseudospectrum
For any candidate azimuth $\theta \in [-180^\circ, +180^\circ]$:
$$P_{MUSIC}(\theta) = \frac{1}{\vec{a}^H(\hat{f}_k, \theta) P_n \vec{a}(\hat{f}_k, \theta)}$$
Normalized to logarithmic decibels:
$$P_{dB}(\theta) = 10 \log_{10}\left( \frac{P_{MUSIC}(\theta)}{\max_\theta P_{MUSIC}(\theta)} \right)$$
The estimated Direction of Arrival is extracted from the global peak:
$$\hat{\theta}_{comp} = \arg\max_\theta P_{dB}(\theta)$$

---

### Step 7: Tracking Engine & Outlier Mitigation
When the Multipath Reliability Gate triggers:
- **`GATED_HOLD` Mode:**
  - If `ACCEPTED`: Track is updated with new estimate: $\theta_{track} = \hat{\theta}_{comp}$.
  - If `REJECTED`: Estimator rejects the burst and **HOLDS LAST VERIFIED BEARING**: $\theta_{track} = \theta_{track, prev}$.
- **`KALMAN_FILTER` Mode:**
  - Continuous white-noise acceleration state space tracking $[x, \dot{x}, y, \dot{y}]^T$ and circular azimuth state $[\theta, \dot{\theta}]^T$.
  - Continuous process noise covariance:
    $$Q(q, \Delta t) = q \begin{bmatrix} \frac{\Delta t^3}{3} & \frac{\Delta t^2}{2} \\ \frac{\Delta t^2}{2} & \Delta t \end{bmatrix}$$
  - **$\chi^2$ Normalized Innovation Squared (NIS) Gating:**
    $$\epsilon_{NIS} = \nu^T S^{-1} \nu \le \chi^2_{1, 0.999} = 10.83$$
  - **Maneuver Detection:** When high-rate avoidance turns occur, $\epsilon_{NIS} > 10.83$ triggers instantaneous $4.0\times Q$ process noise inflation, adapting Kalman gain to follow the aggressive trajectory bypass.
  - When `REJECTED`: Measurement update is bypassed; state propagates on velocity estimate only.

---

### Step 8: Beamspace Phase-Mode UCA-ESPRIT
Circular arrays cannot directly apply standard ESPRIT due to lack of translational shift invariance. The UCA-ESPRIT module synthesizes virtual linear array manifold invariance via spatial Fourier transformation:
1. **Jacobi-Anger Bessel Expansion:**
   $$a_m(\theta) = \sum_{p=-\infty}^{\infty} j^p J_p(kr) e^{j p (\phi_m - \theta)}$$
2. **Beamspace Transformation:**
   $$B = W^H R_{xx} W$$
   where $W$ is the beamspace weighting matrix formed from phase modes $m \in [-M_0, M_0]$.
3. **Shift Invariance:**
   Extracts sub-matrices $E_{s1}$ and $E_{s2}$ from the beamspace signal subspace and solves the rotational invariance equation:
   $$\Psi = (E_{s1}^H E_{s1})^{-1} E_{s1}^H E_{s2}$$
   The DoA is directly computed from the complex eigenvalues $\mu_i$ of $\Psi$:
   $$\hat{\theta}_{ESPRIT} = \arg(\mu_i)$$

---

### Step 9: Switched-Beam Power-Vector ML Estimator
For non-coherent or heavily duty-cycled switched receivers, Direction of Arrival is estimated directly from received power dwell vectors across elements $p = [P_0, P_1, P_2, P_3]^T$:
1. **Negative Log-Likelihood Formulation:**
   $$\text{NLL}(\theta) = \sum_{m=0}^{M-1} \left( \ln(a_m^2(\theta)) + \frac{P_m}{a_m^2(\theta)} \right)$$
2. **Cramér-Rao Variance Inflation:**
   Extracts curvature from reduced deviance $D(\theta) = 2(\text{NLL}(\theta) - \min \text{NLL})$:
   $$\sigma^2_{CRB} = \left( \left. \frac{d^2 \text{NLL}}{d\theta^2} \right|_{\hat{\theta}} \right)^{-1}$$
3. **Power-Weighted Centroid:**
   $$\vec{c} = \sum_{m=0}^{M-1} P_m e^{j \phi_m}, \quad \hat{\theta}_{centroid} = \arg(\vec{c})$$

