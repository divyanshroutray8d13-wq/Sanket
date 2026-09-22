from pathlib import Path

import pandas as pd

from src.graph.build_graph import add_absolute_minutes, load_schedule

ROOT = Path(__file__).resolve().parents[1]
TIMETABLE = ROOT / "data" / "raw" / "trains.csv"      # <- your timetable file
OBS = ROOT / "data" / "processed" / "observations.csv"

obs = pd.read_csv(OBS, dtype={"train_no": str})
obs["train_no"] = obs["train_no"].str.zfill(5)

sched = load_schedule(TIMETABLE)
sched["train_no"] = sched["train_no"].astype(str).str.zfill(5)
sched = sched[sched["train_no"].isin(set(obs["train_no"]))]
sched = add_absolute_minutes(sched)
sched["tt_tod"] = sched["dep_min"] % 1440

t = pd.to_datetime(obs["dep_time"])
s = t - pd.to_timedelta(obs["dep_delay_min"], unit="min")
obs["rr_tod"] = s.dt.hour * 60 + s.dt.minute

m = obs.merge(sched[["train_no", "station_code", "tt_tod"]],
              left_on=["train_no", "from_station"],
              right_on=["train_no", "station_code"], how="left")

found = m["tt_tod"].notna()
diff = ((m["tt_tod"] - m["rr_tod"] + 720) % 1440 - 720).abs()

print(f"trains in observations:        {obs.train_no.nunique()}")
print(f"of those, in 2017 timetable:   {sched.train_no.nunique()}")
print(f"observations matched:          {found.mean():.0%}  ({found.sum()} of {len(m)})")
if found.any():
    d = diff[found]
    print(f"median schedule difference:    {d.median():.0f} min")
    print(f"within 10 min:                 {(d <= 10).mean():.0%}")
    print(f"within 30 min:                 {(d <= 30).mean():.0%}")
    print()
    print("worst 10 matches:")
    cols = ["train_no", "from_station", "rr_tod", "tt_tod"]
    print(m.loc[found].assign(diff=d).sort_values("diff", ascending=False)
           [cols + ["diff"]].head(10).to_string(index=False))

print()
ok = found.mean() >= 0.7 and found.any() and (diff[found] <= 10).mean() >= 0.7
print("VERDICT:", "2017 timetable is usable for scheduled traffic"
      if ok else "too stale - use the RailRadar-schedule fallback")