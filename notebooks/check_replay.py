"""How close were the forecasts in data/live to what really happened?

Every replay file written by `python -m src.forecast.export` holds, for each station,
the forecast (eta_low / eta_median / eta_high), the "apps show" estimate
(baseline_eta, the current delay carried forward) and what really happened
(actual_delay_min). This scores all three.

    python -m notebooks.check_replay
    python -m notebooks.check_replay path/to/other/live/folder
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def wrap(d: int) -> int:
    """Difference between two clock times, correct across midnight."""
    return (d + 720) % 1440 - 720


def load_rows(live_dir: Path):
    rows = []
    for f in sorted(glob.glob(str(live_dir / "[0-9][0-9][0-9][0-9][0-9].json"))):
        data = json.load(open(f, encoding="utf-8"))
        for s in data["stations"]:
            if "actual_delay_min" not in s:      # the old sample file has no actuals
                continue
            sched = minutes(s["scheduled"])
            late = s["actual_delay_min"]
            rows.append(dict(
                train=data["train_no"],
                seq=s["sequence"],
                err_model=abs(late - wrap(minutes(s["eta_median"]) - sched)),
                err_base=abs(late - wrap(minutes(s["baseline_eta"]) - sched)),
                inside=wrap(minutes(s["eta_low"]) - sched) <= late <= wrap(minutes(s["eta_high"]) - sched),
                width=wrap(minutes(s["eta_high"]) - minutes(s["eta_low"])),
            ))
    return rows


def summarise(rows, label):
    m = np.mean([r["err_model"] for r in rows])
    b = np.mean([r["err_base"] for r in rows])
    ins = np.mean([r["inside"] for r in rows])
    w = np.mean([r["width"] for r in rows])
    gain = 100 * (1 - m / b) if b else float("nan")
    print(f"{label:<14} n={len(rows):<4} SANKET off by {m:5.1f} min | carry-forward off by {b:5.1f} min "
          f"| {gain:+5.1f}% | window holds {ins:4.0%}, {w:3.0f} min wide")


def main():
    live_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "live"
    rows = load_rows(live_dir)
    if not rows:
        raise SystemExit(f"no forecasts with actual arrivals in {live_dir}. "
                         "Run: python -m src.forecast.export --all")

    print(f"{len(rows)} station forecasts from {len({r['train'] for r in rows})} trains in {live_dir}\n")
    summarise(rows, "all")
    for label, keep in (("next stop", lambda r: r["seq"] == 1),
                        ("2-3 stops", lambda r: 2 <= r["seq"] <= 3),
                        ("4+ stops", lambda r: r["seq"] >= 4)):
        part = [r for r in rows if keep(r)]
        if part:
            summarise(part, label)

    # Trains where SANKET beat the baseline by the most / least: candidates for a slide.
    per_train = {}
    for r in rows:
        per_train.setdefault(r["train"], []).append(r["err_base"] - r["err_model"])
    ranked = sorted(((np.mean(v), t) for t, v in per_train.items()), reverse=True)
    print("\nBest trains to show (minutes saved per station vs carry-forward):")
    for gain, t in ranked[:3]:
        print(f"  {t}: {gain:+.1f}")
    print("Worst (show these too, honestly):")
    for gain, t in ranked[-3:]:
        print(f"  {t}: {gain:+.1f}")


if __name__ == "__main__":
    main()
