from fastapi.testclient import TestClient

import src.api.main as main


def _payload():
    return {
        "train_no": "12951",
        "train_name": "Demo Train",
        "corridor": "delhi-mumbai",
        "run_date": "2026-09-25",
        "as_of": "2026-09-26T01:00:00+05:30",
        "data_freshness_min": 0,
        "is_live": True,
        "is_mock": False,
        "is_replay": False,
        "replay_note": None,
        "current": {
            "station_code": "RTM",
            "station_name": "Ratlam Jn",
            "delay_min": 11,
            "current_step": 4,
        },
        "stations": [
            {
                "code": "NDLS",
                "name": "New Delhi",
                "scheduled": "08:32",
                "baseline_eta": "08:43",
                "eta_median": "08:40",
                "eta_low": "08:27",
                "eta_high": "09:12",
                "confidence": 0.78,
                "attribution": [],
            }
        ],
        "source": "RailRadar → Sanket forecast_full",
    }


def test_live_endpoint_uses_cache(monkeypatch):
    main._LIVE_CACHE.clear()
    calls = []

    def fake_build(train_no, profile="control"):
        calls.append((train_no, profile))
        return _payload()

    monkeypatch.setattr("src.forecast.live.build_live_payload", fake_build)
    client = TestClient(main.app)

    first = client.get("/eta/12951?live=true")
    second = client.get("/eta/12951?live=true")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == [("12951", "control")]
    assert second.json()["data_freshness_min"] >= 0


def test_live_profile_is_cached_separately(monkeypatch):
    main._LIVE_CACHE.clear()
    calls = []

    def fake_build(train_no, profile="control"):
        calls.append((train_no, profile))
        data = _payload()
        if profile == "app":
            return {
                "train_no": data["train_no"],
                "train_name": data["train_name"],
                "as_of": data["as_of"],
                "is_live": True,
                "stations": [{
                    "code": "NDLS",
                    "name": "New Delhi",
                    "eta_low": "08:27",
                    "eta_high": "09:12",
                    "confidence_label": "medium",
                }],
            }
        return data

    monkeypatch.setattr("src.forecast.live.build_live_payload", fake_build)
    client = TestClient(main.app)

    assert client.get("/eta/12951?live=true").status_code == 200
    assert client.get("/eta/12951?profile=app&live=true").status_code == 200
    assert client.get("/eta/12951?profile=app&live=true").status_code == 200
    assert calls == [("12951", "control"), ("12951", "app")]
