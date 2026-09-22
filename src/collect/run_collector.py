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
RUN_DAYS = OUT_DIR / "_run_days.json"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

MAX_REQUESTS = 46


def load_trains():
    return [ln.strip().zfill(5)
            for ln in TRAIN_LIST.read_text().splitlines() if ln.strip()]


def load_run_days():
    if RUN_DAYS.exists():
        return json.loads(RUN_DAYS.read_text())
    cache = {}
    for f in OUT_DIR.glob("*_20??-??-??.json"):
        try:
            d = json.loads(f.read_text()).get("data") or {}
        except (json.JSONDecodeError, OSError):
            continue
        days = (d.get("train") or {}).get("runDays")
        if days:
            cache[f.name.split("_")[0]] = days
    return cache


def save_run_days(cache):
    RUN_DAYS.write_text(json.dumps(cache, indent=2, sort_keys=True))


def main():
    run_date = sys.argv[1] if len(sys.argv) > 1 else str(date.today() - timedelta(days=1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    trains = load_trains()
    run_days = load_run_days()
    weekday = WEEKDAYS[date.fromisoformat(run_date).weekday()]
    print(f"{len(trains)} trains, date {run_date} ({weekday}), run days known for {len(run_days)}")

    def runs_on_date(t):
        return t not in run_days or weekday in run_days[t]

    to_fetch = [t for t in trains
                if runs_on_date(t) and not (OUT_DIR / f"{t}_{run_date}.json").exists()]
    quota.check(min(len(to_fetch), MAX_REQUESTS))
    print(f"quota: {quota.used()} used, {quota.remaining()} left, {len(to_fetch)} to fetch")

    used = 0
    skipped = 0
    failed = 0
    not_running = 0

    for i, train_no in enumerate(trains, 1):
        path = OUT_DIR / f"{train_no}_{run_date}.json"
        if path.exists():
            skipped += 1
            print(f"[{i}/{len(trains)}] {train_no} skipped, already have it")
            continue
        if not runs_on_date(train_no):
            not_running += 1
            print(f"[{i}/{len(trains)}] {train_no} does not run on {weekday}")
            continue
        if used + failed >= MAX_REQUESTS:
            print(f"[{i}/{len(trains)}] {train_no} STOPPING: reached {MAX_REQUESTS}")
            break
        try:
            payload = fetch_live(train_no, run_date)
            path.write_text(json.dumps(payload, indent=2))
            used += 1
            quota.record(1)
            days = ((payload.get("data") or {}).get("train") or {}).get("runDays")
            if days:
                run_days[train_no] = days
            print(f"[{i}/{len(trains)}] {train_no} ok  ({used} used)")
        except RuntimeError as e:
            print(f"STOPPING: {e}")
            break
        except Exception as e:
            failed += 1
            quota.record(1)
            print(f"[{i}/{len(trains)}] {train_no} failed ({failed} failed): {e}")

        time.sleep(7)

    save_run_days(run_days)

    print(f"\ndone. used {used}, failed {failed}, skipped {skipped}, not running {not_running}")
    print(f"files now in {OUT_DIR}: {len(list(OUT_DIR.glob('*_20??-??-??.json')))}")


if __name__ == "__main__":
    main()