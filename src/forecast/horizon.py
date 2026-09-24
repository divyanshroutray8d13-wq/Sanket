"""Direct multi-horizon ETA model.

Question answered: a train has just left station k with delay d0. How late will
it be when it reaches the halt h stops ahead?

The model predicts `arrival delay at stop k+h  minus  d0` straight from what is
known at station k. It does NOT chain section forecasts: chaining piles up
errors and, on our data, loses to "carry the current delay forward" beyond
about six stops. Predicting the far stop directly does not.

Feature groups (choose any):
  base     (always) delay now, position, time of day, next section, h, booked time
  network  who is ahead of this train at station k (NET features)
  sched    timetable density from the station boards (needs boards)
  hist     what these sections usually cost (leave-one-run-out, training only)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.features.build_features import BASE, NET, build_features
from src.features.history import add_section_history
from src.features.schedule import SCHED
from src.model.calibrate import calibration_split, conformal_margin

MAX_H = 20
QUANTILES = (0.1, 0.5, 0.9)
GROUPS = ("network", "sched", "hist")
BUCKET_TOPS = (1, 3, 6, 10, MAX_H)
BUCKET_LABELS = ("next stop", "2-3 stops", "4-6 stops", "7-10 stops", "11-20 stops")
HORIZON_COLS = ["h", "cum_booked"]
HIST_H = ["cum_hist_mean", "cum_hist_cov"]

# Which plain-English cause each feature is reported under. The wording matters:
# the dashboard colours causes by matching words in these labels (see causes.js).
CAUSE = {
    "dep_delay_min": "usual drift for a delay this size",
    "h": "run length and timetable",
    "cum_booked": "run length and timetable",
    "booked_srt_min": "run length and timetable",
    "length_km": "run length and timetable",
    "step_seq": "run length and timetable",
    "hour": "time of day and train type",
    "dow": "time of day and train type",
    "is_premium": "time of day and train type",
    "headway_prev_min": "train ahead running late",
    "prev_train_delay": "train ahead running late",
    "prev_train_premium": "train ahead running late",
    "n_prev_30": "train ahead running late",
    "sched_before_30": "busy stretch of line",
    "sched_after_30": "busy stretch of line",
    "cum_hist_mean": "usual behaviour of these sections",
    "cum_hist_cov": "usual behaviour of these sections",
}
BIAS_CAUSE = "typical change on this corridor"


def parse_groups(text) -> tuple:
    """'network,hist' -> ('network', 'hist'). 'base' or '' -> ()."""
    if not text or text == "base":
        return ()
    parts = [p.strip() for p in str(text).replace("+", ",").split(",") if p.strip()]
    parts = [p for p in parts if p != "base"]
    bad = [p for p in parts if p not in GROUPS]
    if bad:
        raise ValueError(f"unknown feature group {bad}; choose from base, {', '.join(GROUPS)}")
    return tuple(g for g in GROUPS if g in parts)


def feature_columns(groups=()) -> list:
    cols = list(BASE) + HORIZON_COLS
    if "network" in groups:
        cols += NET
    if "sched" in groups:
        cols += SCHED
    if "hist" in groups:
        cols += HIST_H
    return cols


def bucket_index(h) -> np.ndarray:
    return np.minimum(np.searchsorted(BUCKET_TOPS, np.asarray(h), side="left"),
                      len(BUCKET_TOPS) - 1)


def _epoch_min(ts) -> np.ndarray:
    return ((ts - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds() / 60).to_numpy()


# ----------------------------------------------------------------------------
# Dataset
# ----------------------------------------------------------------------------
def build_horizon_frame(obs, km, groups=(), fit_mask=None, departures=None, max_h=MAX_H):
    """One row per (as-of section k, target section j) inside the same train run.

    `fit_mask` (rows of obs the model may learn from) is needed for `hist`, which
    is computed leave-one-run-out from those rows only.
    Columns: meta (train_no, run_date, k_idx, j_idx, k_step, j_step, to_station),
    the features, `d0`, `true_delay` (arrival delay at the target) and `target`
    (= true_delay - d0, what the model predicts).
    """
    o = obs.reset_index(drop=True)
    groups = tuple(groups)
    if "sched" in groups and departures is None:
        raise ValueError("feature group 'sched' needs station-board departures")
    if "hist" in groups and fit_mask is None:
        raise ValueError("feature group 'hist' needs fit_mask")

    need_net = bool({"network", "sched"} & set(groups))
    X, _ = build_features(o, km, include_network=need_net,
                          departures=departures if "sched" in groups else None)

    dep = pd.to_datetime(o["dep_time"], utc=True)
    arr = pd.to_datetime(o["arr_time"], utc=True)
    d_dep = o["dep_delay_min"].to_numpy(float)
    arr_delay = d_dep + o["minutes_lost"].to_numpy(float)
    sched_dep = _epoch_min(dep) - d_dep
    sched_arr = _epoch_min(arr) - arr_delay
    steps = o["step_seq"].to_numpy(int)

    hist = None
    if "hist" in groups:
        hist = add_section_history(o, fit_mask)["sec_hist_mean"].to_numpy(float)

    ks, js, hs, cum_booked, cum_hist, cov_hist = [], [], [], [], [], []
    for _, idx in o.groupby(["train_no", "run_date"], sort=False).indices.items():
        idx = idx[np.argsort(steps[idx], kind="stable")]
        n = len(idx)
        if hist is not None:
            hv = hist[idx]
            have = ~np.isnan(hv)
            prefix = np.concatenate([[0.0], np.cumsum(np.where(have, hv, 0.0))])
            prefix_n = np.concatenate([[0], np.cumsum(have)])
        for a in range(n):
            for b in range(a, n):
                h = steps[idx[b]] - steps[idx[a]] + 1
                if h > max_h:
                    break
                ks.append(idx[a])
                js.append(idx[b])
                hs.append(h)
                cum_booked.append(sched_arr[idx[b]] - sched_dep[idx[a]])
                if hist is not None:
                    cum_hist.append(prefix[b + 1] - prefix[a])
                    cov_hist.append((prefix_n[b + 1] - prefix_n[a]) / (b - a + 1))

    k = np.asarray(ks, dtype=int)
    j = np.asarray(js, dtype=int)
    frame = pd.DataFrame({
        "train_no": o["train_no"].to_numpy()[k],
        "run_date": o["run_date"].to_numpy()[k],
        "k_idx": k, "j_idx": j,
        "k_step": steps[k], "j_step": steps[j],
        "to_station": o["to_station"].to_numpy()[j],
        "h": np.asarray(hs, dtype=float),
        "cum_booked": np.asarray(cum_booked, dtype=float),
    })
    frame = pd.concat([frame, X.iloc[k].reset_index(drop=True)], axis=1)
    if hist is not None:
        frame["cum_hist_mean"] = np.asarray(cum_hist, dtype=float)
        frame["cum_hist_cov"] = np.asarray(cov_hist, dtype=float)
    frame["d0"] = d_dep[k]
    frame["true_delay"] = arr_delay[j]
    frame["target"] = frame["true_delay"] - frame["d0"]
    return frame


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------
def _params(q, seed=0):
    return dict(objective="quantile", alpha=q, n_estimators=200, learning_rate=0.05,
                num_leaves=15, min_child_samples=30, subsample=0.8, subsample_freq=1,
                colsample_bytree=0.8, reg_lambda=1.0, random_state=seed, verbose=-1)


def fit_models(frame, feats, seed=0) -> dict:
    return {q: LGBMRegressor(**_params(q, seed)).fit(frame[feats], frame["target"])
            for q in QUANTILES}


def raw_predict(models, X) -> pd.DataFrame:
    cols = np.sort(np.column_stack([models[q].predict(X) for q in QUANTILES]), axis=1)
    return pd.DataFrame(cols, columns=["p10", "p50", "p90"], index=X.index)


@dataclass
class Forecaster:
    models: dict
    feats: list
    groups: tuple
    margins: list            # conformal margin (minutes) per horizon bucket
    train_dates: list
    target: float = 0.8
    coverage: list | None = None   # held-out share of windows that held the real arrival, per bucket

    def confidence(self, h) -> np.ndarray:
        """Chance the real arrival falls inside the window, by horizon bucket.

        Measured on held-out data when train.py has filled `coverage`; the
        calibration target otherwise.
        """
        c = np.asarray(self.coverage if self.coverage is not None
                       else [self.target] * len(BUCKET_TOPS), dtype=float)
        return np.clip(c[bucket_index(h)], 0.0, 0.95)

    def predict(self, frame) -> pd.DataFrame:
        """Calibrated p10 / p50 / p90 of (arrival delay - d0), in minutes."""
        p = raw_predict(self.models, frame[self.feats])
        m = np.asarray(self.margins)[bucket_index(frame["h"])]
        p["p10"] = np.minimum(p["p10"] - m, p["p50"])
        p["p90"] = np.maximum(p["p90"] + m, p["p50"])
        return p

    def contributions(self, frame) -> pd.DataFrame:
        """Minutes each cause moved the median forecast (sums to the raw p50).

        Uses LightGBM's built-in exact SHAP values. Columns are the plain-English
        causes; negative means the model expects the train to make up time.
        """
        raw = self.models[0.5].booster_.predict(frame[self.feats], pred_contrib=True)
        out = {}
        for i, feat in enumerate(self.feats):
            label = CAUSE.get(feat, "other")
            out[label] = out.get(label, 0.0) + raw[:, i]
        out[BIAS_CAUSE] = raw[:, -1]
        return pd.DataFrame(out, index=frame.index)


def train_forecaster(obs, km, train_mask, groups=(), departures=None, seed=0,
                     target=0.8, min_bucket_rows=30) -> Forecaster:
    """Fit on the training rows, then calibrate the window on the last training day.

    Two fits, as in src/model/calibrate.py: one without the last training day to
    measure how wrong the raw window is on unseen data, and a final one on all
    training days. Test rows are never touched.
    """
    obs = obs.reset_index(drop=True)
    train_mask = np.asarray(train_mask, dtype=bool)
    groups = tuple(groups)
    feats = feature_columns(groups)
    proper, cal = calibration_split(obs, train_mask)

    frame = build_horizon_frame(obs, km, groups, fit_mask=proper, departures=departures)
    rows_in = lambda f, mask: f[mask[f["k_idx"].to_numpy()]]
    cal_rows = rows_in(frame, cal)
    stage1 = fit_models(rows_in(frame, proper), feats, seed)
    raw = raw_predict(stage1, cal_rows[feats])

    pooled = conformal_margin(cal_rows["target"], raw["p10"], raw["p90"], target)
    b = bucket_index(cal_rows["h"])
    margins = []
    for i in range(len(BUCKET_TOPS)):
        sel = b == i
        margins.append(conformal_margin(cal_rows["target"][sel], raw["p10"][sel],
                                        raw["p90"][sel], target)
                       if sel.sum() >= min_bucket_rows else pooled)

    if "hist" in groups:
        frame = build_horizon_frame(obs, km, groups, fit_mask=train_mask,
                                    departures=departures)
    models = fit_models(rows_in(frame, train_mask), feats, seed)
    dates = sorted(obs.loc[train_mask, "run_date"].unique().tolist())
    return Forecaster(models, feats, groups, margins, dates, target)


# ----------------------------------------------------------------------------
# Evaluation: ETA error by how far ahead, against carrying the delay forward
# ----------------------------------------------------------------------------
def evaluate(frame, preds, n_boot=2000, seed=0) -> dict:
    """ETA error by horizon. Baseline: arrival delay = delay right now.

    `frame` and `preds` are aligned. Error in minutes is |predicted - actual|
    arrival time, which equals |p50 - target| because both share d0.
    """
    f = frame.reset_index(drop=True)
    p = preds.reset_index(drop=True)
    err_m = (p["p50"] - f["target"]).abs()
    err_c = f["target"].abs()
    inside = (f["target"] >= p["p10"]) & (f["target"] <= p["p90"])
    width = p["p90"] - p["p10"]
    b = bucket_index(f["h"])

    rows = []
    for i, label in enumerate(BUCKET_LABELS):
        s = b == i
        if not s.any():
            continue
        rows.append(dict(bucket=label, n=int(s.sum()),
                         mae_model=float(err_m[s].mean()), mae_carry=float(err_c[s].mean()),
                         coverage=float(inside[s].mean()), width=float(width[s].mean())))
    for r in rows:
        r["gain_pct"] = 100 * (1 - r["mae_model"] / r["mae_carry"])

    overall = dict(n=len(f), mae_model=float(err_m.mean()), mae_carry=float(err_c.mean()),
                   coverage=float(inside.mean()), width=float(width.mean()))
    overall["gain_pct"] = 100 * (1 - overall["mae_model"] / overall["mae_carry"])

    # Resample whole train runs: rows of one run share its delays.
    g = pd.DataFrame({"run": f["train_no"] + "|" + f["run_date"], "m": err_m, "c": err_c})
    sums = g.groupby("run").agg(m=("m", "sum"), c=("c", "sum"), n=("m", "size"))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(sums), size=(n_boot, len(sums)))
    m, c = sums["m"].to_numpy()[pick].sum(1), sums["c"].to_numpy()[pick].sum(1)
    gain = 100 * (1 - m / c)
    overall["gain_lo"], overall["gain_hi"] = (float(x) for x in np.percentile(gain, [2.5, 97.5]))
    overall["n_runs"] = int(len(sums))
    return dict(buckets=rows, overall=overall)
