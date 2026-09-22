import numpy as np
import pandas as pd
import pytest

from src.model.train import (
    QUANTILES, PRED_COLS, make_params, fit_quantiles, predict_quantiles,
    run_experiment, write_predictions,
)

KM = {"AAA": 0.0, "BBB": 50.0, "CCC": 120.0}


# ---------------------------------------------------------------- synthetic data

def synthetic_obs(n=360, seed=1):

    rng = np.random.default_rng(seed)
    days = ["2026-09-17", "2026-09-18", "2026-09-19"]
    rows = []
    for i in range(n):
        day = days[i % 3]
        minute = int(rng.integers(0, 24 * 60))
        delay = int(rng.integers(0, 40))
        frm, to = [("AAA", "BBB"), ("BBB", "CCC"), ("CCC", "BBB")][i % 3]
        lost = round(-0.3 * delay + rng.normal(0, 2), 0)
        rows.append(dict(
            train_no=f"{10000 + i:05d}",
            train_category="Premium" if i % 5 == 0 else "Express",
            run_date=day, step_seq=i % 7, from_station=frm, to_station=to,
            booked_srt_min=40 + i % 30, actual_srt_min=40, minutes_lost=lost,
            length_km=50.0, dep_delay_min=delay,
            dep_time=f"{day}T{minute // 60:02d}:{minute % 60:02d}:00+05:30",
            arr_time=f"{day}T{minute // 60:02d}:{minute % 60:02d}:00+05:30",
        ))
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def obs():
    return synthetic_obs()


@pytest.fixture(scope="module")
def masks(obs):
    test = (obs.run_date == "2026-09-19").to_numpy()
    return ~test, test


class Const:
    def __init__(self, v):
        self.v = v

    def predict(self, X):
        return np.full(len(X), self.v, dtype=float)


# ---------------------------------------------------------------- make_params

@pytest.mark.parametrize("q", QUANTILES)
def test_params_are_quantile(q):
    p = make_params(q)
    assert p["objective"] == "quantile"
    assert p["alpha"] == q


def test_params_guard_against_small_data():
    p = make_params(0.5)
    assert p["num_leaves"] <= 31
    assert p["min_child_samples"] >= 20


def test_params_seeded_and_quiet():
    p = make_params(0.5, seed=7)
    assert p["random_state"] == 7
    assert p["verbose"] == -1


# ---------------------------------------------------------------- predict_quantiles

def test_predict_columns_and_length():
    X = pd.DataFrame({"a": range(5)})
    models = {0.1: Const(1), 0.5: Const(2), 0.9: Const(3)}
    out = predict_quantiles(models, X)
    assert list(out.columns) == ["p10", "p50", "p90"]
    assert len(out) == 5
    assert list(out.index) == list(range(5))


def test_predict_fixes_quantile_crossing():
    X = pd.DataFrame({"a": [0, 1]})
    models = {0.1: Const(5), 0.5: Const(3), 0.9: Const(1)}
    out = predict_quantiles(models, X)
    assert out.p10.tolist() == [1, 1]
    assert out.p50.tolist() == [3, 3]
    assert out.p90.tolist() == [5, 5]


# ---------------------------------------------------------------- fit_quantiles

def test_fit_returns_one_model_per_quantile():
    X = pd.DataFrame({"x": np.arange(200, dtype=float)})
    y = pd.Series(np.arange(200, dtype=float))
    models = fit_quantiles(X, y)
    assert set(models) == set(QUANTILES)


def test_median_model_learns_a_real_signal():
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 10, 800)
    y = 3 * x + rng.normal(0, 1, 800)
    X = pd.DataFrame({"x": x})
    models = fit_quantiles(X[:600], pd.Series(y[:600]))
    p = predict_quantiles(models, X[600:])
    mae_model = np.abs(p.p50 - y[600:]).mean()
    mae_mean = np.abs(y[:600].mean() - y[600:]).mean()
    assert mae_model < 0.5 * mae_mean


def test_interval_actually_covers_something():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 10, 1000)
    y = x + rng.normal(0, 2, 1000)
    X = pd.DataFrame({"x": x})
    models = fit_quantiles(X[:700], pd.Series(y[:700]))
    p = predict_quantiles(models, X[700:])
    cover = ((y[700:] >= p.p10) & (y[700:] <= p.p90)).mean()
    assert 0.55 <= cover <= 0.97


def test_handles_missing_values():
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 10, 300)
    x[::3] = np.nan
    X = pd.DataFrame({"x": x})
    y = pd.Series(rng.normal(0, 1, 300))
    out = predict_quantiles(fit_quantiles(X, y), X)
    assert out.notna().all().all()


# ---------------------------------------------------------------- run_experiment

def test_experiment_output_contract(obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=False)
    assert list(out.columns) == PRED_COLS
    assert len(out) == te.sum()


def test_experiment_only_returns_test_rows(obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=False)
    assert set(out.run_date) == {"2026-09-19"}


def test_experiment_y_true_is_minutes_lost(obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=False)
    expected = obs.loc[te, "minutes_lost"].astype(float).tolist()
    assert out.y_true.tolist() == expected


def test_experiment_no_crossing(obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=True)
    assert (out.p10 <= out.p50).all() and (out.p50 <= out.p90).all()


def test_experiment_with_network_runs(obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=True)
    assert out[["p10", "p50", "p90"]].notna().all().all()


def test_no_leakage_from_test_labels(obs, masks):
    tr, te = masks
    a = run_experiment(obs, KM, tr, te, include_network=True)
    scrambled = obs.copy()
    scrambled.loc[te, "minutes_lost"] = 999
    b = run_experiment(scrambled, KM, tr, te, include_network=True)
    pd.testing.assert_frame_equal(a[["p10", "p50", "p90"]],
                                  b[["p10", "p50", "p90"]])


def test_overlapping_masks_rejected(obs):
    both = np.ones(len(obs), dtype=bool)
    with pytest.raises(ValueError):
        run_experiment(obs, KM, both, both, include_network=False)


def test_reproducible(obs, masks):
    tr, te = masks
    a = run_experiment(obs, KM, tr, te, include_network=True, seed=3)
    b = run_experiment(obs, KM, tr, te, include_network=True, seed=3)
    pd.testing.assert_frame_equal(a, b)


def test_model_beats_zero_on_learnable_data(obs, masks):

    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=False)
    mae_model = (out.p50 - out.y_true).abs().mean()
    mae_zero = out.y_true.abs().mean()
    assert mae_model < mae_zero


# ---------------------------------------------------------------- write_predictions

def test_write_creates_dir_and_file(tmp_path, obs, masks):
    tr, te = masks
    out = run_experiment(obs, KM, tr, te, include_network=False)
    path = write_predictions(out, tmp_path / "predictions", "model_base")
    assert path.exists()
    back = pd.read_csv(path, dtype={"train_no": str})
    assert list(back.columns) == PRED_COLS
    assert len(back) == len(out)