# Fixes and enhancements applied

## Original defects corrected
- Fixed the terrain-grid variable scope issue in the Three.js scene initialization.
- Corrected the ground-material attenuation settings that caused a `TypeError` in the estimate and multi-radar logic.

## Electromagnetic material model added
- Added unique per-tree wood and foliage material profiles for all 97 trees, including separate properties for each of the 291 foliage layers.
- Added individual mineral/material profiles for all 12 stones and distinct profiles for four visible water patches.
- Added four selectable ground profiles: dry soil, moist soil, rocky ground and wet soil.
- Added an in-app inspector for relative permittivity (εr), conductivity (σ), relative permeability (μr), effective dielectric loss tangent, magnetic loss tangent and moisture.
- Added a 2.4 GHz reference frequency and documented the fact that values vary with frequency, moisture, temperature and mineral composition.
- Added property-dependent, simplified complex-impedance/Fresnel ground reflection and near-path object-scattering terms to the synthetic RF model.
- Extended the Excel export with reference frequency, ground properties, object count and nearby-object material loss.
- Synced `templates/index.html` and `index_preview.html`.

## Validation performed
- Python source compiles successfully.
- Browser JavaScript module passes Node syntax checking.
- Material-profile tests confirmed unique properties across 97 tree wood profiles, 291 foliage layers, 12 stones and four ground presets.
- Simulated estimate and multi-radar handlers passed smoke tests using a local Flask test stub.
- Ground-material variations changed the modeled loss, and low-loss/high-loss foliage profiles produced different object loss.
- Excel column and width definitions were checked for alignment.

## Scientific limitation
The new property model is a compact educational approximation, not a full-wave Maxwell solver, calibrated ray tracer or measured RF channel. Use measured properties at the operating frequency before relying on quantitative predictions.
