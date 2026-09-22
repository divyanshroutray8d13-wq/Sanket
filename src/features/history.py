import numpy as np
import pandas as pd

SEC_KEYS = ["from_station", "to_station"]       
RUN_KEYS = ["train_no", "run_date"]            
HIST = ["sec_hist_mean", "sec_hist_n"]           


def add_section_history(obs, train_mask, min_count=3):
    obs = obs.reset_index(drop=True).copy()     
    train_mask = np.asarray(train_mask, dtype=bool)
    train = obs[train_mask]                     


    sec = train.groupby(SEC_KEYS)["minutes_lost"].agg(sec_sum="sum", sec_cnt="count")

    run = train.groupby(SEC_KEYS + RUN_KEYS)["minutes_lost"].agg(run_sum="sum", run_cnt="count")

    joined = obs.join(sec, on=SEC_KEYS).join(run, on=SEC_KEYS + RUN_KEYS)
    total = joined["sec_sum"].fillna(0).to_numpy()
    count = joined["sec_cnt"].fillna(0).to_numpy()

    own_sum = np.where(train_mask, joined["run_sum"].fillna(0), 0)
    own_cnt = np.where(train_mask, joined["run_cnt"].fillna(0), 0)
    total = total - own_sum
    count = count - own_cnt

    obs["sec_hist_n"] = count.astype(int)
    safe = np.where(count > 0, count, 1)         
    obs["sec_hist_mean"] = np.where(count >= min_count, total / safe, np.nan)
    return obs