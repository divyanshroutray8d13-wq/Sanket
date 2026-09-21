import numpy as np
import pandas as pd

BASE = ["booked_srt_min", "length_km", "dep_delay_min", "step_seq",
        "hour", "dow", "is_premium"]
NET = ["headway_prev_min", "prev_train_delay", "prev_train_premium",
       "n_prev_30"]


def corridor_km(routes, reference_train):
    filtered = routes[routes.train_no == reference_train].sort_values("step_seq")
    if filtered.empty:
        raise ValueError(f"reference train {reference_train} not found in routes")

    km = {filtered.iloc[0].from_station: 0.0}
    for _, row in filtered.iterrows():
        if row.from_station not in km:
            raise ValueError(
                f"reference train {reference_train} has a gap before "
                f"{row.from_station} — pick a train with a continuous route")
        km[row.to_station] = km[row.from_station] + row.length_km
    return km

def add_time_features(obs):
    o = obs.copy()
    t = pd.to_datetime(o["dep_time"])
    o["hour"] = t.dt.hour
    o["dow"] = t.dt.dayofweek
    o["is_premium"] = (o["train_category"] == "Premium").astype(int)
    return o


def add_direction(obs, km):
    o = obs.copy()
    o["direction"] = np.sign(o["to_station"].map(km) - o["from_station"].map(km))
    return o


def add_network_features(obs, window_min=30, max_headway_min=180):
    o = obs.copy().reset_index(drop=True)
    t = pd.to_datetime(o["dep_time"])
    for c in NET:
        o[c] = np.nan

    for i in o.index:
        if pd.isna(o.at[i, "direction"]):
            continue
        different_train_mask = (
            (o["from_station"] == o.at[i, "from_station"])
            & (o["direction"] == o.at[i, "direction"])
            & (o["train_no"] != o.at[i, "train_no"])
            & (t < t[i]))
        minutes_ago = (t[i] - t[different_train_mask]).dt.total_seconds() / 60
        o.at[i, "n_prev_30"] = int((minutes_ago <= window_min).sum())
        if not different_train_mask.any():
            continue
        largest_t_index = o.index[different_train_mask][t[different_train_mask].argmax()]
        headway = (t[i] - t[largest_t_index]).total_seconds() / 60
        if headway > max_headway_min:
            continue
        o.at[i, "headway_prev_min"] = headway
        o.at[i, "prev_train_delay"] = o.at[largest_t_index, "dep_delay_min"]
        o.at[i, "prev_train_premium"] = 1.0 if o.at[largest_t_index, "train_category"] == "Premium" else 0.0
    return o


def build_features(obs, km, include_network=True):
    o = add_direction(add_time_features(obs), km)
    if include_network:
        o = add_network_features(o)
    cols = BASE + (NET if include_network else [])
    X = o[cols].astype(float).reset_index(drop=True)
    y = obs["minutes_lost"].astype(float).reset_index(drop=True)
    return X, y