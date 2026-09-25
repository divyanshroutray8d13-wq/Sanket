# ETA error by how far ahead the station is

Test day 2026-09-23 (29 train runs, 3578 forecasts). Model: base+network+hist, trained on 6 earlier days. Baseline: carry the current delay forward.

| Station is | Forecasts | SANKET error (min) | Baseline error (min) | Improvement | Window holds |
|---|---:|---:|---:|---:|---:|
| next stop | 343 | 6.6 | 7.7 | +14% | 69% |
| 2-3 stops | 602 | 9.1 | 10.8 | +16% | 79% |
| 4-6 stops | 727 | 12.6 | 14.5 | +13% | 80% |
| 7-10 stops | 744 | 15.5 | 17.1 | +9% | 81% |
| 11-20 stops | 1162 | 18.3 | 19.6 | +7% | 86% |
| **All** | 3578.0 | **13.9** | **15.4** | **+10%** | 81% |

Overall improvement 95% range (whole train runs resampled): +5.4% to +20.9%. If the range crosses zero, do not claim the model is better.

| Feature set | SANKET error (min) | Improvement | 95% range | Window holds | Width (min) |
|---|---:|---:|---|---:|---:|
| base | 14.52 | +5.9% | -1.1 to +18.2 | 83% | 43 |
| base+hist | 13.94 | +9.7% | +4.8 to +20.5 | 81% | 42 |
| base+network | 14.16 | +8.2% | +3.5 to +19.0 | 83% | 42 |
| base+network+hist | 13.88 | +10.0% | +5.4 to +20.9 | 81% | 41 |
| base+network+sched | 14.23 | +7.8% | +2.6 to +18.9 | 83% | 41 |
| base+network+sched+hist | 13.83 | +10.4% | +5.8 to +21.1 | 81% | 40 |
