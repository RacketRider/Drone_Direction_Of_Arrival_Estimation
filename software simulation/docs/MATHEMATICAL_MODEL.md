# Mathematical Model Specification
## EC261: Switched-Interferometric UCA Direction Finding

### 1. Coordinate Systems & Geometry
The coordinate system uses standard 3D cartesian coordinates where:
- Horizontal ground plane: $x$ (East) and $z$ (North).
- Vertical altitude axis: $y$ (Upwards from ground).
- Ground station array center at origin: $\vec{p}_{GS} = (0, 0, 0)$.
- UAV position: $\vec{p}_{UAV}(t) = [x(t), y(t), z(t)]^T$.

True Ground Azimuth Bearing $\theta_{true} \in [-180^\circ, +180^\circ]$:
$$\theta_{true} = \text{atan2}(z(t), x(t)) \times \frac{180^\circ}{\pi}$$
True Elevation Angle:
$$\psi_{elev} = \text{atan2}\left(y(t), \sqrt{x^2(t) + z^2(t)}\right) \times \frac{180^\circ}{\pi}$$

---

### 2. 4-Element Uniform Circular Array (UCA) Manifold

For an $M=4$ element circular array with radius $r = 0.072$ m ($7.2$ cm):
Element azimuth angles:
$$\phi_m = m \cdot \frac{\pi}{2}, \quad m \in \{0, 1, 2, 3\}$$
Element spatial coordinates:
$$\vec{p}_m = [r \cos\phi_m, 0, r \sin\phi_m]^T$$

For an incoming RF plane wave with carrier frequency $f_k$ and azimuth $\theta$, the unit wavevector pointing toward the source is $\hat{k}(\theta) = [\cos\theta, 0, \sin\theta]^T$.
The geometric spatial path delay at element $m$ relative to the array center is:
$$\Delta d_m(\theta) = \vec{p}_m \cdot \hat{k}(\theta) = r [\cos\phi_m \cos\theta + \sin\phi_m \sin\theta] = r \cos(\theta - \phi_m)$$

The corresponding phase advance is:
$$\Phi_m(f_k, \theta) = \frac{2\pi f_k}{c} \Delta d_m(\theta) = \frac{2\pi f_k r}{c} \cos(\theta - \phi_m)$$

The complex steering vector $\vec{a}(f_k, \theta) \in \mathbb{C}^{4 \times 1}$ is:
$$\vec{a}(f_k, \theta) = \begin{bmatrix}
\exp\left(j \frac{2\pi f_k r}{c} \cos(\theta - 0^\circ)\right) \\
\exp\left(j \frac{2\pi f_k r}{c} \cos(\theta - 90^\circ)\right) \\
\exp\left(j \frac{2\pi f_k r}{c} \cos(\theta - 180^\circ)\right) \\
\exp\left(j \frac{2\pi f_k r}{c} \cos(\theta - 270^\circ)\right)
\end{bmatrix}$$

---

### 3. Spatial Aliasing Analysis

To guarantee that the array manifold $\vec{a}(f_k, \theta)$ has no grating lobes or spatial phase ambiguities across $[-180^\circ, +180^\circ]$, the maximum inter-element distance must satisfy:
$$d_{max} < \frac{\lambda_{min}}{2}$$
For the 4-element UCA, the maximum baseline is the diametric distance between opposite elements ($0$ and $2$, or $1$ and $3$):
$$d_{max} = 2r = 2 \times 0.072 = 0.144 \text{ m}$$
At the highest FHSS hop frequency $f_{max} = 928$ MHz:
$$\lambda_{min} = \frac{c}{f_{max}} = \frac{299792458}{928 \times 10^6} \approx 0.32305 \text{ m}$$
$$\frac{d_{max}}{\lambda_{min}} = \frac{0.144}{0.32305} \approx 0.4457 < 0.5$$
The adjacent element chord distance is:
$$d_{adj} = \sqrt{2} r \approx 1.4142 \times 0.072 \approx 0.10182 \text{ m} \implies \frac{d_{adj}}{\lambda_{min}} \approx 0.315 < 0.5$$
Because $d_{max} < 0.5\lambda$ holds across all sub-GHz channels (433 to 928 MHz), the 4-element circular array is mathematically guaranteed to be free from spatial grating lobes and phase wrap ambiguity.

---

### 4. Proposed Dynamic Frequency-Compensated Steering vs Static Baseline

#### Proposed A2 Method:
$$\vec{a}_{comp}(\theta) = \vec{a}(\hat{f}_k, \theta)$$
Where $\hat{f}_k = f_{LO} + \hat{f}_{BB}$ is the dynamically estimated RF carrier frequency identified via FFT from the received telemetry burst.

#### Static Uncompensated Baseline ($f_{ref} = 433$ MHz):
$$\vec{a}_{static}(\theta) = \vec{a}(f_{ref}, \theta)$$
When the transmitter hops to $f_k = 915$ MHz, the true spatial phase in the received covariance matrix is scaled by $f_k$, but the static steering vector assumes $f_{ref}$:
$$\Delta\Phi_m = \frac{2\pi r}{c} (f_k - f_{ref}) \cos(\theta - \phi_m)$$
Because $f_k / f_{ref} \approx 2.11$, the static manifold cannot project onto the true signal subspace, resulting in severe peak flattening, broadening, and susceptibility to multipath-induced angular drift.

---

### 5. Circular Angular Error Metric

Azimuth angle is a circular periodic quantity defined on the circle $\mathbb{S}^1$. The true shortest angular distance error between estimate $\theta_{est}$ and ground truth $\theta_{true}$ is computed using the wrapped difference:
$$\Delta\theta = ((\theta_{est} - \theta_{true} + 180^\circ) \pmod{360^\circ}) - 180^\circ \in [-180^\circ, +180^\circ]$$
This prevents boundary discontinuity bugs when angles cross the $\pm 180^\circ$ azimuth meridian.

---

### 6. Beamspace Phase-Mode Transformation (UCA-ESPRIT)

For circular arrays, the continuous spatial aperture can be decomposed into spatial harmonics via the Jacobi-Anger expansion:
$$e^{j \frac{2\pi r}{\lambda} \cos(\theta - \phi_m)} = \sum_{p=-\infty}^{\infty} j^p J_p(k r) e^{j p (\phi_m - \theta)}$$
Where $J_p(kr)$ is the Bessel function of the first kind of order $p$, and $k = \frac{2\pi}{\lambda}$.
Using a finite beamspace mode order $P$, a transformation matrix $W \in \mathbb{C}^{M \times (2P+1)}$ converts the circular manifold into a virtual uniform linear array (ULA) manifold:
$$a_v(\theta) = W^H \vec{a}(\theta) \approx \begin{bmatrix} e^{-j P \theta} \\ \vdots \\ 1 \\ \vdots \\ e^{j P \theta} \end{bmatrix}$$
The transformed covariance matrix:
$$R_v = W^H R_{xx} W$$
Now exhibits rotational shift-invariance between upper and lower virtual sub-arrays:
$$E_{s2} = E_{s1} \Psi$$
Allowing TLS/LS-ESPRIT to solve for the target azimuth without multidimensional spectral grid searches:
$$\hat{\theta}_{ESPRIT} = -\arg(\text{eig}(\Psi))$$

---

### 7. Switched-Beam Power-Vector Maximum Likelihood

When only non-coherent power dwell measurements $p = [P_0, P_1, P_2, P_3]^T$ are collected across sequential switch cycles:
Under a Gaussian-distributed dwell noise assumption with variance proportional to expected beam power $\mu_m(\theta) = G_m(\theta) P_{tx}$, the negative log-likelihood is:
$$\text{NLL}(\theta) = \sum_{m=0}^{M-1} \left( \ln \mu_m(\theta) + \frac{P_m}{\mu_m(\theta)} \right)$$
The ML estimate $\hat{\theta}_{ML} = \arg\min_\theta \text{NLL}(\theta)$ is refined via Fisher scoring:
$$\theta^{(k+1)} = \theta^{(k)} - \left( \mathcal{I}(\theta^{(k)}) \right)^{-1} \frac{\partial \text{NLL}}{\partial \theta}$$
Where the Fisher Information is:
$$\mathcal{I}(\theta) = \sum_{m=0}^{M-1} \frac{1}{\mu_m^2(\theta)} \left( \frac{\partial \mu_m}{\partial \theta} \right)^2$$
The theoretical asymptotic variance achieves the Cramér-Rao Lower Bound (CRLB):
$$\text{Var}(\hat{\theta}) \ge \mathcal{I}^{-1}(\theta)$$

---

### 8. Multi-Radar Triangulation Fix (Orthogonal Projection LS)

Given $N \ge 2$ ground stations with known positions $\vec{r}_i = [x_i, z_i]^T$ and estimated unit direction vectors $\hat{d}_i = [\cos\theta_i, \sin\theta_i]^T$:
The orthogonal projection operator onto the null space of $\hat{d}_i$ is:
$$P_i^\perp = I - \hat{d}_i \hat{d}_i^T \in \mathbb{R}^{2 \times 2}$$
The closest point of approach $\vec{p} = [x, z]^T$ satisfies:
$$P_i^\perp (\vec{p} - \vec{r}_i) \approx \vec{0}$$
Weighting each station by its angular variance $w_i = \frac{1}{\sigma_i^2}$, the closed-form least-squares target position is:
$$\hat{\vec{p}} = \left( \sum_{i=1}^N w_i P_i^\perp \right)^{-1} \left( \sum_{i=1}^N w_i P_i^\perp \vec{r}_i \right)$$
The condition number $\kappa = \frac{\sigma_{\max}}{\sigma_{\min}}$ of the system matrix $\sum w_i P_i^\perp$ quantifies the Geometric Dilution of Precision (GDOP).

---

### 9. 3D Swept-Segment Cyrus-Beck Intersection Formulation

For continuous swept-volume collision avoidance, a line segment between previous position $\vec{p}_0$ and proposed position $\vec{p}_1$ parameterized by $t \in [0, 1]$ is:
$$\vec{p}(t) = \vec{p}_0 + t (\vec{p}_1 - \vec{p}_0)$$
For an axis-aligned bounding box expanded by total buffer $B = r_{drone} + r_{margin} = 0.8 + 2.2 = 3.0\text{ m}$:
$$[X_{min} - B, X_{max} + B] \times [0, H + B] \times [Z_{min} - B, Z_{max} + B]$$
The segment intersects the volume if and only if:
$$t_{enter} = \max_k \left( \min(t_{k, 1}, t_{k, 2}) \right) \le t_{exit} = \min_k \left( \max(t_{k, 1}, t_{k, 2}) \right)$$
and $[t_{enter}, t_{exit}] \cap [0, 1] \neq \emptyset$, where $t_{k, i}$ are the slab entry and exit parameters along axes $k \in \{x, y, z\}$. Checking this condition at every simulation step prevents high-speed tunneling through obstacles.

