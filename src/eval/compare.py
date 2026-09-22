"""
Is one experiment really better than another, or could the gap be luck?

With only a few hundred test sections, "model A beats model B by 0.5 minutes"
may not hold up. This answers it with a paired bootstrap:

  1. Keep only sections both experiments predicted, so they face the same test.
  2. Resample whole TRAIN RUNS (train_no + run_date) with replacement, many
     times. Sections of one train run share its delays, so resampling single
     sections would pretend we have more independent evidence than we do.
  3. Each time, recompute both MAEs. The spread of the gap is the range we
     can honestly claim.

Run:
    python -m src.eval.compare                                  # real predictions
    python -m src.eval.compare data/processed/predictions_fake  # practice run
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.eval.metrics import DEFAULT_PRED_DIR, ROW_KEY, ablation_table, load_predictions

CLUSTER = ["train_no", "run_date"]
N_BOOT = 5000
SEED = 26028


def paired_bootstrap(a: pd.DataFrame, b: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Compare two prediction tables on their shared rows.

    gain = MAE(b) - MAE(a): how many minutes a is better by (negative = worse).
    lo, hi = 95% range of the gain across resamples.
    share_a_better = fraction of resamples where a had the lower MAE.
    """
    m = a.merge(b, on=ROW_KEY, suffixes=("_a", "_b"))
    if m.empty:
        raise ValueError("the two experiments share no rows, so they cannot be compared")

    m["err_a"] = (m["p50_a"] - m["y_true_a"]).abs()
    m["err_b"] = (m["p50_b"] - m["y_true_a"]).abs()  # same truth for both, checked by ablation_table
    g = m.groupby(CLUSTER).agg(sum_a=("err_a", "sum"), sum_b=("err_b", "sum"), n=("err_a", "size"))
    if len(g) < 2:
        raise ValueError("need at least 2 train runs in the shared rows to estimate a range")

    sum_a, sum_b, n = (g[c].to_numpy(float) for c in ("sum_a", "sum_b", "n"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    rows = n[idx].sum(axis=1)
    gains = sum_b[idx].sum(axis=1) / rows - sum_a[idx].sum(axis=1) / rows

    mae_a = sum_a.sum() / n.sum()
    mae_b = sum_b.sum() / n.sum()
    lo, hi = np.percentile(gains, [2.5, 97.5])
    return {
        "n_rows": int(n.sum()),
        "n_train_runs": int(len(g)),
        "mae_a": float(mae_a),
        "mae_b": float(mae_b),
        "gain": float(mae_b - mae_a),
        "lo": float(lo),
        "hi": float(hi),
        "share_a_better": float(np.mean(gains > 0)),
    }


def verdict(r: dict) -> str:
    if r["lo"] > 0:
        return "clearly better than"
    if r["hi"] < 0:
        return "clearly worse than"
    return "not distinguishable from"


def default_pairs(names: list[str], table: pd.DataFrame) -> list[tuple[str, str, str]]:
    """The comparisons the results write-up needs, when those experiments exist."""
    baselines = [e for e in table["experiment"] if e.startswith("baseline")]  # table is sorted by MAE
    best_baseline = baselines[0] if baselines else None
    pairs = []
    if {"model_network", "model_base"} <= set(names):
        pairs.append(("Do network features help?", "model_network", "model_base"))
    for model in ("model_network", "model_base"):
        if model in names and best_baseline:
            pairs.append((f"{model} vs the best baseline", model, best_baseline))
    if not pairs and len(table) >= 2:  # unknown names: best vs runner-up
        pairs.append(("Best vs runner-up", table["experiment"][0], table["experiment"][1]))
    return pairs


def compare_all(pred_dir: str | Path = DEFAULT_PRED_DIR) -> pd.DataFrame:
    pred_dir = Path(pred_dir)
    table = ablation_table(pred_dir)  # also checks the files agree on y_true
    frames = {f.stem: load_predictions(f) for f in sorted(pred_dir.glob("*.csv"))}
    out = []
    for question, a, b in default_pairs(list(frames), table):
        r = paired_bootstrap(frames[a], frames[b])
        out.append({"question": question, "a": a, "b": b, **r, "verdict": verdict(r)})
    return pd.DataFrame(out)


def main(argv: list[str]) -> None:
    pred_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRED_DIR
    try:
        results = compare_all(pred_dir)
    except FileNotFoundError:
        print(f"No prediction files in {pred_dir} yet.")
        print("To practise on fake data:  python -m src.eval.compare data/processed/predictions_fake")
        sys.exit(1)
    if "fake" in pred_dir.name.lower():
        print("FAKE DATA - practice only, never report these numbers\n")
    if results.empty:
        print("Need at least two experiments to compare.")
        return
    for r in results.itertuples():
        print(r.question)
        print(f"  {r.a} is {r.verdict} {r.b}: {r.gain:+.2f} min "
              f"(95% range {r.lo:+.2f} to {r.hi:+.2f}; better in {r.share_a_better:.0%} of resamples)")
        print(f"  MAE {r.mae_a:.2f} vs {r.mae_b:.2f} on {r.n_rows} sections from {r.n_train_runs} train runs\n")


if __name__ == "__main__":
    main(sys.argv)
