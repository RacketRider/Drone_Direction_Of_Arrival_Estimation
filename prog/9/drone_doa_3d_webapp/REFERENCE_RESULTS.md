# Drone Direction-of-Arrival Simulation Results

- Random seed: `20261010`
- Mode: `full`
- Monte Carlo trials per sweep point: 250
- Array: 6-element switched directional array; 64 samples per beam dwell
- Reference methods MUSIC and UCA-ESPRIT require coherent multi-channel receiver hardware; they are algorithmic benchmarks, not equivalent-cost alternatives.

## SNR sweep
RMSE in degrees; the CSV includes MAE, median, 95th percentile and failure fraction (>15°).

|   snr_db | method    |    mae |   rmse |   median |    p95 |   fail |   n |
|---------:|:----------|-------:|-------:|---------:|-------:|-------:|----:|
|       -5 | esprit    |  6.070 |  6.833 |    6.177 | 10.880 |  0.004 | 250 |
|       -5 | strongest | 17.251 | 20.722 |   15.565 | 36.122 |  0.512 | 250 |
|       -5 | music     |  0.608 |  0.760 |    0.499 |  1.449 |  0.000 | 250 |
|       -5 | pv        |  7.930 | 10.271 |    6.176 | 20.978 |  0.128 | 250 |
|       -5 | centroid  |  8.330 | 10.895 |    6.843 | 22.478 |  0.140 | 250 |
|        0 | esprit    |  5.715 |  6.438 |    6.168 |  9.676 |  0.000 | 250 |
|        0 | strongest | 15.778 | 19.119 |   14.378 | 35.337 |  0.480 | 250 |
|        0 | music     |  0.326 |  0.403 |    0.296 |  0.710 |  0.000 | 250 |
|        0 | pv        |  6.258 |  8.229 |    4.903 | 16.334 |  0.072 | 250 |
|        0 | centroid  |  6.230 |  8.169 |    4.824 | 16.863 |  0.072 | 250 |
|        5 | esprit    |  5.838 |  6.514 |    6.513 |  9.431 |  0.000 | 250 |
|        5 | strongest | 17.177 | 20.393 |   16.242 | 36.196 |  0.536 | 250 |
|        5 | music     |  0.187 |  0.235 |    0.156 |  0.482 |  0.000 | 250 |
|        5 | pv        |  5.373 |  7.107 |    4.219 | 15.006 |  0.052 | 250 |
|        5 | centroid  |  6.424 |  8.235 |    5.168 | 17.656 |  0.080 | 250 |
|       10 | esprit    |  6.137 |  6.713 |    6.809 |  9.286 |  0.000 | 250 |
|       10 | strongest | 17.348 | 20.206 |   16.254 | 35.907 |  0.540 | 250 |
|       10 | music     |  0.099 |  0.125 |    0.082 |  0.244 |  0.000 | 250 |
|       10 | pv        |  4.485 |  5.934 |    3.619 | 11.746 |  0.024 | 250 |
|       10 | centroid  |  6.013 |  7.756 |    4.779 | 14.915 |  0.048 | 250 |
|       15 | esprit    |  5.532 |  6.255 |    5.873 |  9.208 |  0.000 | 250 |
|       15 | strongest | 16.638 | 20.169 |   15.511 | 36.818 |  0.516 | 250 |
|       15 | music     |  0.052 |  0.066 |    0.043 |  0.123 |  0.000 | 250 |
|       15 | pv        |  3.889 |  4.843 |    3.267 |  9.339 |  0.000 | 250 |
|       15 | centroid  |  5.789 |  7.768 |    4.494 | 15.730 |  0.072 | 250 |
|       20 | esprit    |  5.847 |  6.460 |    6.474 |  9.178 |  0.000 | 250 |
|       20 | strongest | 17.422 | 20.666 |   15.864 | 36.799 |  0.528 | 250 |
|       20 | music     |  0.029 |  0.036 |    0.024 |  0.070 |  0.000 | 250 |
|       20 | pv        |  4.018 |  5.122 |    3.177 | 10.017 |  0.008 | 250 |
|       20 | centroid  |  6.314 |  8.071 |    5.526 | 15.676 |  0.060 | 250 |
|       25 | esprit    |  5.806 |  6.454 |    6.439 |  9.178 |  0.000 | 250 |
|       25 | strongest | 17.807 | 21.178 |   16.341 | 37.761 |  0.560 | 250 |
|       25 | music     |  0.016 |  0.020 |    0.014 |  0.040 |  0.000 | 250 |
|       25 | pv        |  3.749 |  4.823 |    3.001 |  9.240 |  0.008 | 250 |
|       25 | centroid  |  5.812 |  7.496 |    4.842 | 15.447 |  0.056 | 250 |

## Tracking results

| method           |   mae |   rmse |   median |    p95 |   fail |    n |   interference_fraction |
|:-----------------|------:|-------:|---------:|-------:|-------:|-----:|------------------------:|
| Raw power-vector | 5.622 |  8.288 |    4.213 | 14.898 |  0.050 | 1200 |                   0.044 |
| Circular EMA     | 3.847 |  5.674 |    2.827 |  9.873 |  0.025 | 1200 |                   0.044 |
| Adaptive Kalman  | 4.436 |  6.598 |    3.122 | 11.969 |  0.038 | 1200 |                   0.044 |

## Timing

| method          |   microseconds_per_estimate |   batch_size |   repetitions |
|:----------------|----------------------------:|-------------:|--------------:|
| strongest       |                        0.04 |          100 |             8 |
| centroid        |                        0.22 |          100 |             8 |
| power-vector ML |                      254.76 |          100 |             8 |
| MUSIC           |                      233.79 |          100 |             8 |

## Figures

- `figures/01_snr_rmse.png`: accuracy versus SNR
- `figures/02_element_count.png`: effect of antenna element count
- `figures/03_hardware_mismatch.png`: calibration mismatch robustness
- `figures/04_tracking.png`: moving target, raw estimates and tracker

## Interpretation and limitations

- Strongest-beam selection is quantized by beam spacing; it is a useful baseline, not a precision estimator.
- Power-vector ML fits the calibrated beam power pattern and should be the primary low-cost algorithm in this project.
- MUSIC/ESPRIT rely on phase-coherent samples and are included as higher-complexity references.
- Confidence and tracker flags are model-derived indicators, not calibrated probabilities until validated on held-out data.
- The model is azimuth-only and synthetic. It does not establish real-world drone detection range or field performance.
- Switched-array dwell timing, antenna-pattern mismatch, multipath and receiver imperfections need hardware validation.

## Reproducibility

Run `python run_experiments.py --quick` for a short smoke run or `python run_experiments.py --out results` for the larger run. Results are synthetic; do not present them as field measurements.
