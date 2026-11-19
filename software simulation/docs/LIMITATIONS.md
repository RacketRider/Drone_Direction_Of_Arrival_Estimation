# System Limitations & Theoretical Discrepancies
## EC261: Honest Physical Boundary Conditions & Assumptions

### 1. Mathematical Limitations of Switched Covariance
- **Coherence Requirement:** Mode B (single-channel switched SDR) assumes that the received signal phase evolves deterministically as $e^{j 2\pi f_{BB} t}$ across the 4 dwell slots ($128 \mu s$). If the UAV telemetry transmitter uses high-baud phase-shift keying (e.g. fast BPSK/QPSK with symbol transitions occurring within a dwell slot) without a known preamble/pilot, phase transitions between slots cannot be modeled by simple carrier de-rotation alone.
- **Switch Settling Time:** The model assumes $N_{settle} = 4$ samples ($2.0 \mu s$) are sufficient for HMC241 settling. On physical hardware, PCB parasitic capacitance, switch drive ringing, and RTL-SDR automatic gain control (AGC) transients may require up to $10–20 \mu s$ of settling time.

---

### 2. Antenna Array & Mutual Coupling
- **Idealized Element Patterns:** The simulation models array elements as ideal isotropic/omnidirectional vertical monopoles. In a physical compact array with $r = 7.2$ cm, mutual electromagnetic coupling between adjacent elements alters the effective active element pattern and introduces cross-channel admittance.
- **Array Elevation Dependency:** The steering manifold in this suite models 2D horizontal ground plane azimuth ($\psi_{elev} = 0$). For UAVs flying at steep elevation angles ($> 60^\circ$), spherical 3D manifold modeling ($a_m(f, \theta, \psi) = \exp(j \frac{2\pi f r}{c} \cos\psi \cos(\theta - \phi_m))$) is necessary to avoid projected baseline foreshortening.

---

### 3. Ray-Tracing & Propagation Assumptions
- **Single-Bounce Specular Reflections vs Full-Wave FDTD:** In the real-time simulation loop ($\sim 20$ Hz), the multipath engine evaluates single-bounce specular reflections from vertical building walls using the Image Source Method and complex concrete impedance. To complement real-time ray-tracing, the suite now provides offline/on-demand **2D TMz and 3D Vector Maxwell Yee-grid FDTD solvers** (`em_solver.py` and `em_solver_3d.py`) in the **EM & Multi-Radar Lab** for analyzing exact near-field diffraction, building edge scattering, and material penetration.
- **Narrowband Assumption:** The MUSIC algorithm relies on the narrowband array assumption:
  $$\frac{2r}{c} \ll \frac{1}{B_{sig}}$$
  For an array diameter of $2r = 0.144$ m, the maximum travel time across the array is $\Delta\tau = 0.48$ ns. For telemetry signals with bandwidth $B \le 500$ kHz, $B \cdot \Delta\tau \approx 0.00024 \ll 1$, satisfying the narrowband condition cleanly.

---

### 4. RTL-SDR Bandwidth & Frequency Hopping
- **Narrowband Capture:** An RTL-SDR has a baseband sample rate of $F_s \le 2.4$ MS/s (modeled at $2.0$ MS/s). It cannot monitor 433 MHz and 915 MHz simultaneously. In real-world operation, the ground station must either hop synchronously with the transmitter or operate multiple SDR tuners.

