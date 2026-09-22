import pandas as pd
from pathlib import Path
from src.eval.split import time_split, attach_corridor, corridor_holdout_split

obs = pd.read_csv("data/processed/observations.csv", dtype={"train_no": str})

train_mask, test_mask = time_split(obs)
print("train rows:", train_mask.sum(), "test rows:", test_mask.sum())
print("test date:", obs.loc[test_mask, "run_date"].unique())

obs = attach_corridor(obs, Path("data/processed"))
print(obs["corridor"].value_counts(dropna=False))