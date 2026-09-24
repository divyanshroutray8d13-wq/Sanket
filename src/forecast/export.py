"""Turn the trained forecaster into the JSON the API serves (data/live/{train}.json).

    python -m src.forecast.export --all                 # every run on the test day, from the best common moment
    python -m src.forecast.export 12951 12925           # chosen trains
    python -m src.forecast.export --all --now 14:00     # "it is 14:00": every train forecast from that moment
    python -m src.forecast.export 12925 --asof 0.5      # from halfway along one run
    python -m src.forecast.export --all --model full    # use the all-days model (see below)

This is a REPLAY of recorded runs: "now" is the moment the train left station k,
and the forecast uses only what was known then. Real arrivals are attached as
`actual` so the dashboard can show forecast against outcome. The default `eval`
model never saw the test day, so the replay is an honest test. The `full` model
has seen every day, so replays of days it trained on are NOT honest.

The JSON follows the frozen mock schema, plus is_replay / replay_note / actual.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.forecast.data import (LIVE_DIR, MODEL_DIR, RAW, load_departures, load_km,
                               load_observations)
from src.forecast.horizon import build_horizon_frame, bucket_index

IST = "Asia/Kolkata"
CORRIDOR_ID = {"mumbai": "delhi-mumbai", "overlap": "delhi-mumbai-partial", "howrah": "delhi-howrah"}
MAX_CAUSES = 4


def clock(ts) -> str:
    return pd.Timestamp(ts).tz_convert(IST).strftime("%H:%M")


def run_meta(raw_dir: Path, train_no: str, run_date: str) -> dict:
    path = Path(raw_dir) / f"{train_no}_{run_date}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())["data"]
    except (KeyError, ValueError):
        return {}
    route = data.get("route") or []
    return dict(
        name=data.get("trainName"),
        names={s["stationCode"]: s.get("stationName") for s in route if s.get("stationCode")},
        sched={s["stationCode"]: s["scheduledArrival"] for s in route
               if s.get("stationCode") and s.get("scheduledArrival")},
    )


def attribution(row: pd.Series, carried: float = 0.0) -> list:
    """Whole-minute causes for the dashboard's "why late" panel.

    They add up to how late the train is expected to be at the station: the delay
    it already has ("delay carried forward") plus what the model expects to happen
    on the way (`row`, from Forecaster.contributions).

    Positive causes are listed one by one (biggest first, at most MAX_CAUSES,
    the rest folded into 'other'). Everything that moves the forecast earlier
    than the baseline is one line, 'time made up', because that is what it
    means for the train, whichever feature the model got it from.
    """
    items = {**{k: float(v) for k, v in row.items()}, "delay carried forward": float(carried)}
    pos = sorted(((k, v) for k, v in items.items() if v > 0), key=lambda kv: -kv[1])
    made_up = sum(v for v in items.values() if v < 0)
    kept, rest = [], 0.0
    for k, v in pos:
        if len(kept) < MAX_CAUSES and round(v) >= 1:
            kept.append({"cause": k, "minutes": int(round(v))})
        else:
            rest += v
    if round(rest) >= 1:
        kept.append({"cause": "other", "minutes": int(round(rest))})
    if round(made_up) <= -1:
        kept.append({"cause": "time made up", "minutes": int(round(made_up))})
    return kept


def pick_start(steps: list, asof: float) -> int:
    """Index into `steps` of the as-of station: `asof` of the way along, leaving >= 2 stops ahead."""
    last_ok = max(len(steps) - 3, 0)
    return int(min(round(asof * (len(steps) - 1)), last_ok))


def parse_now(text, date):
    """'14:00' (IST, on `date`) or a full ISO timestamp -> aware Timestamp."""
    ts = pd.Timestamp(text) if "T" in text or "-" in text else pd.Timestamp(f"{date} {text}")
    return ts.tz_localize(IST) if ts.tzinfo is None else ts


def choose_start(run, obs, asof, now):
    """(k_step, candidate rows). With `now`: the last station the train had left by then,
    and only stops it had not yet reached. Otherwise `asof` of the way along the run."""
    steps = sorted(run["k_step"].unique())
    if now is None:
        if len(steps) < 3:
            return None, None
        k_step = steps[pick_start(steps, asof)]
        return k_step, run[run["k_step"] == k_step]
    dep = pd.to_datetime(obs["dep_time"].to_numpy()[run.groupby("k_step")["k_idx"].first().to_numpy()], utc=True)
    left = [st for st, d in zip(sorted(run["k_step"].unique()), dep) if d <= now]
    if not left:
        return None, None
    k_step = left[-1]
    rows = run[run["k_step"] == k_step]
    arrives = pd.to_datetime(obs["arr_time"].to_numpy()[rows["j_idx"].to_numpy()], utc=True)
    return k_step, rows[np.asarray(arrives > now)]


def build_payload(fc, obs, frame, train_no, run_date, asof=0.35, n_ahead=10, meta=None,
                  now=None) -> dict | None:
    run = frame[(frame["train_no"] == train_no) & (frame["run_date"] == run_date)]
    if run.empty:
        return None
    k_step, cand = choose_start(run, obs, asof, now)
    if k_step is None:
        return None
    sel = cand[cand["h"] <= n_ahead].sort_values("j_step")
    if sel.empty:
        return None
    meta = meta or {}

    preds = fc.predict(sel)
    causes = fc.contributions(sel)
    conf = fc.confidence(sel["h"])

    k_row = obs.iloc[int(sel["k_idx"].iloc[0])]
    d0 = float(sel["d0"].iloc[0])
    stations = []
    for n, (i, r) in enumerate(sel.iterrows(), start=1):
        j_row = obs.iloc[int(r["j_idx"])]
        code = r["to_station"]
        sched = (pd.Timestamp(meta["sched"][code]) if code in meta.get("sched", {})
                 else pd.Timestamp(j_row["arr_time"]) - pd.Timedelta(minutes=float(r["true_delay"])))
        at = lambda minutes: (sched + pd.Timedelta(minutes=float(minutes))).round("min")
        stations.append({
            "code": code,
            "name": meta.get("names", {}).get(code) or code,
            "sequence": n,
            "scheduled": clock(sched),
            "baseline_eta": clock(at(d0)),
            "eta_median": clock(at(d0 + preds.at[i, "p50"])),
            "eta_low": clock(at(d0 + preds.at[i, "p10"])),
            "eta_high": clock(at(d0 + preds.at[i, "p90"])),
            "confidence": round(float(conf[list(sel.index).index(i)]), 2),
            "attribution": attribution(causes.loc[i], d0),
            "actual": clock(j_row["arr_time"]),
            "actual_delay_min": int(round(r["true_delay"])),
        })

    left_at = pd.Timestamp(k_row["dep_time"])
    as_of = now.isoformat() if now is not None else k_row["dep_time"]
    fresh = int(round((now - left_at).total_seconds() / 60)) if now is not None else 0
    from_name = meta.get("names", {}).get(k_row["from_station"]) or k_row["from_station"]
    return {
        "train_no": train_no,
        "train_name": meta.get("name") or f"Train {train_no}",
        "corridor": CORRIDOR_ID.get(k_row.get("corridor"), "other"),
        "run_date": run_date,
        "as_of": as_of,
        "data_freshness_min": max(fresh, 0),
        "is_live": False,
        "is_mock": False,
        "is_replay": True,
        "replay_note": (f"Replay of {run_date}. It is {clock(as_of)}; the forecast uses only what was known "
                        f"when the train left {from_name} at {clock(left_at)}. "
                        f"What really happened is shown for comparison."),
        "current": {
            "station_code": k_row["from_station"],
            "station_name": meta.get("names", {}).get(k_row["from_station"]) or k_row["from_station"],
            "delay_min": int(round(d0)),
        },
        "stations": stations,
    }


def auto_now(fc, obs, frame, date, n_ahead, meta_of, step_min=30):
    """The half-hour of `date` when the most trains have >= 3 stops left to forecast."""
    day = pd.Timestamp(date).tz_localize(IST)
    best, best_n = day, -1
    for i in range(0, 48):
        t = day + pd.Timedelta(minutes=step_min * i)
        n = 0
        for tn in obs.loc[obs["run_date"] == date, "train_no"].unique():
            run = frame[(frame["train_no"] == tn) & (frame["run_date"] == date)]
            _, cand = choose_start(run, obs, 0, t)
            n += cand is not None and len(cand[cand["h"] <= n_ahead]) >= 3
        if n > best_n:
            best, best_n = t, n
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("trains", nargs="*", help="train numbers (5 digits)")
    ap.add_argument("--all", action="store_true", help="every train that ran on the replay day")
    ap.add_argument("--model", choices=["eval", "full"], default="eval")
    ap.add_argument("--date", default=None, help="run date to replay (default: the model's test day)")
    ap.add_argument("--now", default=None,
                    help="forecast every train from one moment: HH:MM (IST) or ISO time, or 'auto'.\n"
                         "Default for --all is 'auto'; needed for a coherent station board.")
    ap.add_argument("--asof", type=float, default=0.35,
                    help="without --now: how far along each run the forecast is made, 0 to 1")
    ap.add_argument("--n-ahead", type=int, default=10, help="stations to forecast")
    ap.add_argument("--out", default=str(LIVE_DIR))
    args = ap.parse_args(argv)
    if not args.trains and not args.all:
        ap.error("give train numbers or --all")

    art = joblib.load(MODEL_DIR / f"forecast_{args.model}.joblib")
    fc, meta = art["forecaster"], art["meta"]
    obs = load_observations()
    km = load_km()
    date = args.date or meta.get("test_date") or obs["run_date"].max()
    if args.model == "full" or date in fc.train_dates:
        print(f"WARNING: the model was trained on {date}. This replay is not an honest test.")

    dep = load_departures(km) if "sched" in fc.groups else None
    fit_mask = obs["run_date"].isin(fc.train_dates).to_numpy()
    frame = build_horizon_frame(obs, km, fc.groups, fit_mask=fit_mask, departures=dep)

    day = obs[obs["run_date"] == date]
    trains = sorted(day["train_no"].unique()) if args.all else [t.zfill(5) for t in args.trains]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    now_text = args.now or ("auto" if args.all else None)
    now = None
    if now_text == "auto":
        now = auto_now(fc, obs, frame, date, args.n_ahead, None)
    elif now_text:
        now = parse_now(now_text, date)
    if now is not None:
        print(f"forecasting from {now.isoformat()}")

    written, skipped = [], []
    for t in trains:
        payload = build_payload(fc, obs, frame, t, date, args.asof, args.n_ahead,
                                run_meta(RAW, t, date), now=now)
        if payload is None:
            skipped.append(t)
            continue
        (out / f"{t}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(t)
    print(f"wrote {len(written)} forecasts to {out} (model {meta.get('features')}, replay of {date})")
    if skipped:
        print(f"skipped (not running at that moment, or nothing left to forecast): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
