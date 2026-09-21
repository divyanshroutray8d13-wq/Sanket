import json
import pandas as pd
import pytest

from src.collect.parse import route_to_observations

COLS = ["train_no", "train_category", "run_date", "step_seq",
        "from_station", "to_station", "booked_srt_min", "actual_srt_min",
        "minutes_lost", "length_km", "dep_delay_min", "dep_time", "arr_time"]


def stop(seq, code, sa, sd, aa, ad, dist, da=None, dd=None):
    return {
        "sequence": seq, "stationCode": code, "stationName": code,
        "isHalt": True,
        "scheduledArrival": sa, "scheduledDeparture": sd,
        "actualArrival": aa, "actualDeparture": ad,
        "delayArrival": da, "delayDeparture": dd,
        "status": "departed" if ad else ("at-station" if aa else "upcoming"),
        "distance": dist, "platform": "1",
    }


def payload(route, success=True, exceptions=None, category="Superfast"):
    return {
        "success": success,
        "data": {
            "trainNumber": "12919",
            "trainName": "Malwa SF Express",
            "startDate": "2026-06-22",
            "status": "running",
            "delayMinutes": 12,
            "train": {"number": "12919", "name": "Malwa SF Express",
                      "type": "Superfast Express", "category": category},
            "exceptions": exceptions or [],
            "route": route,
            "isLive": True,
        },
        "meta": {"traceId": "x", "timestamp": "2026-06-22T12:30:00+05:30"},
    }


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def clean_run():
    return payload([
        stop(1, "INDB", None,
             "2026-06-22T23:55:00+05:30", None,
             "2026-06-23T00:07:00+05:30", 0, None, 12),
        stop(2, "UJN", "2026-06-23T00:55:00+05:30",
             "2026-06-23T01:00:00+05:30", "2026-06-23T01:07:00+05:30",
             "2026-06-23T01:12:00+05:30", 55, 12, 12),
        stop(3, "MKSM", "2026-06-23T02:10:00+05:30",
             "2026-06-23T02:12:00+05:30", "2026-06-23T02:35:00+05:30",
             "2026-06-23T02:37:00+05:30", 96, 25, 25),
        stop(4, "BCH", "2026-06-23T03:00:00+05:30",
             None, "2026-06-23T03:20:00+05:30", None, 140, 20, None),
    ])


# ---------------------------------------------------------------- shape

def test_columns_exact(clean_run):
    df = route_to_observations(clean_run)
    assert list(df.columns) == COLS


def test_row_count(clean_run):
    """Four stops means three sections."""
    assert len(route_to_observations(clean_run)) == 3


def test_step_seq_zero_based_contiguous(clean_run):
    df = route_to_observations(clean_run)
    assert df.step_seq.tolist() == [0, 1, 2]


def test_metadata_carried_through(clean_run):
    df = route_to_observations(clean_run)
    assert set(df.train_no) == {"12919"}
    assert set(df.train_category) == {"Superfast"}
    assert set(df.run_date) == {"2026-06-22"}


# ---------------------------------------------------------------- arithmetic

def test_booked_srt_uses_departure_not_arrival(clean_run):

    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].booked_srt_min.iloc[0] == 70


def test_actual_srt(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].actual_srt_min.iloc[0] == 83


def test_minutes_lost_is_the_label(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].minutes_lost.iloc[0] == 13


def test_minutes_lost_can_be_negative(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 2].minutes_lost.iloc[0] == -5


def test_minutes_lost_is_not_cumulative_delay(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].minutes_lost.iloc[0] != 25


def test_crosses_midnight(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 0].booked_srt_min.iloc[0] == 60
    assert df[df.step_seq == 0].actual_srt_min.iloc[0] == 60


def test_length_is_incremental(clean_run):
    df = route_to_observations(clean_run)
    assert df.length_km.tolist() == pytest.approx([55.0, 41.0, 44.0])


def test_dep_delay_captured(clean_run):
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].dep_delay_min.iloc[0] == 12


def test_integer_dtypes(clean_run):
    df = route_to_observations(clean_run)
    for c in ("booked_srt_min", "actual_srt_min", "minutes_lost",
              "dep_delay_min", "step_seq"):
        assert df[c].dtype.kind in "iu", c


# ---------------------------------------------------------------- skipping

def test_skips_upcoming_stops():
    df = route_to_observations(payload([
        stop(1, "AAA", None, "2026-06-22T06:00:00+05:30", None,
             "2026-06-22T06:05:00+05:30", 0, None, 5),
        stop(2, "BBB", "2026-06-22T07:00:00+05:30",
             "2026-06-22T07:05:00+05:30", "2026-06-22T07:12:00+05:30",
             "2026-06-22T07:18:00+05:30", 60, 12, 13),
        stop(3, "CCC", "2026-06-22T08:00:00+05:30", None, None, None, 120),
    ]))
    assert len(df) == 1
    assert df.iloc[0].to_station == "BBB"


def test_gap_in_middle_renumbers_contiguously():
    df = route_to_observations(payload([
        stop(1, "AAA", None, "2026-06-22T06:00:00+05:30", None,
             "2026-06-22T06:04:00+05:30", 0),
        stop(2, "BBB", "2026-06-22T07:00:00+05:30",
             "2026-06-22T07:05:00+05:30", None, None, 60),
        stop(3, "CCC", "2026-06-22T08:00:00+05:30",
             "2026-06-22T08:05:00+05:30", "2026-06-22T08:20:00+05:30",
             "2026-06-22T08:25:00+05:30", 120, 20, 20),
        stop(4, "DDD", "2026-06-22T09:00:00+05:30", None,
             "2026-06-22T09:30:00+05:30", None, 175, 30),
    ]))
    assert len(df) == 1
    assert df.iloc[0].step_seq == 0
    assert (df.iloc[0].from_station, df.iloc[0].to_station) == ("CCC", "DDD")


def test_drops_absurd_booked_srt():
    df = route_to_observations(payload([
        stop(1, "AAA", None, "2026-06-22T06:00:00+05:30", None,
             "2026-06-22T06:00:00+05:30", 0),
        stop(2, "BBB", "2026-06-22T19:30:00+05:30", None,
             "2026-06-22T19:40:00+05:30", None, 50),
    ]))
    assert len(df) == 0


def test_drops_non_increasing_distance():
    df = route_to_observations(payload([
        stop(1, "AAA", None, "2026-06-22T06:00:00+05:30", None,
             "2026-06-22T06:00:00+05:30", 50),
        stop(2, "BBB", "2026-06-22T07:00:00+05:30", None,
             "2026-06-22T07:10:00+05:30", None, 20),
    ]))
    assert len(df) == 0


# ---------------------------------------------------------------- whole-train rejects

def test_rejects_failed_payload(clean_run):
    bad = dict(clean_run)
    bad["success"] = False
    out = route_to_observations(bad)
    assert len(out) == 0
    assert list(out.columns) == COLS      # still the right shape


def test_rejects_diverted_train(clean_run):
    div = json.loads(json.dumps(clean_run))
    div["data"]["exceptions"] = [{"type": "DIVERTED", "message": "..."}]
    assert len(route_to_observations(div)) == 0


def test_rejects_partially_cancelled(clean_run):
    pc = json.loads(json.dumps(clean_run))
    pc["data"]["exceptions"] = [{"type": "PARTIALLY_CANCELLED", "message": "..."}]
    assert len(route_to_observations(pc)) == 0


def test_allows_harmless_exception(clean_run):
    """A rescheduled departure does not change which sections were run."""
    ok = json.loads(json.dumps(clean_run))
    ok["data"]["exceptions"] = [{"type": "RESCHEDULED", "message": "..."}]
    assert len(route_to_observations(ok)) == 3


def test_empty_route_returns_empty_frame():
    out = route_to_observations(payload([]))
    assert len(out) == 0
    assert list(out.columns) == COLS


def test_rejects_run_with_no_tracking(clean_run):
    dead = json.loads(json.dumps(clean_run))
    for s in dead["data"]["route"]:
        s["delayArrival"] = None
        s["delayDeparture"] = None
    assert len(route_to_observations(dead)) == 0


def test_ignores_non_halt_stations(clean_run):
    with_pass = json.loads(json.dumps(clean_run))
    r = with_pass["data"]["route"]
    passing = dict(r[1]); passing["stationCode"] = "PASS"; passing["isHalt"] = False
    r.insert(2, passing)
    df = route_to_observations(with_pass)
    assert len(df) == 3
    assert "PASS" not in set(df.from_station) | set(df.to_station)


def test_ignores_projected_upcoming_halts(clean_run):
    proj = json.loads(json.dumps(clean_run))
    last = proj["data"]["route"][-1]
    last["status"] = "upcoming"
    assert len(route_to_observations(proj)) == 2


def test_ignores_departed_halt_without_delay(clean_run):
    cp = json.loads(json.dumps(clean_run))
    cp["data"]["route"][1]["delayArrival"] = None
    cp["data"]["route"][1]["delayDeparture"] = None
    df = route_to_observations(cp)
    assert "UJN" not in set(df.from_station) | set(df.to_station)


def test_carries_actual_timestamps(clean_run):
    df = route_to_observations(clean_run)
    row = df[df.step_seq == 1].iloc[0]
    assert row.dep_time == "2026-06-23T01:12:00+05:30"
    assert row.arr_time == "2026-06-23T02:35:00+05:30"
