import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.forecast.data import load_km
from src.features.schedule import board_departures, load_boards
from src.eval.baselines import baseline_section, baseline_zero
from src.model.train import run_experiment, write_predictions

try:
    from src.model.calibrate import run_calibrated_experiment
except ImportError:          # calibrate.py not written yet - run without it
    run_calibrated_experiment = None

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
PRED_DIR = P / "predictions"
BOARD_DIR = ROOT / "data" / "raw" / "railradar" / "boards"

obs = pd.read_csv(P / "observations.csv", dtype={"train_no": str})
# One corridor map per corridor (Delhi-Mumbai first), so Howrah and overlap trains get a
# direction too. With a single map, every section off Delhi-Mumbai had no direction and
# therefore no network features.
km = load_km()
main_km = next(iter(km.values()))

dates = sorted(obs["run_date"].unique())
test_dates = sys.argv[1:] or [dates[-1]]
test = obs["run_date"].isin(test_dates).to_numpy()
train = ~test & (obs["run_date"] < min(test_dates)).to_numpy()

print(f"dates available: {dates}")
print(f"train: {train.sum()} rows from {sorted(obs.loc[train, 'run_date'].unique())}")
print(f"test:  {test.sum()} rows from {test_dates}")
if train.sum() < 200 or test.sum() < 50:
    print("WARNING: very few rows - treat these numbers as a smoke test only")
print()

experiments = {
    "model_base": dict(include_network=False),
    "model_network": dict(include_network=True),
     "model_base_hist": dict(include_network=False, include_history=True)
}

boards = load_boards(BOARD_DIR) if BOARD_DIR.exists() else {}
if boards:
    departures = board_departures(boards, main_km)
    print(f"station boards: {len(boards)} stations, {len(departures)} scheduled departures "
          f"from {departures['train_no'].nunique()} trains")
    experiments["model_network_sched"] = dict(include_network=True, departures=departures)
else:
    print("no station boards yet - skipping model_network_sched")
print()

def score(name, out, margin=np.nan):
    err = (out["p50"] - out["y_true"]).abs()
    cover = ((out["y_true"] >= out["p10"]) & (out["y_true"] <= out["p90"])).mean()
    return dict(experiment=name, rows=len(out), mae=round(err.mean(), 2),
                coverage_10_90=round(cover, 2),
                mean_width=round((out["p90"] - out["p10"]).mean(), 1),
                margin=round(margin, 1) if np.isfinite(margin) else np.nan)


PRED_DIR.mkdir(parents=True, exist_ok=True)
for old in PRED_DIR.glob("*.csv"):
    old.unlink()

summary = []
train_rows, test_rows = obs[train], obs[test]
for name, fn in (("baseline_zero", baseline_zero), ("baseline_section", baseline_section)):
    out = fn(train_rows, test_rows).reset_index(drop=True)
    print(f"wrote {write_predictions(out, PRED_DIR, name).relative_to(ROOT)}")
    summary.append(score(name, out))

n_train_dates = obs.loc[train, "run_date"].nunique()
calibrate = run_calibrated_experiment is not None and n_train_dates >= 2
for name, kw in experiments.items():
    out = run_experiment(obs, km, train, test, **kw)
    print(f"wrote {write_predictions(out, PRED_DIR, name).relative_to(ROOT)}")
    summary.append(score(name, out))
    if calibrate:
        cal, margin = run_calibrated_experiment(obs, km, train, test, **kw)
        print(f"wrote {write_predictions(cal, PRED_DIR, name + '_cal').relative_to(ROOT)}")
        summary.append(score(name + "_cal", cal, margin))

if run_calibrated_experiment is None:
    print("src/model/calibrate.py not found - skipping calibrated runs")
elif n_train_dates < 2:
    print("only one training date - skipping calibrated runs")

zero_mae = obs.loc[test, "minutes_lost"].abs().mean()
summary.append(dict(experiment="predict_zero (reference)", rows=int(test.sum()),
                    mae=round(zero_mae, 2), coverage_10_90=np.nan, mean_width=np.nan,
                    margin=np.nan))

print()
print(pd.DataFrame(summary).to_string(index=False))
print()
print("coverage_10_90 should be near 0.80. Lower = bands too narrow, higher = too wide.")
print("_cal rows: windows widened by 'margin' minutes, learned on the last training day.")

# Rows from trains the model never saw in training are a harder test than rows from trains it
# did. Report both, so a mixed test day is not read as one number.
seen = set(obs.loc[train, "train_no"])
rows = []
for f in sorted(PRED_DIR.glob("*.csv")):
    out = pd.read_csv(f, dtype={"train_no": str})
    err = (out["p50"] - out["y_true"]).abs()
    s_mask = out["train_no"].isin(seen)
    rows.append(dict(experiment=f.stem, mae_seen=round(err[s_mask].mean(), 2), n_seen=int(s_mask.sum()),
                     mae_unseen=round(err[~s_mask].mean(), 2), n_unseen=int((~s_mask).sum())))
print()
print("Error on trains seen in training vs never seen:")
print(pd.DataFrame(rows).to_string(index=False))
