#!/usr/bin/env python3
"""
Auto vs Manual relevancy boxplots (one panel per embedding model).

Source values are the per-model mean cosine similarities transcribed from the
"Auto vs Manual relevancy under three embedding models" bar chart (field-level
raw scores are not in the repo). Each box therefore has n=5 product-model means,
matching the SourceCheckup / FactScore eval boxplot convention.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "figures"
OUT_PNG = OUT_DIR / "relevancy_auto_vs_manual_embedding_boxplots.png"

MODEL_ORDER = ["DermaSensor", "DermGPT", "SkinAnalytics", "SkinVision", "Tandem"]

# Per-model mean cosine from the bar chart labels (2 d.p.).
# Order matches MODEL_ORDER.
EMBEDDING_DATA: dict[str, dict[str, list[float]]] = {
    "OpenAI 3-small (official run)": {
        "auto": [0.40, 0.35, 0.41, 0.39, 0.27],
        "manual": [0.40, 0.44, 0.35, 0.39, 0.38],
    },
    "OpenAI 3-large": {
        "auto": [0.43, 0.34, 0.38, 0.45, 0.26],
        "manual": [0.40, 0.45, 0.36, 0.44, 0.34],
    },
    "Gemini embedding-001": {
        "auto": [0.84, 0.84, 0.84, 0.84, 0.79],
        "manual": [0.84, 0.86, 0.84, 0.85, 0.81],
    },
}


def _bootstrap_ci_mean(
    x: np.ndarray, *, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return (float("nan"), float("nan"))
    samples = rng.choice(x, size=(n_boot, x.size), replace=True)
    means = samples.mean(axis=1)
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return lo, hi


def _permutation_pvalue_diff_means(
    a: np.ndarray, b: np.ndarray, *, n_perm: int = 20000, seed: int = 0
) -> float:
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if a.size == 0 or b.size == 0:
        return float("nan")
    obs = float(a.mean() - b.mean())
    pooled = np.concatenate([a, b])
    n_a = a.size
    count = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        perm_obs = float(pooled[:n_a].mean() - pooled[n_a:].mean())
        if abs(perm_obs) >= abs(obs):
            count += 1
    return float((count + 1) / (n_perm + 1))


def plot_boxplots(*, output_path: Path = OUT_PNG, seed: int = 0) -> Path:
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
        names = list(EMBEDDING_DATA.keys())
        fig = plt.figure(figsize=(12.5, 7.2))
        gs = GridSpec(2, 2, figure=fig, wspace=0.28, hspace=0.35)

        axes = [
            fig.add_subplot(gs[0, 0]),
            fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[1, 0]),
        ]
        ax_stats = fig.add_subplot(gs[1, 1])
        ax_stats.axis("off")
        ax_stats.set_xlim(0, 1)
        ax_stats.set_ylim(0, 1)

        stats_lines = [
            "Groups: Manual vs Auto",
            "(values = per-model mean cosine from bar chart)",
            f"Models (n={len(MODEL_ORDER)}): {', '.join(MODEL_ORDER)}",
            "",
        ]
        all_stats: dict[str, dict] = {}

        for idx, (ax, name) in enumerate(zip(axes, names, strict=True)):
            m = np.array(EMBEDDING_DATA[name]["manual"], dtype=float)
            a = np.array(EMBEDDING_DATA[name]["auto"], dtype=float)
            ax.boxplot(
                [m, a],
                tick_labels=["Manual", "Auto"],
                showmeans=True,
                meanline=True,
                notch=False,
                widths=0.5,
            )
            ax.set_title(name, pad=8, fontsize=11)
            ax.set_ylabel("Mean cosine")
            ax.set_ylim(0.0, 1.0)

            mean_m, mean_a = float(np.mean(m)), float(np.mean(a))
            ci_m = _bootstrap_ci_mean(m, seed=seed + 10 * idx)
            ci_a = _bootstrap_ci_mean(a, seed=seed + 10 * idx + 1)
            p = _permutation_pvalue_diff_means(
                a, m, n_perm=20000, seed=seed + 10 * idx + 2
            )
            delta = mean_a - mean_m
            stats_lines.extend(
                [
                    name,
                    f"  Manual: n={m.size} mean={mean_m:.3f}  95% CI [{ci_m[0]:.3f}, {ci_m[1]:.3f}]",
                    f"  Auto:   n={a.size} mean={mean_a:.3f}  95% CI [{ci_a[0]:.3f}, {ci_a[1]:.3f}]",
                    f"  Δ (Auto − Manual): {delta:+.3f}",
                    f"  permutation p-value (Δmeans Auto−Manual): {p:.4f}",
                    "",
                ]
            )
            all_stats[name] = {
                "manual_mean": mean_m,
                "auto_mean": mean_a,
                "delta_auto_minus_manual": delta,
                "manual_ci95": list(ci_m),
                "auto_ci95": list(ci_a),
                "permutation_p_delta_means": p,
                "n_perm": 20000,
                "manual_values": list(map(float, m)),
                "auto_values": list(map(float, a)),
                "models": list(MODEL_ORDER),
            }

        stats_lines.append("(n_perm=20000; exploratory — n=5 model means)")
        ax_stats.text(
            0.0,
            1.0,
            "\n".join(stats_lines).rstrip(),
            ha="left",
            va="top",
            fontsize=8.5,
            linespacing=1.25,
            color="black",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dddddd"),
        )

        fig.suptitle(
            "Auto vs Manual: relevancy (mean cosine) under three embedding models",
            y=0.98,
            fontsize=12,
        )
        fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.06)
        fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)

    stats_path = output_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(all_stats, indent=2), encoding="utf-8")
    print(f"[OK] Saved {output_path}")
    print(f"[OK] Saved {stats_path}")
    return output_path


if __name__ == "__main__":
    plot_boxplots()
