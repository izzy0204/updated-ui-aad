"""
Create neat bar graphs for SourceCheckup + FactScore-style summary numbers.

Input numbers are hard-coded from the user-provided summary (percentages 0-100).
Outputs a single PNG with two panels:
1) SourceCheckup: per-model Manual vs Auto + overall averages
2) FactScore-style: per-model Manual vs Auto for strict + partial-credit + overall averages
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _annotate_bars(ax, bars, *, fmt: str = "{:.1f}%") -> None:
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + 1.2,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=9,
            color="black",
        )


def _set_black_theme() -> None:
    # Force all labels/text to black for publication.
    plt.rcParams.update(
        {
            "text.color": "black",
            "axes.labelcolor": "black",
            "axes.titlecolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
        }
    )


def plot_sourcecheckup_bars(
    *,
    models: list[str],
    manual: np.ndarray,
    auto: np.ndarray,
    out_path: Path,
) -> None:
    manual_avg = float(manual.mean())
    auto_avg = float(auto.mean())

    fig, ax = plt.subplots(figsize=(8.2, 5.5))
    # Reserve a little right margin for average labels drawn outside axes.
    fig.subplots_adjust(right=0.86)

    x = np.arange(len(models))
    w = 0.35
    c_manual = "#2F5597"  # bar color only (text stays black)
    c_auto = "#C55A11"  # bar color only (text stays black)

    b1 = ax.bar(x - w / 2, manual, w, label="Manual", color=c_manual)
    b2 = ax.bar(x + w / 2, auto, w, label="Auto", color=c_auto)

    # Keep a single title per figure (use suptitle below).
    ax.set_ylabel("Percent supported (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(frameon=False, loc="upper left", labelcolor="black")

    _annotate_bars(ax, b1, fmt="{:.1f}%")
    _annotate_bars(ax, b2, fmt="{:.1f}%")

    # Overall averages as dotted black lines (computed from values above)
    ax.axhline(manual_avg, color="black", linestyle=":", linewidth=1.4, alpha=0.95)
    ax.axhline(auto_avg, color="black", linestyle=":", linewidth=1.4, alpha=0.95)

    # Label dotted lines just outside the axes (in the right margin).
    ax.annotate(
        f"Manual avg {manual_avg:.1f}%",
        xy=(1.01, manual_avg),
        xycoords=("axes fraction", "data"),
        ha="left",
        va="center",
        fontsize=9,
        color="black",
        clip_on=False,
    )
    ax.annotate(
        f"Auto avg {auto_avg:.1f}%",
        xy=(1.01, auto_avg),
        xycoords=("axes fraction", "data"),
        ha="left",
        va="center",
        fontsize=9,
        color="black",
        clip_on=False,
    )

    fig.suptitle("Manual vs Auto: SourceCheckup Results", y=0.98, fontsize=14)
    # Ensure there is room for the title.
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_factscore_bars(
    *,
    models: list[str],
    manual_strict: np.ndarray,
    manual_partial: np.ndarray,
    auto_strict: np.ndarray,
    auto_partial: np.ndarray,
    out_path: Path,
) -> None:
    manual_strict_avg = float(manual_strict.mean())
    manual_partial_avg = float(manual_partial.mean())
    auto_strict_avg = float(auto_strict.mean())
    auto_partial_avg = float(auto_partial.mean())

    fig, ax = plt.subplots(figsize=(9.4, 5.5))
    fig.subplots_adjust(right=0.86)

    x = np.arange(len(models))
    w = 0.18
    c_manual_strict = "#1F4E79"
    c_manual_partial = "#5B9BD5"
    c_auto_strict = "#7F6000"
    c_auto_partial = "#ED7D31"

    bars_ms = ax.bar(x - 1.5 * w, manual_strict, w, label="Manual strict", color=c_manual_strict)
    bars_mp = ax.bar(x - 0.5 * w, manual_partial, w, label="Manual partial", color=c_manual_partial)
    bars_as = ax.bar(x + 0.5 * w, auto_strict, w, label="Auto strict", color=c_auto_strict)
    bars_ap = ax.bar(x + 1.5 * w, auto_partial, w, label="Auto partial", color=c_auto_partial)

    # Keep a single title per figure (use suptitle below).
    ax.set_ylabel("Percent (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(frameon=False, fontsize=9, ncols=2, loc="upper left", labelcolor="black")

    _annotate_bars(ax, bars_ms, fmt="{:.2f}%")
    _annotate_bars(ax, bars_mp, fmt="{:.2f}%")
    _annotate_bars(ax, bars_as, fmt="{:.2f}%")
    _annotate_bars(ax, bars_ap, fmt="{:.2f}%")

    # Overall averages as dotted black guide lines (computed from values above)
    for y in [manual_strict_avg, manual_partial_avg, auto_strict_avg, auto_partial_avg]:
        ax.axhline(y, color="black", linestyle=":", linewidth=1.2, alpha=0.85)

    # Label dotted lines outside axes on the right.
    for label, y in [
        (f"Manual partial avg {manual_partial_avg:.2f}%", manual_partial_avg),
        (f"Manual strict avg {manual_strict_avg:.2f}%", manual_strict_avg),
        (f"Auto partial avg {auto_partial_avg:.2f}%", auto_partial_avg),
        (f"Auto strict avg {auto_strict_avg:.2f}%", auto_strict_avg),
    ]:
        ax.annotate(
            label,
            xy=(1.01, y),
            xycoords=("axes fraction", "data"),
            ha="left",
            va="center",
            fontsize=8,
            color="black",
            clip_on=False,
        )

    fig.suptitle("Manual vs Auto: FactScore Results", y=0.98, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    _set_black_theme()

    # ---- SourceCheckup averages (%)
    models_sc = ["DermGPT", "Dermasensor", "Tandem"]
    manual_sc = np.array([80.6, 91.3, 84.8], dtype=float)
    auto_sc = np.array([59.1, 68.1, 92.3], dtype=float)

    # ---- FactScore-style (%)
    models_fs = ["DermGPT", "DermaSensor", "Tandem"]
    manual_strict = np.array([80.95, 49.18, 70.00], dtype=float)
    manual_partial = np.array([88.10, 63.93, 72.50], dtype=float)
    auto_strict = np.array([35.85, 53.85, 52.94], dtype=float)
    auto_partial = np.array([50.00, 57.21, 55.88], dtype=float)
    manual_strict_avg = float(manual_strict.mean())
    manual_partial_avg = float(manual_partial.mean())
    auto_strict_avg = float(auto_strict.mean())
    auto_partial_avg = float(auto_partial.mean())

    fig_dir = Path("figures")
    fig_dir.mkdir(parents=True, exist_ok=True)

    out_sc = fig_dir / "sourcecheckup_bargraph.png"
    out_fs = fig_dir / "factscore_bargraph.png"

    plot_sourcecheckup_bars(
        models=models_sc,
        manual=manual_sc,
        auto=auto_sc,
        out_path=out_sc,
    )
    plot_factscore_bars(
        models=models_fs,
        manual_strict=manual_strict,
        manual_partial=manual_partial,
        auto_strict=auto_strict,
        auto_partial=auto_partial,
        out_path=out_fs,
    )

    print(f"Saved SourceCheckup bar graph to {out_sc}")
    print(f"Saved FactScore bar graph to {out_fs}")


if __name__ == "__main__":
    main()

