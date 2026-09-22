import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "data" / "processed" / "predictions"
KEY = ["train_no", "run_date", "step_seq"]

a_name, b_name = (sys.argv[1:3] if len(sys.argv) >= 3
                  else ("model_base", "model_network"))
a = pd.read_csv(PRED / f"{a_name}.csv", dtype={"train_no": str})
b = pd.read_csv(PRED / f"{b_name}.csv", dtype={"train_no": str})
m = a.merge(b, on=KEY, suffixes=("_a", "_b"))
if len(m) != len(a) or len(m) != len(b):
    print(f"WARNING: files cover different rows ({len(a)}, {len(b)}, {len(m)} shared)")

err_a = (m["p50_a"] - m["y_true_a"]).abs().to_numpy()
err_b = (m["p50_b"] - m["y_true_a"]).abs().to_numpy()
diff = err_b - err_a                      # negative = B better on that row

rng = np.random.default_rng(0)
n = len(diff)
boot = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(5000)])
lo, hi = np.percentile(boot, [2.5, 97.5])

print(f"rows compared:      {n}")
print(f"MAE {a_name:<22}{err_a.mean():.2f}")
print(f"MAE {b_name:<22}{err_b.mean():.2f}")
print(f"difference (B - A): {diff.mean():+.2f} min   95% interval [{lo:+.2f}, {hi:+.2f}]")
print(f"B better in {(boot < 0).mean():.0%} of resamples")
print()
if hi < 0:
    print(f"VERDICT: {b_name} is genuinely better.")
elif lo > 0:
    print(f"VERDICT: {b_name} is genuinely worse.")
else:
    print("VERDICT: no detectable difference - the interval includes zero.")