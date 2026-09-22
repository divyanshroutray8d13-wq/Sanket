import json
from pathlib import Path

import numpy as np
import pandas as pd

SCHED = ["sched_before_30", "sched_after_30"]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def timetable_departures(sched, km):
    sched = sched.copy()
    sched["train_no"] = sched["train_no"].astype(str).str.zfill(5)
    sched = sched.sort_values(["train_no", "stop_seq"])
    sched["next_station"] = sched.groupby("train_no")["station_code"].shift(-1)
    sched = sched[sched["dep_min"].notna() & sched["next_station"].notna()].copy()
    sched["dep_tod"] = (sched["dep_min"] % 1440).astype(int)
    sched["direction"] = np.sign(sched["next_station"].map(km) - sched["station_code"].map(km))
    sched = sched[sched["direction"].notna() & (sched["direction"] != 0)]
    return (sched[["train_no", "station_code", "dep_tod", "direction"]]
            .rename(columns={"station_code": "station"})
            .reset_index(drop=True))


def scheduled_time(obs):
    return pd.to_datetime(obs["dep_time"]) - pd.to_timedelta(obs["dep_delay_min"], unit="min")


def scheduled_tod(obs):
    s = scheduled_time(obs)
    return s.dt.hour * 60 + s.dt.minute


def load_boards(board_dir):
    return {f.stem: json.loads(f.read_text())
            for f in sorted(Path(board_dir).glob("*.json"))}


def board_departures(boards, km):
    cols = ["train_no", "station", "dep_tod", "direction", "days"]
    rows = []
    for station, payload in boards.items():
        if not payload.get("success") or station not in km:
            continue
        for t in payload["data"]["trains"]:
            train = t["train"]
            stop = t["stop"]
            dep = stop.get("departure")
            if not dep:
                continue
            train_no = str(train["number"]).zfill(5)
            dep_tod = int(dep.split(":")[0]) * 60 + int(dep.split(":")[1])
            day = int(stop.get("departureDay") or 1)
            run = train.get("runDays") or WEEKDAYS
            days = tuple(sorted({WEEKDAYS[(WEEKDAYS.index(d) + day - 1) % 7] for d in run},
                                key=WEEKDAYS.index))
            rows.append(dict(train_no=train_no, station=station, dep_tod=dep_tod,
                             dist=stop.get("distance"), days=days))
    if not rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    df["pos"] = df["station"].map(km)
    dirs = {}
    for train_no, g in df.groupby("train_no"):
        g = g.dropna(subset=["dist"]).sort_values("dist")
        steps = np.sign(np.diff(g["pos"].to_numpy()))
        total = np.sign(steps.sum()) if len(steps) else 0
        dirs[train_no] = float(total) if total != 0 else np.nan
    df["direction"] = df["train_no"].map(dirs)
    df = df[df["direction"].notna()]
    return df[cols].reset_index(drop=True)


def add_schedule_density(obs, departures, window_min=30):
    o = obs.copy().reset_index(drop=True)
    st = scheduled_time(o)
    tod = st.dt.hour * 60 + st.dt.minute
    wd = st.dt.dayofweek
    use_days = "days" in departures.columns
    covered = set(departures["station"])

    for c in SCHED:
        o[c] = np.nan

    for i in o.index:
        if pd.isna(o.at[i, "direction"]) or o.at[i, "from_station"] not in covered:
            continue
        mask = ((departures["station"] == o.at[i, "from_station"])
                & (departures["direction"] == o.at[i, "direction"])
                & (departures["train_no"] != o.at[i, "train_no"]))
        diff = (departures.loc[mask, "dep_tod"] - tod[i] + 720) % 1440 - 720
        if use_days:
            cand_wd = (wd[i] + (tod[i] + diff) // 1440) % 7
            keep = [WEEKDAYS[int(w)] in d
                    for w, d in zip(cand_wd, departures.loc[mask, "days"])]
            diff = diff[keep]
        o.at[i, "sched_before_30"] = int(((-window_min <= diff) & (diff < 0)).sum())
        o.at[i, "sched_after_30"] = int(((0 < diff) & (diff <= window_min)).sum())

    return o