import numpy as np
import pandas as pd
import pytest

from src.features.build_features import add_direction, corridor_km, pick_references
from src.forecast.export import attribution, build_payload, parse_now
from src.forecast.horizon import (BUCKET_LABELS, BUCKET_TOPS, bucket_index, build_horizon_frame,
                                  evaluate, feature_columns, parse_groups, raw_predict,
                                  train_forecaster)

STATIONS = [f"S{i}" for i in range(7)]
KM = {s: 50.0 * i for i, s in enumerate(STATIONS)}
DAYS = ["2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"]


def make_obs(seed=0):
    """3 trains x 4 days, each S0 -> S6 in 6 sections. Delay is a random walk."""
    rng = np.random.default_rng(seed)
    rows = []
    for day in DAYS:
        for n, (train, cat, start) in enumerate([("11111", "Express", 6), ("22222", "Premium", 9),
                                                   ("33333", "Express", 13)]):
            delay = int(rng.integers(0, 15))
            for i in range(6):
                sched_dep = pd.Timestamp(f"{day} {start:02d}:00", tz="Asia/Kolkata") + pd.Timedelta(minutes=45 * i)
                lost = int(rng.integers(-4, 8))
                dep = sched_dep + pd.Timedelta(minutes=delay)
                arr = dep + pd.Timedelta(minutes=40 + lost)
                rows.append(dict(train_no=train, train_category=cat, run_date=day, step_seq=i,
                                 from_station=STATIONS[i], to_station=STATIONS[i + 1],
                                 booked_srt_min=40, actual_srt_min=40 + lost, minutes_lost=lost,
                                 length_km=50.0, dep_delay_min=delay,
                                 dep_time=dep.isoformat(), arr_time=arr.isoformat(),
                                 corridor="mumbai"))
                delay = max(0, delay + lost + int(rng.integers(-2, 3)))   # next halt's departure delay
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def obs():
    return make_obs()


@pytest.fixture(scope="module")
def fitted(obs):
    train = (obs["run_date"] < DAYS[-1]).to_numpy()
    return train, train_forecaster(obs, KM, train, ())


# --- groups and buckets ------------------------------------------------------
def test_parse_groups():
    assert parse_groups("base") == () and parse_groups("") == ()
    assert parse_groups("hist,network") == ("network", "hist")
    assert parse_groups("network+sched") == ("network", "sched")
    with pytest.raises(ValueError):
        parse_groups("network,bogus")


def test_feature_columns_grow_with_groups():
    base = feature_columns(())
    assert set(base) < set(feature_columns(("network",))) < set(feature_columns(("network", "sched", "hist")))
    assert "h" in base and "dep_delay_min" in base


@pytest.mark.parametrize("h,expected", [(1, 0), (2, 1), (3, 1), (4, 2), (6, 2), (7, 3), (10, 3), (11, 4), (20, 4), (99, 4)])
def test_bucket_index(h, expected):
    assert bucket_index(h) == expected
    assert len(BUCKET_LABELS) == len(BUCKET_TOPS)


# --- the dataset -------------------------------------------------------------
def test_frame_pairs_stay_inside_one_run_and_go_forward(obs):
    f = build_horizon_frame(obs, KM)
    assert len(f) == 12 * 21                       # 12 runs x (6 + 5 + ... + 1) pairs
    assert (f["j_step"] >= f["k_step"]).all()
    k, j = obs.iloc[f["k_idx"]], obs.iloc[f["j_idx"]]
    assert (k["train_no"].to_numpy() == j["train_no"].to_numpy()).all()
    assert (k["run_date"].to_numpy() == j["run_date"].to_numpy()).all()
    assert (f["h"] == f["j_step"] - f["k_step"] + 1).all()


def test_frame_target_is_arrival_delay_minus_delay_now(obs):
    f = build_horizon_frame(obs, KM)
    j = obs.iloc[f["j_idx"]].reset_index(drop=True)
    k = obs.iloc[f["k_idx"]].reset_index(drop=True)
    assert np.allclose(f["true_delay"], j["dep_delay_min"] + j["minutes_lost"])
    assert np.allclose(f["d0"], k["dep_delay_min"])
    assert np.allclose(f["target"], f["true_delay"] - f["d0"])


def test_frame_booked_time_is_schedule_minutes_between_the_two_stops(obs):
    f = build_horizon_frame(obs, KM)
    one = f[f["h"] == 1]
    assert np.allclose(one["cum_booked"], 40)       # one section: booked 40 min
    last = f[f["h"] == 3]
    assert np.allclose(last["cum_booked"], 40 + 45 + 45)   # 3 sections: 45 min apart, last one 40 min


def test_frame_respects_max_h(obs):
    assert build_horizon_frame(obs, KM, max_h=2)["h"].max() == 2


def test_sched_group_needs_departures_and_hist_needs_mask(obs):
    with pytest.raises(ValueError):
        build_horizon_frame(obs, KM, ("sched",))
    with pytest.raises(ValueError):
        build_horizon_frame(obs, KM, ("hist",))


def test_hist_features_added(obs):
    mask = (obs["run_date"] < DAYS[-1]).to_numpy()
    f = build_horizon_frame(obs, KM, ("hist",), fit_mask=mask)
    assert {"cum_hist_mean", "cum_hist_cov"} <= set(f.columns)
    assert f["cum_hist_cov"].between(0, 1).all()


# --- training, calibration, no leakage --------------------------------------
def test_forecaster_never_sees_the_test_day(fitted):
    train, fc = fitted
    assert fc.train_dates == DAYS[:-1]
    assert len(fc.margins) == len(BUCKET_TOPS) and all(m >= 0 for m in fc.margins)


def test_predictions_are_ordered_and_widened(obs, fitted):
    train, fc = fitted
    f = build_horizon_frame(obs, KM)
    te = f[~train[f["k_idx"].to_numpy()]].reset_index(drop=True)
    p = fc.predict(te)
    assert (p["p10"] <= p["p50"]).all() and (p["p50"] <= p["p90"]).all()
    raw = raw_predict(fc.models, te[fc.feats])
    assert ((p["p90"] - p["p10"]) >= (raw["p90"] - raw["p10"]) - 1e-9).all()


def test_contributions_add_up_to_the_median_forecast(obs, fitted):
    train, fc = fitted
    f = build_horizon_frame(obs, KM).head(50)
    contrib = fc.contributions(f)
    assert np.allclose(contrib.sum(axis=1), fc.models[0.5].predict(f[fc.feats]), atol=1e-6)


def test_confidence_uses_measured_coverage_when_set(fitted):
    _, fc = fitted
    assert (fc.confidence([1, 5, 15]) == 0.8).all()
    fc.coverage = [0.9, 0.7, 0.6, 0.5, 0.4]
    assert list(fc.confidence([1, 5, 15])) == [0.9, 0.6, 0.4]
    fc.coverage = None


def test_smoke_train_with_network_and_hist(obs):
    train = (obs["run_date"] < DAYS[-1]).to_numpy()
    fc = train_forecaster(obs, KM, train, ("network", "hist"))
    assert set(feature_columns(("network", "hist"))) == set(fc.feats)


# --- evaluation --------------------------------------------------------------
def test_evaluate_perfect_forecast_and_carry_forward_baseline(obs):
    f = build_horizon_frame(obs, KM)
    perfect = pd.DataFrame({"p10": f["target"] - 1, "p50": f["target"], "p90": f["target"] + 1})
    ev = evaluate(f, perfect, n_boot=50)
    assert ev["overall"]["mae_model"] == 0
    assert np.isclose(ev["overall"]["mae_carry"], f["target"].abs().mean())
    assert ev["overall"]["coverage"] == 1.0
    assert sum(b["n"] for b in ev["buckets"]) == len(f)
    assert ev["overall"]["gain_pct"] == 100.0 and ev["overall"]["n_runs"] == 12


def test_evaluate_zero_forecast_equals_the_baseline(obs):
    f = build_horizon_frame(obs, KM)
    zero = pd.DataFrame({"p10": -5.0, "p50": 0.0, "p90": 5.0}, index=f.index)
    ev = evaluate(f, zero, n_boot=50)
    assert np.isclose(ev["overall"]["gain_pct"], 0.0)


# --- export ------------------------------------------------------------------
def minutes(t):      # "HH:MM" -> minutes, for sums that may pass midnight
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def wrap(d):
    return (d + 720) % 1440 - 720


@pytest.fixture(scope="module")
def payload(obs, fitted):
    train, fc = fitted
    frame = build_horizon_frame(obs, KM)
    return build_payload(fc, obs, frame, "11111", DAYS[-1], asof=0.2, n_ahead=10,
                         meta={"name": "Test Express", "names": {s: f"Station {s}" for s in STATIONS}})


def test_payload_matches_the_frozen_schema(payload):
    assert payload["train_no"] == "11111" and payload["train_name"] == "Test Express"
    assert payload["is_replay"] is True and payload["is_mock"] is False and payload["is_live"] is False
    assert set(payload["current"]) == {"station_code", "station_name", "delay_min"}
    need = {"code", "name", "sequence", "scheduled", "baseline_eta", "eta_median", "eta_low",
            "eta_high", "confidence", "attribution"}
    for i, s in enumerate(payload["stations"], start=1):
        assert need <= set(s) and s["sequence"] == i
        assert all(set(a) == {"cause", "minutes"} for a in s["attribution"])


def test_payload_window_is_ordered_and_contains_the_median(payload):
    for s in payload["stations"]:
        lo = wrap(minutes(s["eta_low"]) - minutes(s["scheduled"]))
        mid = wrap(minutes(s["eta_median"]) - minutes(s["scheduled"]))
        hi = wrap(minutes(s["eta_high"]) - minutes(s["scheduled"]))
        assert lo <= mid <= hi


def test_payload_baseline_is_schedule_plus_current_delay(payload):
    d0 = payload["current"]["delay_min"]
    for s in payload["stations"]:
        assert wrap(minutes(s["baseline_eta"]) - minutes(s["scheduled"])) == d0


def test_attribution_adds_up_to_how_late_the_train_will_be(payload):
    for s in payload["stations"]:
        late = wrap(minutes(s["eta_median"]) - minutes(s["scheduled"]))
        assert abs(sum(a["minutes"] for a in s["attribution"]) - late) <= 3   # whole-minute rounding


def test_attribution_folds_negatives_into_one_line():
    row = pd.Series({"a": 6.0, "b": 3.0, "c": -2.0, "d": -4.0, "e": 0.2})
    a = attribution(row)
    assert a == [{"cause": "a", "minutes": 6}, {"cause": "b", "minutes": 3},
                 {"cause": "time made up", "minutes": -6}]


def test_attribution_starts_from_the_delay_the_train_already_has():
    row = pd.Series({"a": 4.0, "b": -1.0})
    assert attribution(row, carried=6.0) == [{"cause": "delay carried forward", "minutes": 6},
                                              {"cause": "a", "minutes": 4},
                                              {"cause": "time made up", "minutes": -1}]
    # a train running early: its head start is time already made up
    assert attribution(pd.Series({"a": 4.0}), carried=-3.0) == [{"cause": "a", "minutes": 4},
                                                              {"cause": "time made up", "minutes": -3}]


def test_payload_replay_uses_only_stops_not_reached_yet_when_now_is_given(obs, fitted):
    train, fc = fitted
    frame = build_horizon_frame(obs, KM)
    now = parse_now("07:30", DAYS[-1])
    p = build_payload(fc, obs, frame, "11111", DAYS[-1], now=now)
    assert p is not None and p["as_of"].startswith(f"{DAYS[-1]}T07:30")
    arrived = pd.to_datetime(obs.loc[(obs.train_no == "11111") & (obs.run_date == DAYS[-1]), "arr_time"], utc=True)
    assert len(p["stations"]) == int((arrived > now).sum())      # exactly the stops still ahead
    assert build_payload(fc, obs, frame, "11111", DAYS[-1], now=parse_now("05:00", DAYS[-1])) is None   # not started
    assert build_payload(fc, obs, frame, "11111", DAYS[-1], now=parse_now("23:00", DAYS[-1])) is None   # already finished


# --- corridor maps -----------------------------------------------------------
def test_add_direction_with_several_maps_keeps_corridors_apart():
    routes = pd.DataFrame([
        dict(train_no="A", step_seq=0, from_station="X", to_station="Y", booked_srt_min=10, length_km=10.0),
        dict(train_no="A", step_seq=1, from_station="Y", to_station="Z", booked_srt_min=10, length_km=10.0),
        dict(train_no="B", step_seq=0, from_station="X", to_station="P", booked_srt_min=10, length_km=10.0),
    ])
    kms = {"one": corridor_km(routes, "A"), "two": corridor_km(routes, "B")}
    obs = pd.DataFrame({"from_station": ["X", "Y", "Z", "X", "Q"], "to_station": ["Y", "Z", "Y", "P", "R"]})
    d = add_direction(obs, kms)["direction"]
    assert list(d[:3]) == [1, 1, -1]                # corridor one: +1 / -1, unchanged encoding
    assert d[3] == 11                                # X -> P only exists on corridor two: 10 + 1
    assert np.isnan(d[4])                            # on neither corridor


def test_add_direction_single_map_is_unchanged():
    obs = pd.DataFrame({"from_station": ["S0", "S1"], "to_station": ["S1", "S0"]})
    assert list(add_direction(obs, KM)["direction"]) == [1, -1]


def test_pick_references_covers_disjoint_branches():
    def route(t, stops):
        return [dict(train_no=t, step_seq=i, from_station=a, to_station=b, booked_srt_min=10, length_km=10.0)
                for i, (a, b) in enumerate(zip(stops, stops[1:]))]
    routes = pd.DataFrame(route("A", ["a1", "a2", "a3", "a4"]) + route("B", ["b1", "b2", "b3"]) +
                          route("C", ["a1", "a2"]))
    refs = pick_references(routes, ["A", "B", "C"])
    assert refs[0] == "A" and "B" in refs and "C" not in refs      # C adds nothing A doesn't cover
