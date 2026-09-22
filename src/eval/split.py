import pandas as pd
from pathlib import Path

def time_split(obs: pd.DataFrame):
    latest_date = obs["run_date"].max()
    test_mask = obs["run_date"] == latest_date
    train_mask = ~test_mask
    return train_mask, test_mask

def attach_corridor(obs: pd.DataFrame, lists_dir: Path) -> pd.DataFrame:
    obs = obs.copy()
    obs["train_no"] = obs["train_no"].astype(str).str.zfill(5)
    corridor_map = {}
    for f in Path(lists_dir).glob("corridor_*trains.txt"):
        if f.name == "corridor_trains.txt":
            name = "mumbai"
        else:
            name = f.stem.replace("corridor_", "").replace("_trains", "")
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                corridor_map[line.zfill(5)] = name
    obs["corridor"] = obs["train_no"].map(corridor_map)
    return obs

def corridor_holdout_split(obs: pd.DataFrame, holdout: str):
    test_mask = obs["corridor"] == holdout
    train_mask = ~test_mask
    return train_mask, test_mask