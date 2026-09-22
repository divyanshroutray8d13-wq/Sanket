import json
from pathlib import Path
import shutil
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    shutil.copy("data/live/12951.json", live_dir / "12951.json")
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
    data = json.loads(Path("data/live/12951.json").read_text())
    data["stations"][0]["confidence"] = confidence
    (live_dir / "12951.json").write_text(json.dumps(data))
    monkeypatch.setenv("SANKET_LIVE_DIR", str(live_dir))

    client = TestClient(app)
    response = client.get("/eta/12951?profile=app")
    assert response.json()["stations"][0]["confidence_label"] == expected_label