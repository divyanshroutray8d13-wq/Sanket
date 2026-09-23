# SANKET results

**Question:** does knowing what other trains are doing make SANKET's arrival forecasts better?

**Short answer:** SANKET's model is clearly better than the way train apps predict delays today, by about 1 minute per section, but with five nights of data the network features are not yet the reason why.

---

## What we compared

Ways of predicting how many minutes a train will lose, or gain, on each stretch of track between two stations. Negative minutes mean the train made up time.

| Experiment | What it does |
|---|---|
| **Baseline: keeps current delay** (`baseline_zero`) | Assumes the train loses no further time. This is roughly what train apps show today: current delay carried forward. |
| **Baseline: section average** (`baseline_section`) | Predicts the average time lost on that stretch in past data. A simple rule, no model. |
| **SANKET, no network features** (`model_base`) | Our model, using only facts about the train itself and the stretch of track. |
| **SANKET, with network features** (`model_network`) | The same model, plus what other trains are doing: who is ahead on the same track, how close, and how late. |
| **SANKET, network + timetable** (`model_network_sched`) | Adds how many other trains are timetabled to leave that station within half an hour either side. |
| **SANKET, plus section history** (`model_base_hist`) | Adds how much time trains have lost on that stretch on earlier days. The train's own run is left out of its own history. |

Each experiment also has a **tuned window** version (`_cal`). Tuning does not change the prediction itself: it measures, on a day the model never learned from, how far outside the window the real value tended to fall, and widens the window by that much. So the tuned versions have the same average error and a more honest window.

`model_base` and `model_network` differ in one thing only: the network features. That makes the comparison between them the direct test of SANKET's main idea.

## How we tested it

- **Data:** real running records from RailRadar for trains on the Delhi to Mumbai corridor, collected nightly from 17 to 21 September 2026. In total 842 test sections from 31 train runs.
- **Split by time:** every experiment learned from earlier days and was tested on the latest day, 21 September. Nothing from the test day was used in training, so the model is scored on a day it has never seen, as it would be in real use. Window tuning used the last training day, 20 September, and never touched the test day.
- **Same test for everyone:** all experiments were scored on exactly the same 842 test sections. The scoring code refuses to compare experiments tested on different rows.

## How we scored it

| Measure | Plain meaning | Better is |
|---|---|---|
| **Average error (MAE)** | How far off the most likely prediction is, in minutes, on average | Lower |
| **Coverage** | How often the real minutes fell inside the predicted window | Close to 80% |
| **Window width** | How wide the predicted window is, in minutes | Narrower, at the same coverage |
| **Bias** | Whether predictions lean too late (positive) or too early (negative) | Close to 0 |

Coverage and width are always read together. A window of "somewhere between 0 and 3 hours" would almost always be right and would be useless.

## Results

| Experiment | Average error (min) | Coverage | Window width (min) | Bias (min) |
|---|---|---|---|---|
| Baseline: keeps current delay | 8.37 | 83% | 27.0 | +3.44 |
| Baseline: section average | 7.12 | 69% | 15.2 | +1.52 |
| SANKET, no network features | 6.05 | 65% | 15.3 | +0.24 |
| SANKET, no network features, tuned window | 6.05 | 79% | 19.2 | +0.24 |
| SANKET, with network features | 6.11 | 65% | 15.1 | +0.53 |
| SANKET, with network features, tuned window | 6.11 | 77% | 18.5 | +0.53 |
| SANKET, network + timetable, tuned window | 6.12 | 78% | 18.9 | +0.59 |
| SANKET, plus section history, tuned window | 6.13 | 81% | 19.7 | +0.96 |

All rows are scored on the same 842 test sections from 31 train runs.

Two things stand out. Every SANKET model is about a minute closer than the better baseline. And before tuning, our windows were right only about 65% of the time while claiming 80%; tuning fixes that, at the cost of about 4 more minutes of width.

![Average error per experiment](figures/10_ablation_mae.png)

![Coverage against the 80% target](figures/11_coverage.png)

## Is the difference real, or luck?

The test day has 842 sections, but they come from only 31 train runs. Sections of one train share its delays: one late train makes all of its sections late together. So the real amount of independent evidence is closer to the number of train runs than to the number of sections.

To avoid overclaiming, we resampled whole train runs 5,000 times and recomputed the gap each time. The range below covers 95% of those resamples. If it crosses zero, we cannot say which experiment is better.

| Question | Gap in average error | 95% range | Verdict |
|---|---|---|---|
| Does SANKET beat the best baseline? (no network features) | +1.07 min | +0.60 to +1.53 | clearly better |
| Does SANKET beat the best baseline? (with network features) | +1.01 min | +0.55 to +1.47 | clearly better |
| Do network features help? (with vs without) | −0.05 min | −0.14 to +0.03 | not distinguishable |
| Does the timetable help on top of that? | −0.01 min | −0.11 to +0.07 | not distinguishable |
| Does the section's past help? | −0.08 min | −0.27 to +0.12 | not distinguishable |

A positive gap means the first experiment had the smaller error.

## What it means

The learned model is worth it. Against the way apps predict delays today, carrying the current delay forward, SANKET is 2.3 minutes closer per section; against the stronger section-average rule it is 1.07 minutes closer, and that gap held in 100% of resamples. Window tuning brings coverage from 65% to 79%, so when SANKET says "8 in 10 chance", it now means it.

With the data we have, adding what other trains are doing did not reliably improve the forecasts: the gap was −0.05 minutes and its range crosses zero. We report this plainly. The likely reasons are a small test set (31 train runs on one day), five nights of collection, and little traffic overlap between the trains we tracked: on this corridor most of our trains rarely meet. The next step is more nights of data on busier shared track, which is exactly what the overlap corridor collection is for.

## Does it work on other routes?

<!-- Fill after the zone-holdout run. Delete this section if it is cut. -->

We trained on ___ and tested on ___, a route the model had never seen. Average error was ___ minutes, compared with ___ on the original test. ___ (one sentence on whether it transfers).

## Limits

- **Small test set.** 31 train runs on one test day. The ranges above show how much that limits certainty.
- **Few days of data.** Collection ran for 5 nights, so the model has seen few kinds of days: no fog season, no festival rush, no major disruption.
- **One main corridor.** Results are for Delhi to Mumbai. Other routes may behave differently.
- **Observed data only.** RailRadar reports where trains were, not why. Causes such as speed restrictions or signal holds are inferred, not recorded.
- **Tracking gaps.** Some trains and some stations are not tracked by RailRadar, and specials were excluded for that reason.

## Reproduce these numbers

From the repo root, with the real prediction files in `data/processed/predictions/`:

```
python -m src.eval.metrics
python -m src.eval.plots
python -m src.eval.compare
python -m src.eval.export_results
```

The last command writes `frontend/public/results.json`, which the dashboard's Results page shows.

Scoring code: `src/eval/metrics.py`, `src/eval/plots.py`, `src/eval/compare.py`, `src/eval/export_results.py`. Test split and baselines: `src/eval/split.py`, `src/eval/baselines.py`. Model, window tuning and the experiment run: `src/model/train.py`, `src/model/calibrate.py`, `notebooks/run_experiments.py`.
