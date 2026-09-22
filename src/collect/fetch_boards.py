import json
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from src.collect import quota
from src.collect.railradar import fetch_station_board
from src.features.build_features import corridor_km

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
BOARD_DIR = ROOT / "data" / "raw" / "railradar" / "boards"
REFERENCE_TRAIN = "19019"


def corridor_stations(limit):
    obs = pd.read_csv(P / "observations.csv", dtype={"train_no": str})
    routes = pd.read_csv(P / "routes.csv", dtype={"train_no": str})
    km = corridor_km(routes, REFERENCE_TRAIN)
    on_line = obs[obs["from_station"].isin(km)]
    ranked = on_line["from_station"].value_counts()
    print(f"{len(ranked)} corridor stations appear in observations; "
          f"taking the top {min(limit, len(ranked))} by row count "
          f"({ranked.head(limit).sum()} of {len(on_line)} rows covered)")
    return list(ranked.head(limit).index)


def summarise(code, payload):
    trains = (payload.get("data") or {}).get("trains") or []
    with_dep = sum(1 for t in trains if (t.get("stop") or {}).get("departure"))
    kinds = Counter((t.get("stop") or {}).get("stopType") for t in trains)
    return f"{code}: {len(trains)} trains, {with_dep} with a departure time, {dict(kinds)}"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    BOARD_DIR.mkdir(parents=True, exist_ok=True)

    stations = corridor_stations(limit)
    to_fetch = [s for s in stations if not (BOARD_DIR / f"{s}.json").exists()]
    quota.check(len(to_fetch))
    print(f"quota: {quota.used()} used, {quota.remaining()} left, {len(to_fetch)} to fetch\n")

    for code in stations:
        path = BOARD_DIR / f"{code}.json"
        if path.exists():
            print(f"{code}: already have it")
            continue
        try:
            payload = fetch_station_board(code)
            quota.record(1)
            path.write_text(json.dumps(payload, indent=2))
            print(summarise(code, payload))
        except RuntimeError as e:
            print(f"STOPPING: {e}")
            break
        except Exception as e:
            quota.record(1)
            print(f"{code}: failed - {e}")
        time.sleep(7)

    print(f"\nboards on disk: {len(list(BOARD_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()