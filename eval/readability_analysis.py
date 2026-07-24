"""
Readability metrics for dermatology AI model cards.

Supports:
- **UI cards**: CHAI-style Markdown under `ui_cards/` (`- **Summary:**` bullets, keyed metrics).
- **JSON cards**: structured objects with the same logical section keys.

Computes Flesch Reading Ease and Flesch–Kincaid grade level per section and
for combined selected fields (OVERALL_SELECTED_FIELDS).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import textstat

# Markdown UI cards live here — same directory as ``run_custom_factscore_ui_cards.py --md-dir``.
# (``factscore_out/ui_cards_custom/`` holds FactScore *eval outputs*, not these sources.)
REPO_ROOT = Path(__file__).resolve().parent
UI_CARDS_MARKDOWN_DIR = REPO_ROOT / "ui_cards"
READABILITY_OUTPUT_DIR = REPO_ROOT / "readability_out"
DEFAULT_UI_CARDS_READABILITY_CSV = READABILITY_OUTPUT_DIR / "ui_cards_readability.csv"

# --- Card naming / grouping helpers (Auto vs Manual) ---

_AUTO_STEM_RE = re.compile(r".*-\d{8}-\d{6}$", re.IGNORECASE)


def infer_card_variant(model_name: str) -> str:
    """Infer whether the card is an Auto-generated run vs a Manual card."""
    return "Auto" if _AUTO_STEM_RE.match(model_name.strip()) else "Manual"


def infer_model_family(model_name: str) -> str:
    """Infer the base model family from a UI-card stem / model name."""
    s = model_name.strip().lower()
    if s.startswith("dermgpt"):
        return "DermGPT"
    if s.startswith("dermasensor"):
        return "Dermasensor"
    if s.startswith("tandem"):
        return "Tandem"
    # fallback: best-effort title case
    return model_name.strip()


def add_display_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add standardized labels used in plots/tables:
    - model_family: DermGPT / Dermasensor / Tandem
    - card_variant: Auto / Manual
    - model_label: e.g. "DermGPT (Auto)"
    Keeps existing model_name unchanged for traceability.
    """
    if df.empty:
        return df

    out = df.copy()
    out["model_family"] = out["model_name"].astype(str).map(infer_model_family)
    out["card_variant"] = out["model_name"].astype(str).map(infer_card_variant)
    out["model_label"] = out["model_family"].astype(str) + " (" + out["card_variant"].astype(str) + ")"
    return out


def _bootstrap_ci_mean(x: np.ndarray, *, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
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


def _permutation_pvalue_diff_means(a: np.ndarray, b: np.ndarray, *, n_perm: int = 20000, seed: int = 0) -> float:
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
    # add-one smoothing
    return float((count + 1) / (n_perm + 1))

# Markdown `- **Label:**` bullets (normalized lowercase) → READABILITY_FIELDS keys
_MD_SINGLE_LABEL_TO_FIELD: dict[str, str] = {
    "summary": "summary",
    "intended use & workflow": "intended_use_and_workflow",
    "model limitations": "model_limitations",
    "ai system facts": "ai_system_facts",
    "developer-supplied warnings": "developer_supplied_warnings",
    "clinical risk level": "clinical_risk_level",
    "how to use": "how_to_use",
    "transparency information": "transparency_information",
}

# Under ### Usefulness / Efficacy (etc.), include these bullet labels in the combined section text.
_MD_METRIC_INNER_LABELS = frozenset(
    {
        "goal of metric(s)",
        "result",
        "interpretation",
    }
)

# UI cards use ``- **Label:** text`` (colon inside bold), not ``- **Label**: text``.
_BULLET_LINE = re.compile(r"^\s*-\s*\*\*([^*]+):\*\*\s*(.*)$")


def _normalize_md_label(label: str) -> str:
    s = label.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_reference_citations(text: str) -> str:
    """Remove bracket reference markers like ``[1]`` or ``[1, 8]`` from UI card prose."""
    return re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", text).strip()


def parse_ui_card_markdown(md: str, *, strip_citations: bool = True) -> dict[str, str]:
    """
    Extract section texts from a CHAI UI card Markdown file.

    - Standalone bullets (Summary, Intended Use & Workflow, …) map to READABILITY_FIELDS.
    - Under ``### Usefulness / Efficacy``, ``### Fairness & Equity``, and
      ``### Safety & Reliability``, bullets *Goal of Metric(s)*, *Result*, and
      *Interpretation* are concatenated into usefulness_efficacy_result,
      fairness_equity_interpretation, and safety_reliability_interpretation.
    """
    split_ref = re.split(r"(?im)^##\s*References\s*$", md, maxsplit=1)
    body = split_ref[0]

    singles: dict[str, str] = {}
    multi_parts: dict[str, list[str]] = {
        "usefulness_efficacy_result": [],
        "fairness_equity_interpretation": [],
        "safety_reliability_interpretation": [],
    }

    current_multi: str | None = None
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("###"):
            low = stripped.lower()
            if "usefulness" in low and "efficacy" in low:
                current_multi = "usefulness_efficacy_result"
            elif "fairness" in low and "equity" in low:
                current_multi = "fairness_equity_interpretation"
            elif "safety" in low and "reliability" in low:
                current_multi = "safety_reliability_interpretation"
            else:
                current_multi = None
            i += 1
            continue

        if stripped.startswith("##") and not stripped.startswith("###"):
            current_multi = None
            i += 1
            continue

        m = _BULLET_LINE.match(line)
        if m:
            label_raw = m.group(1).strip()
            content_parts = [m.group(2).strip()]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if _BULLET_LINE.match(nxt) or nxt.strip().startswith("##"):
                    break
                if nxt.strip():
                    content_parts.append(nxt.strip())
                i += 1
            text = " ".join(content_parts)
            if strip_citations:
                text = strip_reference_citations(text)

            nl = _normalize_md_label(label_raw)
            if current_multi and nl in _MD_METRIC_INNER_LABELS:
                multi_parts[current_multi].append(text)
            else:
                field = _MD_SINGLE_LABEL_TO_FIELD.get(nl)
                if field:
                    singles[field] = text
            continue

        i += 1

    out: dict[str, str] = dict(singles)
    for key, chunks in multi_parts.items():
        if chunks:
            out[key] = "\n\n".join(chunks)
    return out


READABILITY_FIELDS = [
    "summary",
    "intended_use_and_workflow",
    "model_limitations",
    "ai_system_facts",
    "usefulness_efficacy_result",
    "safety_reliability_interpretation",
    "fairness_equity_interpretation",
    "transparency_information",
    "developer_supplied_warnings",
    "clinical_risk_level",
    "how_to_use",
]


def load_model_card(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def score_text(text: str) -> dict[str, float | int | None]:
    text = clean_text(text)

    if not text:
        return {
            "word_count": 0,
            "sentence_count": 0,
            "flesch_reading_ease": None,
            "flesch_kincaid_grade": None,
        }

    word_count = textstat.lexicon_count(text, removepunct=True)
    sentence_count = textstat.sentence_count(text)

    if word_count == 0 or sentence_count == 0:
        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "flesch_reading_ease": None,
            "flesch_kincaid_grade": None,
        }

    try:
        fre = float(textstat.flesch_reading_ease(text))
        fk = float(textstat.flesch_kincaid_grade(text))
        if math.isnan(fre) or math.isnan(fk):
            fre, fk = None, None
    except (ZeroDivisionError, ValueError, TypeError):
        fre, fk = None, None

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "flesch_reading_ease": fre,
        "flesch_kincaid_grade": fk,
    }


def _sections_from_path(
    path: Path,
    fields: list[str],
    *,
    strip_citations: bool,
) -> tuple[str, dict[str, str]]:
    """Return (model_name, mapping of READABILITY_FIELDS subset -> raw section text)."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".md":
        md = path.read_text(encoding="utf-8")
        sections = parse_ui_card_markdown(md, strip_citations=strip_citations)
        model_name = path.stem
        filtered = {k: sections[k] for k in fields if k in sections and sections[k].strip()}
        return model_name, filtered

    if suffix == ".json":
        card = load_model_card(path)
        model_name = str(card.get("model_name", path.stem))
        filtered = {}
        for k in fields:
            v = card.get(k)
            if isinstance(v, str) and v.strip():
                filtered[k] = v
        return model_name, filtered

    raise ValueError(f"Unsupported file type (expected .md or .json): {path}")


def analyze_card(
    path: str | Path,
    fields: list[str] | None = None,
    *,
    strip_citations: bool = True,
) -> pd.DataFrame:
    path = Path(path)
    if fields is None:
        fields = list(READABILITY_FIELDS)

    model_name, sections = _sections_from_path(path, fields, strip_citations=strip_citations)

    rows: list[dict[str, Any]] = []

    for field in fields:
        value = sections.get(field)
        if isinstance(value, str) and value.strip():
            scores = score_text(value)
            rows.append(
                {
                    "model_name": model_name,
                    "file": path.name,
                    "section": field,
                    "format": path.suffix.lower().lstrip(".") or "unknown",
                    "text": clean_text(value),
                    **scores,
                }
            )

    combined_text = " ".join(row["text"] for row in rows)

    if combined_text.strip():
        overall_scores = score_text(combined_text)
        rows.append(
            {
                "model_name": model_name,
                "file": path.name,
                "section": "OVERALL_SELECTED_FIELDS",
                "format": path.suffix.lower().lstrip(".") or "unknown",
                "text": combined_text,
                **overall_scores,
            }
        )

    return pd.DataFrame(rows)


def iter_card_paths(
    input_dir: Path,
    *,
    recursive: bool = False,
    extensions: tuple[str, ...] = (".md", ".json"),
) -> list[Path]:
    exts = tuple(e if e.startswith(".") else f".{e}" for e in extensions)
    seen: set[Path] = set()
    out: list[Path] = []
    for ext in exts:
        pat = f"*{ext}"
        if recursive:
            found = input_dir.rglob(pat)
        else:
            found = input_dir.glob(pat)
        for p in found:
            if p.is_file():
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def analyze_folder(
    input_dir: str | Path,
    output_csv: str | Path,
    *,
    recursive: bool = False,
    fields: list[str] | None = None,
    extensions: tuple[str, ...] = (".md", ".json"),
    strip_citations: bool = True,
) -> pd.DataFrame:
    input_dir = Path(input_dir)
    paths = iter_card_paths(input_dir, recursive=recursive, extensions=extensions)

    if not paths:
        raise ValueError(
            f"No matching card files ({', '.join(extensions)}) in {input_dir} (recursive={recursive})"
        )

    all_rows: list[pd.DataFrame] = []
    for path in paths:
        df = analyze_card(path, fields=fields, strip_citations=strip_citations)
        all_rows.append(df)

    final_df = pd.concat(all_rows, ignore_index=True)
    final_df.to_csv(output_csv, index=False)
    return final_df


def _pivot_metric(
    df: pd.DataFrame,
    metric: str,
    *,
    exclude_overall: bool = True,
    model_col: str = "model_name",
) -> pd.DataFrame:
    work = df.copy()
    if exclude_overall:
        work = work[work["section"] != "OVERALL_SELECTED_FIELDS"]
    pivot = work.pivot_table(
        index=model_col,
        columns="section",
        values=metric,
        aggfunc="first",
    )
    return pivot


def plot_readability_heatmaps(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    exclude_overall: bool = True,
    figsize: tuple[float, float] = (14, 8),
    model_col: str = "model_name",
    filename_suffix: str = "",
) -> list[Path]:
    """
    Save heatmaps of Flesch Reading Ease and Flesch–Kincaid grade by model and section.
    Missing sections render as masked (NaN) cells in the heatmap.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = [
        (
            "flesch_reading_ease",
            f"readability_heatmap_flesch_reading_ease{filename_suffix}.png",
            "Flesch Reading Ease",
        ),
        (
            "flesch_kincaid_grade",
            f"readability_heatmap_flesch_kincaid_grade{filename_suffix}.png",
            "Flesch–Kincaid grade",
        ),
    ]

    saved: list[Path] = []
    for metric, filename, title in metrics:
        pivot = _pivot_metric(df, metric, exclude_overall=exclude_overall, model_col=model_col)
        if pivot.empty:
            continue

        fig, ax = plt.subplots(figsize=figsize)
        data = np.ma.masked_invalid(pivot.to_numpy(dtype=float))
        cmap = plt.get_cmap("RdYlGn").copy()
        cmap.set_bad(color=(0.9, 0.9, 0.9, 1.0))

        im = ax.imshow(data, aspect="auto", cmap=cmap)

        ax.set_xticks(np.arange(pivot.shape[1]))
        ax.set_yticks(np.arange(pivot.shape[0]))
        ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(pivot.index, fontsize=9)
        ax.set_title(f"{title} by model and section")

        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.set_ylabel(title)

        raw = pivot.to_numpy(dtype=float)
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = raw[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f"{val:.1f}", ha="center", va="center", color="black", fontsize=7)

        fig.tight_layout()
        out_path = output_dir / filename
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(out_path)

    return saved


def plot_overall_bars(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    figsize: tuple[float, float] = (10, 5),
    model_col: str = "model_name",
    filename_suffix: str = "",
) -> Path | None:
    """Bar chart of OVERALL_SELECTED_FIELDS scores per model."""
    overall = df[df["section"] == "OVERALL_SELECTED_FIELDS"].copy()
    if overall.empty:
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    models = overall[model_col].astype(str).tolist()
    x = np.arange(len(models))
    width = 0.35

    fre = pd.to_numeric(overall["flesch_reading_ease"], errors="coerce")
    fk = pd.to_numeric(overall["flesch_kincaid_grade"], errors="coerce")

    fig, ax1 = plt.subplots(figsize=figsize)
    ax2 = ax1.twinx()

    ax1.bar(x - width / 2, fre, width, label="Flesch Reading Ease", color="steelblue")
    ax2.bar(x + width / 2, fk, width, label="Flesch–Kincaid grade", color="darkorange")

    ax1.set_xticks(x)
    ax1.set_xticklabels(models, rotation=25, ha="right")
    ax1.set_ylabel("Flesch Reading Ease")
    ax2.set_ylabel("Flesch–Kincaid grade")
    ax1.set_title("Overall readability (combined selected fields)")

    lines_labels = [ax.get_legend_handles_labels() for ax in [ax1, ax2]]
    lines, labels = [sum(lol, []) for lol in zip(*lines_labels)]
    ax1.legend(lines, labels, loc="upper right")

    fig.tight_layout()
    out_path = output_dir / f"readability_overall_comparison{filename_suffix}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_overall_auto_vs_manual_boxplot(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    filename_suffix: str = "",
    figsize: tuple[float, float] = (10, 4.5),
    seed: int = 0,
) -> Path | None:
    """
    Boxplot comparing OVERALL_SELECTED_FIELDS readability for Auto vs Manual cards.
    Shows two subplots: Flesch Reading Ease and Flesch–Kincaid grade.
    Adds bootstrap 95% CI for the mean (per group) and a permutation-test p-value
    for difference in means (Auto - Manual).
    """
    overall = df[df["section"] == "OVERALL_SELECTED_FIELDS"].copy()
    if overall.empty or "card_variant" not in overall.columns:
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Keep only Auto/Manual groups with at least one row
    groups = ["Manual", "Auto"]
    data_by_group: dict[str, pd.DataFrame] = {
        g: overall[overall["card_variant"] == g].copy() for g in groups
    }
    if all(d.empty for d in data_by_group.values()):
        return None

    # If only one group is present, a comparison plot is not meaningful
    present = [g for g in groups if not data_by_group[g].empty]
    if len(present) < 2:
        return None

    metrics = [
        ("flesch_reading_ease", "Flesch Reading Ease"),
        ("flesch_kincaid_grade", "Flesch–Kincaid grade"),
    ]

    # Dedicated annotation panel prevents overlap/jumbled wrapping.
    from matplotlib.gridspec import GridSpec  # local import to keep top clean

    fig = plt.figure(figsize=figsize)
    gs = GridSpec(1, 3, figure=fig, width_ratios=[1.0, 1.0, 1.25], wspace=0.35)

    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_stats = fig.add_subplot(gs[0, 2])
    ax_stats.axis("off")

    axes = [ax_left, ax_right]

    stats_lines: list[str] = []
    stats_lines.append("Overall readability (OVERALL_SELECTED_FIELDS)")
    stats_lines.append("Groups: Manual vs Auto")
    stats_lines.append("")

    for ax, (metric, short_title) in zip(axes, metrics, strict=False):
        m_manual = pd.to_numeric(data_by_group["Manual"][metric], errors="coerce").to_numpy(dtype=float)
        m_auto = pd.to_numeric(data_by_group["Auto"][metric], errors="coerce").to_numpy(dtype=float)
        m_manual = m_manual[~np.isnan(m_manual)]
        m_auto = m_auto[~np.isnan(m_auto)]

        ax.boxplot(
            [m_manual, m_auto],
            labels=["Manual", "Auto"],
            showmeans=True,
            meanline=True,
            notch=True,
        )
        ax.set_title(short_title)
        if metric == "flesch_reading_ease":
            ax.set_ylabel("Higher = easier")
        else:
            ax.set_ylabel("Lower = easier")

        man_mean = float(np.mean(m_manual)) if m_manual.size else float("nan")
        auto_mean = float(np.mean(m_auto)) if m_auto.size else float("nan")
        man_ci = _bootstrap_ci_mean(m_manual, seed=seed)
        auto_ci = _bootstrap_ci_mean(m_auto, seed=seed + 1)
        p = _permutation_pvalue_diff_means(m_auto, m_manual, seed=seed)

        stats_lines.append(short_title)
        stats_lines.append(f"  n_manual={m_manual.size}   mean={man_mean:.2f}   95% CI [{man_ci[0]:.2f}, {man_ci[1]:.2f}]")
        stats_lines.append(f"  n_auto  ={m_auto.size}   mean={auto_mean:.2f}   95% CI [{auto_ci[0]:.2f}, {auto_ci[1]:.2f}]")
        stats_lines.append(f"  permutation p-value (Δmeans Auto−Manual): {p:.4f}")
        stats_lines.append("")

    # Render stats text in its own panel with a light box.
    ax_stats.text(
        0.0,
        1.0,
        "\n".join(stats_lines).rstrip(),
        ha="left",
        va="top",
        fontsize=9,
        linespacing=1.25,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dddddd"),
    )

    fig.suptitle("Auto vs Manual readability (boxplots)", y=1.02)
    fig.tight_layout()

    out_path = output_dir / f"readability_overall_auto_vs_manual_boxplot{filename_suffix}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_mode_comparison_boxplots(
    *,
    sourcecheckup_manual: list[float],
    sourcecheckup_auto: list[float],
    factscore_strict_manual: list[float],
    factscore_strict_auto: list[float],
    factscore_partial_manual: list[float],
    factscore_partial_auto: list[float],
    output_path: str | Path,
    title: str = "Auto vs Manual: SourceCheckup + FactScore-style",
    seed: int = 0,
) -> Path:
    """
    Boxplots comparing Manual vs Auto for:
    - SourceCheckup fraction supported (%)
    - FactScore strict (%)
    - FactScore partial-credit (%)

    Layout: 2x2 grid with three boxplots + one stats panel (no overlap).
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = [
        ("SourceCheckup (%)", np.array(sourcecheckup_manual, dtype=float), np.array(sourcecheckup_auto, dtype=float)),
        ("FactScore strict (%)", np.array(factscore_strict_manual, dtype=float), np.array(factscore_strict_auto, dtype=float)),
        (
            "FactScore partial-credit (%)",
            np.array(factscore_partial_manual, dtype=float),
            np.array(factscore_partial_auto, dtype=float),
        ),
    ]

    from matplotlib.gridspec import GridSpec  # local import

    fig = plt.figure(figsize=(11.5, 7.2))
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1.0, 1.0], height_ratios=[1.0, 1.0], wspace=0.35, hspace=0.35)

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_stats = fig.add_subplot(gs[1, 1])
    ax_stats.axis("off")

    axes = [ax_a, ax_b, ax_c]

    stats_lines: list[str] = []
    stats_lines.append(title)
    stats_lines.append("Groups: Manual vs Auto (values are % per model; n=3 each group)")
    stats_lines.append("")

    for idx, (ax, (metric_name, manual_vals, auto_vals)) in enumerate(zip(axes, metrics, strict=False)):
        manual_vals = manual_vals[~np.isnan(manual_vals)]
        auto_vals = auto_vals[~np.isnan(auto_vals)]

        ax.boxplot(
            [manual_vals, auto_vals],
            labels=["Manual", "Auto"],
            showmeans=True,
            meanline=True,
            notch=True,
        )
        ax.set_title(metric_name)
        ax.set_ylabel("Percent")
        ax.set_ylim(0, 100)

        man_mean = float(np.mean(manual_vals)) if manual_vals.size else float("nan")
        auto_mean = float(np.mean(auto_vals)) if auto_vals.size else float("nan")
        man_ci = _bootstrap_ci_mean(manual_vals, seed=seed + 10 * idx)
        auto_ci = _bootstrap_ci_mean(auto_vals, seed=seed + 10 * idx + 1)
        p = _permutation_pvalue_diff_means(auto_vals, manual_vals, seed=seed + 10 * idx + 2)

        stats_lines.append(metric_name)
        stats_lines.append(
            f"  Manual: n={manual_vals.size} mean={man_mean:.2f}  95% CI [{man_ci[0]:.2f}, {man_ci[1]:.2f}]"
        )
        stats_lines.append(
            f"  Auto:   n={auto_vals.size} mean={auto_mean:.2f}  95% CI [{auto_ci[0]:.2f}, {auto_ci[1]:.2f}]"
        )
        stats_lines.append(f"  permutation p-value (Δmeans Auto−Manual): {p:.4f}")
        stats_lines.append("")

    ax_stats.text(
        0.0,
        1.0,
        "\n".join(stats_lines).rstrip(),
        ha="left",
        va="top",
        fontsize=9,
        linespacing=1.25,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dddddd"),
    )

    fig.suptitle(title, y=0.99)
    # Use constrained layout to avoid tight_layout issues with mixed axes.
    try:
        fig.set_constrained_layout(True)
    except Exception:
        pass
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_readability_plots(
    df: pd.DataFrame,
    output_dir: str | Path,
    *,
    exclude_overall_from_heatmap: bool = True,
    model_col: str = "model_name",
    filename_suffix: str = "",
) -> list[Path]:
    """Generate default figures for a multi-model results table."""
    output_dir = Path(output_dir)
    paths: list[Path] = []

    paths.extend(
        plot_readability_heatmaps(
            df,
            output_dir,
            exclude_overall=exclude_overall_from_heatmap,
            model_col=model_col,
            filename_suffix=filename_suffix,
        )
    )

    # Prefer a single, publication-friendly overall plot comparing Auto vs Manual.
    box = plot_overall_auto_vs_manual_boxplot(
        df,
        output_dir,
        filename_suffix=filename_suffix,
    )
    if box is not None:
        paths.append(box)

    return paths
