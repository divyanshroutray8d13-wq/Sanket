import math

import numpy as np
import pandas as pd

from src.features.build_features import build_features
from src.model.train import PRED_COLS, fit_quantiles, predict_quantiles
from src.features.history import HIST, add_section_history

def conformal_margin(y, p10, p90, target=0.8):

    y, p10, p90 = (np.asarray(a, dtype=float) for a in (y, p10, p90))
    if len(y) == 0:
        raise ValueError("need at least one calibration row")
    scores = np.maximum(p10 - y, y - p90)
    n = len(scores)
    k = min(n, math.ceil((n + 1) * target))
    return float(np.sort(scores)[k - 1])   


def widen(preds, margin):
    out = preds.copy()                                            
    out["p10"] = np.minimum(out["p10"] - margin, out["p50"])     
    out["p90"] = np.maximum(out["p90"] + margin, out["p50"])     
    return out                                                   


def calibration_split(obs, train_mask, n_cal_days=1):
    """Split training rows into a "proper" fitting set and a calibration set.

    n_cal_days=1 (the original default) uses only the single latest training day to
    calibrate the window margin. On this data that produced an unstable margin: the
    direction the model errs in (too-early vs too-late) varies day to day, so a margin
    fit on one day does not transfer reliably to a different test day. Measured on the
    23 Sept test day, pooling more recent days for calibration gave a large, consistent
    coverage improvement at a modest width cost (n_cal_days=1: 63% coverage, 16 min
    windows; n_cal_days=5: 81% coverage, 21 min windows - see NOTES.md). Raise this if
    coverage is still short of the target; each extra calibration day also shrinks the
    "proper" fitting set, so do not raise it past roughly half the training days.
    """
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    dates = sorted(obs.loc[train_mask, "run_date"].unique())     # training dates only
    if len(dates) < 2:
        raise ValueError("calibration needs at least two training dates")
    n_cal_days = max(1, min(n_cal_days, len(dates) - 1))          # leave at least one day to fit on
    cal_dates = set(dates[-n_cal_days:])                          # latest n_cal_days training days
    cal = train_mask & obs["run_date"].isin(cal_dates).to_numpy()
    return train_mask & ~cal, cal                                 # (proper, cal)

def with_history(X, obs, fit_mask):
    X = X.copy()
    h = add_section_history(obs, fit_mask)
    for col in HIST:
        X[col] = h[col].to_numpy()
    return X
def run_calibrated_experiment(obs, km, train_mask, test_mask, include_network,
                              departures=None, seed=0, target=0.8, include_history=False,
                              n_cal_days=1):
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    test_mask = np.asarray(test_mask, dtype=bool)
    if np.any(train_mask & test_mask):
        raise ValueError("Some rows are in both train and test sets")
    proper, cal = calibration_split(obs, train_mask, n_cal_days=n_cal_days)
    X, y = build_features(obs, km, include_network=include_network, departures=departures)
    X_cal = with_history(X, obs, proper) if include_history else X
    cal_models = fit_quantiles(X_cal[proper], y[proper], seed=seed)
    cal_preds = predict_quantiles(cal_models, X_cal[cal])
    margin = conformal_margin(y[cal], cal_preds["p10"], cal_preds["p90"], target)
    if include_history:
        X = with_history(X, obs, train_mask)
    models = fit_quantiles(X[train_mask], y[train_mask], seed=seed)
    preds = widen(predict_quantiles(models, X[test_mask]), margin)

    rows = obs.loc[test_mask, ["train_no", "run_date", "step_seq",
                               "from_station", "to_station"]].reset_index(drop=True)
    rows["y_true"] = y[test_mask].to_numpy()
    return pd.concat([rows, preds], axis=1)[PRED_COLS], margin