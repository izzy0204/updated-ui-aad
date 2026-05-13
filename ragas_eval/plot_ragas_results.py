from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATASET_CSV = ROOT / "ragas_dataset.csv"
RESULTS_CSV = ROOT / "ragas_results.csv"
OUT_DIR = ROOT / "figures"


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

    # Only compare by model (Auto cards only)
    merged = merged[merged["provenance"].eq("A")].copy()

    # Averages per model
    summary = (
        merged.groupby(["model"], as_index=False)
        .agg(
            avg_faithfulness=("faithfulness", "mean"),
            avg_answer_relevancy=("answer_relevancy", "mean"),
        )
        .sort_values(["model"])
    )
    summary.to_csv(ROOT / "ragas_model_summary.csv", index=False)

    model_order = ["DermaSensor", "DermGPT", "Tandem"]
    summary = summary.set_index("model").reindex(model_order).reset_index()

    plot_df = summary.set_index("model")[["avg_faithfulness", "avg_answer_relevancy"]].copy()
    plot_df.columns = ["Faithfulness", "Answer relevancy"]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot_df.plot(
        kind="bar",
        ax=ax,
        rot=0,
        color=["#4C78A8", "#F58518"],
    )
    ax.set_title("RAGAS average faithfulness and answer relevancy by model")
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
    combined_path = OUT_DIR / "ragas_metrics_by_model.png"
    plt.savefig(combined_path, dpi=200, bbox_inches="tight", pad_inches=0.2)
    plt.close()

    # Optional: per-field chart (answer relevancy) for quick diagnostics
    field_summary = (
        merged.groupby(["model", "field"], as_index=False)
        .agg(avg_answer_relevancy=("answer_relevancy", "mean"))
        .sort_values(["model", "field"])
    )
    field_summary.to_csv(ROOT / "ragas_field_summary.csv", index=False)

    print(
        "Wrote:\n"
        f"- {combined_path}\n"
        f"- {ROOT / 'ragas_model_summary.csv'}"
    )


if __name__ == "__main__":
    main()

