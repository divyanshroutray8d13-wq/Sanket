from pathlib import Path

import pandas as pd

from src.features.build_features import NET, build_features, corridor_km, add_direction

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"

obs = pd.read_csv(P / "observations.csv", dtype={"train_no": str})
routes = pd.read_csv(P / "routes.csv", dtype={"train_no": str})

km = corridor_km(routes, "19019")
print(f"reference line covers {len(km)} stations")

d = add_direction(obs, km)
print(f"direction known for {d.direction.notna().mean():.0%} of rows")

X, y = build_features(obs, km, include_network=True)

print("\nhow often each network feature has a value:")
print(X[NET].notna().mean().round(2))

print("\nnetwork feature ranges:")
print(X[NET].describe().round(1))

print("\ncorrelation with minutes_lost:")
print(X.corrwith(y).round(3).sort_values())
