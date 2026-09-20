import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.graph.build_graph import (
    load_schedule, add_absolute_minutes, build_routes, build_sections
)

df = load_schedule("data/raw/trains.csv")
print(f"{df.train_no.nunique()} trains, {len(df)} stops")

df = add_absolute_minutes(df)
routes = build_routes(df)
print(f"{len(routes)} route steps")

sections = build_sections(routes)
print(f"{len(sections)} unique sections")
print(f"busiest section carries {sections.n_trains.max()} trains")
print(sections.head(15))

routes.to_csv("data/processed/routes.csv", index=False)
sections.to_csv("data/processed/sections.csv", index=False)