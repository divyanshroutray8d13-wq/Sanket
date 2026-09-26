"""
Build corridor_overlap_routes.csv / corridor_overlap_sections.csv for the
overlap corridor: the map and any code that globs data/processed/corridor*_routes.csv
needs these, same as corridor_routes.csv and corridor_howrah_routes.csv.

build_named_corridor.py can't do this one - that script picks trains by which
two end stations they touch, but the overlap corridor is picked differently
(notebooks/build_overlap.py: trains that share track sections with the
Delhi-Mumbai corridor). The train list is already decided and committed at
data/processed/corridor_overlap_trains.txt, so this script just builds the
route/section files for exactly that list, the same way build_corridor.py
does for Delhi-Mumbai.

Run from the repo root:
    python notebooks/build_overlap_routes.py

Reads:
    data/raw/trains.csv                       full timetable
    data/processed/corridor_overlap_trains.txt  the already-picked train list

Writes:
    data/processed/corridor_overlap_routes.csv
    data/processed/corridor_overlap_sections.csv
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.graph.build_graph import load_schedule, add_absolute_minutes, build_routes, build_sections  # noqa: E402

DATA_PATH = ROOT / "data" / "raw" / "trains.csv"
TRAIN_LIST = ROOT / "data" / "processed" / "corridor_overlap_trains.txt"
OUT_DIR = ROOT / "data" / "processed"


def main():
    trains = [ln.strip().zfill(5) for ln in TRAIN_LIST.read_text().splitlines() if ln.strip()]
    print(f"Overlap corridor trains: {len(trains)}")

    df = load_schedule(DATA_PATH)
    print(f"Loaded {df.train_no.nunique()} trains and {len(df)} stops.")

    sub = df[df["train_no"].astype(str).str.zfill(5).isin(trains)].copy()
    sub["train_no"] = sub["train_no"].astype(str).str.zfill(5)
    found = sorted(sub["train_no"].unique())
    missing = sorted(set(trains) - set(found))
    if missing:
        print(f"WARNING: {len(missing)} overlap trains not found in the timetable: {missing}")
    print(f"Trains with a schedule: {len(found)}")

    routes = build_routes(add_absolute_minutes(sub))
    sections = build_sections(routes)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    routes.to_csv(OUT_DIR / "corridor_overlap_routes.csv", index=False)
    sections.to_csv(OUT_DIR / "corridor_overlap_sections.csv", index=False)

    print(f"Route steps: {len(routes)}")
    print(f"Unique directional sections: {len(sections)}")
    if not sections.empty:
        print(f"Busiest section: {sections.iloc[0].section_id} carries {int(sections.n_trains.max())} trains")
    print("-> data/processed/corridor_overlap_routes.csv")
    print("-> data/processed/corridor_overlap_sections.csv")


if __name__ == "__main__":
    main()
