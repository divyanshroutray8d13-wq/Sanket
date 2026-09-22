import pandas as pd
from src.eval.split import time_split, corridor_holdout_split, attach_corridor

def test_attach_corridor_matches_base_file(tmp_path):
    (tmp_path / "corridor_trains.txt").write_text("12345\n")
    obs = pd.DataFrame({"train_no": ["12345"]})
    result = attach_corridor(obs, tmp_path)
    assert result["corridor"].iloc[0] == "mumbai"


def test_time_split_no_leakage():
    obs = pd.DataFrame({"run_date": ["2026-09-20", "2026-09-20", "2026-09-21"]})
    train_mask, test_mask = time_split(obs)
    assert obs.loc[test_mask, "run_date"].nunique() == 1
    assert obs.loc[test_mask, "run_date"].iloc[0] == "2026-09-21"
    assert not set(obs.loc[train_mask, "run_date"]) & set(obs.loc[test_mask, "run_date"])

def test_corridor_holdout_no_leakage():
    obs = pd.DataFrame({"corridor": ["mumbai", "mumbai", "howrah"]})
    train_mask, test_mask = corridor_holdout_split(obs, "howrah")
    assert "howrah" not in set(obs.loc[train_mask, "corridor"])
    assert set(obs.loc[test_mask, "corridor"]) == {"howrah"}