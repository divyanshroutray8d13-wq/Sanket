import json
import shutil

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    shutil.copy("tests/fixtures/mock_12951.json", live_dir / "12951.json")

    corridors_data = [
        {
            "name": "delhi-mumbai",
            "trains": ["12951", "12952"],
            "sections": ["NDLS-KOTA", "KOTA-RTM", "RTM-BRC", "BRC-ST"],
        }
    ]
    # corridors.json now lives OUTSIDE live_dir, matching the real layout
    (tmp_path / "corridors.json").write_text(json.dumps(corridors_data))

    monkeypatch.setenv("SANKET_LIVE_DIR", str(live_dir))
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_control_profile_returns_full_data(client):
    response = client.get("/eta/12951")
    assert response.status_code == 200
    data = response.json()
    assert data["train_no"] == "12951"
    assert "attribution" in data["stations"][0]


def test_app_profile_has_expected_keys(client):
    response = client.get("/eta/12951?profile=app")
    data = response.json()
    assert set(data.keys()) == {"train_no", "train_name", "as_of", "is_live", "stations"}
    station = data["stations"][0]
    assert set(station.keys()) == {"code", "name", "eta_low", "eta_high", "confidence_label"}


def test_board_profile_has_expected_keys(client):
    response = client.get("/eta/12951?profile=board")
    data = response.json()
    assert set(data.keys()) == {"train_no", "train_name", "as_of", "stations"}
    station = data["stations"][0]
    assert set(station.keys()) == {"code", "name", "eta"}


def test_unknown_profile_returns_400(client):
    response = client.get("/eta/12951?profile=bogus")
    assert response.status_code == 400


def test_unknown_train_returns_404(client):
    response = client.get("/eta/99999")
    assert response.status_code == 404


@pytest.mark.parametrize("confidence,expected_label", [
    (0.8, "high"),
    (0.6, "medium"),
    (0.59, "low"),
])
def test_confidence_label_boundaries(confidence, expected_label, tmp_path, monkeypatch):
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    data = json.loads(open("tests/fixtures/mock_12951.json").read())
    data["stations"][0]["confidence"] = confidence
    (live_dir / "12951.json").write_text(json.dumps(data))
    monkeypatch.setenv("SANKET_LIVE_DIR", str(live_dir))

    client = TestClient(app)
    response = client.get("/eta/12951?profile=app")
    assert response.json()["stations"][0]["confidence_label"] == expected_label


@pytest.mark.parametrize("bad_train_no", [
    "abc",
    "1234",
    "123456",
    "12a51",
    "..%5Csecret",
    "12951%0A",
    "١٢٩٥١",  # Arabic-Indic digits — visually similar, not ASCII 0-9
])
def test_invalid_train_no_returns_400(bad_train_no, client):
    response = client.get(f"/eta/{bad_train_no}")
    assert response.status_code == 400


def test_cors_allows_dashboard_origin(client):
    response = client.get(
        "/eta/12951",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_other_origin(client):
    response = client.get(
        "/eta/12951",
        headers={"Origin": "http://evil.com"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_station_finds_train_at_known_station(client):
    response = client.get("/station/ST")
    assert response.status_code == 200
    data = response.json()
    assert any(t["train_no"] == "12951" for t in data)


def test_station_lowercase_code_is_normalized(client):
    response = client.get("/station/st")
    assert response.status_code == 200
    data = response.json()
    assert any(t["train_no"] == "12951" for t in data)


def test_station_empty_for_unknown_station(client):
    response = client.get("/station/ZZZZZ")
    assert response.status_code == 200
    assert response.json() == []


def test_station_invalid_code_returns_400(client):
    response = client.get("/station/!!!!!!!!!")
    assert response.status_code == 400


def test_corridors_returns_file_contents(client):
    response = client.get("/corridors")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "delhi-mumbai"
    assert "12951" in data[0]["trains"]


def test_corridors_missing_file_returns_404(tmp_path, monkeypatch):
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    # no corridors.json created at tmp_path level — on purpose
    monkeypatch.setenv("SANKET_LIVE_DIR", str(live_dir))
    client = TestClient(app)

    response = client.get("/corridors")
    assert response.status_code == 404