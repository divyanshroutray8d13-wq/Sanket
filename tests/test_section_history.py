"""Spec for src/features/history.py -> add_section_history(obs, train_mask, min_count=3).

For every row it adds two columns:
  sec_hist_n    = how many TRAINING rows exist on the same section (from, to),
                  NOT counting rows from the row's own run (train_no, run_date)
  sec_hist_mean = mean minutes_lost of those rows, or NaN if sec_hist_n < min_count

Leakage rules:
  - only rows where train_mask is True feed the statistics (test rows never do)
  - a training row never sees its own run (leave-one-run-out), otherwise the
    model learns "sec_hist_mean already contains my answer"
Set SEC_KEYS in history.py to your real section column names.
"""
import numpy as np
import pandas as pd
import pytest

from src.features.history import add_section_history, SEC_KEYS, HIST

A, B, C = "AAA", "BBB", "CCC"


def make(rows):
    # rows: (from, to, train_no, run_date, minutes_lost)
    return pd.DataFrame(
        [{SEC_KEYS[0]: f, SEC_KEYS[1]: t, "train_no": n, "run_date": d, "minutes_lost": y}
         for f, t, n, d, y in rows]
    )


@pytest.fixture
def obs():
    return make([
        (A, B, "1", "d1", 2.0),   # 0 train
        (A, B, "2", "d1", 4.0),   # 1 train
        (A, B, "3", "d2", 6.0),   # 2 train
        (A, B, "4", "d2", 8.0),   # 3 train
        (A, B, "5", "d3", 100.0), # 4 test
        (B, C, "1", "d1", -3.0),  # 5 train
        (B, C, "5", "d3", 50.0),  # 6 test
    ])


TRAIN = np.array([1, 1, 1, 1, 0, 1, 0], dtype=bool)


def test_adds_both_columns(obs):
    out = add_section_history(obs, TRAIN)
    for col in HIST:
        assert col in out.columns
    assert HIST == ["sec_hist_mean", "sec_hist_n"]


def test_same_length_and_order(obs):
    out = add_section_history(obs, TRAIN)
    assert len(out) == len(obs)
    assert list(out["minutes_lost"]) == list(obs["minutes_lost"])


def test_does_not_mutate_input(obs):
    before = obs.copy()
    add_section_history(obs, TRAIN)
    pd.testing.assert_frame_equal(obs, before)


def test_test_row_gets_mean_of_all_training_rows(obs):
    out = add_section_history(obs, TRAIN)
    assert out.loc[4, "sec_hist_n"] == 4
    assert out.loc[4, "sec_hist_mean"] == pytest.approx(5.0)   # (2+4+6+8)/4


def test_training_row_excludes_its_own_run(obs):
    out = add_section_history(obs, TRAIN)
    assert out.loc[0, "sec_hist_n"] == 3
    assert out.loc[0, "sec_hist_mean"] == pytest.approx(6.0)   # (4+6+8)/3
    assert out.loc[3, "sec_hist_mean"] == pytest.approx(4.0)   # (2+4+6)/3


def test_test_targets_never_leak(obs):
    a = add_section_history(obs, TRAIN)
    changed = obs.copy()
    changed.loc[[4, 6], "minutes_lost"] = -999.0
    b = add_section_history(changed, TRAIN)
    pd.testing.assert_series_equal(a["sec_hist_mean"], b["sec_hist_mean"])
    pd.testing.assert_series_equal(a["sec_hist_n"], b["sec_hist_n"])


def test_below_min_count_is_nan(obs):
    out = add_section_history(obs, TRAIN)
    assert out.loc[6, "sec_hist_n"] == 1
    assert np.isnan(out.loc[6, "sec_hist_mean"])


def test_min_count_is_respected(obs):
    out = add_section_history(obs, TRAIN, min_count=1)
    assert out.loc[6, "sec_hist_mean"] == pytest.approx(-3.0)


def test_only_run_on_section_gets_zero_and_nan(obs):
    out = add_section_history(obs, TRAIN, min_count=1)
    assert out.loc[5, "sec_hist_n"] == 0
    assert np.isnan(out.loc[5, "sec_hist_mean"])


def test_unseen_section_gets_zero_and_nan(obs):
    extra = pd.concat([obs, make([(C, A, "9", "d3", 1.0)])], ignore_index=True)
    out = add_section_history(extra, np.append(TRAIN, False))
    assert out.loc[7, "sec_hist_n"] == 0
    assert np.isnan(out.loc[7, "sec_hist_mean"])


def test_direction_matters(obs):
    extra = pd.concat([obs, make([(B, A, "9", "d3", 1.0)])], ignore_index=True)
    out = add_section_history(extra, np.append(TRAIN, False))
    assert out.loc[7, "sec_hist_n"] == 0    # B->A is not A->B


def test_same_run_rows_all_excluded():
    # a run that appears twice on one section (rare, but must not leak)
    o = make([(A, B, "1", "d1", 10.0), (A, B, "1", "d1", 20.0),
              (A, B, "2", "d1", 1.0), (A, B, "3", "d1", 3.0)])
    out = add_section_history(o, np.ones(4, dtype=bool), min_count=1)
    assert out.loc[0, "sec_hist_n"] == 2
    assert out.loc[0, "sec_hist_mean"] == pytest.approx(2.0)


def test_non_default_index_is_handled(obs):
    shuffled = obs.copy()
    shuffled.index = [70, 60, 50, 40, 30, 20, 10]
    out = add_section_history(shuffled, TRAIN)
    assert out["sec_hist_mean"].iloc[4] == pytest.approx(5.0)


def test_n_is_integer(obs):
    out = add_section_history(obs, TRAIN)
    assert pd.api.types.is_integer_dtype(out["sec_hist_n"])
