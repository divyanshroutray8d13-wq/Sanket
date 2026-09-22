import json

import pandas as pd

from notebooks.build_map_data import build, nice_name, train_paths


def test_nice_name():
    assert nice_name("VADODARA JN") == "Vadodara Junction"
    assert nice_name("  SURAT ") == "Surat"


def test_train_paths_orders_steps_and_adds_last_stop():
    routes = pd.DataFrame(
        {"train_no": ["12951"] * 3, "step_seq": [2, 0, 1],
         "from_station": ["BRC", "BCT", "ST"], "to_station": ["RTM", "ST", "BRC"]}
    )
    assert train_paths(routes) == {"12951": ["BCT", "ST", "BRC", "RTM"]}


def test_build_uses_aliases_and_reports_missing(tmp_path):
    coords = {"BCT": (18.97, 72.82, "Mumbai Central"), "ST": (21.2, 72.84, "Surat")}
    routes = tmp_path / "corridor_routes.csv"
    pd.DataFrame({"train_no": ["12953"], "step_seq": [0], "from_station": ["MMCT"], "to_station": ["ST"]}).to_csv(routes, index=False)
    mock = tmp_path / "12953.json"
    mock.write_text(json.dumps({"current": {"station_code": "MMCT"}, "stations": [{"code": "ST"}, {"code": "XYZ"}]}))

    data, missing = build(coords, [routes], [mock])
    assert data["paths"] == {"12953": ["MMCT", "ST"]}
    assert data["stations"]["MMCT"] == [18.97, 72.82, "Mumbai Central"]
    assert missing == ["XYZ"]


def test_sections_follow_the_network_not_a_straight_line():
    from notebooks.build_map_data import section_tracks, track_network

    # A coast line A - X - B, with no direct A-B link: the section must bend through X
    a, x, b = (19.0, 72.8), (19.2, 73.0), (19.4, 72.8)  # hops of about 30 km
    adj = track_network([[a, x, b]])
    stations = {"A": [*a, "A"], "B": [*b, "B"], "C": [25.0, 80.0, "Far away"]}
    tracks = section_tracks({("A", "B"), ("B", "A"), ("A", "C")}, stations, adj)
    assert tracks == {"A>B": [[19.0, 72.8], [19.2, 73.0], [19.4, 72.8]]}  # one direction; C not on network
