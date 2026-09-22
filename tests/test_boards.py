import json

import numpy as np
import pandas as pd
import pytest

from src.features.schedule import (
    board_departures, load_boards, add_schedule_density,
)
from src.features.build_features import add_direction

KM = {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}
DAILY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def entry(number, dep, dist, day=1, run=DAILY, stop_type="intermediate"):
    return {"train": {"number": number, "runDays": run},
            "stop": {"departure": dep, "departureDay": day,
                     "distance": dist, "stopType": stop_type}}


def board(*entries, ok=True):
    return {"success": ok, "data": {"trains": list(entries)}}


@pytest.fixture
def boards():
    return {
        "AAA": board(
            entry("12951", "10:00", 0, stop_type="origin"),
            entry("33333", "11:00", 0),                      # only seen here
            entry("4419", "12:00", 5),
        ),
        "BBB": board(
            entry("12951", "10:45", 50),
            entry("12952", "10:50", 70),
            entry("22222", "00:30", 400, day=2, run=["mon"]),
            entry("4419", "12:40", 55),
        ),
        "CCC": board(
            entry("12951", None, 120, stop_type="destination"),
            entry("12952", "09:50", 0, stop_type="origin"),
            entry("22222", "01:40", 470, day=2, run=["mon"]),
        ),
        "ZZZ": board(entry("12951", "15:00", 300)),          # off the line
        "BAD": board(entry("99999", "10:00", 0), ok=False),  # failed payload
    }


def rows(df, train, station=None):
    r = df[df.train_no == train]
    return r if station is None else r[r.station == station]


# ------------------------------------------------------------ board_departures

def test_columns(boards):
    assert list(board_departures(boards, KM).columns) == \
        ["train_no", "station", "dep_tod", "direction", "days"]


def test_forward_train(boards):
    d = board_departures(boards, KM)
    assert set(rows(d, "12951").direction) == {1.0}


def test_backward_train(boards):
    d = board_departures(boards, KM)
    assert set(rows(d, "12952").direction) == {-1.0}


def test_departure_time_of_day(boards):
    d = board_departures(boards, KM)
    assert rows(d, "12951", "AAA").dep_tod.iloc[0] == 600


def test_terminating_stop_has_no_departure_row(boards):
    assert rows(board_departures(boards, KM), "12951", "CCC").empty


def test_single_station_train_dropped(boards):
    assert rows(board_departures(boards, KM), "33333").empty


def test_off_line_station_ignored(boards):
    assert "ZZZ" not in set(board_departures(boards, KM).station)


def test_failed_payload_ignored(boards):
    assert "99999" not in set(board_departures(boards, KM).train_no)


def test_train_numbers_padded(boards):
    assert "04419" in set(board_departures(boards, KM).train_no)


def test_days_shift_with_departure_day(boards):
    r = rows(board_departures(boards, KM), "22222", "BBB")
    assert r.days.iloc[0] == ("tue",)


def test_daily_train_runs_every_day(boards):
    r = rows(board_departures(boards, KM), "12951", "AAA")
    assert r.days.iloc[0] == tuple(DAILY)


# ------------------------------------------------------------ load_boards

def test_load_boards_keys_are_station_codes(tmp_path):
    (tmp_path / "KOTA.json").write_text(json.dumps(board()))
    (tmp_path / "RTM.json").write_text(json.dumps(board()))
    assert set(load_boards(tmp_path)) == {"KOTA", "RTM"}


# ------------------------------------------------------------ run-day filtering

def obs_row(dep_time, delay=0):
    return dict(train_no="99999", train_category="Express",
                run_date=dep_time[:10], step_seq=0, from_station="AAA",
                to_station="BBB", booked_srt_min=40, actual_srt_min=40,
                minutes_lost=0, length_km=50.0, dep_delay_min=delay,
                dep_time=dep_time, arr_time=dep_time)


def dep(train, tod, days, direction=1.0, station="AAA"):
    return dict(train_no=train, station=station, dep_tod=tod,
                direction=direction, days=tuple(days))


def density(obs, deps):
    return add_schedule_density(add_direction(obs, KM), deps).iloc[0]


def test_counts_only_trains_running_that_day():
    deps = pd.DataFrame([dep("11111", 590, ["fri"]),
                         dep("22222", 580, ["mon"]),
                         dep("33333", 615, DAILY)])
    r = density(pd.DataFrame([obs_row("2026-09-18T10:00:00+05:30")]), deps)
    assert r.sched_before_30 == 1
    assert r.sched_after_30 == 1


def test_run_day_across_midnight():
    deps = pd.DataFrame([dep("11111", 1430, ["fri"]),
                         dep("22222", 1430, ["sat"])])
    r = density(pd.DataFrame([obs_row("2026-09-19T00:10:00+05:30")]), deps)
    assert r.sched_before_30 == 1