"""
FAKE prediction files, for building metrics and charts before real
predictions exist. Never report numbers from these.

Uses the same four experiment names as the real run, so practice charts look
exactly like the final ones. Writes to data/processed/predictions_fake/
(NOT predictions/), so fake and real results can never be mixed up.

Run:   python -m src.eval.make_fake_predictions
Then:  python -m src.eval.metrics data/processed/predictions_fake
       python -m src.eval.plots data/processed/predictions_fake
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.eval.metrics import PRED_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "data" / "processed" / "observations.csv"
OUT = ROOT / "data" / "processed" / "predictions_fake"

# name -> (noise on p50 in minutes, half-width of the p10..p90 band)
# baseline_zero is special: it always predicts 0 minutes lost.
FAKE_EXPERIMENTS = {
    "baseline_zero": (None, 14),
    "baseline_section": (12, 12),
    "model_base": (8, 10),
    "model_network": (5, 9),
}


def main() -> None:
    obs = pd.read_csv(OBS, dtype={"train_no": str, "run_date": str})
    test = obs[obs["run_date"] == obs["run_date"].max()].copy()  # mimic a latest-day test set
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("fake_*.csv"):  # names used by the first version of this script
        old.unlink()
    rng = np.random.default_rng(26028)

    for name, (noise, half) in FAKE_EXPERIMENTS.items():
        df = test.copy()
        df["y_true"] = df["minutes_lost"]
        if noise is None:
            df["p50"] = 0.0
        else:
            df["p50"] = df["y_true"] + rng.normal(0, noise, len(df)).round(1)
        df["p10"] = df["p50"] - half
        df["p90"] = df["p50"] + half
        df[PRED_COLUMNS].to_csv(OUT / f"{name}.csv", index=False)
        print(f"wrote {name}.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
