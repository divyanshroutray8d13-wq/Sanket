import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

app = FastAPI(title="SANKET API")

VALID_PROFILES = {"control", "app", "board"}


def get_live_dir() -> Path:
    return Path(os.environ.get("SANKET_LIVE_DIR", "data/live"))


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


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/eta/{train_no}")
def get_eta(train_no: str, profile: str = "control"):
    if profile not in VALID_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile '{profile}'")

    live_dir = get_live_dir()
    file_path = live_dir / f"{train_no}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"No data for train {train_no}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if profile == "control":
        return data
    elif profile == "app":
        return to_app_profile(data)
    else:
        return to_board_profile(data)