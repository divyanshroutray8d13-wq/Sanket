"""
Build a named corridor (corridor 2 onwards) from the timetable.

Corridor 1 (Delhi-Mumbai) stays in notebooks/build_corridor.py and keeps its
original file names, because the collector and observations depend on them.

Run from the repo root:
    python notebooks/build_named_corridor.py howrah
    python notebooks/build_named_corridor.py chennai

Writes to data/processed/:
    corridor_{name}_trains.txt      the trains to collect (committed to git)
    corridor_{name}_routes.csv      route steps of those trains
    corridor_{name}_sections.csv    directional sections of those trains
    corridor_{name}_candidates.csv  every train that touched both ends, with
                                    tier, direction and whether it was picked
                                    (use it to swap in a replacement if
                                    RailRadar does not track a picked train)
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.graph.build_graph import (  # noqa: E402
    add_absolute_minutes,
    build_routes,
    build_sections,
    load_schedule,
)

DATA_PATH = ROOT / "data" / "raw" / "trains.csv"
OUT_DIR = ROOT / "data" / "processed"
MAX_TRAINS = 15

CORRIDORS = {
    "howrah": {
        "label": "Delhi-Howrah",
        "end_a": {"NDLS", "DLI", "NZM", "ANVT"},
        "end_b": {"HWH", "SDAH", "KOAA"},
    },
    # Fallback third corridor if Mumbai suburban trains are not tracked
    "chennai": {
        "label": "Delhi-Chennai",
        "end_a": {"NDLS", "NZM"},
        "end_b": {"MAS", "MS"},
    },
}

# Lower tier = picked first. Premium, then regular express, then the rest.
PREMIUM = re.compile(r"RAJDHANI|DURONTO|SHATABDI|HUMSAFAR|TEJAS|VANDE|GARIB ?RATH|SAMPARK", re.I)
EXPRESS = re.compile(r"\bEXP|EXPRESS|\bMAIL\b|\bSF\b|SUPERFAST|ANTYODAYA", re.I)
SPECIAL = re.compile(r"\bSPL\b|SPECIAL", re.I)


def tier_of(name) -> int:
    name = "" if pd.isna(name) else str(name)
    if SPECIAL.search(name):
        return 3  # specials do not run every day, so RailRadar may not have them
    if PREMIUM.search(name):
        return 0
    if EXPRESS.search(name):
        return 1
    return 2


def find_candidates(df: pd.DataFrame, end_a: set, end_b: set) -> pd.DataFrame:
    """Every train touching both ends, with its direction and tier."""
    rows = []
    for train_no, g in df.sort_values(["train_no", "stop_seq"]).groupby("train_no", sort=False):
        codes = g["station_code"].astype(str).tolist()
        a_pos = [i for i, c in enumerate(codes) if c in end_a]
        b_pos = [i for i, c in enumerate(codes) if c in end_b]
        if not a_pos or not b_pos:
            continue
        rows.append({
            "train_no": str(train_no).strip(),
            "train_name": g["train_name"].iloc[0],
            "direction": "a_to_b" if a_pos[0] < b_pos[0] else "b_to_a",
            "tier": tier_of(g["train_name"].iloc[0]),
            "n_stops": len(codes),
        })
    return pd.DataFrame(rows, columns=["train_no", "train_name", "direction", "tier", "n_stops"])


def usable(train_no: pd.Series) -> pd.Series:
    """Five-digit numbers only, and not starting with 0: 0xxxx trains are
    specials, which RailRadar did not track on their run days (see NOTES.md)."""
    return train_no.str.fullmatch(r"[1-9]\d{4}")


def select_trains(cands: pd.DataFrame, limit: int = MAX_TRAINS) -> list[str]:
    """Pick up to `limit` usable trains, best tier first, alternating
    directions so both ways of the corridor are covered."""
    ok = cands[usable(cands["train_no"])]
    queues = {
        d: ok[ok["direction"] == d].sort_values(["tier", "train_no"])["train_no"].tolist()
        for d in ("a_to_b", "b_to_a")
    }
    picked = []
    while len(picked) < limit and (queues["a_to_b"] or queues["b_to_a"]):
        for d in ("a_to_b", "b_to_a"):
            if queues[d] and len(picked) < limit:
                picked.append(queues[d].pop(0))
    return picked


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[1] not in CORRIDORS:
        print(f"Usage: python notebooks/build_named_corridor.py [{' | '.join(CORRIDORS)}]")
        sys.exit(1)
    name = argv[1]
    cfg = CORRIDORS[name]

    df = load_schedule(DATA_PATH)
    print(f"Loaded {df.train_no.nunique()} trains and {len(df)} stops.")

    codes = set(df["station_code"].dropna().astype(str))
    found_a, found_b = sorted(cfg["end_a"] & codes), sorted(cfg["end_b"] & codes)
    print(f"{cfg['label']}: end A codes found {found_a}, end B codes found {found_b}")
    if not found_a or not found_b:
        raise RuntimeError("One end of the corridor has no matching station codes in the schedule.")

    cands = find_candidates(df, cfg["end_a"], cfg["end_b"])
    if cands.empty:
        raise RuntimeError("No trains touch both ends of this corridor.")
    not_usable = int((~usable(cands["train_no"])).sum())

    picked = select_trains(cands)
    cands["selected"] = cands["train_no"].isin(picked)

    sub = df[df["train_no"].astype(str).str.strip().isin(picked)].copy()
    routes = build_routes(add_absolute_minutes(sub))
    sections = build_sections(routes)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"corridor_{name}_trains.txt").write_text(
        "".join(f"{t}\n" for t in picked), encoding="utf-8"
    )
    routes.to_csv(OUT_DIR / f"corridor_{name}_routes.csv", index=False)
    sections.to_csv(OUT_DIR / f"corridor_{name}_sections.csv", index=False)
    cands.sort_values(["selected", "tier", "train_no"], ascending=[False, True, True]).to_csv(
        OUT_DIR / f"corridor_{name}_candidates.csv", index=False
    )

    sel = cands[cands["selected"]]
    tiers = sel["tier"].map({0: "premium", 1: "express", 2: "other", 3: "special"}).value_counts()
    print(f"Candidates touching both ends: {len(cands)} ({not_usable} skipped: not five digits, or a 0xxxx special)")
    print(f"Selected: {len(picked)} "
          f"({(sel.direction == 'a_to_b').sum()} towards end B, {(sel.direction == 'b_to_a').sum()} towards end A)")
    print("By tier: " + ", ".join(f"{k} {v}" for k, v in tiers.items()))
    print(f"Route steps: {len(routes)}")
    print(f"Unique directional sections: {len(sections)}")
    if not sections.empty:
        print(f"Busiest section: {sections.iloc[0].section_id} carries {int(sections.n_trains.max())} trains")


if __name__ == "__main__":
    main(sys.argv)
