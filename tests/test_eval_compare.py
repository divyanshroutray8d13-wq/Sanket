"""
Tests for src/eval/compare.py

Run:   pytest tests/test_eval_compare.py -v
"""

import pandas as pd
import pytest

from src.eval.compare import compare_all, paired_bootstrap, verdict
from src.eval.metrics import PRED_COLUMNS


def _frame(p50_offset, ys=(0, 5, -3, 12, 7, -1), trains=("12951", "12951", "12953", "12953", "12909", "12909")):
    rows = [
        [t, "2026-09-19", i, "ST", "BRC", y, y + p50_offset - 8, y + p50_offset, y + p50_offset + 8]
        for i, (t, y) in enumerate(zip(trains, ys))
    ]
    df = pd.DataFrame(rows, columns=PRED_COLUMNS)
    df["train_no"] = df["train_no"].str.zfill(5)
    return df


def test_identical_predictions_are_not_distinguishable():
    r = paired_bootstrap(_frame(2), _frame(2))
    assert r["gain"] == 0
    assert r["lo"] <= 0 <= r["hi"]
    assert verdict(r) == "not distinguishable from"


def test_consistently_better_is_a_clear_win():
    r = paired_bootstrap(_frame(0), _frame(5))  # a exact, b always 5 min off
    assert r["gain"] == pytest.approx(5)
    assert r["lo"] == pytest.approx(5) and r["hi"] == pytest.approx(5)
    assert r["share_a_better"] == 1.0
    assert verdict(r) == "clearly better than"


def test_worse_is_a_clear_loss():
    r = paired_bootstrap(_frame(5), _frame(0))
    assert verdict(r) == "clearly worse than"


def test_counts_train_runs_not_rows():
    r = paired_bootstrap(_frame(0), _frame(5))
    assert r["n_rows"] == 6
    assert r["n_train_runs"] == 3


def test_uses_only_shared_rows():
    r = paired_bootstrap(_frame(0), _frame(5).iloc[:4])
    assert r["n_rows"] == 4


def test_same_seed_same_answer():
    noisy = _frame(0)
    noisy["p50"] = noisy["p50"] + [3, -1, 4, 0, -2, 6]
    assert paired_bootstrap(noisy, _frame(2)) == paired_bootstrap(noisy, _frame(2))


def test_one_train_run_is_not_enough():
    one = dict(trains=("12951",) * 6)
    with pytest.raises(ValueError, match="at least 2 train runs"):
        paired_bootstrap(_frame(0, **one), _frame(5, **one))


def test_compare_all_asks_the_ablation_questions(tmp_path):
    for name, off in [("baseline_zero", 9), ("baseline_section", 7), ("model_base", 4), ("model_network", 1)]:
        _frame(off).to_csv(tmp_path / f"{name}.csv", index=False)
    res = compare_all(tmp_path)
    assert list(res["question"]) == [
        "Do network features help?",
        "model_network vs the best baseline",
        "model_base vs the best baseline",
    ]
    assert set(res["b"][1:]) == {"baseline_section"}  # best baseline = lowest MAE
