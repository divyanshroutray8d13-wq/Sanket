import pandas as pd
from src.eval.baselines import baseline_zero, baseline_section

def test_baseline_zero_p50_is_zero():
    train = pd.DataFrame({"minutes_lost": [1, 2, 3, -1, 0]})
    test = pd.DataFrame({
        "train_no": ["12345"], "run_date": ["2026-09-20"], "step_seq": [0],
        "from_station": ["A"], "to_station": ["B"], "minutes_lost": [5],
    })
    result = baseline_zero(train, test)
    assert (result["p50"] == 0).all()
    assert result["y_true"].iloc[0] == 5

def test_baseline_section_uses_section_mean():
    train = pd.DataFrame({
        "from_station": ["A", "A", "B"],
        "to_station": ["B", "B", "C"],
        "minutes_lost": [2, 4, 100],   # A->B mean = 3, B->C mean = 100
    })
    test = pd.DataFrame({
        "train_no": ["1"], "run_date": ["2026-09-20"], "step_seq": [0],
        "from_station": ["A"], "to_station": ["B"], "minutes_lost": [999],
    })
    result = baseline_section(train, test)
    assert result["p50"].iloc[0] == 3

def test_baseline_section_falls_back_to_overall_mean():
    train = pd.DataFrame({
        "from_station": ["A"], "to_station": ["B"], "minutes_lost": [10],
    })
    test = pd.DataFrame({
        "train_no": ["1"], "run_date": ["2026-09-20"], "step_seq": [0],
        "from_station": ["X"], "to_station": ["Y"], "minutes_lost": [0],  # never-seen section
    })
    result = baseline_section(train, test)
    assert result["p50"].iloc[0] == 10  # overall mean, since X->Y unseen in train