import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

app = FastAPI(title="SANKET API")

def get_live_dir() -> Path:
    return Path(os.environ.get("SANKET_LIVE_DIR", "data/live"))

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/eta/{train_no}")
def get_eta(train_no: str):
    live_dir = get_live_dir()
    file_path = live_dir / f"{train_no}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"No data for train {train_no}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data