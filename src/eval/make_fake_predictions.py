"""
FAKE prediction files, for building metrics and charts before real
predictions exist. Never report numbers from these.

Writes to data/processed/predictions_fake/ (NOT predictions/), so fake and
real results can never be mixed up.

Run:   python -m src.eval.make_fake_predictions
Then:  python -m src.eval.metrics data/processed/predictions_fake
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.eval.metrics import PRED_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "data" / "processed" / "observations.csv"
OUT = ROOT / "data" / "processed" / "predictions_fake"

# name -> (noise in minutes, half-width of the p10..p90 band)
FAKE_EXPERIMENTS = {
    "fake_sharp": (4, 8),
    "fake_noisy": (10, 8),
    "fake_wide": (10, 16),
}


def main() -> None:
    obs = pd.read_csv(OBS, dtype={"train_no": str, "run_date": str})
    test = obs[obs["run_date"] == obs["run_date"].max()].copy()  # mimic a latest-day test set
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(26028)

    for name, (noise, half) in FAKE_EXPERIMENTS.items():
        df = test.copy()
        df["y_true"] = df["minutes_lost"]
        df["p50"] = df["y_true"] + rng.normal(0, noise, len(df)).round(1)
        df["p10"] = df["p50"] - half
        df["p90"] = df["p50"] + half
        df[PRED_COLUMNS].to_csv(OUT / f"{name}.csv", index=False)
        print(f"wrote {name}.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
