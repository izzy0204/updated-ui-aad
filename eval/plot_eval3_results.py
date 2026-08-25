#!/usr/bin/env python3
"""
SourceCheckup figures + permutation p-values for eval-3 (5 models × Manual/Auto).

Reads:
  eval/sourcecheckup_out/results_eval3_cards_corpus/sourcecheckup_all_summaries.json

Writes under eval/figures/eval3/:
  - sourcecheckup_bargraph.png
  - sourcecheckup_auto_vs_manual_boxplots.png  (means, bootstrap CIs, permutation p)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

EVAL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_ROOT))

from readability_analysis import (  # noqa: E402
    _bootstrap_ci_mean,
    _permutation_pvalue_diff_means,
    infer_card_variant,
    infer_model_family,
)
from run_mode_bargraphs_from_text import _set_black_theme, plot_sourcecheckup_bars  # noqa: E402

SOURCECHECKUP_SUMMARY = (
    EVAL_ROOT / "sourcecheckup_out" / "results_eval3_cards_corpus" / "sourcecheckup_all_summaries.json"
)
FIGURES_OUT = EVAL_ROOT / "figures" / "eval3"
MODEL_ORDER = ["DermGPT", "Dermasensor", "DERM", "SkinVision", "Forus"]


def _parse_cli() -> tuple[Path, Path, Path, list[str]]:
    import argparse

    ap = argparse.ArgumentParser(description="Plot eval-3 SourceCheckup figures + p-values.")
    ap.add_argument(
        "--summary",
        type=str,
        default=str(SOURCECHECKUP_SUMMARY),
        help="Path to sourcecheckup_all_summaries.json",
    )
    ap.add_argument(
        "--figures-out",
        type=str,
        default=str(FIGURES_OUT),
        help="Directory for PNG/JSON figure outputs",
    )
    ap.add_argument(
        "--tsv-out",
        type=str,
        default="",
        help="Optional TSV path (default: beside summary as sourcecheckup_manual_vs_auto.tsv)",
    )
    ap.add_argument(
        "--also-boxplot-excluding",
        nargs="*",
        default=None,
        help="Write an additional Auto-vs-Manual boxplot excluding these model families. "
        "Pass the flag alone to exclude SkinVision by default.",
    )
    args = ap.parse_args()
    summary = Path(args.summary)
    figures_out = Path(args.figures_out)
    if args.tsv_out:
        tsv_out = Path(args.tsv_out)
    else:
        tsv_out = summary.parent / "sourcecheckup_manual_vs_auto.tsv"
    if args.also_boxplot_excluding is None:
        exclude_extra: list[str] = []
    elif len(args.also_boxplot_excluding) == 0:
        exclude_extra = ["SkinVision"]
    else:
        exclude_extra = list(args.also_boxplot_excluding)
    return summary, figures_out, tsv_out, exclude_extra


def load_summary(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"[ERROR] Missing summary file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def split_by_variant(rows: list[dict]) -> dict[str, dict[str, tuple[float, float]]]:
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for row in rows:
        name = str(row.get("name", ""))
        family = infer_model_family(name)
        variant = infer_card_variant(name)
        strict_pct = float(row["strict_score"]) * 100.0
        partial_pct = float(row["partial_credit_score"]) * 100.0
        out.setdefault(family, {})[variant] = (strict_pct, partial_pct)
        print(f"[map] {name} → {family} / {variant} strict={strict_pct:.1f}%")
    return out


def ordered_values(
    by_family: dict[str, dict[str, tuple[float, float]]],
    variant: str,
    idx: int,
    model_order: list[str] | None = None,
) -> np.ndarray:
    order = model_order or MODEL_ORDER
    values = []
    for model in order:
        entry = by_family.get(model, {}).get(variant)
        if entry is None:
            raise SystemExit(
                f"[ERROR] Missing {variant} result for model '{model}'. "
                f"Have families: {sorted(by_family.keys())}"
            )
        values.append(entry[idx])
    return np.array(values, dtype=float)


def plot_sourcecheckup_boxplots(
    *,
    manual: list[float],
    auto: list[float],
    output_path: Path,
    title: str,
    models: list[str] | None = None,
    seed: int = 0,
    metric_label: str = "SourceCheckup (%)",
) -> Path:
    """Manual vs Auto SourceCheckup boxplot + stats panel (CI + permutation p).

    Matches the eval-2 / readability layout (boxplot + white stats box), but
    disables notches for small n (n≈4–5) so CI notches do not fold the boxes.
    """
    # Ensure light theme even if barplots previously set a dark rcParams theme.
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
        m = np.array(manual, dtype=float)
        a = np.array(auto, dtype=float)
        model_names = models if models is not None else MODEL_ORDER
        n_models = len(model_names)

        fig = plt.figure(figsize=(10.5, 4.8))
        gs = GridSpec(1, 2, figure=fig, width_ratios=[1.0, 1.15], wspace=0.18)
        ax = fig.add_subplot(gs[0, 0])
        ax_stats = fig.add_subplot(gs[0, 1])
        ax_stats.axis("off")
        ax_stats.set_xlim(0, 1)
        ax_stats.set_ylim(0, 1)

        # notch=False: with n=4–5 the median CI often exceeds the IQR and
        # produces the broken hourglass / clipped boxes seen in prior figures.
        ax.boxplot(
            [m, a],
            tick_labels=["Manual", "Auto"],
            showmeans=True,
            meanline=True,
            notch=False,
            widths=0.5,
        )
        ax.set_ylabel("Percent")
        ax.set_ylim(0, 100)
        ax.set_title(metric_label, pad=8)

        mean_m, mean_a = float(np.mean(m)), float(np.mean(a))
        ci_m = _bootstrap_ci_mean(m, seed=seed)
        ci_a = _bootstrap_ci_mean(a, seed=seed + 1)
        p = _permutation_pvalue_diff_means(a, m, n_perm=20000, seed=seed)
        delta = mean_a - mean_m

        stats_lines = [
            "Groups: Manual vs Auto (values are % per model)",
            f"Models (n={n_models}): {', '.join(model_names)}",
            "",
            metric_label,
            f"  Manual: n={m.size} mean={mean_m:.2f}  95% CI [{ci_m[0]:.2f}, {ci_m[1]:.2f}]",
            f"  Auto:   n={a.size} mean={mean_a:.2f}  95% CI [{ci_a[0]:.2f}, {ci_a[1]:.2f}]",
            f"  Δ (Auto − Manual): {delta:+.2f} pp",
            f"  permutation p-value (Δmeans Auto−Manual): {p:.4f}",
            "  (n_perm=20000)",
        ]
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
        fig.subplots_adjust(left=0.08, right=0.98, top=0.86, bottom=0.12, wspace=0.18)
        fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)

    stats = {
        "manual_mean": mean_m,
        "auto_mean": mean_a,
        "delta_auto_minus_manual": delta,
        "manual_ci95": list(ci_m),
        "auto_ci95": list(ci_a),
        "permutation_p_delta_means": p,
        "n_perm": 20000,
        "manual_values": list(map(float, m)),
        "auto_values": list(map(float, a)),
        "models": list(model_names),
    }
    stats_path = output_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[OK] Saved {output_path}")
    print(f"[OK] Saved {stats_path}")
    return output_path


def main() -> None:
    summary_path, figures_out, tsv_path, exclude_extra = _parse_cli()
    _set_black_theme()
    figures_out.mkdir(parents=True, exist_ok=True)

    rows = load_summary(summary_path)
    by_family = split_by_variant(rows)

    sc_manual = ordered_values(by_family, "Manual", 0)
    sc_auto = ordered_values(by_family, "Auto", 0)
    sc_manual_partial = ordered_values(by_family, "Manual", 1)
    sc_auto_partial = ordered_values(by_family, "Auto", 1)

    out_sc = figures_out / "sourcecheckup_bargraph.png"
    plot_sourcecheckup_bars(
        models=MODEL_ORDER, manual=sc_manual, auto=sc_auto, out_path=out_sc
    )
    print(f"[OK] Saved {out_sc}")

    out_partial = figures_out / "sourcecheckup_partial_credit_bargraph.png"
    plot_sourcecheckup_bars(
        models=MODEL_ORDER,
        manual=sc_manual_partial,
        auto=sc_auto_partial,
        out_path=out_partial,
    )
    print(f"[OK] Saved {out_partial}")

    out_box = figures_out / "sourcecheckup_auto_vs_manual_boxplots.png"
    plot_sourcecheckup_boxplots(
        manual=list(sc_manual),
        auto=list(sc_auto),
        output_path=out_box,
        title="Auto vs Manual: SourceCheckup strict (eval-3, 5 models)",
        models=MODEL_ORDER,
        metric_label="SourceCheckup strict (%)",
    )

    out_box_partial = figures_out / "sourcecheckup_auto_vs_manual_boxplots_partial.png"
    plot_sourcecheckup_boxplots(
        manual=list(sc_manual_partial),
        auto=list(sc_auto_partial),
        output_path=out_box_partial,
        title="Auto vs Manual: SourceCheckup partial-credit (eval-3, 5 models)",
        models=MODEL_ORDER,
        seed=1,
        metric_label="SourceCheckup partial-credit (%)",
    )

    if exclude_extra:
        keep = [m for m in MODEL_ORDER if m not in set(exclude_extra)]
        if len(keep) < 2:
            raise SystemExit(f"[ERROR] Need ≥2 models after excluding {exclude_extra}; have {keep}")
        m_ex = ordered_values(by_family, "Manual", 0, model_order=keep)
        a_ex = ordered_values(by_family, "Auto", 0, model_order=keep)
        tag = "_excl_" + "_".join(x.lower() for x in exclude_extra)
        out_box_ex = figures_out / f"sourcecheckup_auto_vs_manual_boxplots{tag}.png"
        plot_sourcecheckup_boxplots(
            manual=list(m_ex),
            auto=list(a_ex),
            output_path=out_box_ex,
            title=f"Auto vs Manual: SourceCheckup (eval-3, excl. {', '.join(exclude_extra)})",
            models=keep,
        )

    lines = ["model\tmanual_strict\tauto_strict\tmanual_partial\tauto_partial"]
    for i, model in enumerate(MODEL_ORDER):
        lines.append(
            f"{model}\t{sc_manual[i]:.4f}\t{sc_auto[i]:.4f}\t"
            f"{sc_manual_partial[i]:.4f}\t{sc_auto_partial[i]:.4f}"
        )
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Saved {tsv_path}")


if __name__ == "__main__":
    main()
