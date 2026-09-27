import pandas as pd

from src.eval.split import corridor_holdout_split
from src.forecast.data import load_observations, load_km
from src.forecast.horizon import build_horizon_frame, train_forecaster, evaluate

obs = load_observations()
km = load_km()

train_mask, test_mask = corridor_holdout_split(obs, holdout="howrah")
print(f"train: {train_mask.sum()} rows (mumbai + overlap) | test (howrah, unseen): {test_mask.sum()} rows")

for label, groups in [("base", ()), ("base+network+hist", ("network", "hist"))]:
    fc = train_forecaster(obs, km, train_mask.to_numpy(), groups)
    frame = build_horizon_frame(obs, km, groups, fit_mask=train_mask.to_numpy())
    te = frame[test_mask.to_numpy()[frame["k_idx"].to_numpy()]].reset_index(drop=True)
    if te.empty:
        print(f"{label}: no test rows built (Howrah runs may be too short for the horizon window)")
        continue
    preds = fc.predict(te)
    result = evaluate(te, preds)
    o = result["overall"]
    print(f"{label:<20} MAE {o['mae_model']:.2f} min | carry-forward {o['mae_carry']:.2f} | "
          f"gain {o['gain_pct']:+.1f}% (95% range {o['gain_lo']:+.1f} to {o['gain_hi']:+.1f}) | "
          f"window holds {o['coverage']:.0%}, n={o['n']} from {o['n_runs']} runs")