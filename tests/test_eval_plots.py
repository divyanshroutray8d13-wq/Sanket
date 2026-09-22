"""
Tests for src/eval/plots.py

Run:   pytest tests/test_eval_plots.py -v
"""

import pandas as pd
import pytest

from src.eval.metrics import PRED_COLUMNS
from src.eval.plots import is_baseline, make_plots, nice_name


def _write(path, p50s, ys=(0, 5, -3, 12)):
    rows = [
        ["12951", "2026-09-19", i, "ST", "BRC", y, p - 8, p, p + 8]
        for i, (y, p) in enumerate(zip(ys, p50s))
    ]
    pd.DataFrame(rows, columns=PRED_COLUMNS).to_csv(path, index=False)


@pytest.fixture
def pred_dir(tmp_path):
    d = tmp_path / "predictions"
    d.mkdir()
    _write(d / "baseline_zero.csv", [0, 0, 0, 0])
    _write(d / "model_network.csv", [1, 4, -2, 10])
    return d


def test_writes_both_charts(pred_dir, tmp_path):
    out = tmp_path / "figs"
    paths = make_plots(pred_dir, out)
    assert [p.name for p in paths] == ["10_ablation_mae.png", "11_coverage.png"]
    for p in paths:
        assert p.exists() and p.stat().st_size > 5_000  # a real image, not an empty file


def test_fake_folder_never_writes_to_docs(tmp_path, monkeypatch):
    import src.eval.plots as plots

    d = tmp_path / "predictions_fake"
    d.mkdir()
    _write(d / "model_network.csv", [1, 4, -2, 10])
    monkeypatch.setattr(plots, "FAKE_OUT", tmp_path / "figures_fake")
    monkeypatch.setattr(plots, "REAL_OUT", tmp_path / "docs_figures")

    paths = make_plots(d)

    assert all(p.parent == tmp_path / "figures_fake" for p in paths)
    assert not (tmp_path / "docs_figures").exists()


def test_empty_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_plots(tmp_path, tmp_path / "figs")


def test_names_and_roles():
    assert nice_name("model_network") == "SANKET, with network features"
    assert nice_name("something_new") == "something_new"
    assert is_baseline("baseline_section")
    assert not is_baseline("model_base")
