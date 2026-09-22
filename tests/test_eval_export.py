"""
Tests for src/eval/export_results.py

Run:   pytest tests/test_eval_export.py -v
"""

import json

import pandas as pd

from src.eval import export_results
from src.eval.metrics import PRED_COLUMNS


def _write(path, offset):
    ys = (0, 5, -3, 12, 7, -1)
    trains = ("12951", "12951", "12953", "12953", "12909", "12909")
    rows = [[t, "2026-09-19", i, "ST", "BRC", y, y + offset - 8, y + offset, y + offset + 8]
            for i, (t, y) in enumerate(zip(trains, ys))]
    pd.DataFrame(rows, columns=PRED_COLUMNS).to_csv(path, index=False)


def _dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    for exp, off in [("baseline_zero", 9), ("model_base", 4), ("model_network", 1)]:
        _write(d / f"{exp}.csv", off)
    return d


def test_build_has_what_the_page_needs(tmp_path):
    data = export_results.build(_dir(tmp_path, "predictions"))
    assert data["is_sample"] is False
    assert data["n_sections"] == 6 and data["n_train_runs"] == 3
    assert [e["experiment"] for e in data["experiments"]] == ["model_network", "model_base", "baseline_zero"]
    assert data["experiments"][-1]["role"] == "baseline"
    assert data["comparisons"][0]["question"] == "Do network features help?"
    json.dumps(data)  # must be plain JSON


def test_fake_folder_writes_the_sample_file_only(tmp_path, monkeypatch):
    monkeypatch.setattr(export_results, "PUBLIC", tmp_path / "public")
    export_results.main(["x", str(_dir(tmp_path, "predictions_fake"))])
    assert (tmp_path / "public" / "results.sample.json").exists()
    assert not (tmp_path / "public" / "results.json").exists()
