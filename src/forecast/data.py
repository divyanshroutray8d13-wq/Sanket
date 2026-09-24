"""Shared loaders for the forecast code: observations, corridor maps, boards."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.eval.split import attach_corridor
from src.features.build_features import corridor_km, pick_references
from src.features.schedule import board_departures, load_boards

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "railradar"
BOARD_DIR = RAW / "boards"
MODEL_DIR = ROOT / "models"
LIVE_DIR = ROOT / "data" / "live"
PUBLIC = ROOT / "frontend" / "public"

MAIN_REFERENCE = "19019"          # Delhi-Mumbai reference train (continuous route)
TRAIN_LISTS = ("howrah", "overlap")


def load_observations(processed: Path = PROCESSED) -> pd.DataFrame:
    obs = pd.read_csv(processed / "observations.csv", dtype={"train_no": str})
    obs["train_no"] = obs["train_no"].str.zfill(5)
    return attach_corridor(obs, processed).reset_index(drop=True)


def load_routes(processed: Path = PROCESSED) -> pd.DataFrame:
    return pd.read_csv(processed / "routes.csv", dtype={"train_no": str})


def build_km(routes: pd.DataFrame, processed: Path = PROCESSED) -> dict:
    """One {station: km} map per corridor. The first (Delhi-Mumbai) is the main one.

    Howrah and overlap trains get up to three maps each, built from reference trains
    that together cover most of their sections, so those sections get a direction
    (and therefore network features) instead of NaN.
    """
    kms = {"mumbai": corridor_km(routes, MAIN_REFERENCE)}
    for name in TRAIN_LISTS:
        path = processed / f"corridor_{name}_trains.txt"
        if not path.exists():
            continue
        trains = [ln.strip().zfill(5) for ln in path.read_text().splitlines() if ln.strip()]
        for i, ref in enumerate(pick_references(routes, trains)):
            kms[f"{name}{i + 1}"] = corridor_km(routes, ref)
    return kms


def load_km(processed: Path = PROCESSED) -> dict:
    """Corridor maps. Built from routes.csv when it is there (and cached in
    corridor_km.json, which IS committed); otherwise read from the cache, so
    a teammate without the 4 MB routes.csv can still train and export."""
    cache = processed / "corridor_km.json"
    routes_csv = processed / "routes.csv"
    if routes_csv.exists():
        kms = build_km(load_routes(processed), processed)
        cache.write_text(json.dumps(kms, separators=(",", ":")))
        return kms
    if cache.exists():
        return json.loads(cache.read_text())
    raise FileNotFoundError("need data/processed/routes.csv (ask Rivy) or the cached corridor_km.json")


def load_departures(km: dict, board_dir: Path = BOARD_DIR):
    """Scheduled departures from the station boards (main corridor only), or None."""
    if not board_dir.exists():
        return None
    boards = load_boards(board_dir)
    if not boards:
        return None
    return board_departures(boards, next(iter(km.values())))
