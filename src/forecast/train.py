"""Train, evaluate and save the ETA forecaster.

    python -m src.forecast.train                       # base features, test on the latest day
    python -m src.forecast.train --features network,hist
    python -m src.forecast.train --compare             # every feature set side by side
    python -m src.forecast.train --test-date 2026-09-21

Writes:
    models/forecast_eval.joblib   trained on days BEFORE the test day (used for replays)
    models/forecast_full.joblib   trained on every day (used for anything live)
    frontend/public/eta_horizon.json   the Results page reads this
    docs/eta_horizon.md                the same table for the README / slides
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import joblib
import numpy as np

from src.features.build_features import add_direction
from src.forecast.data import (MODEL_DIR, PUBLIC, ROOT, load_departures,
                               load_km, load_observations)
from src.forecast.horizon import (BUCKET_LABELS, build_horizon_frame, evaluate,
                                  parse_groups, train_forecaster)

PRESETS = ["base", "hist", "network", "network,hist", "network,sched", "network,sched,hist"]


def run_one(obs, km, dep, groups, train, test, seed=0):
    fc = train_forecaster(obs, km, train, groups, departures=dep, seed=seed)
    frame = build_horizon_frame(obs, km, groups, fit_mask=train, departures=dep)
    te = frame[test[frame["k_idx"].to_numpy()]].reset_index(drop=True)
    ev = evaluate(te, fc.predict(te))
    return fc, ev


def label(groups) -> str:
    return "+".join(("base",) + tuple(groups))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--features", default="base", help="base | network | sched | hist, comma-separated")
    ap.add_argument("--test-date", default=None, help="default: the latest run_date")
    ap.add_argument("--compare", action="store_true", help="also score every preset feature set")
    ap.add_argument("--no-full", action="store_true", help="skip the all-days model")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    obs = load_observations()
    km = load_km()
    dep = load_departures(km)

    dates = sorted(obs["run_date"].unique())
    test_date = args.test_date or dates[-1]
    if test_date not in dates:
        raise SystemExit(f"no observations for {test_date}; have {dates}")
    test = (obs["run_date"] == test_date).to_numpy()
    train = (obs["run_date"] < test_date).to_numpy()
    if len(set(obs.loc[train, "run_date"])) < 2:
        raise SystemExit("need at least two training days (one is used to calibrate the window)")

    chosen = parse_groups(args.features)
    if "sched" in chosen and dep is None:
        raise SystemExit("'sched' needs station boards in data/raw/railradar/boards")
    print(f"train days {sorted(set(obs.loc[train, 'run_date']))} | test day {test_date}")
    known = add_direction(obs, km)["direction"].notna().mean()
    print(f"direction known for {known:.0%} of rows ({len(km)} corridor maps)\n")

    sets = []
    if args.compare:
        for text in PRESETS:
            g = parse_groups(text)
            if "sched" in g and dep is None:
                continue
            sets.append(g)
    if chosen not in sets:
        sets.append(chosen)

    scored, chosen_fc, chosen_ev = [], None, None
    for g in sets:
        fc, ev = run_one(obs, km, dep, g, train, test, args.seed)
        o = ev["overall"]
        scored.append(dict(name=label(g), mae_model=o["mae_model"], mae_carry=o["mae_carry"],
                           gain_pct=o["gain_pct"], gain_lo=o["gain_lo"], gain_hi=o["gain_hi"],
                           coverage=o["coverage"], width=o["width"]))
        print(f"{label(g):<22} MAE {o['mae_model']:5.2f} min | carry-forward {o['mae_carry']:5.2f} | "
              f"gain {o['gain_pct']:+5.1f}% (95% range {o['gain_lo']:+.1f} to {o['gain_hi']:+.1f}) | "
              f"window holds {o['coverage']:.0%}, {o['width']:.0f} min wide")
        if g == chosen:
            chosen_fc, chosen_ev = fc, ev

    print(f"\nChosen: {label(chosen)}. Error by how far ahead the station is:")
    for r in chosen_ev["buckets"]:
        print(f"  {r['bucket']:<12} n={r['n']:<5} model {r['mae_model']:5.2f}  carry {r['mae_carry']:5.2f}  "
              f"gain {r['gain_pct']:+5.1f}%  window holds {r['coverage']:.0%}")

    cov = {r["bucket"]: r["coverage"] for r in chosen_ev["buckets"]}
    chosen_fc.coverage = [cov.get(b, chosen_fc.target) for b in BUCKET_LABELS]
    meta = dict(features=label(chosen), test_date=test_date, train_dates=chosen_fc.train_dates,
                generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(dict(forecaster=chosen_fc, meta=meta), MODEL_DIR / "forecast_eval.joblib")
    if not args.no_full:
        full = train_forecaster(obs, km, np.ones(len(obs), bool), chosen, departures=dep, seed=args.seed)
        full.coverage = chosen_fc.coverage
        joblib.dump(dict(forecaster=full, meta={**meta, "train_dates": full.train_dates, "test_date": None}),
                    MODEL_DIR / "forecast_full.joblib")

    o = chosen_ev["overall"]
    out = dict(
        generated_at=meta["generated_at"], is_sample=False, test_date=test_date,
        feature_set=label(chosen), baseline="carry the current delay forward",
        n_test_runs=o["n_runs"], n_test_rows=o["n"], n_train_days=len(chosen_fc.train_dates),
        overall={k: round(float(v), 3) for k, v in o.items()},
        buckets=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                 for r in chosen_ev["buckets"]],
        feature_sets=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                      for r in scored],
    )
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "eta_horizon.json").write_text(json.dumps(out, indent=2))
    write_markdown(out)
    print(f"\nsaved models/ , frontend/public/eta_horizon.json , docs/eta_horizon.md")


def write_markdown(out):
    o = out["overall"]
    lines = [
        "# ETA error by how far ahead the station is",
        "",
        f"Test day {out['test_date']} ({out['n_test_runs']} train runs, {out['n_test_rows']} forecasts). "
        f"Model: {out['feature_set']}, trained on {out['n_train_days']} earlier days. "
        f"Baseline: {out['baseline']}.",
        "",
        "| Station is | Forecasts | SANKET error (min) | Baseline error (min) | Improvement | Window holds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in out["buckets"]:
        lines.append(f"| {r['bucket']} | {r['n']} | {r['mae_model']:.1f} | {r['mae_carry']:.1f} | "
                     f"{r['gain_pct']:+.0f}% | {r['coverage']:.0%} |")
    lines += [
        f"| **All** | {o['n']} | **{o['mae_model']:.1f}** | **{o['mae_carry']:.1f}** | "
        f"**{o['gain_pct']:+.0f}%** | {o['coverage']:.0%} |",
        "",
        f"Overall improvement 95% range (whole train runs resampled): {o['gain_lo']:+.1f}% to {o['gain_hi']:+.1f}%. "
        "If the range crosses zero, do not claim the model is better.",
        "",
        "| Feature set | SANKET error (min) | Improvement | 95% range | Window holds | Width (min) |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for r in out["feature_sets"]:
        lines.append(f"| {r['name']} | {r['mae_model']:.2f} | {r['gain_pct']:+.1f}% | "
                     f"{r['gain_lo']:+.1f} to {r['gain_hi']:+.1f} | {r['coverage']:.0%} | {r['width']:.0f} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "eta_horizon.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
