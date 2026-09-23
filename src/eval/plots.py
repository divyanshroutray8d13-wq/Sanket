"""
Charts for the ablation result, for the deck and docs/results.md.

    10_ablation_mae.png   MAE per experiment (the headline slide)
    11_coverage.png       how often the real value fell inside the window,
                          against the 0.80 target, with each window's width

Run:
    python -m src.eval.plots                                  # real results -> docs/figures/
    python -m src.eval.plots data/processed/predictions_fake  # practice run

A folder with "fake" in its name is treated as practice data: charts are
stamped FAKE DATA and saved to data/processed/figures_fake/ (gitignored), so
they can never end up in docs/figures/ or the PPT by accident.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only, never open a window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.eval.metrics import DEFAULT_PRED_DIR, ablation_table  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REAL_OUT = ROOT / "docs" / "figures"
FAKE_OUT = ROOT / "data" / "processed" / "figures_fake"

COVERAGE_TARGET = 0.80

# Two roles, not a rainbow: baselines are neutral, SANKET models carry the accent.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3de"
BASELINE_COLOR = "#a8a69e"
MODEL_COLOR = "#2a78d6"
FAKE_COLOR = "#c0392b"

# Plain-English names for the slide. Anything else shows its file name.
NICE_NAMES = {
    "baseline_zero": "Baseline: keeps current delay",
    "baseline_section": "Baseline: section average",
    "model_base": "SANKET, no network features",
    "model_network": "SANKET, with network features",
    "model_network_sched": "SANKET, network + timetable",
    "model_base_hist": "SANKET, plus section history",
}
# Experiments ending in _cal have calibrated windows: the same p50, widened p10-p90.
CALIBRATED = "_cal"


def nice_name(experiment: str) -> str:
    if experiment.endswith(CALIBRATED):
        return f"{nice_name(experiment[: -len(CALIBRATED)])} (tuned window)"
    return NICE_NAMES.get(experiment, experiment)


def is_baseline(experiment: str) -> bool:
    return experiment.startswith("baseline")


def _style(ax, fig) -> None:
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=TEXT_2, labelsize=10, length=0)
    ax.tick_params(axis="y", colors=TEXT, labelsize=11, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def _titles(fig, title: str, subtitle: str, fake: bool) -> None:
    fig.text(0.02, 0.96, title, fontsize=15, weight="bold", color=TEXT, va="top")
    fig.text(0.02, 0.885, subtitle, fontsize=10.5, color=TEXT_2, va="top")
    if fake:
        fig.text(0.98, 0.96, "FAKE DATA - not a result", fontsize=10.5, weight="bold",
                 color=FAKE_COLOR, va="top", ha="right")


def _legend(fig, table: pd.DataFrame) -> None:
    roles = {is_baseline(e) for e in table["experiment"]}
    if len(roles) < 2:
        return  # one role only: the title already says what the bars are
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BASELINE_COLOR, label="Baseline"),
        plt.Rectangle((0, 0), 1, 1, color=MODEL_COLOR, label="SANKET model"),
    ]
    # Top right, above the plot, so it never covers a bar or a label
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.985, 0.905), ncol=2,
               frameon=False, fontsize=10, labelcolor=TEXT_2, handlelength=1, handleheight=1)


def one_row_per_idea(table: pd.DataFrame) -> pd.DataFrame:
    """Drop the untuned twin of each experiment.

    Tuning only widens the window, so both have the same average error and the
    error chart would show every bar twice. The coverage chart keeps both,
    because there the tuning is the whole point.
    """
    names = set(table["experiment"])
    keep = [e for e in table["experiment"] if f"{e}{CALIBRATED}" not in names]
    out = table[table["experiment"].isin(keep)].copy()
    out["experiment"] = [
        e[: -len(CALIBRATED)] if e.endswith(CALIBRATED) and e[: -len(CALIBRATED)] in names else e
        for e in out["experiment"]
    ]
    return out.reset_index(drop=True)


def _layout(table: pd.DataFrame, plot_inches: float = 6.2):
    """Give the names as much room as the longest one needs, so nothing is cut off."""
    longest = max(len(nice_name(e)) for e in table["experiment"])
    names = min(0.085 * longest + 0.3, 4.6)
    width = names + plot_inches
    return (width, 1.6 + 0.6 * len(table)), names / width


def _bars(table: pd.DataFrame, value: str, figsize):
    # Best row first in the table -> top of the chart
    t = table.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    _style(ax, fig)
    colors = [BASELINE_COLOR if is_baseline(e) else MODEL_COLOR for e in t["experiment"]]
    ax.barh(range(len(t)), t[value], height=0.42, color=colors)
    ax.set_yticks(range(len(t)), [nice_name(e) for e in t["experiment"]])
    return fig, ax, t


def plot_ablation_mae(table: pd.DataFrame, out: Path, fake: bool = False) -> Path:
    n = int(table["n"].iloc[0])
    table = one_row_per_idea(table)
    figsize, left = _layout(table)
    fig, ax, t = _bars(table, "mae", figsize=figsize)
    top = t["mae"].max()
    for i, v in enumerate(t["mae"]):
        ax.text(v + top * 0.015, i, f"{v:.1f} min", va="center", fontsize=11, color=TEXT)
    ax.set_xlim(0, top * 1.18)
    ax.set_xlabel("average error of the predicted minutes lost per section (lower is better)\n"
                  "tuning the window changes how often it is right, not this number",
                  color=TEXT_2, fontsize=10)
    _legend(fig, table)
    _titles(fig, "How far off each forecast is",
            f"Mean absolute error on the same {n} test sections", fake)
    fig.subplots_adjust(left=left, right=0.97, top=0.76, bottom=0.18)
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


def plot_coverage(table: pd.DataFrame, out: Path, fake: bool = False) -> Path:
    n = int(table["n"].iloc[0])
    figsize, left = _layout(table)
    fig, ax, t = _bars(table, "coverage", figsize=figsize)
    ax.axvline(COVERAGE_TARGET, color=TEXT, linewidth=1.5)
    ax.text(COVERAGE_TARGET, len(t) - 0.35, "target 80%", ha="center", va="bottom",
            fontsize=10, color=TEXT)
    # Labels in one column right of 100%, so they never collide with the target line
    for i, (c, w) in enumerate(zip(t["coverage"], t["mean_width"])):
        ax.text(1.03, i, f"{c:.0%}", va="center", fontsize=11, color=TEXT, weight="bold")
        ax.text(1.14, i, f"window {w:.0f} min wide", va="center", fontsize=10.5, color=TEXT_2)
    ax.set_xlim(0, 1.5)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0], ["0%", "20%", "40%", "60%", "80%", "100%"])
    ax.set_xlabel("share of sections where the real delay fell inside the predicted window",
                  color=TEXT_2, fontsize=10)
    _legend(fig, table)
    _titles(fig, "How often the window catches the real delay",
            f"{n} test sections. Read it together with window width.", fake)
    fig.subplots_adjust(left=left, right=0.97, top=0.72, bottom=0.18)
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


def make_plots(pred_dir: str | Path = DEFAULT_PRED_DIR, out_dir: str | Path | None = None) -> list[Path]:
    pred_dir = Path(pred_dir)
    fake = "fake" in pred_dir.name.lower()
    out_dir = Path(out_dir) if out_dir else (FAKE_OUT if fake else REAL_OUT)
    out_dir.mkdir(parents=True, exist_ok=True)

    table = ablation_table(pred_dir)
    return [
        plot_ablation_mae(table, out_dir / "10_ablation_mae.png", fake),
        plot_coverage(table, out_dir / "11_coverage.png", fake),
    ]


def main(argv: list[str]) -> None:
    pred_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRED_DIR
    try:
        paths = make_plots(pred_dir)
    except FileNotFoundError:
        print(f"No prediction files in {pred_dir} yet.")
        print("To practise on fake data:  python -m src.eval.plots data/processed/predictions_fake")
        sys.exit(1)
    for p in paths:
        print(f"wrote {p}")


if __name__ == "__main__":
    main(sys.argv)
