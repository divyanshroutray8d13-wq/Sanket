import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from src.collect.railradar import fetch_live
from src.collect import quota

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "railradar"
TRAIN_LIST = ROOT / "data" / "processed" / "corridor_trains.txt"

MAX_REQUESTS = 46


def load_trains():
    return [ln.strip().zfill(5)
            for ln in TRAIN_LIST.read_text().splitlines() if ln.strip()]


def main():
    run_date = sys.argv[1] if len(sys.argv) > 1 else str(date.today() - timedelta(days=1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    trains = load_trains()
    print(f"{len(trains)} trains, date {run_date}")

    to_fetch = [t for t in trains
                if not (OUT_DIR / f"{t}_{run_date}.json").exists()]
    quota.check(min(len(to_fetch), MAX_REQUESTS))
    print(f"quota: {quota.used()} used, {quota.remaining()} left")

    used = 0
    skipped = 0
    failed = 0

    for i, train_no in enumerate(trains, 1):
        path = OUT_DIR / f"{train_no}_{run_date}.json"
        if path.exists():
            skipped += 1
            print(f"[{i}/{len(trains)}] {train_no} skipped ({skipped} skipped)")
            continue
        if used >= MAX_REQUESTS:
            print(f"[{i}/{len(trains)}] {train_no} STOPPING: used {used} >= {MAX_REQUESTS}")
            break
        try:
            payload = fetch_live(train_no, run_date)
            path.write_text(json.dumps(payload, indent=2))
            used += 1
            print(f"[{i}/{len(trains)}] {train_no} ok  ({used} used)")
        except RuntimeError as e:
            print(f"STOPPING: {e}")
            break
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(trains)}] {train_no} failed ({failed} failed): {e}")
            continue

        time.sleep(7)

    print(f"\ndone. requests used {used}, skipped {skipped}, failed {failed}")
    print(f"files now in {OUT_DIR}: {len(list(OUT_DIR.glob('*.json')))}")

    if used:
        print(f"quota now: {quota.record(used)} used")


if __name__ == "__main__":
    main()