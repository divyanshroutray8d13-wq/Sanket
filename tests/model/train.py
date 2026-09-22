from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.features.build_features import build_features

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
                   departures=None, seed=0):
    obs=obs.reset_index(drop=True)
    train_mask = train_mask.to_numpy()
    test_mask = test_mask.to_numpy()
    if np.any(train_mask & test_mask):
        raise ValueError("Some rows are in both train and test sets")
    fit_X, fit_y = build_features(obs[train_mask], km, include_network=include_network,
                                departures=departures)
    trained_models = fit_quantiles(fit_X, fit_y, seed=seed)
    test_X, _ = build_features(obs[test_mask], km, include_network=include_network, departures=departures)
    predictions = predict_quantiles(trained_models, test_X)
    take_cols = ["train_no", "run_date", "step_seq", "from_station", "to_station"]
    test_rows = obs[test_mask].reset_index(drop=True)[take_cols]
    return pd.concat([test_rows, predictions], axis=1).assign(y_true=obs[test_mask].reset_index(drop=True)["minutes_lost"]) 


def write_predictions(df, out_dir, name):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.csv"
    df[PRED_COLS].to_csv(out_path, index=False)
    return out_path
   