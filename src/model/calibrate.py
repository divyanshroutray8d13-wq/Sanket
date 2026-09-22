import math

import numpy as np
import pandas as pd

from src.features.build_features import build_features
from src.model.train import PRED_COLS, fit_quantiles, predict_quantiles


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


def calibration_split(obs, train_mask):
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    dates = sorted(obs.loc[train_mask, "run_date"].unique())     # training dates only
    if len(dates) < 2:
        raise ValueError("calibration needs at least two training dates")
    cal = train_mask & (obs["run_date"] == dates[-1]).to_numpy()  # latest training day
    return train_mask & ~cal, cal                                 # (proper, cal)


def run_calibrated_experiment(obs, km, train_mask, test_mask, include_network,
                              departures=None, seed=0, target=0.8):
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    test_mask = np.asarray(test_mask, dtype=bool)
    if np.any(train_mask & test_mask):
        raise ValueError("Some rows are in both train and test sets")
    proper, cal = calibration_split(obs, train_mask)
    X, y = build_features(obs, km, include_network=include_network, departures=departures)
    cal_models = fit_quantiles(X[proper], y[proper], seed=seed)
    cal_preds = predict_quantiles(cal_models, X[cal])
    margin = conformal_margin(y[cal], cal_preds["p10"], cal_preds["p90"], target)
    models = fit_quantiles(X[train_mask], y[train_mask], seed=seed)
    preds = widen(predict_quantiles(models, X[test_mask]), margin)

    rows = obs.loc[test_mask, ["train_no", "run_date", "step_seq",
                               "from_station", "to_station"]].reset_index(drop=True)
    rows["y_true"] = y[test_mask].to_numpy()
    return pd.concat([rows, preds], axis=1)[PRED_COLS], margin