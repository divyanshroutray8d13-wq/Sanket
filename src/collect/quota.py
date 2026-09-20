import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "raw" / "railradar" / "_quota.json"

MONTHLY_LIMIT = 1000
HARD_CEILING = 850


def _load():
    if not LEDGER.exists():
        return {"month": date.today().strftime("%Y-%m"), "used": 0}
    d = json.loads(LEDGER.read_text())
    if d.get("month") != date.today().strftime("%Y-%m"):
        return {"month": date.today().strftime("%Y-%m"), "used": 0}
    return d


def used():
    return _load()["used"]


def remaining():
    return HARD_CEILING - used()


def record(n):
    d = _load()
    d["used"] += n
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=2))
    return d["used"]


def check(planned):
    u = used()
    if u + planned > HARD_CEILING:
        raise RuntimeError(
            f"quota: {u} used, {planned} planned, ceiling {HARD_CEILING}. "
            f"Only {remaining()} left. Reduce the run."
        )
    return u