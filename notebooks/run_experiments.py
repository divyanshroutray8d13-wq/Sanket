
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.build_features import corridor_km
from src.features.schedule import board_departures, load_boards
from src.model.train import run_experiment, write_predictions

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
PRED_DIR = P / "predictions"
BOARD_DIR = ROOT / "data" / "raw" / "railradar" / "boards"
REFERENCE_TRAIN = "19019"

obs = pd.read_csv(P / "observations.csv", dtype={"train_no": str})
routes = pd.read_csv(P / "routes.csv", dtype={"train_no": str})
km = corridor_km(routes, REFERENCE_TRAIN)

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
}

boards = load_boards(BOARD_DIR) if BOARD_DIR.exists() else {}
if boards:
    departures = board_departures(boards, km)
    print(f"station boards: {len(boards)} stations, {len(departures)} scheduled departures "
          f"from {departures['train_no'].nunique()} trains")
    experiments["model_network_sched"] = dict(include_network=True, departures=departures)
else:
    print("no station boards yet - skipping model_network_sched")
print()

summary = []
for name, kw in experiments.items():
    out = run_experiment(obs, km, train, test, **kw)
    path = write_predictions(out, PRED_DIR, name)
    err = (out["p50"] - out["y_true"]).abs()
    cover = ((out["y_true"] >= out["p10"]) & (out["y_true"] <= out["p90"])).mean()
    summary.append(dict(experiment=name, rows=len(out), mae=round(err.mean(), 2),
                        coverage_10_90=round(cover, 2),
                        mean_width=round((out["p90"] - out["p10"]).mean(), 1)))
    print(f"wrote {path.relative_to(ROOT)}")

zero_mae = obs.loc[test, "minutes_lost"].abs().mean()
summary.append(dict(experiment="predict_zero (reference)", rows=int(test.sum()),
                    mae=round(zero_mae, 2), coverage_10_90=np.nan, mean_width=np.nan))

print()
print(pd.DataFrame(summary).to_string(index=False))
print()
print("coverage_10_90 should be near 0.80. Lower = bands too narrow, higher = too wide.")
