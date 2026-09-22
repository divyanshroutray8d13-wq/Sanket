import pandas as pd
from pathlib import Path
from src.eval.split import time_split
from src.eval.baselines import baseline_zero, baseline_section

obs = pd.read_csv("data/processed/observations.csv", dtype={"train_no": str})
train_mask, test_mask = time_split(obs)
train, test = obs[train_mask], obs[test_mask]

out_dir = Path("data/processed/predictions")
out_dir.mkdir(parents=True, exist_ok=True)

baseline_zero(train, test).to_csv(out_dir / "baseline_zero.csv", index=False)
baseline_section(train, test).to_csv(out_dir / "baseline_section.csv", index=False)