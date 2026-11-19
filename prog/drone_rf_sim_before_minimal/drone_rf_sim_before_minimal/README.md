# Drone RF DoA Lab: 3D propagation and direction-finding simulation

An interactive 3D simulation of RF direction-of-arrival (DoA) estimation for a drone in an outdoor scene with trees, rocks, soil and puddles. Each object has its own electromagnetic material. The drone's waves are ray-traced against the real meshes (reflection, refraction/penetration, diffraction, scattering). The resulting signals feed the project's switched-beam **PV-ML** estimator at every receiver. Two or more receivers combine their bearings into a position estimate.

## How to run

1. Open `index.html` in **Chrome or Edge** (double-click it). No Python or server is needed.
2. Internet access is needed the first time, because Three.js and the Excel library load from a CDN.

> Keep `rf_physics.js` in the same folder as `index.html`.

## What you can do

| Action | How |
|---|---|
| See how a wave interacts with a **tree, rock, puddle or the ground** | Click it. Probe rays appear in 3D: incident (amber), reflected (orange), refracted inside the material (green), internal reflection (light green), exiting (blue), scattered (grey), surface normal (dark). The object turns semi-transparent so the refracted rays inside are visible. Animated packets slow down inside the material (v = c/n). |
| Get close to the object | **Double-click** it, or use **⌖ Zoom to selection**. **⤢ Overview** returns to the overview camera. |
| Watch Maxwell's equations at work | The inspector's **Wave view** runs a live 2D FDTD through the object's real cross-section. It shows reflection, a shorter wavelength inside, absorption, shadowing and diffraction. Switch between *Field Ez* and *Intensity*, and change the slice height and grid. |
| Change materials | The inspector has presets plus εr, σ and μr sliders. Derived values update live: εc, n, tan δ, attenuation in dB/m, skin depth, λ inside, η, Brewster angle, and a Fresnel chart. |
| Move things | Drag the drone, receivers, interferers, rocks, trees or puddles. Dragging empty space orbits the camera. |
| Multiple receivers | Add/remove receivers (1–6). One receiver gives a **bearing only**. Two or more give a weighted least-squares **position** with an error ellipse. |
| Multiple signals | Add a Wi-Fi AP, a ground controller or a second drone, each with its own power and channel (co- or adjacent). The table shows **SNR, SIR and SINR separately**. |
| SNR scenarios | Use the −10 / 0 / +10 / +20 dB presets, or set the transmit power directly. |
| Compare mechanisms | Turn direct, penetration, ground reflection, facet reflection, 2-bounce, diffraction and diffuse scattering on or off. With penetration off, obstacles become opaque. |
| Coverage map | *Display → Compute map* draws a coherent received-power slice. Shadows and ground-reflection fringes are visible. |
| Export | **Excel**: measurement log, every path at the current instant, the scene materials and the settings. **CSV**: the measurement log. |

Scenarios: Mixed forest edge, Open field, Light woodland, Dense forest with a low-altitude drone, and Rocky outcrop. Flight paths are deterministic (orbit, fly across, approach, figure-eight, forest transit, or hover/manual). There is no randomised path.

## Physics summary

* **Materials:** `εc = εr − jσ/(ωε0)`, `n = √(εc μr)`, `α = k0·|Im n|`. Fresnel TE/TM coefficients use complex impedances. Polarisation is carried as a complex 3-vector through every bounce.
* **Direct path:** exact segment–triangle intersection. Each crossed object adds interface loss at the true facet angles plus bulk attenuation `e^{−αL}` and phase `(β−k0)L` (straight-line slab approximation).
* **Ground:** image method with soil Fresnel coefficients (water inside puddles) and Rayleigh roughness.
* **Facets:** image method on every rock/trunk facet, with a finite-facet (physical-optics) correction, plus ground↔facet second order.
* **Diffraction:** ITU-R P.526 knife-edge over the top and around the sides of a blocking obstacle.
* **Diffuse scattering:** Lambertian effective-roughness model for rocks and trunks, volume scattering for canopies (incoherent).
* **Receiver:** N-beam switched array with one RF chain (same model as `doa_sim.py`). Beam power is drawn as an average of L samples, then **PV-ML**, then a Kalman tracker. Bartlett and MUSIC run on an equivalent coherent circular array for reference.
* **Localisation:** weighted least-squares bearing intersection in X–Z. Altitude is **not** estimated, because the arrays are azimuth-only.
* **FDTD:** 2D TMz Yee grid with a graded absorbing boundary and an oblique plane-wave source. Grid resolution (cells/λ) is reported, with a warning when it is coarse.

## Honest limitations (state these in the report)

* Material values are representative presets near 2.4 GHz, not site measurements.
* Ray optics is a high-frequency approximation. Facet–facet multi-bounce and reflection-after-transmission paths are not traced.
* The FDTD view is a **2D local cross-section**, not a 3D full-scene Maxwell solve.
* All RF data are synthetic. No SDR hardware is connected, and nothing here is a field-validated detection claim.

## Files

* `index.html`: 3D application (Three.js), UI, charts, export.
* `rf_physics.js`: propagation engine, DoA estimators, tracker, localiser, FDTD (dependency-free).
* `tests/test_physics.js`: 41 checks against analytical results (Fresnel/Brewster/Snell, penetration loss, two-ray ground model, image method, knife-edge, PV-ML and MUSIC accuracy, localisation, Kalman wrap-around, FDTD wavelength and stability). Run with `node tests/test_physics.js`.
