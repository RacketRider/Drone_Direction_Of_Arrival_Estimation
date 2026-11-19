# RF Propagation & Multipath Physics
## EC261: Channel Modeling in Urban/Semi-Urban Arenas

### 1. Free-Space Path Loss (FSPL) & Delay
For a direct propagation path of length $d_{LOS} = \|\vec{p}_{UAV} - \vec{p}_{GS}\|$, the physical attenuation follows Friis transmission equation:
$$\text{FSPL}(d, f) = \left(\frac{4\pi d f}{c}\right)^2$$
In decibels:
$$\text{FSPL}_{dB} = 20 \log_{10}(d) + 20 \log_{10}(f) - 147.55$$
The geometric propagation delay is:
$$\tau_{LOS} = \frac{d_{LOS}}{c}$$
Carrier phase accumulation over distance $d_{LOS}$:
$$\phi_{prop} = -\frac{2\pi f d_{LOS}}{c} \pmod{2\pi}$$

---

### 2. Concrete Building Occlusion
When the UAV flies behind a concrete obstacle, the direct Line-of-Sight ray is occluded. Line segment intersection with the 3D bounding box $[x_{min}, x_{max}] \times [0, h] \times [z_{min}, z_{max}]$ is evaluated using 3D slab ray-tracing:
- If ray penetrates below rooftop height $h$, direct path attenuation is heavily penalized:
  $$A_{atten} = -25 \text{ dB} \implies A_{linear} \approx 0.056$$
- Signals propagating through reinforced concrete experience heavy diffraction loss and attenuation, shifting the dominant received energy to multipath reflections.

---

### 3. Specular Reflection via Image Source Method
For each planar vertical face of Building Alpha and Beta:
Let the wall plane be defined by outward unit normal $\hat{n}$ and offset $d_{plane}$.
1. **Virtual Image Source:**
   The ground station $\vec{p}_{GS} = (0, 0, 0)$ is mirrored across the wall plane:
   $$\vec{p}'_{GS} = \vec{p}_{GS} - 2(\vec{p}_{GS} \cdot \hat{n} - d_{plane})\hat{n}$$
2. **Specular Point $\vec{p}_{refl}$:**
   The intersection of line segment $[\vec{p}_{UAV}, \vec{p}'_{GS}]$ with the plane gives the specular bounce point:
   $$\vec{p}_{refl} = \vec{p}_{UAV} + t (\vec{p}'_{GS} - \vec{p}_{UAV}), \quad t \in (0, 1)$$
3. **Visibility Verification:**
   Valid if $\vec{p}_{refl}$ falls within the physical rectangular face bounds: $y \in [0, h]$ and within the wall's horizontal coordinates.
4. **Multipath Delay & Phase:**
   Total reflected path length:
   $$d_{NLOS} = \|\vec{p}_{UAV} - \vec{p}_{refl}\| + \|\vec{p}_{refl} - \vec{p}_{GS}\|$$
   Excess delay relative to LOS:
   $$\Delta\tau = \frac{d_{NLOS} - d_{LOS}}{c}$$
   Carrier phase rotation:
   $$\Delta\phi = 2\pi f \Delta\tau + \pi$$
   (where $\pi$ represents the electromagnetic reflection phase flip at a dielectric interface).

---

### 4. Dispersive Wall Scattering
Concrete walls exhibit surface roughness relative to sub-GHz wavelengths ($\lambda \approx 32$ cm at 915 MHz). Over the duration of an $N=256$ snapshot burst ($128 \mu s$), spatial scattering and micro-Doppler modulate the reflected phase:
$$s_{NLOS}(t) = \alpha_{NLOS} \cdot s(t - \Delta\tau) \cdot e^{j \Delta\phi} \cdot e^{j \psi_{scatter}(t)}$$
Where $\psi_{scatter}(t)$ introduces phase dispersion across the burst. This phase dispersion decorrelates the multipath reflection from the direct LOS path, raising the second eigenvalue $\lambda_2$ in the spatial covariance matrix and enabling the **Eigenvalue Reliability Gate** to detect and reject the corrupted burst.

---

### 5. Complex AWGN Channel
Complex zero-mean additive white Gaussian noise is added independently to each antenna channel:
$$x_m[n] = x_{direct, m}[n] + \sum_p x_{NLOS, m, p}[n] + n_m[n]$$
$$n_m[n] \sim \mathcal{CN}(0, \sigma^2)$$
With $\sigma^2 = P_{sig} \cdot 10^{-\text{SNR}_{dB}/10}$, ensuring exact calibration to specified SNR values from $-5$ dB to $+30$ dB.

---

### 6. Complex Concrete Dielectric Impedance & Fresnel Reflection
Concrete facets in the simulation arena are modeled as conductive lossy dielectrics with complex permittivity:
$$\varepsilon^* = \varepsilon_0 \varepsilon_r - j \frac{\sigma}{\omega}$$
Where:
- $\varepsilon_r = 5.50$ (Relative permittivity of cured reinforced concrete)
- $\sigma = 0.020\ \text{S/m}$ (Conductivity)
- $\omega = 2\pi f$ (Angular RF frequency)
- Dielectric loss tangent: $\tan \delta = \frac{\sigma}{\omega \varepsilon_0 \varepsilon_r} \approx 0.030$ at 915 MHz.

The complex intrinsic impedance of concrete is:
$$\eta = \sqrt{\frac{\mu_0}{\varepsilon^*}} \approx 160.6\ \Omega$$
Compared to free space $\eta_0 \approx 376.73\ \Omega$, the normal incidence Fresnel reflection magnitude is:
$$|\Gamma| = \left| \frac{\eta - \eta_0}{\eta + \eta_0} \right| \approx 0.408\ (40.8\%)$$

---

### 7. Yee-Grid FDTD Full-Wave Electromagnetic Solvers
For sub-wavelength wave scattering and near-field diffraction around building corners, the simulation provides numerical finite-difference time-domain (FDTD) solvers:

#### A. 2D TMz Yee-Grid FDTD (`em_solver.py`)
Decouples Maxwell's equations into transversal electric $E_z$ and magnetic $H_x, H_y$ components:
$$\frac{\partial H_x}{\partial t} = -\frac{1}{\mu_0} \frac{\partial E_z}{\partial y}$$
$$\frac{\partial H_y}{\partial t} = \frac{1}{\mu_0} \frac{\partial E_z}{\partial x}$$
$$\frac{\partial E_z}{\partial t} = \frac{1}{\varepsilon} \left( \frac{\partial H_y}{\partial x} - \frac{\partial H_x}{\partial y} - \sigma E_z \right)$$
- Spatial resolution: $\Delta x = \Delta y = 0.034\ \text{m}$ (10 cells per wavelength at 915 MHz).
- Temporal stability: $\Delta t = \frac{\Delta x}{\sqrt{2} c} \cdot 0.99$.
- Absorbing sponge boundary layers prevent non-physical artificial boundary reflections.

#### B. 3D Cartesian Vector Maxwell Yee-Grid FDTD (`em_solver_3d.py`)
Computes all 6 coupled electromagnetic field vectors ($E_x, E_y, E_z, H_x, H_y, H_z$) on a staggered Yee cell grid:
$$\vec{H}^{n+1/2} = \vec{H}^{n-1/2} - \frac{\Delta t}{\mu} (\nabla \times \vec{E}^n)$$
$$\vec{E}^{n+1} = \left(\frac{2\varepsilon - \sigma \Delta t}{2\varepsilon + \sigma \Delta t}\right) \vec{E}^n + \left(\frac{2\Delta t}{2\varepsilon + \sigma \Delta t}\right) (\nabla \times \vec{H}^{n+1/2})$$
- Enforces Courant-Friedrichs-Lewy (CFL) stability criterion:
  $$C = c \Delta t \sqrt{\frac{1}{\Delta x^2} + \frac{1}{\Delta y^2} + \frac{1}{\Delta z^2}} \le 0.95$$
- Verifies finite field propagation and spatial wave dissipation throughout concrete voxels.

