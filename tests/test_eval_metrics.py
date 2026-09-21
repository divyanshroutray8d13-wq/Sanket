"""
Tests for src/eval/metrics.py

Run:   pytest tests/test_eval_metrics.py -v

These pin down what each number means, so the ablation table can be trusted.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from src.eval.metrics import PRED_COLUMNS, ablation_table, evaluate, load_predictions


# ---------------------------------------------------------------- evaluate()

def test_coverage_is_one_when_every_value_is_inside():
    y = [0, 5, -3]
    r = evaluate(y, p10=[-10, -10, -10], p50=[0, 0, 0], p90=[10, 10, 10])
    assert r["coverage"] == 1.0


def test_coverage_is_zero_when_no_value_is_inside():
    y = [50, -50, 30]
    r = evaluate(y, p10=[-10, -10, -10], p50=[0, 0, 0], p90=[10, 10, 10])
    assert r["coverage"] == 0.0


def test_interval_edges_count_as_inside():
    r = evaluate([-10, 10], p10=[-10, -10], p50=[0, 0], p90=[10, 10])
    assert r["coverage"] == 1.0


def test_mae_is_zero_when_p50_is_exact():
    y = [3, -7, 12]
    r = evaluate(y, p10=[0, -9, 10], p50=y, p90=[5, -5, 14])
    assert r["mae"] == 0.0
    assert r["rmse"] == 0.0
    assert r["bias"] == 0.0


def test_known_values_including_negative_minutes():
    # errors (p50 - y): +2, -4  ->  mae 3, rmse sqrt(10), bias -1
    r = evaluate([-5, 8], p10=[-9, 0], p50=[-3, 4], p90=[0, 10])
    assert r["n"] == 2
    assert r["mae"] == pytest.approx(3.0)
    assert r["rmse"] == pytest.approx(np.sqrt(10))
    assert r["bias"] == pytest.approx(-1.0)
    assert r["mean_width"] == pytest.approx((9 + 10) / 2)


def test_crossing_rate_flags_out_of_order_quantiles():
    # second row has p10 above p50
    r = evaluate([0, 0], p10=[-5, 3], p50=[0, 1], p90=[5, 6])
    assert r["crossing_rate"] == 0.5


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        evaluate([1, 2], p10=[0], p50=[1, 2], p90=[3, 4])


def test_missing_values_raise():
    with pytest.raises(ValueError):
        evaluate([1, np.nan], p10=[0, 0], p50=[1, 1], p90=[2, 2])


def test_empty_input_raises():
    with pytest.raises(ValueError):
        evaluate([], p10=[], p50=[], p90=[])


# ------------------------------------------------- files and ablation_table()

def _write(path, rows):
    pd.DataFrame(rows, columns=PRED_COLUMNS).to_csv(path, index=False)


def _rows(p50s, ys=(0, 0, 0)):
    return [
        ["12951", "2026-09-19", i, "ST", "BRC", y, p - 5, p, p + 5]
        for i, (y, p) in enumerate(zip(ys, p50s))
    ]


def test_ablation_table_one_row_per_file_best_first(tmp_path):
    _write(tmp_path / "bad.csv", _rows([10, 10, 10]))
    _write(tmp_path / "good.csv", _rows([1, 1, 1]))
    _write(tmp_path / "mid.csv", _rows([5, 5, 5]))

    table = ablation_table(tmp_path)

    assert list(table["experiment"]) == ["good", "mid", "bad"]
    assert list(table["mae"]) == [1.0, 5.0, 10.0]
    assert (table["n"] == 3).all()


def test_ablation_table_warns_when_rows_differ(tmp_path):
    _write(tmp_path / "a.csv", _rows([1, 1, 1]))
    _write(tmp_path / "b.csv", _rows([1, 1]))  # one row short
    with pytest.warns(UserWarning, match="different rows"):
        ablation_table(tmp_path)


def test_ablation_table_silent_when_rows_match(tmp_path):
    _write(tmp_path / "a.csv", _rows([1, 1, 1]))
    _write(tmp_path / "b.csv", _rows([2, 2, 2]))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ablation_table(tmp_path)


def test_misaligned_truth_is_caught(tmp_path):
    _write(tmp_path / "a.csv", _rows([1, 1, 1], ys=(0, 5, 9)))
    _write(tmp_path / "b.csv", _rows([1, 1, 1], ys=(0, 9, 5)))  # rows 1 and 2 swapped
    with pytest.raises(ValueError, match="disagree on y_true"):
        ablation_table(tmp_path)


def test_matching_truth_passes(tmp_path):
    _write(tmp_path / "a.csv", _rows([1, 1, 1], ys=(0, 5, 9)))
    _write(tmp_path / "b.csv", _rows([4, 4, 4], ys=(0, 5, 9)))
    assert len(ablation_table(tmp_path)) == 2


def test_empty_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ablation_table(tmp_path)


def test_missing_column_raises(tmp_path):
    pd.DataFrame(_rows([1, 1, 1]), columns=PRED_COLUMNS).drop(columns="p90").to_csv(
        tmp_path / "broken.csv", index=False
    )
    with pytest.raises(ValueError, match="p90"):
        load_predictions(tmp_path / "broken.csv")


def test_duplicate_rows_raise(tmp_path):
    rows = _rows([1, 1, 1])
    rows[1][2] = 0  # same step_seq twice
    _write(tmp_path / "dup.csv", rows)
    with pytest.raises(ValueError, match="duplicate"):
        load_predictions(tmp_path / "dup.csv")


def test_train_numbers_padded_to_five_digits(tmp_path):
    rows = _rows([1, 1, 1])
    rows[0][0] = "2951"
    _write(tmp_path / "short.csv", rows)
    assert load_predictions(tmp_path / "short.csv")["train_no"].iloc[0] == "02951"
