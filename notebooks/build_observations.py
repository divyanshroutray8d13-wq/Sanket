import json
from pathlib import Path

import pandas as pd

from src.collect.parse import route_to_observations

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "railradar"
OUT = ROOT / "data" / "processed" / "observations.csv"

files = sorted(RAW.glob("*_2026-*.json"))
frames = [route_to_observations(json.loads(f.read_text())) for f in files]

rejected = [f.name for f, fr in zip(files, frames) if len(fr) == 0]
frames = [fr for fr in frames if len(fr)]

obs = pd.concat(frames, ignore_index=True)
obs.to_csv(OUT, index=False)

print(f"{len(files)} files read, {len(frames)} usable, {len(rejected)} rejected")
print(f"{len(obs)} observations")
print()
print(obs.minutes_lost.describe())
print()

runs = obs.groupby(["train_no", "run_date"]).agg(
    sections=("minutes_lost", "size"),
    zero_frac=("minutes_lost", lambda s: (s == 0).mean()),
    mean_lost=("minutes_lost", "mean"),
    category=("train_category", "first"),
)
print(runs.sort_values("zero_frac").to_string())
print()
print("zero fraction by category:")
print(runs.groupby("category").zero_frac.mean().round(2))
print()

rejected_trains = sorted({n.split("_")[0] for n in rejected})
print(f"trains with at least one untracked run: {rejected_trains}")