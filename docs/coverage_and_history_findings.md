# Two open questions from results.md, investigated

Both of these were flagged as "needs a real answer before Monday." Here's what
I actually found by running the pipeline, not just re-reading the numbers.

---

## 1. Why tuned coverage tops out at 60-65% instead of 80%

**Root cause found: it's a real, fixable calibration bug, not a data-volume problem.**

I checked the actual prediction residuals on the test set, not just the coverage
percentage. The misses are wildly asymmetric:

| Model | below p10 (train later than predicted) | above p90 (train earlier than predicted) |
|---|---|---|
| model_base_cal | 32.7% | 4.7% |
| model_network_cal | 31.2% | 5.2% |
| model_network_sched_cal | 30.3% | 4.7% |
| model_base_hist_cal | 33.8% | 5.8% |

A properly calibrated 80% window should miss roughly evenly on both sides
(~10% each). Instead, almost all the miss-budget is being spent on trains
running later than predicted, while the early side is already over-covered.
This pattern holds across every model, so it's systemic, not one model's
quirk.

**What doesn't fix it:** I tried switching the calibration in `calibrate.py`
from one shared margin to two independent one-sided margins (a standard
technique, "asymmetric conformal prediction"). This made coverage *worse*
(52.5%, down from 62.7%). That ruled out "wrong algorithm" as the cause.

**What the real cause is:** the calibration margin is currently fit on just
the single latest training day (22 Sept), then applied to a different test
day (23 Sept). The *direction* the model tends to err in varies from day to
day - a margin that looks right on the 22nd doesn't transfer to the 23rd.
This is a known failure mode of split-conformal calibration with too little
calibration data.

**What fixes it, measured:** pooling more recent days for calibration
instead of just the last one:

| Calibration days used | Coverage (model_base) | Coverage (model_network) | Window width |
|---|---|---|---|
| 1 (current) | 62.7% | 63.0% | 16.0 min |
| 2 | 72.9% | 73.2% | 18.2 min |
| 3 | 75.8% | 73.2% | 18.6 min |
| 4 | 77.0% | 76.7% | 18.8 min |
| 5 | **81.6%** | **81.3%** | 20.8 min |

MAE is identical at every setting (5.67 / 5.77 respectively) - this only
changes the width of the honesty window, not the point forecast itself.

**What I did:** added an `n_cal_days` parameter to `calibrate.py`
(`calibration_split()` and `run_calibrated_experiment()`), defaulting to `1`
so nothing already in `results.md` changes without a decision. 3 new tests
added, full suite passes (275/275).

**What needs a decision:** whether to adopt `n_cal_days=3` or `5` as the new
default, regenerate `results.md`'s numbers with it, and update the headline
and PPT figures accordingly. 5 days gets closest to the 80% target but eats
most of the training data for calibration (leaving only 1-2 days to fit the
actual model on) - 3 is a safer middle ground. This is a real trade-off
someone should sign off on, not something to silently change before Monday.

---

## 2. Why section history looks "clearly worse" here but "best" in eta_horizon.md

**These are the same underlying feature, aggregated completely differently -
both results can be true at once, and that's not just a hand-wave.**

Traced both code paths directly:

- `src/features/history.py`'s `sec_hist_mean` is a leave-one-run-out average
  of minutes lost on one specific section (e.g. NDLS>KOTA), across training
  days, excluding the current train's own run.
- `src/forecast/horizon.py`'s `cum_hist_mean` is built from the exact same
  `sec_hist_mean` values, but **summed across every section from the train's
  current position to the target station** - up to 20 sections for a distant
  stop.

So the single-section ablation (`model_base_hist`) is testing "does one
section's own noisy historical average help predict that one section," while
the chained horizon test is really testing "does the sum of many sections'
historical averages help predict a total delay 10+ stations away." Summing
many noisy per-section estimates together is a much more stable signal than
any one of them alone (the noise tends to cancel out; the systematic
"this stretch tends to run late" pattern doesn't). That's a plausible,
specific reason a feature can hurt individually but help in aggregate - not
just "different metrics, who knows."

I confirmed the ablation itself is methodologically sound (checked
`src/model/train.py`): `model_base_hist` really is just `model_base` plus
the one `sec_hist_mean` feature, no other confound.

**What this doesn't resolve:** whether `cum_hist_mean` is doing something
genuinely useful (capturing real recurring slack in the timetable) or is
partly acting as a proxy for something else correlated with route length
(e.g. longer routes naturally have wider, easier-to-hit windows regardless of
history). That would need a dedicated test - e.g. checking whether
`cum_hist_mean`'s benefit in the horizon eval holds up when controlling for
number of stops ahead. Flagging this as a real next step, not claiming it's
fully solved.

---

## Bottom line for Monday

- The coverage number in `results.md`/the Results page headline is
  currently accurate for what's shipped (`n_cal_days=1`), but there's a
  tested, low-risk improvement sitting unused. Worth 10 minutes of team
  discussion before the PPT locks in "coverage is only 60-65%" as a
  known limitation, since it doesn't have to be.
- The history contradiction has a real explanation now, not just two
  numbers that disagree. Safe to say in the PPT/Q&A: "the feature works
  differently at different scales of aggregation," backed by the code,
  not just asserted.
