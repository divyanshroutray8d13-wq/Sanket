import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.railradar.in/v1"


def _key():
    k = os.getenv("RAILRADAR_API_KEY")
    if not k:
        raise RuntimeError("RAILRADAR_API_KEY missing from .env")
    return k


def fetch_live(train_no, date=None):
    params = {}
    if date:
        params["date"] = date
    r = requests.get(
        f"{BASE}/trains/{train_no}/live",
        headers={"Authorization": f"Bearer {_key()}"},
        params=params,
        timeout=30,
    )
    if r.status_code == 429:
        raise RuntimeError("rate limited - stop and check quota")
    r.raise_for_status()
    return r.json()