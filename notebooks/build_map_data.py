"""
Build the small data file the dashboard's route map needs.

Run from the repo root:
    python notebooks/build_map_data.py

Reads:
    data/raw/datameet_stations.json   station coordinates (CC0, datameet/railways).
    data/raw/datameet_trains.json     every train's line through its stations (CC0), used
                                      to draw sections along the real track.
                                      Both are downloaded automatically the first time.
    data/processed/corridor*_routes.csv   the route of every corridor train
    frontend/public/mock/*.json, data/live/*.json   stations the forecasts mention

Writes:
    frontend/public/geo/map.json
        {"stations": {"ST": [lat, lon, "Surat"], ...},
         "paths":    {"12951": ["BCT", "BVI", "ST", ...], ...},
         "tracks":   {"BVI>ST": [[lat, lon], ...], ...}}

How "tracks" works: every train line in datameet passes through the stations it
runs past, so joined together they form a network that follows the real rails.
For each pair of consecutive stops we take the shortest path through that network.
A non-stop run like Borivali > Surat then bends along the coast through Vapi and
Valsad instead of cutting straight across the sea. Sections with no path in the
network are left out, and the map draws those as straight lines.

Only stations we actually use are kept, so the file stays small.
Re-run it after a new corridor's routes file is built.
"""

from __future__ import annotations

import heapq
import json
import math
import re
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://raw.githubusercontent.com/datameet/railways/master/stations.json"
SOURCE = ROOT / "data" / "raw" / "datameet_stations.json"
TRAINS_URL = "https://raw.githubusercontent.com/datameet/railways/master/trains.json"
TRAINS = ROOT / "data" / "raw" / "datameet_trains.json"
MAX_HOP_KM = 40  # longer hops between neighbouring points are data errors or shortcuts; drop them
SNAP_KM = 3  # a station must be this close to the network to be routed
OUT = ROOT / "frontend" / "public" / "geo" / "map.json"

# Codes that changed after the datameet file was made: our code -> datameet code
ALIASES = {"MMCT": "BCT"}


def nice_name(raw: str) -> str:
    """'VADODARA JN' -> 'Vadodara Junction'."""
    name = " ".join(w.capitalize() for w in raw.strip().split())
    return re.sub(r"\bJn\.?$", "Junction", name)


def download(url: str, path: Path) -> None:
    if not path.exists():
        print(f"Downloading {url.rsplit('/', 1)[-1]} to {path.relative_to(ROOT)} ...")
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, path)


def load_coords(path: Path = SOURCE) -> dict[str, tuple[float, float, str]]:
    download(SOURCE_URL, path)
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    out = {}
    for f in features:
        if not f.get("geometry"):
            continue
        lon, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        out[p["code"]] = (round(lat, 5), round(lon, 5), nice_name(p.get("name") or p["code"]))
    return out


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in km between two (lat, lon) points; flat-earth is fine at these scales."""
    return math.hypot((a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2)))


def track_network(lines: list[list[tuple[float, float]]]) -> dict:
    """Join train lines into one network: point -> {neighbour: km}."""
    adj: dict = {}
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            w = km(a, b)
            if w > MAX_HOP_KM:
                continue
            adj.setdefault(a, {})[b] = w
            adj.setdefault(b, {})[a] = w
    return adj


def load_network(path: Path = TRAINS) -> dict:
    download(TRAINS_URL, path)
    lines = []
    for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
        g = f.get("geometry")
        if g and g["type"] == "LineString":
            lines.append([(round(lat, 5), round(lon, 5)) for lon, lat in g["coordinates"]])
    return track_network(lines)


def snap(point: tuple[float, float], adj: dict) -> tuple[float, float] | None:
    if point in adj:
        return point
    best = min(adj, key=lambda q: km(point, q), default=None)
    return best if best is not None and km(point, best) <= SNAP_KM else None


def shortest_path(adj: dict, a, b) -> list | None:
    dist, prev, heap = {a: 0.0}, {}, [(0.0, a)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == b:
            break
        if d > dist[u]:
            continue
        for v, w in adj[u].items():
            if d + w < dist.get(v, math.inf):
                dist[v], prev[v] = d + w, u
                heapq.heappush(heap, (d + w, v))
    if b not in dist:
        return None
    out = [b]
    while out[-1] != a:
        out.append(prev[out[-1]])
    return out[::-1]


def section_tracks(pairs: set[tuple[str, str]], stations: dict, adj: dict) -> dict[str, list]:
    """'A>B' -> points along the real track from A to B. One direction per pair."""
    tracks = {}
    for a, b in sorted(pairs):
        if f"{b}>{a}" in tracks or a not in stations or b not in stations:
            continue
        na = snap(tuple(stations[a][:2]), adj)
        nb = snap(tuple(stations[b][:2]), adj)
        if na is None or nb is None or na == nb:
            continue
        path = shortest_path(adj, na, nb)
        # A detour far longer than the direct distance means the network has a gap: skip it
        if path and sum(km(p, q) for p, q in zip(path, path[1:])) < 2.5 * km(na, nb) + 20:
            tracks[f"{a}>{b}"] = [[round(lat, 4), round(lon, 4)] for lat, lon in path]
    return tracks


def lookup(code: str, coords: dict) -> tuple[float, float, str] | None:
    return coords.get(code) or coords.get(ALIASES.get(code, ""))


def train_paths(routes: pd.DataFrame) -> dict[str, list[str]]:
    """Ordered station codes for each train: every from_station, then the last to_station."""
    paths = {}
    routes = routes.assign(train_no=routes["train_no"].astype(str).str.zfill(5))
    for no, g in routes.sort_values(["train_no", "step_seq"]).groupby("train_no"):
        codes = g["from_station"].tolist() + [g["to_station"].iloc[-1]]
        paths[no] = codes
    return paths


def forecast_codes(files: list[Path]) -> set[str]:
    codes = set()
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        codes |= {s["code"] for s in d.get("stations", [])}
        if d.get("current", {}).get("station_code"):
            codes.add(d["current"]["station_code"])
    return codes


def forecast_pairs(files: list[Path]) -> set[tuple[str, str]]:
    """Consecutive stops in each forecast, starting from where the train is now."""
    pairs = set()
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        codes = [d.get("current", {}).get("station_code")] + [s["code"] for s in d.get("stations", [])]
        codes = [c for c in codes if c]
        pairs |= set(zip(codes, codes[1:]))
    return pairs


def build(
    coords: dict, routes_files: list[Path], forecast_files: list[Path], adj: dict | None = None
) -> tuple[dict, list[str]]:
    paths = {}
    for f in routes_files:
        paths.update(train_paths(pd.read_csv(f, dtype={"train_no": str})))

    wanted = forecast_codes(forecast_files) | {c for p in paths.values() for c in p}
    stations, missing = {}, []
    for code in sorted(wanted):
        hit = lookup(code, coords)
        if hit:
            stations[code] = list(hit)
        else:
            missing.append(code)
    # The map skips stations it has no coordinates for, so keep paths as they are.
    data = {"stations": stations, "paths": paths}
    if adj:
        pairs = {pair for p in paths.values() for pair in zip(p, p[1:])} | forecast_pairs(forecast_files)
        data["tracks"] = section_tracks(pairs, stations, adj)
    return data, missing


def main() -> None:
    routes_files = sorted((ROOT / "data" / "processed").glob("corridor*_routes.csv"))
    forecast_files = sorted((ROOT / "frontend" / "public" / "mock").glob("*.json")) + sorted(
        (ROOT / "data" / "live").glob("*.json")
    )
    data, missing = build(load_coords(), routes_files, forecast_files, load_network())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"routes files: {', '.join(f.name for f in routes_files) or 'none'}")
    print(
        f"{len(data['stations'])} stations, {len(data['paths'])} train paths, "
        f"{len(data['tracks'])} sections on real track -> {OUT.relative_to(ROOT)}"
    )
    if missing:
        print(f"no coordinates for {len(missing)}: {', '.join(missing)} (add to ALIASES if renamed)")


if __name__ == "__main__":
    main()
