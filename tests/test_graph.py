
import pandas as pd
import pytest

from src.graph.build_graph import (
    hhmm_to_minutes,
    add_absolute_minutes,
    build_routes,
    build_sections,
)

COLS = ["train_no", "train_name", "stop_seq", "station_code",
        "arrival", "departure", "distance_km"]


def mk(rows):
    return pd.DataFrame(rows, columns=COLS)

# ---------------------------------------------------------------- fixtures
@pytest.fixture
def konkan():
    """Train 107 exactly as it appears in the real file, sentinels resolved."""
    return mk([
        ("107", "SWV-MAO-VLNK", 1, "SWV",  None,       "10:25:00",  0.0),
        ("107", "SWV-MAO-VLNK", 2, "THVM", "11:06:00", "11:08:00", 32.0),
        ("107", "SWV-MAO-VLNK", 3, "KRMI", "11:28:00", "11:30:00", 49.0),
        ("107", "SWV-MAO-VLNK", 4, "MAO",  "12:10:00", None,       78.0),
    ])


@pytest.fixture
def overnight():
    """Departs 23:40, arrives 00:25 next day, then runs on into the morning."""
    return mk([
        ("9001", "NIGHT EXP", 1, "PPP", None,       "23:40:00",   0.0),
        ("9001", "NIGHT EXP", 2, "QQQ", "00:25:00", "00:30:00",  52.0),
        ("9001", "NIGHT EXP", 3, "RRR", "02:05:00", "02:10:00", 140.0),
        ("9001", "NIGHT EXP", 4, "SSS", "06:15:00", None,       390.0),
    ])


# ---------------------------------------------------------------- time parsing

def test_hhmm_basic():
    assert hhmm_to_minutes("10:25:00") == 625
    assert hhmm_to_minutes("00:00:00") == 0
    assert hhmm_to_minutes("23:59:00") == 1439


def test_hhmm_missing():
    assert hhmm_to_minutes(None) is None
    assert hhmm_to_minutes("") is None
    assert hhmm_to_minutes(float("nan")) is None


# ---------------------------------------------------------------- unwrapping

def test_absolute_minutes_same_day(konkan):
    df = add_absolute_minutes(konkan)
    assert df.loc[df.stop_seq == 1, "dep_min"].iloc[0] == 625   # 10:25
    assert df.loc[df.stop_seq == 2, "arr_min"].iloc[0] == 666   # 11:06
    assert df.loc[df.stop_seq == 4, "arr_min"].iloc[0] == 730   # 12:10


def test_absolute_minutes_first_arrival_is_null(konkan):
    df = add_absolute_minutes(konkan)
    assert pd.isna(df.loc[df.stop_seq == 1, "arr_min"].iloc[0])


def test_absolute_minutes_last_departure_is_null(konkan):
    df = add_absolute_minutes(konkan)
    assert pd.isna(df.loc[df.stop_seq == 4, "dep_min"].iloc[0])


def test_absolute_minutes_rolls_over_midnight(overnight):
    df = add_absolute_minutes(overnight)
    assert df.loc[df.stop_seq == 1, "dep_min"].iloc[0] == 1420
    assert df.loc[df.stop_seq == 2, "arr_min"].iloc[0] == 1465


def test_absolute_minutes_keeps_rising_after_rollover(overnight):
    df = add_absolute_minutes(overnight)
    assert df.loc[df.stop_seq == 3, "arr_min"].iloc[0] == 1565
    assert df.loc[df.stop_seq == 4, "arr_min"].iloc[0] == 1815


def test_absolute_minutes_monotonic(overnight):
    df = add_absolute_minutes(overnight).sort_values("stop_seq")
    seq = []
    for _, r in df.iterrows():
        for v in (r.arr_min, r.dep_min):
            if pd.notna(v):
                seq.append(v)
    assert seq == sorted(seq)


def test_absolute_minutes_handles_dwell_across_midnight():
    df = add_absolute_minutes(mk([
        ("9002", "X", 1, "AAA", None,       "23:50:00", 0.0),
        ("9002", "X", 2, "BBB", "23:58:00", "00:03:00", 9.0),
        ("9002", "X", 3, "CCC", "00:40:00", None,      40.0),
    ]))
    assert df.loc[df.stop_seq == 2, "arr_min"].iloc[0] == 1438
    assert df.loc[df.stop_seq == 2, "dep_min"].iloc[0] == 1443   # 1440 + 3
    assert df.loc[df.stop_seq == 3, "arr_min"].iloc[0] == 1480


def test_absolute_minutes_per_train_independent(konkan, overnight):
    """Two trains in one frame must not share an offset."""
    df = add_absolute_minutes(pd.concat([konkan, overnight], ignore_index=True))
    k = df[df.train_no == "107"]
    assert k.loc[k.stop_seq == 1, "dep_min"].iloc[0] == 625


# ---------------------------------------------------------------- routes

def test_routes_real_train(konkan):
    r = build_routes(add_absolute_minutes(konkan)).sort_values("step_seq")
    assert len(r) == 3
    assert r.booked_srt_min.tolist() == [41, 20, 40]
    assert r.length_km.tolist() == pytest.approx([32.0, 17.0, 29.0])


def test_routes_columns(konkan):
    r = build_routes(add_absolute_minutes(konkan))
    assert list(r.columns) == ["train_no", "step_seq", "from_station",
                               "to_station", "booked_srt_min", "length_km"]


def test_routes_step_seq_zero_based(konkan):
    r = build_routes(add_absolute_minutes(konkan))
    assert sorted(r.step_seq.tolist()) == [0, 1, 2]


def test_routes_uses_departure_not_arrival(konkan):
    r = build_routes(add_absolute_minutes(konkan))
    assert r[r.step_seq == 1].booked_srt_min.iloc[0] == 20


def test_routes_overnight_not_negative(overnight):
    r = build_routes(add_absolute_minutes(overnight)).sort_values("step_seq")
    assert r.booked_srt_min.tolist() == [45, 95, 245]
    assert (r.booked_srt_min > 0).all()


def test_routes_length_incremental(overnight):
    r = build_routes(add_absolute_minutes(overnight)).sort_values("step_seq")
    assert r.length_km.tolist() == pytest.approx([52.0, 88.0, 250.0])


def test_routes_srt_is_integer(konkan):
    r = build_routes(add_absolute_minutes(konkan))
    assert r.booked_srt_min.dtype.kind in "iu"


def test_routes_drops_absurd_section():
    df = add_absolute_minutes(mk([
        ("9003", "X", 1, "AAA", None,       "06:00:00", 0.0),
        ("9003", "X", 2, "BBB", "19:30:00", None,      50.0),
    ]))
    assert len(build_routes(df)) == 0


def test_routes_drops_non_increasing_distance():

    df = add_absolute_minutes(mk([
        ("9004", "X", 1, "AAA", None,       "06:00:00", 10.0),
        ("9004", "X", 2, "BBB", "06:40:00", None,        5.0),
    ]))
    assert len(build_routes(df)) == 0


# ---------------------------------------------------------------- sections

def test_sections_shared_counts_trains(konkan):

    other = mk([
        ("108", "MAO-SWV", 1, "THVM", None,       "16:10:00",  0.0),
        ("108", "MAO-SWV", 2, "KRMI", "16:32:00", "16:35:00", 17.0),
        ("108", "MAO-SWV", 3, "MAO",  "17:20:00", None,       46.0),
    ])
    both = pd.concat([konkan, other], ignore_index=True)
    s = build_sections(build_routes(add_absolute_minutes(both)))
    assert s[s.section_id == "THVM>KRMI"].n_trains.iloc[0] == 2
    assert s[s.section_id == "SWV>THVM"].n_trains.iloc[0] == 1


def test_sections_columns(konkan):
    s = build_sections(build_routes(add_absolute_minutes(konkan)))
    assert list(s.columns) == ["section_id", "from_station",
                               "to_station", "length_km", "n_trains"]


def test_sections_unique(konkan):
    s = build_sections(build_routes(add_absolute_minutes(konkan)))
    assert s.section_id.is_unique
    assert len(s) == 3


def test_sections_id_format(konkan):
    s = build_sections(build_routes(add_absolute_minutes(konkan)))
    assert "SWV>THVM" in set(s.section_id)


def test_sections_sorted_by_traffic(konkan):
    other = mk([
        ("108", "R", 1, "THVM", None,       "16:10:00",  0.0),
        ("108", "R", 2, "KRMI", "16:32:00", None,       17.0),
    ])
    both = pd.concat([konkan, other], ignore_index=True)
    s = build_sections(build_routes(add_absolute_minutes(both)))
    assert s.iloc[0].section_id == "THVM>KRMI"
    assert s.n_trains.tolist() == sorted(s.n_trains.tolist(), reverse=True)


def test_sections_direction_matters(konkan):
  
    rev = mk([
        ("109", "REV", 1, "THVM", None,       "08:00:00",  0.0),
        ("109", "REV", 2, "SWV",  "08:45:00", None,       32.0),
    ])
    both = pd.concat([konkan, rev], ignore_index=True)
    ids = set(build_sections(build_routes(add_absolute_minutes(both))).section_id)
    assert "SWV>THVM" in ids and "THVM>SWV" in ids


def test_sections_length_is_median(konkan):
    other = mk([
        ("110", "Y", 1, "SWV",  None,       "14:00:00",  0.0),
        ("110", "Y", 2, "THVM", "14:50:00", None,       33.0),
    ])
    both = pd.concat([konkan, other], ignore_index=True)
    s = build_sections(build_routes(add_absolute_minutes(both)))
    assert s[s.section_id == "SWV>THVM"].length_km.iloc[0] == pytest.approx(32.5)


# ---------------------------------------------------------------- integration

def test_every_used_section_is_in_sections(konkan, overnight):
    both = pd.concat([konkan, overnight], ignore_index=True)
    r = build_routes(add_absolute_minutes(both))
    s = build_sections(r)
    assert set(r.from_station + ">" + r.to_station) == set(s.section_id)


def test_no_duplicate_steps(konkan, overnight):
    both = pd.concat([konkan, overnight], ignore_index=True)
    r = build_routes(add_absolute_minutes(both))
    assert not r.duplicated(subset=["train_no", "step_seq"]).any()
