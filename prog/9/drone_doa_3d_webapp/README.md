# Drone DoA 3D Lab

Interactive browser front-end connected to the project's actual Python DoA simulation library (`doa_sim.py`). It renders a virtual 3D antenna site and drone, animates drone azimuth using speed/range, and requests fresh estimates from Python.

## Features
- 3D orbitable scene with a drone, circular antenna site, individual directional antenna panels, beam visualization, true/raw/tracked bearing rays.
- Controls for azimuth, elevation, range, speed, antenna count, SNR, samples per dwell, Rician K-factor, interference and estimator.
- Estimator: Power-vector ML (PV-ML) only, applied independently to each active radar.
- Adaptive Kalman tracking using the Python simulation's `AngleTracker`.
- Live history chart, beam power readings, angle error, recent RMSE and confidence.
- Export recent measurements from every active radar to an Excel workbook (.xlsx).

## Run on Windows
1. Extract the ZIP archive.
2. Open Command Prompt in the extracted folder.
3. Install the required Python dependencies (including Flask):
   ```bat
   python -m pip install -r requirements.txt
   ```
4. Start the local Python server:
   ```bat
   python app.py
   ```
5. Open **http://127.0.0.1:5000** in Chrome or Edge. Keep the terminal window open while using the page.

The page calls the Flask Python backend over localhost. Three.js is loaded from jsDelivr, so internet access is required for the 3D renderer. Do not open `templates/index.html` directly; start `app.py` first.

## Important interpretation notes
- All RF data are synthetic. This is not connected to an SDR and does not detect actual drone transmissions.
- The existing estimator is azimuth-only. Elevation and range control the 3D geometry but are not currently estimated by the DoA algorithms.
- MUSIC and ESPRIT use coherent multichannel array snapshots, so they are reference methods with higher receiver hardware requirements than the switched-beam system.
- Browser/backend estimates use the uploaded project's `doa_sim.py`; they should still be validated against recorded RF data before field-performance claims.

## Adaptive flight paths for any radar count

Flight paths are no longer tied only to the primary radar. The app computes the centroid (average X/Z position) of all active radar stations and the layout footprint (distance from that centroid to the farthest radar). With one radar, the original flight paths are preserved. With two to six radars, the same path controls adapt to the complete layout:

- **Approach radar / network centre:** with one radar, the drone approaches that radar as before. With multiple radars, it approaches the centre of the full radar network.
- **Depart from radar / network:** with one radar, the drone departs outward as before. With multiple radars, it starts near the network and moves outward beyond the full radar footprint.
- **Fly past radar / across network:** with one radar, the original fly-by remains. With multiple radars, the flight line passes through the central area of the radar layout, crossing the field covered by the stations.
- **Orbit around radar / network:** with one radar, the drone circles the radar as before. With multiple radars, it circles the network centroid outside the outermost radar.
- **Manual position / hold:** the drone stays at the manually selected coordinates.

The direction slider chooses the radial heading or fly-by axis; speed controls motion. Adding or moving radars changes the computed network centre and footprint, so the flight geometry adapts to the current arrangement rather than assuming four radars or a fixed compass layout. These are synthetic teaching trajectories, not a validated aerodynamic model.

## 3D visual refresh

The refreshed scene uses a larger cinematic viewport, improved perspective and tone mapping, soft shadows, layered atmospheric lighting, a matte ground plane with major/minor engineering grids, concentric range rings, and a detailed antenna mast/platform. Directional antenna panels now have illuminated element strips and translucent beam volumes. The drone model has a sculpted body/canopy, carbon-style arms, motor cans, spinning twin-blade propellers, rotor-disc effects, front/rear navigation lights, a ground marker, and an altitude projection line. The radar scan ring and drone marker animate while the simulation is running.

For the best appearance, use a modern browser with WebGL enabled and an internet connection for the Three.js modules. On a lower-powered computer, close other GPU-heavy tabs or lower the browser window size. This remains a stylized engineering visualization, not photorealistic rendering or a validated electromagnetic propagation model.


## Moving objects in the 3D scene
- Click directly on the drone and hold the mouse button while dragging it to move its ground position.
- Click directly on the primary radar and drag it to move the radar site.
- Drag empty space to orbit the camera; use the mouse wheel to zoom and right-drag to pan.
- Use the X/Z number fields for precise positions, then select **Apply coordinates**.
- **Reset object positions** restores the initial drone and radar locations.
- Moving either object switches the flight mode to Manual / hold so the animation does not immediately override the position.

## Multi-radar drone localization

The scene now supports up to six radar stations (the original primary radar plus five additional radars). Use **Add radar** to place a new station, then drag any radar model directly in the 3D scene to reposition it. **Remove last** removes the most recently added secondary station. The drone broadcasts visible expanding spherical signal pulses in all directions; each station reports its own synthetic received signal strength and noisy DoA bearing. A yellow **true-bearing line** connects every radar to the drone. The blue per-radar DoA line shows each station’s measured bearing estimate, and a purple **track-bearing line** shows that station’s independently smoothed bearing over time. Each radar maintains its own track filter, so the purple line is no longer exclusive to Radar 1. All stations use the same 3D model and are labelled simply **1, 2, 3, ...**.

With two or more radars, the Python `/api/multiradar` endpoint combines the independent bearing measurements using weighted least-squares intersection to estimate the drone's horizontal X/Z location. The interface displays the estimated location, position error against the known simulated truth, and each radar's range, measured bearing, smoothed track bearing, and signal capture status. Radar geometry matters: stations spread around the flight area produce a better estimate than stations placed almost on the same line.

All RF readings are synthetic teaching data, not hardware measurements. The position estimate is 2D (X/Z); drone altitude remains visualized separately.


### Radar beam visualization

The large translucent cone-shaped antenna scanning lights and their boresight rays are disabled for all radar stations. Radar-to-drone true-bearing, measured DoA, and tracked-bearing lines remain visible, along with the drone's expanding omnidirectional signal pulses.


### Per-radar diagnostics
The Azimuth history panel includes a Radar selector. Changing it updates both the azimuth history and switched-beam power profile for the selected radar. Shared RF controls (directional antenna count, SNR, samples per dwell, Rician K-factor, and interference settings) are applied to every radar in each multi-radar measurement. PV-ML is the only enabled estimator in the interface and is applied independently at every radar.


## Drone controls in multi-radar mode

Drone controls describe the shared drone, not Radar 1. With one radar, azimuth and range retain their original Radar 1-relative meaning. With multiple radars, the azimuth slider sets the drone flight heading from the centroid of all active radar positions; the distance slider sets the distance from that network centre (or the closest-pass offset in fly-by mode). Elevation and speed affect the same drone for every radar. RF settings such as estimator, antenna count, SNR, samples per beam dwell, Rician K-factor, and interference are common settings applied to each radar's independent synthetic measurement. Radar positions and individual measurement histories remain station-specific.


### World coordinate axes
The 3D scene marks the origin with three labelled positive coordinate axes: X in red, Y in green, and Z in blue. Their arrows indicate positive direction; all three share the origin.


### Coordinate display note
The multi-radar dashboard displays estimated X / Y / Z coordinates. The current bearing-line least-squares solver estimates horizontal X/Z; Y is the drone altitude from the simulation state, not an independently estimated vertical coordinate. The displayed position error is therefore horizontal X/Z error.


### Direct coordinate controls (updated)

The Direct Scene Control panel now exposes the drone X/Y/Z coordinates and a dynamically generated X/Z coordinate row for every active radar. Adding or removing radars updates these rows automatically. Radar stations remain ground-based (Y = 0); the drone Y field controls its altitude. Enter coordinates and choose Apply coordinates to place the drone and all radars.


## Excel measurement export

The Export measurement Excel button downloads `drone_doa_measurements.xlsx`. It contains one row per radar per measurement timestamp, with each radar's position, true and estimated bearing, tracked bearing, angular errors, range, received power, effective SNR, drone ground-truth coordinates, estimated horizontal position, and horizontal position error. The workbook intentionally omits `track_state`, the boolean `received` flag, `location_solution_valid`, `method`, `samples`, and `interference`. Up to 30,000 recent radar-measurement rows are retained in the browser session.

The interface hides explanatory helper text and connection/status badges to keep the demonstration view cleaner. The only selectable estimator is PV-ML.


## Synthetic forest propagation experiment

The RF controls now include **Open area**, **Light vegetation**, and **Dense forest / low altitude**.
The environment model applies path-dependent attenuation to effective SNR and a random angular bias
to approximate multipath. Each radar gets its own simulated path loss and angular bias, so the
same drone can produce different bearing quality at different stations. The Excel export records
the selected environment, vegetation loss, and simulated multipath bias for each radar measurement.

These forest parameters are illustrative teaching assumptions, not a calibrated foliage model or
validated prediction for a specific RF frequency, tree species, soil moisture, or forest layout.
The simulation remains synthetic and should not be presented as field-tested performance.


### Randomized flight path
Select **Randomized route (new every selection)** from Drone Control. The app generates a new closed 3D waypoint route around the active radar network every time this mode is selected. The drone follows it at the selected speed; choosing another mode and returning to Randomized route generates a different route. The path is synthetic and intended for visualization/testing.

## Object-specific electromagnetic material model

The 3D scene now assigns individual RF material profiles to each tree trunk, each of its three foliage layers, every stone, and each displayed water patch. The **Electromagnetic material inspector** lets you select an individual object/component and see:

- Relative dielectric permittivity, εr
- Electrical conductivity, σ in S/m
- Relative magnetic permeability, μr
- Effective dielectric loss tangent, tan δe, including the conductivity contribution at the 2.4 GHz reference frequency
- Magnetic loss tangent, tan δm, and nominal moisture percentage

The ground selector offers four different property profiles: dry soil, moist soil, rocky ground and wet soil. The chosen ground properties are used in a complex-impedance/Fresnel reflection approximation. Nearby visible trees, stones and water patches contribute small object-specific attenuation and multipath terms based on their own profiles and distance from each radar-to-drone path. The Excel export includes the reference frequency, selected ground properties, number of nearby material objects and their combined illustrative loss.

**Scientific limitation:** these are representative teaching presets near 2.4 GHz, not exact values of real objects. Permittivity and electrical loss depend strongly on frequency, moisture, temperature, orientation and mixture; most ordinary wood/soil/rock has relative permeability close to 1, while iron-rich mineral content can make some rocks more magnetic. The propagation layer is a compact stochastic approximation, not a full-wave Maxwell solver, ray-tracing engine or field-calibrated RF predictor. Use measured material data for a specific frequency/site before treating the outputs as quantitative predictions.

Background ranges and context: [FHWA dielectric ranges](https://infotechnology.fhwa.dot.gov/gpr-ground-penetrating-radar-utility-general/), [microwave dielectric properties of rock](https://pmc.ncbi.nlm.nih.gov/articles/PMC4986322/), [USGS electrical and magnetic properties of rock and soil](https://www.usgs.gov/publications/electrical-and-magnetic-properties-rock-and-soil).

## Propagation study: geometric blockage + 2D FDTD

The **Propagation study** panel calls `POST /api/propagation-study` and runs:

- Segment/triangle intersection when triangle facets are explicitly supplied to the API; axis-aligned box and analytic circle tests are also supported. The existing browser scene sends object-level circle proxies, not the rendered Three.js triangle meshes, so those results are proxy-based until triangle facets are exported from the browser.
- A bounded 2D TMz Yee-grid finite-difference time-domain (FDTD) simulation at the selected frequency. It updates the out-of-plane electric field and in-plane magnetic fields in a local wavelength-resolved patch, with material-dependent permittivity/conductivity and a lossy sponge edge.
- A normalized field heatmap and basic finite-value/Courant metadata.

### Important scope and limitations

This is a **2D local cross-section solver**, not a full 3D Maxwell solve and not a solver for the entire 45 m scene. At 2.4 GHz, the free-space wavelength is about 12.5 cm; a 10-cell-per-wavelength grid needs roughly 1.25 cm cells. Resolving tens of metres at that scale creates millions of cells and is not a lightweight browser-demo workload. The boundary is a lossy sponge, not a perfectly matched layer (PML/CPML). Material maps are simplified object cross-sections. The current scene-to-solver bridge uses analytic object proxies; true exact tests against the rendered meshes require exporting their world-space triangles and submitting those triangles to the API. Do not present this prototype as experimentally validated or as a full 3D electromagnetic model.

### Run and test

```bash
pip install -r requirements.txt
python -m unittest test_em_solver.py -v
python app.py
```

The automated tests cover triangle and proxy intersections, a clear path, and finite bounded FDTD output. These are smoke tests, not validation against a laboratory measurement or a published reference solution.

The propagation endpoint also returns single-bounce specular reflection candidates found by reflecting the source across supplied triangle planes and checking that the reflection point lies inside the facet. It returns facet-centroid diffuse-scatter candidates as a visualization aid. The diffuse candidates are not a physical scattering solution, and candidate path amplitudes, polarization, phase coefficients, and antenna patterns are not yet solved by this ray helper.


## Bounded 3-D Maxwell FDTD mode

The Propagation Study panel now offers **Run 3D Maxwell FDTD**. It calls `/api/propagation-study-3d`, which runs a vector 3-D Yee-style update for Ex/Ey/Ez and Hx/Hy/Hz on a small local voxel patch and renders the central |Ez| slice. The included air/soil/rock/vegetation inclusions are illustrative voxel geometry, not imported tree/rock meshes. Geometry ray tests remain a separate 3-D triangle/primitive operation.

Run `python -m unittest test_em_solver_3d.py -v` to exercise the 3-D solver's finite-field and Courant checks. This is a bounded prototype with a lossy sponge boundary, not CPML, and it is not a 45 m full-scene solve. At 2.4 GHz, wavelength-resolved full-scene 3-D FDTD would require an extremely large grid. Results have not been validated against a reference solver or laboratory measurements.
