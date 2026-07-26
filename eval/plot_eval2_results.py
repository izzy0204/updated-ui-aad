"""
Generate FactScore + SourceCheckup figures for the eval-2 round (5 models,
Manual vs Auto), reading real numbers from the JSON summaries instead of
hand-transcribing them.

The original `run_mode_bargraphs_from_text.py` / `run_mode_comparison_plot_from_text.py`
hardcode percentages as literal Python lists and don't read any file -- fine
for a one-off snapshot, but they'd silently go stale on a rerun. This script
reuses their exact plotting functions (`plot_sourcecheckup_bars`,
`plot_factscore_bars`, `plot_mode_comparison_boxplots`) with live data from:
  - eval/factscore_out/eval2_cards/factscore_like_summary_ui_cards.json
  - eval/sourcecheckup_out/results_eval2_cards/sourcecheckup_all_summaries.json

Card name -> (model family, Manual/Auto variant) uses the same
`infer_model_family` / `infer_card_variant` helpers `readability_analysis.py`
already uses, so classification stays consistent across every eval figure in
this repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_ROOT))

import numpy as np  # noqa: E402

from readability_analysis import (  # noqa: E402
    infer_card_variant,
    infer_model_family,
    plot_mode_comparison_boxplots,
)
from run_mode_bargraphs_from_text import (  # noqa: E402
    _set_black_theme,
    plot_factscore_bars,
    plot_sourcecheckup_bars,
)

FACTSCORE_SUMMARY = EVAL_ROOT / "factscore_out" / "eval2_cards" / "factscore_like_summary_ui_cards.json"
SOURCECHECKUP_SUMMARY = EVAL_ROOT / "sourcecheckup_out" / "results_eval2_cards" / "sourcecheckup_all_summaries.json"
FIGURES_OUT = EVAL_ROOT / "figures" / "eval2"

# Fixed model display order, shared across all eval-2 figures.
MODEL_ORDER = ["DermGPT", "Dermasensor", "SkinAnalytics", "SkinVision", "Tandem"]


def load_summary(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"[ERROR] Missing summary file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def split_by_variant(rows: list[dict], *, strict_key: str, partial_key: str) -> dict[str, dict[str, tuple[float, float]]]:
    """model_family -> variant ('Manual'/'Auto') -> (strict_pct, partial_pct)."""
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for row in rows:
        name = str(row.get("name", ""))
        family = infer_model_family(name)
        variant = infer_card_variant(name)
        strict_pct = float(row[strict_key]) * 100.0
        partial_pct = float(row[partial_key]) * 100.0
        out.setdefault(family, {})[variant] = (strict_pct, partial_pct)
    return out


def ordered_values(by_family: dict[str, dict[str, tuple[float, float]]], variant: str, idx: int) -> np.ndarray:
    values = []
    for model in MODEL_ORDER:
        entry = by_family.get(model, {}).get(variant)
        if entry is None:
            raise SystemExit(f"[ERROR] Missing {variant} result for model '{model}' -- check the summary files cover all 10 eval-2 cards.")
        values.append(entry[idx])
    return np.array(values, dtype=float)


def main() -> None:
    _set_black_theme()
    FIGURES_OUT.mkdir(parents=True, exist_ok=True)

    factscore_rows = load_summary(FACTSCORE_SUMMARY)
    sourcecheckup_rows = load_summary(SOURCECHECKUP_SUMMARY)

    fs_by_family = split_by_variant(factscore_rows, strict_key="score_strict", partial_key="score_partial_credit")
    sc_by_family = split_by_variant(sourcecheckup_rows, strict_key="strict_score", partial_key="partial_credit_score")

    # ---- SourceCheckup bar graph (strict/fraction-supported only, matching the original style)
    sc_manual = ordered_values(sc_by_family, "Manual", 0)
    sc_auto = ordered_values(sc_by_family, "Auto", 0)
    out_sc = FIGURES_OUT / "sourcecheckup_bargraph.png"
    plot_sourcecheckup_bars(models=MODEL_ORDER, manual=sc_manual, auto=sc_auto, out_path=out_sc)
    print(f"[OK] Saved {out_sc}")

    # ---- FactScore bar graph (strict + partial-credit, Manual vs Auto)
    fs_manual_strict = ordered_values(fs_by_family, "Manual", 0)
    fs_manual_partial = ordered_values(fs_by_family, "Manual", 1)
    fs_auto_strict = ordered_values(fs_by_family, "Auto", 0)
    fs_auto_partial = ordered_values(fs_by_family, "Auto", 1)
    out_fs = FIGURES_OUT / "factscore_bargraph.png"
    plot_factscore_bars(
        models=MODEL_ORDER,
        manual_strict=fs_manual_strict,
        manual_partial=fs_manual_partial,
        auto_strict=fs_auto_strict,
        auto_partial=fs_auto_partial,
        out_path=out_fs,
    )
    print(f"[OK] Saved {out_fs}")

    # ---- Combined Manual vs Auto boxplots (SourceCheckup + FactScore strict + FactScore partial)
    out_box = FIGURES_OUT / "sourcecheckup_factscore_auto_vs_manual_boxplots.png"
    plot_mode_comparison_boxplots(
        sourcecheckup_manual=list(sc_manual),
        sourcecheckup_auto=list(sc_auto),
        factscore_strict_manual=list(fs_manual_strict),
        factscore_strict_auto=list(fs_auto_strict),
        factscore_partial_manual=list(fs_manual_partial),
        factscore_partial_auto=list(fs_auto_partial),
        output_path=out_box,
        title="Auto vs Manual: SourceCheckup + FactScore-style (eval-2, 5 models)",
    )
    print(f"[OK] Saved {out_box}")


if __name__ == "__main__":
    main()
