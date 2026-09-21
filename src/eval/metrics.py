"""
Scoring for SANKET predictions.

Every experiment writes one CSV to data/processed/predictions/{experiment}.csv
with exactly these columns (the Model -> Evaluation contract):

    train_no, run_date, step_seq, from_station, to_station, y_true, p10, p50, p90

y_true is the real minutes lost on that section (negative = time recovered).
p10 / p50 / p90 are the model's 10th, 50th and 90th percentile predictions.

Run:   python -m src.eval.metrics                 # scores data/processed/predictions/
       python -m src.eval.metrics some/other/dir  # scores another folder
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PRED_COLUMNS = [
    "train_no", "run_date", "step_seq", "from_station", "to_station",
    "y_true", "p10", "p50", "p90",
]
ROW_KEY = ["train_no", "run_date", "step_seq"]

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRED_DIR = ROOT / "data" / "processed" / "predictions"


def evaluate(y, p10, p50, p90) -> dict:
    """Score one set of predictions.

    Returns
        n              rows scored
        mae            mean absolute error of p50, in minutes
        rmse           root mean squared error of p50, in minutes
        bias           mean of (p50 - y); positive = predicts too much delay
        coverage       share of rows with p10 <= y <= p90 (target about 0.80)
        mean_width     average p90 - p10, in minutes (narrower is better, at equal coverage)
        crossing_rate  share of rows where p10 > p50 or p50 > p90 (should be 0)
    """
    y, p10, p50, p90 = (np.asarray(a, dtype=float) for a in (y, p10, p50, p90))

    if not (y.shape == p10.shape == p50.shape == p90.shape):
        raise ValueError("y, p10, p50 and p90 must all be the same length")
    if y.size == 0:
        raise ValueError("nothing to evaluate: got zero rows")
    for name, arr in (("y", y), ("p10", p10), ("p50", p50), ("p90", p90)):
        if np.isnan(arr).any():
            raise ValueError(f"{name} contains missing values; fix the predictions file rather than scoring around them")

    err = p50 - y
    return {
        "n": int(y.size),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "bias": float(np.mean(err)),
        "coverage": float(np.mean((p10 <= y) & (y <= p90))),
        "mean_width": float(np.mean(p90 - p10)),
        "crossing_rate": float(np.mean((p10 > p50) | (p50 > p90))),
    }


def load_predictions(path: str | Path) -> pd.DataFrame:
    """Read one predictions CSV and check it follows the contract."""
    df = pd.read_csv(path, dtype={"train_no": str, "run_date": str})
    missing = [c for c in PRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{Path(path).name} is missing columns: {missing}")
    if df.duplicated(ROW_KEY).any():
        raise ValueError(f"{Path(path).name} has duplicate rows for the same (train_no, run_date, step_seq)")
    # Train numbers are five digits everywhere else in the project
    df["train_no"] = df["train_no"].str.zfill(5)
    return df[PRED_COLUMNS]


def ablation_table(pred_dir: str | Path = DEFAULT_PRED_DIR) -> pd.DataFrame:
    """One row per experiment file in pred_dir, best (lowest MAE) first.

    Warns if experiments were scored on different rows, because then their
    MAEs are not a fair comparison.

    Stops with an error if two experiments disagree on y_true for the same
    row. The real minutes lost on a section is a fact, so any disagreement
    means a file has its rows misaligned, and its score would be meaningless.
    """
    pred_dir = Path(pred_dir)
    files = sorted(pred_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no prediction CSVs found in {pred_dir}")

    rows, keysets, truths = [], {}, {}
    for f in files:
        df = load_predictions(f)
        scores = evaluate(df["y_true"], df["p10"], df["p50"], df["p90"])
        rows.append({"experiment": f.stem, **scores})
        keysets[f.stem] = set(map(tuple, df[ROW_KEY].astype(str).to_numpy()))
        truths[f.stem] = df.assign(step_seq=df["step_seq"].astype(str)).set_index(ROW_KEY)["y_true"]

    _check_truths_agree(truths)

    first = next(iter(keysets.values()))
    if any(k != first for k in keysets.values()):
        sizes = ", ".join(f"{name}={len(k)}" for name, k in keysets.items())
        warnings.warn(
            "experiments were scored on different rows, so MAEs are not directly "
            f"comparable ({sizes}). Make every experiment predict the same test set.",
            stacklevel=2,
        )

    table = pd.DataFrame(rows).sort_values("mae", kind="stable").reset_index(drop=True)
    return table


def _check_truths_agree(truths: dict[str, pd.Series]) -> None:
    """Every experiment must report the same y_true for the rows they share."""
    names = list(truths)
    ref_name, ref = names[0], truths[names[0]]
    for name in names[1:]:
        other = truths[name]
        shared = ref.index.intersection(other.index)
        diff = ~np.isclose(ref.loc[shared].to_numpy(float), other.loc[shared].to_numpy(float))
        if diff.any():
            bad = shared[diff]
            example = bad[0]
            raise ValueError(
                f"{ref_name} and {name} disagree on y_true for {len(bad)} shared row(s), "
                f"e.g. train {example[0]} on {example[1]} step {example[2]}: "
                f"{ref.loc[example]} vs {other.loc[example]}. "
                "One of the files has its rows misaligned."
            )


def main(argv: list[str]) -> None:
    pred_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRED_DIR
    try:
        table = ablation_table(pred_dir)
    except FileNotFoundError:
        print(f"No prediction files in {pred_dir} yet.")
        print("Real ones arrive when Aaru and Rivy write their experiments there.")
        print("To practise on fake data:  python -m src.eval.metrics data/processed/predictions_fake")
        sys.exit(1)
    with pd.option_context("display.float_format", "{:.2f}".format, "display.width", 120):
        print(table.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv)
