# Switched-Interferometric SDR Model
## EC261: Physical Modeling of Single-Channel Sequential Sampling

### 1. Hardware Architecture Overview
The receiver hardware comprises:
- **Array:** 4-element Uniform Circular Array ($r = 0.072$ m).
- **RF Switch:** Analog Devices / Hittite **HMC241 SP4T** non-reflective GaAs solid-state switch.
- **Controller:** **ESP32 microcontroller** toggling GPIO control pins $A$ and $B$.
- **SDR Frontend:** Single **RTL-SDR** (R820T2 tuner + RTL2832U ADC) streaming baseband IQ at $2.0$ MS/s.

```
Antenna 0 ──┐
Antenna 1 ──┤  HMC241 SP4T
Antenna 2 ──┼──[ RF Switch ]──> RTL-SDR Tuner (2 MS/s) ──> Baseband IQ
Antenna 3 ──┘        ▲
                     │ (GPIO A, B)
                 [ ESP32 ]
```

---

### 2. Physical Sequential Sampling vs Spatial Covariance

In a standard 4-channel coherent receiver (**Mode A**), all four antennas are sampled simultaneously at time $t_n$:
$$X[n] = [x_0[n], x_1[n], x_2[n], x_3[n]]^T$$
The sample covariance matrix $R_{xx} = \frac{1}{N} X X^H$ captures spatial phase differences directly.

In a switched receiver (**Mode B**), only **one** antenna is connected to the single SDR ADC at any given time.
For a burst of $N=256$ samples ($128 \mu s$ total duration at 2 MS/s):
- Slot 0: Antenna 0 is connected for $n \in [0, 63]$ ($T_{dwell} = 32 \mu s$).
- Slot 1: Antenna 1 is connected for $n \in [64, 127]$ ($T_{dwell} = 32 \mu s$).
- Slot 2: Antenna 2 is connected for $n \in [128, 191]$ ($T_{dwell} = 32 \mu s$).
- Slot 3: Antenna 3 is connected for $n \in [192, 255]$ ($T_{dwell} = 32 \mu s$).

---

### 3. Critical Phase Evolution & Temporal De-Rotation

Between Slot 0 and Slot $m \in \{1, 2, 3\}$, the transmitted signal carrier has evolved in time by:
$$\Delta t_m = m \cdot T_{dwell}$$
The complex baseband waveform received at slot $m$ is:
$$x_m(t + \Delta t_m) = a_m(f_k, \theta) \cdot s(t + \Delta t_m) = a_m(f_k, \theta) \cdot s(t) \cdot e^{j 2\pi f_{BB} \Delta t_m}$$
If sequential samples are naively assembled into a covariance matrix without correction:
$$\arg(x_m) - \arg(x_0) = \underbrace{\Phi_m(\theta)}_{\text{Spatial DOA Phase}} + \underbrace{2\pi f_{BB} \Delta t_m}_{\text{Temporal Carrier Phase Drift}}$$
At $f_{BB} = 150$ kHz, over $\Delta t_3 = 96 \mu s$:
$$2\pi f_{BB} \Delta t_3 = 2\pi \times 150000 \times 96\times 10^{-6} \approx 28.8\pi \text{ radians} \implies \text{Severe phase wrapping!}$$
This temporal phase drift completely corrupts the spatial phase relationship, destroying the rank-1 structure of $R_{xx}$ and producing random bearing errors.

#### Digital De-Rotation Model:
The baseband offset $\hat{f}_{BB}$ is estimated with high precision ($< 10$ Hz) using fine differential phase estimation. Each slot is digitally de-rotated:
$$x_m^{reconstructed}[k] = x_m[k] \cdot \exp\left(-j 2\pi \hat{f}_{BB} \cdot m \cdot T_{dwell}\right)$$
This aligns all 4 antenna channels to an equivalent instantaneous spatial snapshot.

---

### 4. Switch Transients & Settling Time
During the actuation transition of the GaAs FET switch, RF impedance mismatch and charge injection corrupt the first few ADC samples.
- The first $N_{settle} = 4$ samples ($2.0 \mu s$) of each dwell slot are discarded as transient corrupted samples.
- Effective snapshots per slot: $N_{eff} = N_{dwell} - N_{settle} = 64 - 4 = 60$ clean samples.

---

### 5. RTL-SDR Local Oscillator (LO) & Bandwidth Model
- RTL-SDR complex baseband bandwidth is limited to $B = 2.0$ MHz ($-1.0$ MHz to $+1.0$ MHz around LO).
- If the SDR LO is fixed at $915$ MHz and the drone hops to $433$ MHz, the signal falls $482$ MHz out of band and is rejected by the tuner filter ($-60$ dB attenuation).
- **Synchronous Hopping Mode:** Simulates an SDR tuner retuning synchronously with the transmitter hopping schedule ($f_{LO} = f_k - f_{IF}$ with $f_{IF} = 150$ kHz).
- **Static LO Mode:** Demonstrates burst acquisition failure when hopping across wide frequency bands with a single narrowband SDR.

