"""
Tests for src/features/build_features.py

Turns the observation table into a model-ready feature matrix X and label y,
with a single switch that adds or removes the NETWORK features. That switch is
the whole experiment: same model, same data, with and without knowledge of
the trains around it.

Run:   pytest tests/test_features.py -v

==============================================================================
THE RULE THAT MATTERS MOST — NO PEEKING AT THE FUTURE
==============================================================================

Every feature for a train leaving station A must be knowable AT THE MOMENT it
leaves A. So when you look at "other trains", you may only use trains that
left A STRICTLY EARLIER. Using a train that left later is leakage: the model
looks brilliant in testing and is worthless in reality. Several tests below
exist only to catch this.

==============================================================================
WHAT YOU IMPLEMENT
==============================================================================

BASE = ["booked_srt_min", "length_km", "dep_delay_min", "step_seq",
        "hour", "dow", "is_premium"]
NET  = ["headway_prev_min", "prev_train_delay", "prev_train_premium",
        "n_prev_30"]

corridor_km(routes, reference_train) -> dict
    From the TIMETABLE routes table (routes.csv from build_graph), walk the
    reference train's steps in step_seq order and return
    {station_code: km from that train's origin}. Origin is 0.0.
    Gives every station on the line a position, so direction can be judged.

add_time_features(obs) -> DataFrame
    Adds, from dep_time (ISO, +05:30 offset — use LOCAL time):
        hour        0..23
        dow         0=Monday .. 6=Sunday
        is_premium  1 if train_category == "Premium" else 0

add_direction(obs, km) -> DataFrame
    Adds direction = sign(km[to_station] - km[from_station]):  +1.0 or -1.0.
    NaN if either station is missing from km (off the reference line).

add_network_features(obs, window_min=30, max_headway_min=180) -> DataFrame
    For each row, look at OTHER trains (different train_no) that departed the
    SAME from_station in the SAME direction STRICTLY EARLIER (by dep_time):
        headway_prev_min    minutes since the most recent such departure
        prev_train_delay    that train's dep_delay_min
        prev_train_premium  1.0 if that train is Premium else 0.0
        n_prev_30           how many such departures in the last window_min
    If the most recent one is more than max_headway_min ago, treat it as "no
    train ahead": the three prev_* features are NaN (n_prev_30 still counts).
    If direction is NaN, ALL four are NaN.
    Compare absolute timestamps, never run_date — trains cross midnight.

build_features(obs, km, include_network=True) -> (X, y)
    Runs the three add_* steps, returns
        X  numeric DataFrame, columns exactly BASE (+ NET if include_network)
        y  obs["minutes_lost"] as float
    NaN is allowed in X — LightGBM handles missing values natively.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.build_features import (
    BASE, NET, corridor_km, add_time_features, add_direction,
    add_network_features, build_features,
)

KM = {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}


def row(train, cat, frm, to, dep, delay=0, lost=0, run="2026-09-18"):
    return dict(train_no=train, train_category=cat, run_date=run, step_seq=0,
                from_station=frm, to_station=to, booked_srt_min=40,
                actual_srt_min=40 + lost, minutes_lost=lost, length_km=50.0,
                dep_delay_min=delay, dep_time=dep, arr_time=dep)


@pytest.fixture
def obs():
    T = "2026-09-18T{}:00+05:30"
    return pd.DataFrame([
        row("11111", "Express", "AAA", "BBB", T.format("10:00"), delay=5, lost=2),
        row("22222", "Premium", "AAA", "BBB", T.format("10:20"), delay=12, lost=-3),
        row("33333", "Express", "AAA", "BBB", T.format("10:40"), delay=0, lost=7),
        row("44444", "Express", "AAA", "BBB", T.format("14:00"), delay=3, lost=1),
        row("55555", "Express", "BBB", "AAA", T.format("10:30"), delay=9, lost=4),
        row("66666", "Express", "XXX", "YYY", T.format("10:35"), delay=1, lost=0),
    ])


def get(df, train):
    return df[df.train_no == train].iloc[0]


# ---------------------------------------------------------------- corridor_km

def test_corridor_km_accumulates_along_reference():
    routes = pd.DataFrame([
        dict(train_no="19019", step_seq=0, from_station="AAA", to_station="BBB",
             booked_srt_min=40, length_km=50.0),
        dict(train_no="19019", step_seq=1, from_station="BBB", to_station="CCC",
             booked_srt_min=60, length_km=70.0),
        dict(train_no="99999", step_seq=0, from_station="ZZZ", to_station="AAA",
             booked_srt_min=10, length_km=9.0),
    ])
    assert corridor_km(routes, "19019") == {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}


def test_corridor_km_respects_step_order():
    routes = pd.DataFrame([
        dict(train_no="19019", step_seq=1, from_station="BBB", to_station="CCC",
             booked_srt_min=60, length_km=70.0),
        dict(train_no="19019", step_seq=0, from_station="AAA", to_station="BBB",
             booked_srt_min=40, length_km=50.0),
    ])
    assert corridor_km(routes, "19019")["CCC"] == pytest.approx(120.0)


# ---------------------------------------------------------------- time

def test_time_features_use_local_time(obs):
    """10:00 at +05:30 is hour 10, not 04:30 UTC."""
    df = add_time_features(obs)
    assert get(df, "11111").hour == 10


def test_time_features_day_of_week(obs):
    """18 September 2026 is a Friday -> 4."""
    assert get(add_time_features(obs), "11111").dow == 4


def test_is_premium(obs):
    df = add_time_features(obs)
    assert get(df, "22222").is_premium == 1
    assert get(df, "11111").is_premium == 0


# ---------------------------------------------------------------- direction

def test_direction_forward_and_back(obs):
    df = add_direction(obs, KM)
    assert get(df, "11111").direction == 1.0
    assert get(df, "55555").direction == -1.0


def test_direction_unknown_off_line(obs):
    assert np.isnan(get(add_direction(obs, KM), "66666").direction)


# ---------------------------------------------------------------- network

def net(obs):
    return add_network_features(add_direction(add_time_features(obs), KM))


def test_first_train_has_no_train_ahead(obs):
    r = get(net(obs), "11111")
    assert np.isnan(r.headway_prev_min)
    assert np.isnan(r.prev_train_delay)
    assert np.isnan(r.prev_train_premium)
    assert r.n_prev_30 == 0


def test_headway_and_prev_train(obs):
    """33333 leaves AAA at 10:40; the train ahead is 22222 at 10:20."""
    r = get(net(obs), "33333")
    assert r.headway_prev_min == pytest.approx(20.0)
    assert r.prev_train_delay == 12
    assert r.prev_train_premium == 1.0


def test_n_prev_30_counts_only_the_window(obs):
    """For 33333 at 10:40 the window is [10:10, 10:40): only 22222. Not 11111."""
    assert get(net(obs), "33333").n_prev_30 == 1


def test_no_leakage_from_later_trains(obs):
    """
    11111 leaves first. 22222 and 33333 leave AFTER it and must have zero
    influence on its features. If this fails, the model is seeing the future.
    """
    r = get(net(obs), "11111")
    assert np.isnan(r.headway_prev_min) and r.n_prev_30 == 0


def test_no_leakage_simultaneous_departure():
    """A train leaving at the exact same minute is not 'ahead'. Strictly earlier."""
    T = "2026-09-18T{}:00+05:30"
    o = pd.DataFrame([
        row("11111", "Express", "AAA", "BBB", T.format("10:00"), delay=5),
        row("22222", "Express", "AAA", "BBB", T.format("10:00"), delay=9),
    ])
    r = get(net(o), "22222")
    assert np.isnan(r.headway_prev_min) and r.n_prev_30 == 0


def test_train_ahead_too_far_counts_as_none(obs):
    """44444 at 14:00: last departure 10:40 is 200 min back, over the 180 cap."""
    r = get(net(obs), "44444")
    assert np.isnan(r.headway_prev_min)
    assert np.isnan(r.prev_train_delay)


def test_opposite_direction_is_ignored(obs):
    """55555 goes BBB->AAA. Nothing else leaves BBB that way, so nothing ahead."""
    r = get(net(obs), "55555")
    assert np.isnan(r.headway_prev_min)
    assert r.n_prev_30 == 0


def test_unknown_direction_gives_all_nan(obs):
    r = get(net(obs), "66666")
    for c in NET:
        assert np.isnan(r[c]), c


def test_crosses_midnight_uses_timestamps_not_run_date():
    """
    Two trains with different run_dates, 20 minutes apart across midnight.
    The later one must see the earlier one as its train ahead.
    """
    o = pd.DataFrame([
        row("11111", "Express", "AAA", "BBB", "2026-09-18T23:50:00+05:30",
            delay=6, run="2026-09-18"),
        row("22222", "Express", "AAA", "BBB", "2026-09-19T00:10:00+05:30",
            delay=2, run="2026-09-19"),
    ])
    r = get(net(o), "22222")
    assert r.headway_prev_min == pytest.approx(20.0)
    assert r.prev_train_delay == 6


def test_same_train_is_never_its_own_train_ahead():
    T = "2026-09-18T{}:00+05:30"
    o = pd.DataFrame([
        row("11111", "Express", "AAA", "BBB", T.format("10:00"), delay=5),
        row("11111", "Express", "AAA", "BBB", T.format("10:10"), delay=5),
    ])
    assert np.isnan(get(net(o).iloc[[1]], "11111").headway_prev_min)


# ---------------------------------------------------------------- build_features

def test_build_without_network_has_base_only(obs):
    X, y = build_features(obs, KM, include_network=False)
    assert list(X.columns) == BASE


def test_build_with_network_adds_net(obs):
    X, y = build_features(obs, KM, include_network=True)
    assert list(X.columns) == BASE + NET


def test_build_label_is_minutes_lost(obs):
    X, y = build_features(obs, KM)
    assert y.tolist() == [2.0, -3.0, 7.0, 1.0, 4.0, 0.0]


def test_build_is_numeric(obs):
    X, _ = build_features(obs, KM)
    assert all(np.issubdtype(t, np.number) for t in X.dtypes)


def test_build_keeps_row_count_and_order(obs):
    X, y = build_features(obs, KM)
    assert len(X) == len(y) == len(obs)


def test_label_is_not_a_feature(obs):
    """The answer must never sneak into the inputs."""
    X, _ = build_features(obs, KM)
    for leak in ("minutes_lost", "actual_srt_min", "arr_time"):
        assert leak not in X.columns
