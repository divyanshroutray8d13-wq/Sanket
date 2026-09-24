# ETA error by how far ahead the station is

Test day 2026-09-24 (25 train runs, 2592 forecasts). Model: base+network+hist, trained on 7 earlier days. Baseline: carry the current delay forward.

| Station is | Forecasts | SANKET error (min) | Baseline error (min) | Improvement | Window holds |
|---|---:|---:|---:|---:|---:|
| next stop | 274 | 5.8 | 7.9 | +27% | 85% |
| 2-3 stops | 474 | 8.6 | 11.9 | +28% | 78% |
| 4-6 stops | 554 | 11.9 | 16.0 | +25% | 78% |
| 7-10 stops | 548 | 14.7 | 19.0 | +23% | 74% |
| 11-20 stops | 742 | 19.9 | 27.1 | +27% | 70% |
| **All** | 2592.0 | **13.5** | **18.2** | **+26%** | 76% |

Overall improvement 95% range (whole train runs resampled): -0.4% to +48.2%. If the range crosses zero, do not claim the model is better.

| Feature set | SANKET error (min) | Improvement | 95% range | Window holds | Width (min) |
|---|---:|---:|---|---:|---:|
| base | 16.58 | +9.0% | +3.4 to +21.5 | 75% | 45 |
| base+hist | 13.70 | +24.8% | -0.7 to +46.5 | 76% | 44 |
| base+network | 15.93 | +12.6% | +7.6 to +23.0 | 81% | 48 |
| base+network+hist | 13.53 | +25.7% | -0.4 to +48.2 | 76% | 42 |
| base+network+sched | 16.23 | +10.9% | +5.9 to +22.2 | 80% | 48 |
| base+network+sched+hist | 13.70 | +24.8% | -1.3 to +46.9 | 76% | 43 |
