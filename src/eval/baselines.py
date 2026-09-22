import pandas as pd
import numpy as np
from pathlib import Path

PRED_COLUMNS = ["train_no", "run_date", "step_seq", "from_station", "to_station",
                "y_true", "p10", "p50", "p90"]

def _base_frame(test: pd.DataFrame) -> pd.DataFrame:
    out = test[["train_no", "run_date", "step_seq", "from_station", "to_station"]].copy()
    out["y_true"] = test["minutes_lost"]
    return out

def baseline_zero(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    out = _base_frame(test)
    out["p50"] = 0.0
    out["p10"] = np.percentile(train["minutes_lost"], 10)
    out["p90"] = np.percentile(train["minutes_lost"], 90)
    return out[PRED_COLUMNS]

def baseline_section(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    section_mean = train.groupby(["from_station", "to_station"])["minutes_lost"].mean()
    overall_mean = train["minutes_lost"].mean()

    out = _base_frame(test)
    keys = list(zip(test["from_station"], test["to_station"]))
    out["p50"] = [section_mean.get(k, overall_mean) for k in keys]

    # residuals computed against each row's own section mean (fallback to overall)
    train_section_pred = train.apply(
        lambda r: section_mean.get((r["from_station"], r["to_station"]), overall_mean),
        axis=1,
    )
    residuals = train["minutes_lost"] - train_section_pred
    res10, res90 = np.percentile(residuals, 10), np.percentile(residuals, 90)

    out["p10"] = out["p50"] + res10
    out["p90"] = out["p50"] + res90
    return out[PRED_COLUMNS]