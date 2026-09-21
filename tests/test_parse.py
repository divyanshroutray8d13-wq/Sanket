"""
Tests for src/collect/parse.py

Turns a RailRadar /v1/trains/{number}/live payload into one row per SECTION
that the train actually completed — the real-world equivalent of what your
simulator produces.

Run:   pytest tests/test_parse.py -v

==============================================================================
WHY THIS FILE IS THE MOST IMPORTANT PARSER YOU WILL WRITE
==============================================================================

Every row it emits is a real observation: a real train, on a real section,
on a real day, with the real minutes it lost. This is your training data and
your evidence. If this parser is subtly wrong, everything downstream is wrong
and nothing will tell you.

==============================================================================
WHAT YOU IMPLEMENT
==============================================================================

route_to_observations(payload: dict) -> pd.DataFrame

    Input: the full decoded JSON of one API response (the whole envelope,
    including the "success" and "data" keys).

    Output: one row per CONSECUTIVE PAIR of route stops where BOTH ends have
    real observed times. Columns, in this exact order:

        train_no        str     from data.trainNumber
        train_category  str     from data.train.category  (e.g. "Superfast")
        run_date        str     from data.startDate       ("YYYY-MM-DD")
        step_seq        int     0-based, contiguous over the rows you keep
        from_station    str
        to_station      str
        booked_srt_min  int     schedArr(B)   - schedDep(A)
        actual_srt_min  int     actualArr(B)  - actualDep(A)
        minutes_lost    int     actual_srt_min - booked_srt_min
        length_km       float   distance(B)   - distance(A)
        dep_delay_min   int     delayDeparture at A (how late it entered)

    SKIP a pair when any of these is true:
        - actualDeparture at A is null      (train had not left yet)
        - actualArrival   at B is null      (train had not arrived yet)
        - scheduledDeparture at A is null   (origin has no scheduled arrival,
                                             but it does have a departure —
                                             this guard is for odd payloads)
        - scheduledArrival  at B is null
        - the computed booked_srt_min <= 0 or > 720
        - length_km <= 0

    ALSO SKIP THE WHOLE TRAIN (return an empty DataFrame with the right
    columns) when:
        - payload["success"] is not True
        - data.exceptions contains any entry with type "DIVERTED" or
          "PARTIALLY_CANCELLED"    <- a diverted train did not run the
                                      sections its route claims, so every
                                      row would be a lie

    NOTES
    - Timestamps are ISO 8601 with a +05:30 offset. pd.to_datetime parses
      them directly; subtract and use .total_seconds() / 60.
    - Do NOT use delayArrival/delayDeparture to compute minutes_lost. Those
      are cumulative delay against the whole schedule, not time lost on this
      section. The difference is the entire point of the project.
    - Gaps are fine: if stop 5 has no actual time but stops 6 and 7 do, you
      keep 6->7 and renumber step_seq contiguously.
"""

import json
import pandas as pd
import pytest

from src.collect.parse import route_to_observations

COLS = ["train_no", "train_category", "run_date", "step_seq",
        "from_station", "to_station", "booked_srt_min", "actual_srt_min",
        "minutes_lost", "length_km", "dep_delay_min"]


def stop(seq, code, sa, sd, aa, ad, dist, da=None, dd=None):
    """Build one route entry the way RailRadar returns it."""
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
    """
    Three completed sections, taken from the shape of the real Malwa payload.

      INDB  dep sched 23:55  actual 00:07      dist 0
      UJN   arr sched 00:55  actual 01:07      dist 55
            dep sched 01:00  actual 01:12
      MKSM  arr sched 02:10  actual 02:35      dist 96
            dep sched 02:12  actual 02:37
      BCH   arr sched 03:00  actual 03:20      dist 140

    Section 1  INDB->UJN : booked 60, actual 60, lost  0, 55 km
    Section 2  UJN ->MKSM: booked 70, actual 83, lost 13, 41 km
    Section 3  MKSM->BCH : booked 48, actual 43, lost -5, 44 km   (made up time)
    """
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
    """
    UJN->MKSM booked must be schedArr(MKSM) 02:10 minus schedDep(UJN) 01:00
    = 70 minutes. Arrival-to-arrival gives 75 and bakes in dwell time.
    """
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].booked_srt_min.iloc[0] == 70


def test_actual_srt(clean_run):
    """UJN->MKSM actual: 02:35 minus 01:12 = 83 minutes."""
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].actual_srt_min.iloc[0] == 83


def test_minutes_lost_is_the_label(clean_run):
    """83 - 70 = 13. This single number is what the model learns."""
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].minutes_lost.iloc[0] == 13


def test_minutes_lost_can_be_negative(clean_run):
    """
    MKSM->BCH: booked 48, actual 43. The train made up 5 minutes.
    Do NOT clip this to zero — recovery is real and the model must see it.
    """
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 2].minutes_lost.iloc[0] == -5


def test_minutes_lost_is_not_cumulative_delay(clean_run):
    """
    delayArrival at MKSM is 25 (cumulative against schedule) but only 13 of
    those minutes were lost on UJN->MKSM. If you see 25 here you used the
    delay field instead of computing the section time, and the whole premise
    of the project is gone.
    """
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].minutes_lost.iloc[0] != 25


def test_crosses_midnight(clean_run):
    """
    INDB departs 23:55 on the 22nd and reaches UJN 00:55 on the 23rd.
    That is 60 minutes. The ISO dates carry the day, so this only breaks
    if you parse times without their date.
    """
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 0].booked_srt_min.iloc[0] == 60
    assert df[df.step_seq == 0].actual_srt_min.iloc[0] == 60


def test_length_is_incremental(clean_run):
    df = route_to_observations(clean_run)
    assert df.length_km.tolist() == pytest.approx([55.0, 41.0, 44.0])


def test_dep_delay_captured(clean_run):
    """How late the train ENTERED the section — a model feature."""
    df = route_to_observations(clean_run)
    assert df[df.step_seq == 1].dep_delay_min.iloc[0] == 12


def test_integer_dtypes(clean_run):
    df = route_to_observations(clean_run)
    for c in ("booked_srt_min", "actual_srt_min", "minutes_lost",
              "dep_delay_min", "step_seq"):
        assert df[c].dtype.kind in "iu", c


# ---------------------------------------------------------------- skipping

def test_skips_upcoming_stops():
    """Train has only reached stop 2. Only one section is observed."""
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
    """
    Stop 2 was never reported. 1->2 and 2->3 are both unusable, but 3->4
    is fine and must come out as step_seq 0.
    """
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
    """13 hours booked on one section is bad data."""
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
    """
    A diverted train did not travel the sections its route lists. Every row
    would be fiction. Drop the whole run.
    """
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
    """
    Every halt has actual times but no delay data at all. That is the
    signature of a run RailRadar did not track: 'actual' is just the
    schedule copied across. Treating it as a punctual train would teach the
    model that nothing is ever late.
    """
    dead = json.loads(json.dumps(clean_run))
    for s in dead["data"]["route"]:
        s["delayArrival"] = None
        s["delayDeparture"] = None
    assert len(route_to_observations(dead)) == 0


def test_ignores_non_halt_stations(clean_run):
    """
    Passing points carry interpolated times, not observations. A non-halt
    stop inserted between two halts must not create extra sections.
    """
    with_pass = json.loads(json.dumps(clean_run))
    r = with_pass["data"]["route"]
    passing = dict(r[1]); passing["stationCode"] = "PASS"; passing["isHalt"] = False
    r.insert(2, passing)
    df = route_to_observations(with_pass)
    assert len(df) == 3
    assert "PASS" not in set(df.from_station) | set(df.to_station)


def test_ignores_projected_upcoming_halts(clean_run):
    """
    RailRadar fills actualArrival on halts the train has NOT reached yet,
    with a projection (schedule + current delay). Status says 'upcoming'.
    Those are forecasts, not observations, and must never become labels.
    """
    proj = json.loads(json.dumps(clean_run))
    last = proj["data"]["route"][-1]
    last["status"] = "upcoming"
    assert len(route_to_observations(proj)) == 2


def test_ignores_departed_halt_without_delay(clean_run):
    """
    A 'departed' halt with an actual time but no delay value is the schedule
    copied across, not a measurement. Seen in real data on 22653.
    """
    cp = json.loads(json.dumps(clean_run))
    cp["data"]["route"][1]["delayArrival"] = None
    cp["data"]["route"][1]["delayDeparture"] = None
    df = route_to_observations(cp)
    assert "UJN" not in set(df.from_station) | set(df.to_station)
