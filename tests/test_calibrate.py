"""
Tests for src/model/calibrate.py — making the time windows honest.

THE PROBLEM
Our first real run: the 10-90 window held the true arrival 66% of the time,
not 80%. The windows are too narrow — the model is overconfident. A window
the dashboard shows as "80% sure" that is right two times in three misleads
every passenger and controller who trusts it.

THE FIX: split conformal calibration (conformalized quantile regression)
1. Hold back the LAST training day as a calibration day.
2. Train on the other training days, predict the calibration day.
3. For each calibration row, measure how far the truth fell OUTSIDE its
   window (negative if it was inside):   score = max(p10 - y, y - p90)
4. margin = the score that 80% of rows stay under (with a small-sample
   correction, below).
5. Train on ALL training days, predict the test days, and widen every window
   by the margin:  p10 - margin,  p90 + margin.
If the model was overconfident the margin is positive and windows grow; if it
was too cautious the margin is negative and they shrink. Either way coverage
moves towards 80%, and the method only ever looks at training data.

Run:   pytest tests/test_calibrate.py -v

==============================================================================
WHAT YOU IMPLEMENT  (src/model/calibrate.py)
==============================================================================

conformal_margin(y, p10, p90, target=0.8) -> float
    scores = max(p10 - y, y - p90), element-wise
    n = number of rows;  k = ceil((n + 1) * target), capped at n
    return the k-th smallest score (1-based), as a float
    Raise ValueError if there are no rows.
    The "+1" is the small-sample correction that makes the guarantee hold.

widen(preds, margin) -> DataFrame
    Copy of preds with p10 - margin and p90 + margin.
    A negative margin narrows — but never past p50: clip so that
    p10 <= p50 <= p90 still holds on every row. p50 never changes.

calibration_split(obs, train_mask) -> (proper_mask, cal_mask)
    cal = training rows from the LATEST training date.
    proper = all other training rows.
    Raise ValueError if the training rows cover fewer than two dates.

run_calibrated_experiment(obs, km, train_mask, test_mask, include_network,
                          departures=None, seed=0, target=0.8)
        -> (DataFrame, margin)
    Same output columns as run_experiment (PRED_COLS). Steps 1-5 above.
    Build features ONCE on the whole table (same reason as run_experiment).
    Raise ValueError if train and test overlap.
"""

import numpy as np
import pandas as pd
import pytest

from src.model.calibrate import (
    conformal_margin, widen, calibration_split, run_calibrated_experiment,
)
from src.model.train import PRED_COLS

KM = {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}


# ---------------------------------------------------------------- conformal_margin

def test_margin_all_inside_is_negative():
    """Every truth sits 2 min inside its window -> margin -2 (windows can shrink)."""
    y = np.zeros(10)
    assert conformal_margin(y, y - 2, y + 2) == pytest.approx(-2.0)


def test_margin_uses_the_right_rank():
    """
    Scores 1..9 (truth 1..9 min above p90). n=9, k=ceil(10*0.8)=8 -> 8th
    smallest = 8.
    """
    y = np.arange(1, 10, dtype=float)
    zeros = np.zeros(9)
    assert conformal_margin(y, zeros, zeros) == pytest.approx(8.0)


def test_margin_counts_misses_below_too():
    """Truth below p10 counts the same as truth above p90."""
    y = np.array([-5.0, 5.0])
    zeros = np.zeros(2)
    assert conformal_margin(y, zeros, zeros, target=0.5) == pytest.approx(5.0)


def test_margin_rank_capped_for_tiny_samples():
    """n=2, target 0.9: ceil(3*0.9)=3 > n -> use the largest score, don't crash."""
    y = np.array([1.0, 3.0])
    zeros = np.zeros(2)
    assert conformal_margin(y, zeros, zeros, target=0.9) == pytest.approx(3.0)


def test_margin_empty_raises():
    with pytest.raises(ValueError):
        conformal_margin([], [], [])


# ---------------------------------------------------------------- widen

def preds():
    return pd.DataFrame({"p10": [-4.0, 0.0], "p50": [0.0, 1.0], "p90": [4.0, 2.0]})


def test_widen_positive():
    out = widen(preds(), 3.0)
    assert out.p10.tolist() == [-7.0, -3.0]
    assert out.p90.tolist() == [7.0, 5.0]


def test_widen_never_touches_p50():
    assert widen(preds(), 3.0).p50.tolist() == [0.0, 1.0]


def test_negative_margin_never_crosses_p50():
    """A -3 margin would put row 2's p10 at 3 > p50 = 1. Clip to p50."""
    out = widen(preds(), -3.0)
    assert (out.p10 <= out.p50).all() and (out.p50 <= out.p90).all()
    assert out.p10.tolist() == [-1.0, 1.0]
    assert out.p90.tolist() == [1.0, 1.0]


def test_widen_does_not_modify_input():
    p = preds()
    widen(p, 3.0)
    assert p.p10.tolist() == [-4.0, 0.0]


# ---------------------------------------------------------------- calibration_split

def dated(dates):
    return pd.DataFrame({"run_date": dates})


def test_split_holds_back_latest_training_day():
    o = dated(["2026-09-17", "2026-09-18", "2026-09-18", "2026-09-19"])
    train = np.array([True, True, True, False])
    proper, cal = calibration_split(o, train)
    assert proper.tolist() == [True, False, False, False]
    assert cal.tolist() == [False, True, True, False]


def test_split_never_uses_test_rows():
    o = dated(["2026-09-17", "2026-09-18", "2026-09-19"])
    train = np.array([True, True, False])
    proper, cal = calibration_split(o, train)
    assert not proper[2] and not cal[2]


def test_split_needs_two_training_dates():
    o = dated(["2026-09-17", "2026-09-17", "2026-09-19"])
    with pytest.raises(ValueError):
        calibration_split(o, np.array([True, True, False]))


# ---------------------------------------------------------------- end to end

def overconfident_obs(n_per_day=250, seed=3):
    """
    minutes_lost = -0.3 * delay + heavy noise. With so much noise and small
    trees, raw quantile models tend to under-cover; calibration must pull
    coverage back up.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for d, day in enumerate(["2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"]):
        for i in range(n_per_day):
            minute = int(rng.integers(0, 1440))
            delay = int(rng.integers(0, 40))
            frm, to = [("AAA", "BBB"), ("BBB", "CCC")][i % 2]
            rows.append(dict(
                train_no=f"{d}{i:04d}", train_category="Express", run_date=day,
                step_seq=i % 7, from_station=frm, to_station=to,
                booked_srt_min=40, actual_srt_min=40,
                minutes_lost=float(round(-0.3 * delay + rng.standard_t(3) * 6)),
                length_km=50.0, dep_delay_min=delay,
                dep_time=f"{day}T{minute // 60:02d}:{minute % 60:02d}:00+05:30",
                arr_time=f"{day}T{minute // 60:02d}:{minute % 60:02d}:00+05:30"))
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def run():
    obs = overconfident_obs()
    test = (obs.run_date == "2026-09-20").to_numpy()
    out, margin = run_calibrated_experiment(obs, KM, ~test, test, include_network=False)
    return obs, test, out, margin


def test_output_contract(run):
    obs, test, out, _ = run
    assert list(out.columns) == PRED_COLS
    assert len(out) == test.sum()


def test_margin_is_a_number(run):
    assert np.isfinite(run[3])


def test_calibrated_coverage_near_target(run):
    """Calibrated 10-90 windows should hold the truth close to 80% of the time."""
    _, _, out, _ = run
    cover = ((out.y_true >= out.p10) & (out.y_true <= out.p90)).mean()
    assert 0.70 <= cover <= 0.90


def test_no_crossing_after_calibration(run):
    _, _, out, _ = run
    assert (out.p10 <= out.p50).all() and (out.p50 <= out.p90).all()


def test_overlap_rejected():
    obs = overconfident_obs(n_per_day=30)
    both = np.ones(len(obs), dtype=bool)
    with pytest.raises(ValueError):
        run_calibrated_experiment(obs, KM, both, both, include_network=False)
