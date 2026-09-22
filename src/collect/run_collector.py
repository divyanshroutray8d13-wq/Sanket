import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from src.collect.railradar import fetch_live
from src.collect import quota

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "railradar"
LISTS_DIR = ROOT / "data" / "processed"
RUN_DAYS = OUT_DIR / "_run_days.json"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

MAX_REQUESTS = 100


def list_path(corridor):
    name = "corridor_trains.txt" if corridor == "main" else f"corridor_{corridor}_trains.txt"
    return LISTS_DIR / name


def available_corridors():
    names = ["main"] if list_path("main").exists() else []
    for f in sorted(LISTS_DIR.glob("corridor_*_trains.txt")):
        names.append(f.name[len("corridor_"):-len("_trains.txt")])
    return names


def load_trains(corridor):
    corridors = available_corridors() if corridor == "all" else [corridor]
    trains = []
    for c in corridors:
        path = list_path(c)
        if not path.exists():
            raise SystemExit(f"no train list for corridor '{c}' ({path.name}). "
                             f"Available: {', '.join(available_corridors())}, all")
        for ln in path.read_text().splitlines():
            t = ln.strip().zfill(5)
            if ln.strip() and t not in trains:
                trains.append(t)
    return trains


def parse_args(argv):
    corridor, run_date = "main", None
    for a in argv:
        try:
            date.fromisoformat(a)
            run_date = a
        except ValueError:
            corridor = a
    return corridor, run_date or str(date.today() - timedelta(days=1))


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
    corridor, run_date = parse_args(sys.argv[1:])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    trains = load_trains(corridor)
    run_days = load_run_days()
    weekday = WEEKDAYS[date.fromisoformat(run_date).weekday()]
    print(f"corridor '{corridor}': {len(trains)} trains, date {run_date} ({weekday}), "
          f"run days known for {sum(t in run_days for t in trains)}")

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