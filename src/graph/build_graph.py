
from numpy.ma import absolute
import pandas as pd

from pathlib import Path

COLUMN_MAP = {
    "Train No": "train_no",
    "Train Name": "train_name",
    "SEQ": "stop_seq",
    "Station Code": "station_code",
    "Arrival time": "arrival",
    "Departure Time": "departure",
    "Distance": "distance_km",
}


def load_schedule(path):
    df = pd.read_csv(path, dtype=str)
    df = df.rename(columns=COLUMN_MAP)
    df = df[list(COLUMN_MAP.values())]

    df["stop_seq"] = pd.to_numeric(df["stop_seq"], errors="coerce")
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")

    bad = df["stop_seq"].isna() | df["distance_km"].isna()
    if bad.any():
        print(f"load_schedule: dropped {bad.sum()} malformed rows")
    df = df[~bad].copy()
    df["stop_seq"] = df["stop_seq"].astype(int)

    df = df.sort_values(["train_no", "stop_seq"]).reset_index(drop=True)

    first = df.groupby("train_no")["stop_seq"].transform("min")
    last = df.groupby("train_no")["stop_seq"].transform("max")
    df.loc[(df["stop_seq"] == first) & (df["arrival"] == "00:00:00"), "arrival"] = None
    df.loc[(df["stop_seq"] == last) & (df["departure"] == "00:00:00"), "departure"] = None

    df = df.groupby("train_no").filter(lambda g: len(g) >= 2)
    return df
   
def hhmm_to_minutes(t):
    """Convert "HH:MM:SS" to minutes since midnight. None if missing."""
    if pd.isna(t) or t == "":
        return None
    h, m = str(t).split(":")[:2]
    return int(h) * 60 + int(m)


def add_absolute_minutes(df):
    df = df.sort_values(["train_no", "stop_seq"]).copy()
    df["arr_min"] = pd.NA
    df["dep_min"] = pd.NA

    for train_no, group in df.groupby("train_no", sort=False):
        offset = 0
        prev = None

        for idx in group.index:
            for col, out_col in (("arrival", "arr_min"), ("departure", "dep_min")):
               t = hhmm_to_minutes(df.at[idx, col])
               if t is None:
                  continue
               if prev is not None and t + offset < prev:
                  offset += 1440
               absolute = t + offset
               df.at[idx, out_col] = absolute
               prev = absolute
    df["arr_min"] = pd.to_numeric(df["arr_min"])
    df["dep_min"] = pd.to_numeric(df["dep_min"])
    return df

def build_routes(df):
    df = df.sort_values(["train_no", "stop_seq"]).copy()
    nxt = df.groupby("train_no", sort=False).shift(-1)

    out = pd.DataFrame({
        "train_no": df["train_no"],
        "from_station": df["station_code"],
        "to_station": nxt["station_code"],
        "booked_srt_min": nxt["arr_min"] - df["dep_min"],
        "length_km": nxt["distance_km"] - df["distance_km"],
    })

    drop = (out["to_station"].isna()
            | out["booked_srt_min"].isna()
            | out["length_km"].isna())
    out = out[~drop].copy()

    if not out.empty:
        out = out[(out["booked_srt_min"] > 0) & (out["booked_srt_min"] <= 720)]
        out = out[out["length_km"] > 0].copy()

    out["booked_srt_min"] = out["booked_srt_min"].astype(int)
    out["step_seq"] = out.groupby("train_no", sort=False).cumcount()

    return out[["train_no", "step_seq", "from_station",
                "to_station", "booked_srt_min", "length_km"]]

def build_sections(routes):
    g = routes.groupby(["from_station", "to_station"], sort=False)

    out = g.agg(
        length_km=("length_km", "median"),
        n_trains=("train_no", "nunique"),
    ).reset_index()

    out["section_id"] = out["from_station"] + ">" + out["to_station"]
    out["n_trains"] = out["n_trains"].astype(int)

    out = out.sort_values(["n_trains", "section_id"],
                          ascending=[False, True]).reset_index(drop=True)

    return out[["section_id", "from_station", "to_station",
                "length_km", "n_trains"]]