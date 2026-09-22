"""
Write the ablation result as one JSON file for the dashboard's Results page.

Run:
    python -m src.eval.export_results                                  # real -> frontend/public/results.json
    python -m src.eval.export_results data/processed/predictions_fake  # practice -> results.sample.json

The page shows results.json when it exists, and otherwise falls back to
results.sample.json with a "Sample results" banner. A folder with "fake" in
its name always writes the sample file, so fake numbers can never be shown
as the real result.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.eval.compare import compare_all
from src.eval.metrics import DEFAULT_PRED_DIR, ablation_table, load_predictions
from src.eval.plots import is_baseline, nice_name

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"


def build(pred_dir: str | Path = DEFAULT_PRED_DIR) -> dict:
    pred_dir = Path(pred_dir)
    table = ablation_table(pred_dir)
    comps = compare_all(pred_dir)

    first = load_predictions(sorted(pred_dir.glob("*.csv"))[0])
    runs = first[["train_no", "run_date"]].drop_duplicates()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_sample": "fake" in pred_dir.name.lower(),
        "test_dates": sorted(first["run_date"].unique().tolist()),
        "n_sections": int(table["n"].iloc[0]),
        "n_train_runs": int(len(runs)),
        "experiments": [
            {
                "experiment": r.experiment,
                "label": nice_name(r.experiment),
                "role": "baseline" if is_baseline(r.experiment) else "model",
                "mae": round(float(r.mae), 2),
                "coverage": round(float(r.coverage), 3),
                "mean_width": round(float(r.mean_width), 1),
                "bias": round(float(r.bias), 2),
            }
            for r in table.itertuples()
        ],
        "comparisons": [
            {
                "question": c.question,
                "a": c.a,
                "b": c.b,
                "a_label": nice_name(c.a),
                "b_label": nice_name(c.b),
                "gain": round(float(c.gain), 2),
                "lo": round(float(c.lo), 2),
                "hi": round(float(c.hi), 2),
                "share_a_better": round(float(c.share_a_better), 3),
                "verdict": c.verdict,
            }
            for c in (comps.itertuples() if not comps.empty else [])
        ],
    }


def main(argv: list[str]) -> None:
    pred_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRED_DIR
    try:
        data = build(pred_dir)
    except FileNotFoundError:
        print(f"No prediction files in {pred_dir} yet.")
        print("To practise:  python -m src.eval.export_results data/processed/predictions_fake")
        sys.exit(1)
    out = PUBLIC / ("results.sample.json" if data["is_sample"] else "results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv)
