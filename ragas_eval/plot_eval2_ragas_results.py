"""
Generate RAGAS figures for the eval-2 round (5 auto-generated models),
reading real numbers from ragas_eval/eval2_ragas_dataset.csv +
eval2_ragas_results.csv.

This mirrors ragas_eval/plot_ragas_results.py, which is hardcoded to the
original 3-model round (ragas_dataset.csv / ragas_results.csv,
model_order=["DermaSensor","DermGPT","Tandem"]) and writes flat into
ragas_eval/figures/ -- left untouched so the old round's outputs stay
reproducible. This script targets the eval-2 files/model set and writes
into ragas_eval/figures/eval2/ instead.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATASET_CSV = ROOT / "eval2_ragas_dataset.csv"
RESULTS_CSV = ROOT / "eval2_ragas_results.csv"
OUT_DIR = ROOT / "figures" / "eval2"

MODEL_ORDER = ["DermGPT", "DermaSensor", "SkinAnalytics", "SkinVision", "Tandem"]


def main() -> None:
    import matplotlib.pyplot as plt

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset = pd.read_csv(DATASET_CSV)
    results = pd.read_csv(RESULTS_CSV).rename(
        columns={"user_input": "question", "response": "answer", "retrieved_contexts": "contexts"}
    )

    merged = dataset.merge(
        results[["question", "answer", "faithfulness", "answer_relevancy"]],
        on=["question", "answer"],
        how="left",
        validate="one_to_one",
    )

    merged["provenance"] = merged["card_label"].str.split(" · ").str[0]
    merged["model"] = merged["card_label"].str.split(" · ").str[1]

    # Only compare by model (Auto cards only -- this dataset has no Manual "M ·" rows)
    merged = merged[merged["provenance"].eq("A")].copy()

    missing_models = set(MODEL_ORDER) - set(merged["model"].unique())
    if missing_models:
        raise SystemExit(f"[ERROR] Missing RAGAS rows for model(s): {sorted(missing_models)}")

    # Averages per model
    summary = (
        merged.groupby(["model"], as_index=False)
        .agg(
            avg_faithfulness=("faithfulness", "mean"),
            avg_answer_relevancy=("answer_relevancy", "mean"),
        )
        .sort_values(["model"])
    )
    summary.to_csv(OUT_DIR / "ragas_eval2_model_summary.csv", index=False)

    summary = summary.set_index("model").reindex(MODEL_ORDER).reset_index()

    plot_df = summary.set_index("model")[["avg_faithfulness", "avg_answer_relevancy"]].copy()
    plot_df.columns = ["Faithfulness", "Answer relevancy"]

    fig, ax = plt.subplots(figsize=(max(9, 1.7 * len(MODEL_ORDER) + 2.0), 4.5))
    plot_df.plot(
        kind="bar",
        ax=ax,
        rot=0,
        color=["#4C78A8", "#F58518"],
    )
    ax.set_title("RAGAS average faithfulness and answer relevancy by model (eval-2, Auto cards)")
    ax.set_ylabel("Score")
    ax.set_xlabel("")
    ax.legend(
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0,
    )
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.5)
    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", padding=2, fontsize=8)

    plt.tight_layout()
    combined_path = OUT_DIR / "ragas_eval2_metrics_by_model.png"
    plt.savefig(combined_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    plt.close()

    # Per-field chart (answer relevancy) for quick diagnostics
    field_summary = (
        merged.groupby(["model", "field"], as_index=False)
        .agg(avg_answer_relevancy=("answer_relevancy", "mean"))
        .sort_values(["model", "field"])
    )
    field_summary.to_csv(OUT_DIR / "ragas_eval2_field_summary.csv", index=False)

    field_pivot = field_summary.pivot(index="field", columns="model", values="avg_answer_relevancy")
    field_pivot = field_pivot.reindex(columns=[m for m in MODEL_ORDER if m in field_pivot.columns])
    field_pivot["__mean"] = field_pivot.mean(axis=1)
    field_pivot = field_pivot.sort_values("__mean").drop(columns="__mean")

    fig2, ax2 = plt.subplots(figsize=(9, 5.5))
    field_pivot.plot(kind="barh", ax=ax2, width=0.8)
    ax2.set_title("RAGAS answer relevancy by field and model (eval-2, Auto cards)")
    ax2.set_xlabel("Answer relevancy")
    ax2.set_ylabel("")
    ax2.set_xlim(0, 1.0)
    ax2.grid(axis="x", linestyle="--", linewidth=0.6, alpha=0.5)
    ax2.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
    plt.tight_layout()
    field_path = OUT_DIR / "ragas_eval2_answer_relevancy_by_field.png"
    plt.savefig(field_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    plt.close()

    print(
        "Wrote:\n"
        f"- {combined_path}\n"
        f"- {field_path}\n"
        f"- {OUT_DIR / 'ragas_eval2_model_summary.csv'}\n"
        f"- {OUT_DIR / 'ragas_eval2_field_summary.csv'}"
    )


if __name__ == "__main__":
    main()
