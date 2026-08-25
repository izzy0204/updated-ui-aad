#!/usr/bin/env python3
"""
FactScore + Flesch figures for eval-3, plus best-of(eval-2, eval-3) figures.

Best-of rule (per model family × Manual/Auto, per metric):
  - FactScore strict / partial-credit: max (higher better)
  - Flesch Reading Ease: max (higher = easier)
  - Flesch–Kincaid grade: min (lower = easier)

Style matches eval-2 (`plot_factscore_bars`, readability boxplots, black theme).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

EVAL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_ROOT))

from readability_analysis import (  # noqa: E402
    _bootstrap_ci_mean,
    _permutation_pvalue_diff_means,
    add_display_labels,
    infer_card_variant,
    infer_model_family,
    plot_overall_auto_vs_manual_boxplot,
)
from run_mode_bargraphs_from_text import (  # noqa: E402
    _set_black_theme,
    plot_factscore_bars,
    plot_sourcecheckup_bars,
)

FACTSCORE_EVAL2 = EVAL_ROOT / "factscore_out" / "eval2_cards" / "factscore_like_summary_ui_cards.json"
FACTSCORE_EVAL3 = EVAL_ROOT / "factscore_out" / "eval3_cards" / "factscore_like_summary_ui_cards.json"
READABILITY_EVAL2 = EVAL_ROOT / "readability_out" / "eval2_ui_cards_readability.csv"
READABILITY_EVAL3 = EVAL_ROOT / "readability_out" / "eval3_ui_cards_readability.csv"

FIGURES_EVAL3 = EVAL_ROOT / "figures" / "eval3"
FIGURES_BEST = EVAL_ROOT / "figures" / "best_of_eval2_eval3"

# Canonical families after SkinAnalytics→DERM / Tandem→Forus rename.
MODEL_ORDER = ["DermGPT", "Dermasensor", "DERM", "SkinVision", "Forus"]


def load_json(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"[ERROR] Missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def factscore_by_family(rows: list[dict]) -> dict[str, dict[str, tuple[float, float]]]:
    """family -> variant -> (strict_pct, partial_pct)."""
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for row in rows:
        name = str(row.get("name", ""))
        family = infer_model_family(name)
        variant = infer_card_variant(name)
        out.setdefault(family, {})[variant] = (
            float(row["score_strict"]) * 100.0,
            float(row["score_partial_credit"]) * 100.0,
        )
    return out


def readability_overall_by_family(csv_path: Path) -> dict[str, dict[str, tuple[float, float]]]:
    """family -> variant -> (FRE, FK grade) from OVERALL_SELECTED_FIELDS.

    When an eval folder has duplicate manuals (e.g. Forus.md + tandem-manual-eval-3.md),
    keep the first observed score for that (family, variant).
    """
    df = add_display_labels(pd.read_csv(csv_path))
    overall = df[df["section"] == "OVERALL_SELECTED_FIELDS"].copy()
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for _, row in overall.iterrows():
        family = str(row["model_family"])
        variant = str(row["card_variant"])
        fre = float(row["flesch_reading_ease"])
        fk = float(row["flesch_kincaid_grade"])
        out.setdefault(family, {})
        if variant not in out[family]:
            out[family][variant] = (fre, fk)
    return out


def best_of_factscore(
    a: dict[str, dict[str, tuple[float, float]]],
    b: dict[str, dict[str, tuple[float, float]]],
) -> dict[str, dict[str, tuple[float, float]]]:
    out: dict[str, dict[str, tuple[float, float]]] = {}
    families = set(a) | set(b)
    for family in families:
        out[family] = {}
        for variant in ("Manual", "Auto"):
            candidates = []
            if family in a and variant in a[family]:
                candidates.append(a[family][variant])
            if family in b and variant in b[family]:
                candidates.append(b[family][variant])
            if not candidates:
                continue
            # Independent best per metric component.
            best_strict = max(c[0] for c in candidates)
            best_partial = max(c[1] for c in candidates)
            out[family][variant] = (best_strict, best_partial)
    return out


def best_of_readability(
    a: dict[str, dict[str, tuple[float, float]]],
    b: dict[str, dict[str, tuple[float, float]]],
) -> dict[str, dict[str, tuple[float, float]]]:
    out: dict[str, dict[str, tuple[float, float]]] = {}
    families = set(a) | set(b)
    for family in families:
        out[family] = {}
        for variant in ("Manual", "Auto"):
            candidates = []
            if family in a and variant in a[family]:
                candidates.append(a[family][variant])
            if family in b and variant in b[family]:
                candidates.append(b[family][variant])
            if not candidates:
                continue
            best_fre = max(c[0] for c in candidates)
            best_fk = min(c[1] for c in candidates)
            out[family][variant] = (best_fre, best_fk)
    return out


def ordered(by_family: dict[str, dict[str, tuple[float, float]]], variant: str, idx: int) -> np.ndarray:
    values = []
    for model in MODEL_ORDER:
        entry = by_family.get(model, {}).get(variant)
        if entry is None:
            raise SystemExit(
                f"[ERROR] Missing {variant} for '{model}'. Have: "
                f"{ {m: sorted(v.keys()) for m, v in by_family.items()} }"
            )
        values.append(entry[idx])
    return np.array(values, dtype=float)


def plot_factscore_boxplots(
    *,
    strict_manual: list[float],
    strict_auto: list[float],
    partial_manual: list[float],
    partial_auto: list[float],
    output_path: Path,
    title: str,
    seed: int = 0,
) -> Path:
    """Manual vs Auto FactScore boxplots (strict + partial) + stats panel."""
    with plt.rc_context(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "text.color": "black",
            "axes.labelcolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
            "axes.edgecolor": "black",
        }
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics = [
            ("FactScore strict (%)", np.array(strict_manual, dtype=float), np.array(strict_auto, dtype=float)),
            (
                "FactScore partial-credit (%)",
                np.array(partial_manual, dtype=float),
                np.array(partial_auto, dtype=float),
            ),
        ]

        fig = plt.figure(figsize=(11.0, 4.8))
        gs = GridSpec(1, 3, figure=fig, width_ratios=[1.0, 1.0, 1.2], wspace=0.28)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[0, 1])
        ax_stats = fig.add_subplot(gs[0, 2])
        ax_stats.axis("off")
        axes = [ax_a, ax_b]

        stats_lines = [
            "Groups: Manual vs Auto (values are % per model)",
            f"Models (n={len(MODEL_ORDER)}): {', '.join(MODEL_ORDER)}",
            "",
        ]

        for idx, (ax, (name, m, a)) in enumerate(zip(axes, metrics, strict=True)):
            ax.boxplot(
                [m, a],
                tick_labels=["Manual", "Auto"],
                showmeans=True,
                meanline=True,
                notch=False,
                widths=0.5,
            )
            ax.set_title(name, pad=8)
            ax.set_ylabel("Percent")
            ax.set_ylim(0, 100)

            mean_m, mean_a = float(np.mean(m)), float(np.mean(a))
            ci_m = _bootstrap_ci_mean(m, seed=seed + 10 * idx)
            ci_a = _bootstrap_ci_mean(a, seed=seed + 10 * idx + 1)
            p = _permutation_pvalue_diff_means(a, m, n_perm=20000, seed=seed + 10 * idx + 2)
            delta = mean_a - mean_m
            stats_lines.extend(
                [
                    name,
                    f"  Manual: n={m.size} mean={mean_m:.2f}  95% CI [{ci_m[0]:.2f}, {ci_m[1]:.2f}]",
                    f"  Auto:   n={a.size} mean={mean_a:.2f}  95% CI [{ci_a[0]:.2f}, {ci_a[1]:.2f}]",
                    f"  Δ (Auto − Manual): {delta:+.2f} pp",
                    f"  permutation p-value (Δmeans Auto−Manual): {p:.4f}",
                    "",
                ]
            )

        ax_stats.text(
            0.0,
            1.0,
            "\n".join(stats_lines).rstrip(),
            ha="left",
            va="top",
            fontsize=9,
            linespacing=1.3,
            color="black",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dddddd"),
        )
        fig.suptitle(title, y=0.98, fontsize=12)
        fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.12)
        fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
    print(f"[OK] Saved {output_path}")
    return output_path


def readability_df_from_best(
    best: dict[str, dict[str, tuple[float, float]]],
) -> pd.DataFrame:
    """Synthetic overall-only frame for plot_overall_auto_vs_manual_boxplot."""
    rows = []
    for family in MODEL_ORDER:
        for variant in ("Manual", "Auto"):
            fre, fk = best[family][variant]
            rows.append(
                {
                    "model_name": f"{family}-{variant.lower()}-best",
                    "model_family": family,
                    "card_variant": variant,
                    "model_label": f"{family} ({variant})",
                    "section": "OVERALL_SELECTED_FIELDS",
                    "flesch_reading_ease": fre,
                    "flesch_kincaid_grade": fk,
                }
            )
    return pd.DataFrame(rows)


def plot_readability_bars(
    *,
    models: list[str],
    manual: np.ndarray,
    auto: np.ndarray,
    out_path: Path,
    ylabel: str,
    title: str,
    ylim: tuple[float, float] | None = None,
) -> None:
    """Manual vs Auto bars in the same style as SourceCheckup/FactScore eval-2 graphs."""
    # Reuse SourceCheckup bar styling (Manual blue / Auto orange).
    # For FK grade, values are not 0–100 percentages — adjust ylim.
    if ylim is None:
        plot_sourcecheckup_bars(models=models, manual=manual, auto=auto, out_path=out_path)
        # Retitle: plot_sourcecheckup_bars hardcodes its title; redraw lightly.
        # Simpler: call a local copy below.
    # Always draw locally so title/ylabel match the metric.
    _set_black_theme()
    from run_mode_bargraphs_from_text import _annotate_bars, _declutter_ys

    manual_avg = float(manual.mean())
    auto_avg = float(auto.mean())
    fig, ax = plt.subplots(figsize=(max(8.2, 1.6 * len(models) + 2.0), 5.5))
    fig.subplots_adjust(right=0.86)
    x = np.arange(len(models))
    w = 0.35
    b1 = ax.bar(x - w / 2, manual, w, label="Manual", color="#2F5597")
    b2 = ax.bar(x + w / 2, auto, w, label="Auto", color="#C55A11")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    if ylim is not None:
        ax.set_ylim(*ylim)
    else:
        lo = min(0.0, float(np.min([manual.min(), auto.min()])) - 5)
        hi = float(np.max([manual.max(), auto.max()])) + 10
        ax.set_ylim(lo, hi)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(frameon=False, loc="upper left", labelcolor="black")
    _annotate_bars(ax, b1, fmt="{:.1f}")
    _annotate_bars(ax, b2, fmt="{:.1f}")
    ax.axhline(manual_avg, color="black", linestyle=":", linewidth=1.4, alpha=0.95)
    ax.axhline(auto_avg, color="black", linestyle=":", linewidth=1.4, alpha=0.95)
    label_ys = _declutter_ys([manual_avg, auto_avg], min_gap=max(2.0, (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.06))
    for text, y in [
        (f"Manual avg {manual_avg:.1f}", label_ys[0]),
        (f"Auto avg {auto_avg:.1f}", label_ys[1]),
    ]:
        ax.annotate(
            text,
            xy=(1.01, y),
            xycoords=("axes fraction", "data"),
            ha="left",
            va="center",
            fontsize=9,
            color="black",
            clip_on=False,
        )
    fig.suptitle(title, y=0.98, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved {out_path}")


def write_best_tsv(
    path: Path,
    fs: dict[str, dict[str, tuple[float, float]]],
    rd: dict[str, dict[str, tuple[float, float]]],
) -> None:
    lines = [
        "model\tvariant\tfactscore_strict\tfactscore_partial\tflesch_reading_ease\tflesch_kincaid_grade"
    ]
    for model in MODEL_ORDER:
        for variant in ("Manual", "Auto"):
            s, p = fs[model][variant]
            fre, fk = rd[model][variant]
            lines.append(f"{model}\t{variant}\t{s:.4f}\t{p:.4f}\t{fre:.4f}\t{fk:.4f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Saved {path}")


def emit_factscore_figures(
    by_family: dict[str, dict[str, tuple[float, float]]],
    figures_out: Path,
    *,
    title_suffix: str,
) -> None:
    figures_out.mkdir(parents=True, exist_ok=True)
    ms = ordered(by_family, "Manual", 0)
    mp = ordered(by_family, "Manual", 1)
    a_s = ordered(by_family, "Auto", 0)
    a_p = ordered(by_family, "Auto", 1)

    out_bar = figures_out / "factscore_bargraph.png"
    plot_factscore_bars(
        models=MODEL_ORDER,
        manual_strict=ms,
        manual_partial=mp,
        auto_strict=a_s,
        auto_partial=a_p,
        out_path=out_bar,
    )
    print(f"[OK] Saved {out_bar}")

    plot_factscore_boxplots(
        strict_manual=list(ms),
        strict_auto=list(a_s),
        partial_manual=list(mp),
        partial_auto=list(a_p),
        output_path=figures_out / "factscore_auto_vs_manual_boxplots.png",
        title=f"Auto vs Manual: FactScore ({title_suffix})",
    )


def emit_readability_figures(
    by_family: dict[str, dict[str, tuple[float, float]]],
    figures_out: Path,
    *,
    title_suffix: str,
) -> None:
    figures_out.mkdir(parents=True, exist_ok=True)
    fre_m = ordered(by_family, "Manual", 0)
    fre_a = ordered(by_family, "Auto", 0)
    fk_m = ordered(by_family, "Manual", 1)
    fk_a = ordered(by_family, "Auto", 1)

    plot_readability_bars(
        models=MODEL_ORDER,
        manual=fre_m,
        auto=fre_a,
        out_path=figures_out / "flesch_reading_ease_bargraph.png",
        ylabel="Flesch Reading Ease",
        title=f"Manual vs Auto: Flesch Reading Ease ({title_suffix})",
    )
    plot_readability_bars(
        models=MODEL_ORDER,
        manual=fk_m,
        auto=fk_a,
        out_path=figures_out / "flesch_kincaid_grade_bargraph.png",
        ylabel="Flesch–Kincaid grade",
        title=f"Manual vs Auto: Flesch–Kincaid Grade ({title_suffix})",
    )

    df = readability_df_from_best(by_family)
    box = plot_overall_auto_vs_manual_boxplot(df, figures_out)
    if box is not None:
        # Retitle via a small overlay note is hard; rewrite with custom title by re-saving
        # is already done by plot_overall_*. Leave default title; print path.
        print(f"[OK] Saved {box}")


def main() -> None:
    _set_black_theme()

    fs2 = factscore_by_family(load_json(FACTSCORE_EVAL2))
    fs3 = factscore_by_family(load_json(FACTSCORE_EVAL3))
    rd2 = readability_overall_by_family(READABILITY_EVAL2)
    rd3 = readability_overall_by_family(READABILITY_EVAL3)

    print("[INFO] Eval-3 FactScore / Flesch figures")
    emit_factscore_figures(fs3, FIGURES_EVAL3, title_suffix="eval-3, 5 models")
    emit_readability_figures(rd3, FIGURES_EVAL3 / "readability", title_suffix="eval-3, 5 models")

    fs_best = best_of_factscore(fs2, fs3)
    rd_best = best_of_readability(rd2, rd3)

    print("[INFO] Best-of eval-2 + eval-3 figures")
    emit_factscore_figures(fs_best, FIGURES_BEST, title_suffix="best of eval-2/3, 5 models")
    emit_readability_figures(rd_best, FIGURES_BEST / "readability", title_suffix="best of eval-2/3, 5 models")
    write_best_tsv(FIGURES_BEST / "best_of_scores.tsv", fs_best, rd_best)

    # Also dump which round won for transparency.
    lines = ["model\tvariant\tmetric\teval2\teval3\tbest\twinner"]
    for model in MODEL_ORDER:
        for variant in ("Manual", "Auto"):
            for metric, idx, prefer in [
                ("factscore_strict", 0, "max"),
                ("factscore_partial", 1, "max"),
                ("flesch_reading_ease", 0, "max"),
                ("flesch_kincaid_grade", 1, "min"),
            ]:
                src = fs2 if metric.startswith("fact") else rd2
                src3 = fs3 if metric.startswith("fact") else rd3
                v2 = src[model][variant][idx]
                v3 = src3[model][variant][idx]
                best = max(v2, v3) if prefer == "max" else min(v2, v3)
                if prefer == "max":
                    winner = "eval2" if v2 >= v3 else "eval3"
                    if abs(v2 - v3) < 1e-9:
                        winner = "tie"
                else:
                    winner = "eval2" if v2 <= v3 else "eval3"
                    if abs(v2 - v3) < 1e-9:
                        winner = "tie"
                lines.append(f"{model}\t{variant}\t{metric}\t{v2:.4f}\t{v3:.4f}\t{best:.4f}\t{winner}")
    win_path = FIGURES_BEST / "best_of_winners.tsv"
    win_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Saved {win_path}")


if __name__ == "__main__":
    main()
