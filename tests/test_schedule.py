import numpy as np
import pandas as pd
import pytest

from src.features.schedule import (
    SCHED, timetable_departures, scheduled_tod, add_schedule_density,
)
from src.features.build_features import BASE, NET, add_direction, build_features

KM = {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}


def stop(train, seq, station, arr, dep):
    return dict(train_no=train, stop_seq=seq, station_code=station,
                arr_min=arr, dep_min=dep)


@pytest.fixture
def sched():
    return pd.DataFrame([
        stop("1001", 1, "AAA", np.nan, 600),     # 10:00 AAA -> BBB (+1)
        stop("1001", 2, "BBB", 640, 645),        # 10:45 BBB -> CCC (+1)
        stop("1001", 3, "CCC", 720, np.nan),     # terminus
        stop("2002", 1, "CCC", np.nan, 590),     # CCC -> BBB (-1)
        stop("2002", 2, "BBB", 645, 650),        # BBB -> AAA (-1)
        stop("2002", 3, "AAA", 700, np.nan),
        stop("3003", 1, "AAA", np.nan, 1430),    # AAA -> XXX, off the line
        stop("3003", 2, "XXX", 1480, np.nan),
        stop("4004", 1, "AAA", np.nan, 1450),    # day 2, 00:10
        stop("4004", 2, "BBB", 1500, np.nan),
    ])


def dep(train, station, tod, direction):
    return dict(train_no=train, station=station, dep_tod=tod,
                direction=direction)


def obs_row(train, frm, to, dep_time, delay):
    return dict(train_no=train, train_category="Express",
                run_date="2026-09-18", step_seq=0, from_station=frm,
                to_station=to, booked_srt_min=40, actual_srt_min=40,
                minutes_lost=0, length_km=50.0, dep_delay_min=delay,
                dep_time=dep_time, arr_time=dep_time)


# ------------------------------------------------------ timetable_departures

def test_departures_columns(sched):
    d = timetable_departures(sched, KM)
    assert list(d.columns) == ["train_no", "station", "dep_tod", "direction"]


def test_departures_pads_train_numbers(sched):
    assert "01001" in set(timetable_departures(sched, KM).train_no)


def test_departures_rows(sched):
    d = timetable_departures(sched, KM)
    got = set(zip(d.train_no, d.station, d.dep_tod, d.direction))
    assert got == {
        ("01001", "AAA", 600, 1.0), ("01001", "BBB", 645, 1.0),
        ("02002", "CCC", 590, -1.0), ("02002", "BBB", 650, -1.0),
        ("04004", "AAA", 10, 1.0),
    }


def test_departures_wraps_day_two_to_time_of_day(sched):
    d = timetable_departures(sched, KM)
    assert d[d.train_no == "04004"].dep_tod.iloc[0] == 10


def test_departures_drops_off_line_and_terminus(sched):
    d = timetable_departures(sched, KM)
    assert "03003" not in set(d.train_no)
    assert not ((d.train_no == "01001") & (d.station == "CCC")).any()


# ------------------------------------------------------ scheduled_tod

def test_scheduled_tod_subtracts_delay():
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T10:05:00+05:30", 5)])
    assert scheduled_tod(o).iloc[0] == 600


def test_scheduled_tod_is_local_time():
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T00:20:00+05:30", 0)])
    assert scheduled_tod(o).iloc[0] == 20


# ------------------------------------------------------ add_schedule_density

@pytest.fixture
def deps():
    return pd.DataFrame([
        dep("11111", "AAA", 580, 1.0),   # 09:40  -20
        dep("22222", "AAA", 590, 1.0),   # 09:50  -10
        dep("33333", "AAA", 600, 1.0),   # 10:00    0  -> neither
        dep("44444", "AAA", 615, 1.0),   # 10:15  +15
        dep("55555", "AAA", 640, 1.0),   # 10:40  +40  -> outside
        dep("66666", "AAA", 595, -1.0),  # opposite direction
        dep("77777", "BBB", 598, 1.0),   # other station
    ])


def density(obs, deps):
    return add_schedule_density(add_direction(obs, KM), deps)


def test_counts_before_and_after(deps):
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T10:05:00+05:30", 5)])
    r = density(o, deps).iloc[0]
    assert r.sched_before_30 == 2
    assert r.sched_after_30 == 1


def test_uses_scheduled_not_actual_time(deps):
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T10:05:00+05:30", 5)])
    assert density(o, deps).iloc[0].sched_before_30 == 2


def test_ignores_own_train(deps):
    extra = pd.concat([deps, pd.DataFrame([dep("99999", "AAA", 590, 1.0)])],
                      ignore_index=True)
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T10:05:00+05:30", 5)])
    assert density(o, extra).iloc[0].sched_before_30 == 2


def test_wraps_around_midnight():
    d = pd.DataFrame([dep("11111", "AAA", 1430, 1.0),
                      dep("22222", "AAA", 5, 1.0),
                      dep("33333", "AAA", 30, 1.0)])
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-19T00:10:00+05:30", 0)])
    r = density(o, d).iloc[0]
    assert r.sched_before_30 == 2
    assert r.sched_after_30 == 1


def test_unknown_direction_is_nan(deps):
    o = pd.DataFrame([obs_row("99999", "XXX", "YYY",
                              "2026-09-18T10:05:00+05:30", 5)])
    r = density(o, deps).iloc[0]
    assert np.isnan(r.sched_before_30) and np.isnan(r.sched_after_30)


def test_empty_slot_counts_zero(deps):
    o = pd.DataFrame([obs_row("99999", "AAA", "BBB",
                              "2026-09-18T03:00:00+05:30", 0)])
    r = density(o, deps).iloc[0]
    assert r.sched_before_30 == 0 and r.sched_after_30 == 0


# ------------------------------------------------------ build_features

def _obs():
    return pd.DataFrame([obs_row("99999", "AAA", "BBB",
                                 "2026-09-18T10:05:00+05:30", 5)])


def test_build_with_departures_adds_sched(deps):
    X, _ = build_features(_obs(), KM, include_network=True, departures=deps)
    assert list(X.columns) == BASE + NET + SCHED


def test_build_without_departures_unchanged():
    X, _ = build_features(_obs(), KM, include_network=True)
    assert list(X.columns) == BASE + NET


def test_build_base_only_ignores_departures(deps):
    X, _ = build_features(_obs(), KM, include_network=False, departures=deps)
    assert list(X.columns) == BASE


def test_station_without_schedule_is_nan_not_zero(deps):
    o = pd.DataFrame([obs_row("99999", "CCC", "BBB",
                              "2026-09-18T10:05:00+05:30", 5)])
    r = density(o, deps).iloc[0]
    assert np.isnan(r.sched_before_30) and np.isnan(r.sched_after_30)