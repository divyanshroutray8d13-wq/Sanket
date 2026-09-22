from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.features.build_features import build_features
from src.features.history import HIST, add_section_history

QUANTILES = (0.1, 0.5, 0.9)
PRED_COLS = ["train_no", "run_date", "step_seq", "from_station",
             "to_station", "y_true", "p10", "p50", "p90"]


def make_params(q, seed=0):
    return dict(objective="quantile", alpha=q, n_estimators=200,
                learning_rate=0.05, num_leaves=15, min_child_samples=20,
                subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                reg_lambda=1.0, random_state=seed, verbose=-1)


def fit_quantiles(X, y, seed=0):
    return {q: LGBMRegressor(**make_params(q, seed)).fit(X, y) for q in QUANTILES}


def predict_quantiles(models, X):
    predictions = np.column_stack([models[q].predict(X) for q in QUANTILES])
    predictions = np.sort(predictions, axis=1)
    return pd.DataFrame(predictions, columns=["p10", "p50", "p90"])


def run_experiment(obs, km, train_mask, test_mask, include_network,
                   departures=None, seed=0, include_history=False):
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    test_mask = np.asarray(test_mask, dtype=bool)
    if np.any(train_mask & test_mask):
        raise ValueError("Some rows are in both train and test sets")

    X, y = build_features(obs, km, include_network=include_network,
                          departures=departures)
    if include_history:
        h = add_section_history(obs, train_mask)
        for col in HIST:
            X[col] = h[col].to_numpy()
    trained_models = fit_quantiles(X[train_mask], y[train_mask], seed=seed)
    predictions = predict_quantiles(trained_models, X[test_mask])

    take_cols = ["train_no", "run_date", "step_seq", "from_station", "to_station"]
    test_rows = obs.loc[test_mask, take_cols].reset_index(drop=True)
    test_rows["y_true"] = y[test_mask].to_numpy()
    return pd.concat([test_rows, predictions], axis=1)[PRED_COLS]


def write_predictions(df, out_dir, name):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.csv"
    df[PRED_COLS].to_csv(out_path, index=False)
    return out_path