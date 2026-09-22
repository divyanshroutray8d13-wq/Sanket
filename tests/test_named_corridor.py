"""
Tests for notebooks/build_named_corridor.py (train selection only).

Run:   pytest tests/test_named_corridor.py -v
"""

import pandas as pd

from notebooks.build_named_corridor import find_candidates, select_trains, tier_of

A = {"NDLS", "DLI"}
B = {"HWH", "SDAH"}


def _sched(trains):
    """trains: {train_no: (name, [station codes in order])}"""
    rows = []
    for no, (name, codes) in trains.items():
        for i, c in enumerate(codes, 1):
            rows.append({"train_no": no, "train_name": name, "stop_seq": i, "station_code": c})
    return pd.DataFrame(rows)


def test_only_trains_touching_both_ends():
    df = _sched({
        "12301": ("HOWRAH RAJDHANI", ["HWH", "DHN", "NDLS"]),
        "12001": ("BHOPAL SHATABDI", ["NDLS", "AGC", "BPL"]),  # one end only
    })
    assert find_candidates(df, A, B)["train_no"].tolist() == ["12301"]


def test_direction_follows_stop_order():
    df = _sched({
        "12301": ("RAJDHANI", ["HWH", "NDLS"]),
        "12302": ("RAJDHANI", ["NDLS", "HWH"]),
    })
    c = find_candidates(df, A, B).set_index("train_no")["direction"]
    assert c["12302"] == "a_to_b"
    assert c["12301"] == "b_to_a"


def test_tiers():
    assert tier_of("HOWRAH RAJDHANI") == 0
    assert tier_of("POORVA EXPRESS") == 1
    assert tier_of("KALKA MAIL") == 1
    assert tier_of("LOCAL PASSENGER") == 2
    assert tier_of("HWH NDLS SPL") == 3


def _cands(rows):
    return pd.DataFrame(rows, columns=["train_no", "train_name", "direction", "tier", "n_stops"])


def test_skips_non_five_digit_numbers():
    c = _cands([["2381", "X EXP", "a_to_b", 1, 5], ["12381", "X EXP", "a_to_b", 1, 5]])
    assert select_trains(c) == ["12381"]


def test_skips_zero_prefix_specials():
    c = _cands([["09003", "HWH NDLS EXP", "a_to_b", 1, 5], ["12301", "RAJDHANI", "a_to_b", 0, 5]])
    assert select_trains(c) == ["12301"]


def test_caps_at_limit_and_balances_directions():
    rows = [[f"1{i:04d}", "EXP", "a_to_b", 1, 5] for i in range(15)]
    rows += [[f"2{i:04d}", "EXP", "b_to_a", 1, 5] for i in range(15)]
    picked = select_trains(_cands(rows), limit=20)
    assert len(picked) == 20
    assert sum(p.startswith("1") for p in picked) == 10


def test_premium_picked_before_other():
    c = _cands([
        ["11111", "LOCAL", "a_to_b", 2, 5],
        ["22222", "RAJDHANI", "a_to_b", 0, 5],
    ])
    assert select_trains(c, limit=1) == ["22222"]


def test_fills_from_other_direction_when_one_runs_out():
    rows = [["10001", "EXP", "a_to_b", 1, 5]]
    rows += [[f"2{i:04d}", "EXP", "b_to_a", 1, 5] for i in range(5)]
    assert len(select_trains(_cands(rows), limit=4)) == 4
