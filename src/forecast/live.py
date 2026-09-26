"""Live RailRadar -> Sanket ETA adapter.

This module keeps the existing replay artifacts untouched. It fetches one live
RailRadar payload, builds Sanket-compatible features for the train's current
halt and future halts, then runs the existing forecast_full model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.collect.railradar import fetch_live
from src.features.build_features import build_features
from src.features.history import add_section_history
from src.forecast.data import load_km, load_observations
from src.forecast.horizon import Forecaster, feature_columns

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "forecast_full.joblib"
CORRIDORS_PATH = ROOT / "data" / "corridors.json"


def _route(payload: dict) -> list[dict]:
    return (payload.get("data") or {}).get("route") or []


def _halt_route(payload: dict) -> list[dict]:
    return [s for s in _route(payload) if s.get("isHalt")]


def _iso_minutes(a: Any, b: Any) -> float:
    return (pd.Timestamp(b) - pd.Timestamp(a)).total_seconds() / 60.0


def _pick_current(halt_route: list[dict], now: pd.Timestamp) -> int:
    candidates: list[tuple[pd.Timestamp, int]] = []
    for i, station in enumerate(halt_route):
        actual_dep = station.get("actualDeparture")
        if actual_dep:
            ts = pd.Timestamp(actual_dep)
            if ts.tzinfo is not None and ts <= now:
                candidates.append((ts, i))
    if candidates:
        return max(candidates)[1]

    candidates = []
    for i, station in enumerate(halt_route):
        if station.get("status") == "departed" and station.get("scheduledDeparture"):
            ts = pd.Timestamp(station["scheduledDeparture"])
            if ts.tzinfo is not None and ts <= now:
                candidates.append((ts, i))
    if candidates:
        return max(candidates)[1]

    raise ValueError("RailRadar has not reported a usable departed halt yet")


def _train_meta(payload: dict) -> tuple[str, str, str]:
    data = payload.get("data") or {}
    train_no = str(data.get("trainNumber") or data.get("train_no") or "").zfill(5)
    if not train_no.isdigit() or len(train_no) != 5:
        raise ValueError("RailRadar payload has no valid train number")
    train = data.get("train") or {}
    category = str(train.get("category") or data.get("trainCategory") or "Express")
    run_date = str(data.get("startDate") or pd.Timestamp.now(tz="Asia/Kolkata").date())
    return train_no, category, run_date


def _build_live_rows(
    payload: dict, halt_route: list[dict], current_idx: int, now: pd.Timestamp
) -> tuple[pd.DataFrame, int]:
    train_no, category, run_date = _train_meta(payload)
    rows = []
    for step, (a, b) in enumerate(
        zip(halt_route[current_idx:], halt_route[current_idx + 1:]),
        start=current_idx,
    ):
        sd = a.get("scheduledDeparture")
        sa = b.get("scheduledArrival")
        if not sd or not sa:
            continue

        booked = _iso_minutes(sd, sa)
        length = float(b.get("distance", 0) or 0) - float(a.get("distance", 0) or 0)
        if booked <= 0 or length <= 0:
            continue

        delay = float(a.get("delayDeparture") or a.get("delayArrival") or 0)
        dep_actual = a.get("actualDeparture") or now.isoformat()
        arr_actual = b.get("actualArrival") or sa

        rows.append([
            train_no, category, run_date, step,
            a["stationCode"], b["stationCode"],
            round(booked), round(booked), 0.0, length, delay,
            dep_actual, arr_actual,
        ])

    if not rows:
        raise ValueError("No future halt-to-halt sections are available")

    cols = [
        "train_no", "train_category", "run_date", "step_seq",
        "from_station", "to_station", "booked_srt_min", "actual_srt_min",
        "minutes_lost", "length_km", "dep_delay_min", "dep_time", "arr_time",
    ]
    return pd.DataFrame(rows, columns=cols), current_idx


def _live_km(halt_route: list[dict]) -> dict[str, float]:
    return {
        str(s["stationCode"]): float(s.get("distance", 0) or 0)
        for s in halt_route
        if s.get("stationCode") and s.get("distance") is not None
    }


def _hist_features(obs: pd.DataFrame) -> pd.DataFrame:
    mask = np.ones(len(obs), dtype=bool)
    return add_section_history(obs, mask, min_count=3)


def _as_clock(ts: pd.Timestamp) -> str:
    return ts.tz_convert("Asia/Kolkata").strftime("%H:%M")


def _corridor_for_train(train_no: str) -> str | None:
    if not CORRIDORS_PATH.exists():
        return None
    try:
        corridors = __import__("json").loads(CORRIDORS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    for corridor in corridors:
        if str(train_no) in {str(x).zfill(5) for x in corridor.get("trains", [])}:
            return corridor.get("name")
    return None


def _forecast_rows(
    payload: dict, obs: pd.DataFrame, forecaster: Forecaster, now: pd.Timestamp
) -> tuple[list[dict], dict]:
    halt_route = _halt_route(payload)
    current_idx = _pick_current(halt_route, now)
    if current_idx >= len(halt_route) - 1:
        raise ValueError("Train is at the end of the route; no future ETA to predict")

    live_rows, _ = _build_live_rows(payload, halt_route, current_idx, now)
    historical = obs.copy().reset_index(drop=True)
    hist = _hist_features(historical)

    kms = {"live": _live_km(halt_route)}
    kms.update(load_km())
    combined = pd.concat([historical, live_rows], ignore_index=True)
    X_all, _ = build_features(combined, kms, include_network=True)
    live_offset = len(historical)
    x = X_all.iloc[live_offset].copy()

    hist_map = hist.groupby(
        ["from_station", "to_station"], dropna=False
    )["sec_hist_mean"].first()

    future = live_rows.reset_index(drop=True)
    sections = list(zip(future["from_station"], future["to_station"]))
    means = [hist_map.get((a, b), np.nan) for a, b in sections]

    current = halt_route[current_idx]
    current_sched_dep = pd.Timestamp(current["scheduledDeparture"])
    current_delay = float(
        current.get("delayDeparture") or current.get("delayArrival") or 0
    )
    current_step = int(future.iloc[0]["step_seq"])

    rows = []
    for target_offset, target in enumerate(halt_route[current_idx + 1:], start=1):
        if target_offset > 20:
            break

        target_code = target.get("stationCode")
        target_sched_arr = target.get("scheduledArrival")
        if not target_code or not target_sched_arr:
            continue

        h = target_offset
        cum_booked = _iso_minutes(current_sched_dep, target_sched_arr)
        section_means = means[:target_offset]
        valid = [m for m in section_means if pd.notna(m)]
        cum_hist_mean = float(np.sum(valid)) if valid else np.nan
        cum_hist_cov = float(len(valid) / target_offset)

        frame = pd.DataFrame([x.to_dict()])
        frame["h"] = float(h)
        frame["cum_booked"] = float(cum_booked)
        frame["cum_hist_mean"] = cum_hist_mean
        frame["cum_hist_cov"] = cum_hist_cov
        frame = frame[feature_columns(forecaster.groups)]

        pred = forecaster.predict(frame).iloc[0]
        contrib = forecaster.contributions(frame).iloc[0].to_dict()
        confidence = float(forecaster.confidence(h))

        def eta(extra: float) -> str:
            return _as_clock(
                pd.Timestamp(target_sched_arr)
                + pd.to_timedelta(current_delay + extra, unit="min")
            )

        rows.append({
            "code": target_code,
            "name": target.get("stationName") or target_code,
            "sequence": int(target.get("sequence", current_idx + h)),
            "scheduled": _as_clock(pd.Timestamp(target_sched_arr)),
            "baseline_eta": _as_clock(
                pd.Timestamp(target_sched_arr)
                + pd.to_timedelta(current_delay, unit="min")
            ),
            "eta_median": eta(float(pred["p50"])),
            "eta_low": eta(float(pred["p10"])),
            "eta_high": eta(float(pred["p90"])),
            "confidence": confidence,
            "attribution": [
                {"cause": k, "minutes": int(round(v))}
                for k, v in sorted(
                    contrib.items(), key=lambda kv: -abs(float(kv[1]))
                )
                if abs(float(v)) >= 0.5
            ][:8],
            "actual": None,
            "actual_delay_min": None,
        })

    meta = {
        "station_code": current.get("stationCode"),
        "station_name": current.get("stationName") or current.get("stationCode"),
        "delay_min": int(round(current_delay)),
        "current_step": current_step,
    }
    return rows, meta


def build_live_payload(train_no: str, profile: str = "control") -> dict:
    payload = fetch_live(str(train_no).zfill(5))
    now = pd.Timestamp.now(tz="Asia/Kolkata")
    obs = load_observations()
    artifact = __import__("joblib").load(MODEL_PATH)
    forecaster: Forecaster = artifact["forecaster"]
    stations, current = _forecast_rows(payload, obs, forecaster, now)
    data = payload.get("data") or {}
    normalized_train = str(train_no).zfill(5)

    out = {
        "train_no": normalized_train,
        "train_name": (
            data.get("trainName")
            or (data.get("train") or {}).get("name")
            or f"Train {train_no}"
        ),
        "corridor": _corridor_for_train(normalized_train),
        "run_date": data.get("startDate"),
        "as_of": now.isoformat(),
        "data_freshness_min": 0,
        "is_live": True,
        "is_mock": False,
        "is_replay": False,
        "replay_note": None,
        "current": current,
        "stations": stations,
        "source": "RailRadar → Sanket forecast_full",
    }

    if profile == "app":
        return {
            "train_no": out["train_no"],
            "train_name": out["train_name"],
            "as_of": out["as_of"],
            "is_live": True,
            "stations": [
                {
                    "code": s["code"],
                    "name": s["name"],
                    "eta_low": s["eta_low"],
                    "eta_high": s["eta_high"],
                    "confidence_label": (
                        "high" if s["confidence"] >= 0.8
                        else "medium" if s["confidence"] >= 0.6
                        else "low"
                    ),
                }
                for s in stations
            ],
        }

    if profile == "board":
        return {
            "train_no": out["train_no"],
            "train_name": out["train_name"],
            "as_of": out["as_of"],
            "stations": [
                {"code": s["code"], "name": s["name"], "eta": s["eta_median"]}
                for s in stations
            ],
        }

    return out
