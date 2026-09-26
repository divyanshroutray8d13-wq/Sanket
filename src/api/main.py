import json
import os
import re
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SANKET API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

VALID_PROFILES = {"control", "app", "board"}

# RailRadar is a quota-limited live source. Cache each live response briefly so
# browser refreshes and multiple UI components do not create duplicate provider calls.
LIVE_CACHE_TTL_SEC = 90
_LIVE_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}
_LIVE_CACHE_LOCK = threading.Lock()


def _get_cached_live(train_no: str, profile: str):
    key = (train_no, profile)
    now = time.monotonic()

    with _LIVE_CACHE_LOCK:
        cached = _LIVE_CACHE.get(key)
        if cached is not None:
            stored_at, data = cached
            age = now - stored_at
            if age < LIVE_CACHE_TTL_SEC:
                result = dict(data)
                result["data_freshness_min"] = round(age / 60, 2)
                return result

            _LIVE_CACHE.pop(key, None)

        # Hold the lock while the provider/model call happens. This prevents
        # simultaneous browser requests from all missing the cache at once.
        from src.forecast.live import build_live_payload

        data = build_live_payload(train_no, profile=profile)
        _LIVE_CACHE[key] = (now, data)
        result = dict(data)
        result["data_freshness_min"] = 0
        return result
TRAIN_NO = re.compile(r"[0-9]{5}")
STATION_CODE = re.compile(r"[A-Z0-9]{1,8}")


def get_live_dir() -> Path:
    return Path(os.environ.get("SANKET_LIVE_DIR", "data/live"))


def get_corridors_path() -> Path:
    # corridors.json lives OUTSIDE data/live, as a sibling folder —
    # so /station's scan of data/live never has to skip it.
    return get_live_dir().parent / "corridors.json"


def confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    elif confidence >= 0.6:
        return "medium"
    else:
        return "low"


def to_app_profile(data: dict) -> dict:
    return {
        "train_no": data["train_no"],
        "train_name": data["train_name"],
        "as_of": data["as_of"],
        "is_live": data["is_live"],
        "stations": [
            {
                "code": s["code"],
                "name": s["name"],
                "eta_low": s["eta_low"],
                "eta_high": s["eta_high"],
                "confidence_label": confidence_label(s.get("confidence", 0.6)),
            }
            for s in data["stations"]
        ],
    }


def to_board_profile(data: dict) -> dict:
    return {
        "train_no": data["train_no"],
        "train_name": data["train_name"],
        "as_of": data["as_of"],
        "stations": [
            {"code": s["code"], "name": s["name"], "eta": s["eta_median"]}
            for s in data["stations"]
        ],
    }


def load_train_file(file_path: Path) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Data file for this train is corrupted: {file_path.name}",
        )


def time_to_sort_key(time_str: str) -> int:
    hours, minutes = map(int, time_str.split(":"))
    total = hours * 60 + minutes
    if hours < 4:
        total += 24 * 60
    return total


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/eta/{train_no}")
def get_eta(train_no: str, profile: str = "control", live: bool = False):
    if not TRAIN_NO.fullmatch(train_no):
        raise HTTPException(status_code=400, detail="train_no must be exactly 5 digits")

    if profile not in VALID_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile '{profile}'")

    if live:
        try:
            return _get_cached_live(train_no, profile)
        except Exception as exc:
            # The caller explicitly requested live data; do not silently switch
            # to replay data because that would make the UI look live when it is not.
            raise HTTPException(status_code=502, detail=f"Live forecast failed: {exc}") from exc

    live_dir = get_live_dir()
    file_path = live_dir / f"{train_no}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"No data for train {train_no}")

    data = load_train_file(file_path)

    if profile == "control":
        return data
    elif profile == "app":
        return to_app_profile(data)
    else:
        return to_board_profile(data)


@app.get("/station/{code}")
def get_station(code: str):
    code = code.upper()

    if not STATION_CODE.fullmatch(code):
        raise HTTPException(status_code=400, detail="station code must be 1-8 letters/digits")

    live_dir = get_live_dir()
    results = []

    # Only scan files that look like a 5-digit train number — this alone
    # keeps corridors.json (or anything else) out, even if it ever ends up
    # back in this folder by mistake.
    for file_path in live_dir.glob("[0-9][0-9][0-9][0-9][0-9].json"):
        try:
            data = load_train_file(file_path)
        except HTTPException:
            continue

        if "stations" not in data:
            continue

        for station in data["stations"]:
            if station["code"] == code:
                results.append({
                    "train_no": data["train_no"],
                    "train_name": data["train_name"],
                    "eta_low": station["eta_low"],
                    "eta_high": station["eta_high"],
                    "eta_median": station["eta_median"],
                })

    results.sort(key=lambda r: time_to_sort_key(r["eta_median"]))
    return results


@app.get("/corridors")
def get_corridors():
    file_path = get_corridors_path()

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="corridors.json not found")

    return load_train_file(file_path)