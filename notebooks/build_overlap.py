import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
routes = pd.read_csv(ROOT / "data/processed/routes.csv", dtype={"train_no": str})
sections = pd.read_csv(ROOT / "data/processed/corridor_sections.csv")

corridor_section_ids = set(sections["section_id"])

routes["train_no"] = routes["train_no"].str.zfill(5)
routes["section_id"] = routes["from_station"] + ">" + routes["to_station"]

overlap = (routes.groupby("train_no")["section_id"]
           .apply(lambda s: s.isin(corridor_section_ids).sum())
           .reset_index(name="shared_sections"))
overlap = overlap[overlap["shared_sections"] > 0]

current = set(ln.strip().zfill(5) for ln in
              (ROOT / "data/processed/corridor_trains.txt").read_text().splitlines() if ln.strip())
overlap = overlap[~overlap["train_no"].isin(current)]

never_tracked = {"09003","09004","09005","09006","12493","12907","12911","12912","22413","22917"}
overlap = overlap[~overlap["train_no"].isin(never_tracked)]
overlap = overlap[~overlap["train_no"].str.startswith("0")]

# NOTE: SPL/SPECIAL name filter not applied - routes.csv has no train_name column.
# Ask Rivy where train names live if this matters before the collection run.

overlap = overlap.sort_values("shared_sections", ascending=False)
top30 = overlap.head(30)

print(f"candidates with any overlap: {len(overlap)}")
print(f"top shared sections: {top30.iloc[0]['shared_sections']}")
print(f"bottom (30th) shared sections: {top30.iloc[-1]['shared_sections']}")
print(top30.to_string(index=False))

out = ROOT / "data/processed/corridor_overlap_trains.txt"
out.write_text("".join(f"{t}\n" for t in top30["train_no"]))
print(f"\nwritten to {out}")