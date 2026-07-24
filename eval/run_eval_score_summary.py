"""
Summarize FactScore-like and SourceCheckup scores for UI cards.

Reads:
- factscore_out/ui_cards_custom/factscore_like_summary_ui_cards.json
- sourcecheckup_out/results_upstream_ui_cards/*_upstream_sourcecheckup_results.summary.json

Writes a CSV with per-model averages (DermGPT / Dermasensor / Tandem),
split by Auto vs Manual.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from readability_analysis import infer_card_variant, infer_model_family


def load_factscore_summary(path: Path) -> pd.DataFrame:
    rows = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(columns={"name": "card_name"})
    df["model_family"] = df["card_name"].astype(str).map(infer_model_family)
    df["card_variant"] = df["card_name"].astype(str).map(infer_card_variant)
    df["source"] = "factscore_like"
    return df


def load_sourcecheckup_summaries(results_dir: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for p in sorted(results_dir.glob("*_upstream_sourcecheckup_results.summary.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Use file stem for naming (matches md stem variants)
        card_name = p.name.replace("_upstream_sourcecheckup_results.summary.json", "")
        rows.append(
            {
                "card_name": card_name,
                "fraction_supported": obj.get("fraction_supported"),
                "unique_statements": obj.get("unique_statements"),
                "statements_with_at_least_one_found": obj.get("statements_with_at_least_one_found"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["model_family"] = df["card_name"].astype(str).map(infer_model_family)
    df["card_variant"] = df["card_name"].astype(str).map(infer_card_variant)
    df["source"] = "sourcecheckup"
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize avg FactScore + SourceCheckup scores by model.")
    ap.add_argument(
        "--factscore-summary",
        default="factscore_out/ui_cards_custom/factscore_like_summary_ui_cards.json",
        help="Path to FactScore-like summary JSON.",
    )
    ap.add_argument(
        "--sourcecheckup-dir",
        default="sourcecheckup_out/results_upstream_ui_cards",
        help="Directory containing SourceCheckup *.summary.json files.",
    )
    ap.add_argument(
        "--output",
        default="eval_score_out/ui_cards_model_avg_scores.csv",
        help="Output CSV path.",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    fact_path = (root / args.factscore_summary).resolve()
    src_dir = (root / args.sourcecheckup_dir).resolve()
    out_path = root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dfs: list[pd.DataFrame] = []
    if fact_path.is_file():
        dfs.append(load_factscore_summary(fact_path))
    if src_dir.is_dir():
        dfs.append(load_sourcecheckup_summaries(src_dir))

    if not dfs or all(d.empty for d in dfs):
        raise SystemExit("No inputs found / parsed for FactScore-like or SourceCheckup summaries.")

    combined = pd.concat([d for d in dfs if not d.empty], ignore_index=True)

    # Aggregate per (source, model_family, card_variant)
    agg_rows: list[pd.DataFrame] = []

    # FactScore-like: average strict + partial credit
    fs = combined[combined["source"] == "factscore_like"].copy()
    if not fs.empty:
        fs_agg = (
            fs.groupby(["source", "model_family", "card_variant"], as_index=False)
            .agg(
                n_cards=("card_name", "count"),
                score_strict_mean=("score_strict", "mean"),
                score_partial_credit_mean=("score_partial_credit", "mean"),
            )
            .sort_values(["model_family", "card_variant"])
        )
        agg_rows.append(fs_agg)

    # SourceCheckup: average fraction_supported
    sc = combined[combined["source"] == "sourcecheckup"].copy()
    if not sc.empty:
        sc["fraction_supported"] = pd.to_numeric(sc["fraction_supported"], errors="coerce")
        sc_agg = (
            sc.groupby(["source", "model_family", "card_variant"], as_index=False)
            .agg(
                n_cards=("card_name", "count"),
                fraction_supported_mean=("fraction_supported", "mean"),
            )
            .sort_values(["model_family", "card_variant"])
        )
        agg_rows.append(sc_agg)

    final = pd.concat(agg_rows, ignore_index=True) if agg_rows else pd.DataFrame()
    final.to_csv(out_path, index=False)

    print(f"Saved model averages to {out_path}")
    with pd.option_context("display.max_rows", 200, "display.max_columns", 200):
        print(final.to_string(index=False))


if __name__ == "__main__":
    main()

