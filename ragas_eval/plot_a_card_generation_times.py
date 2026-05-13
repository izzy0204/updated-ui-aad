from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
IN_CSV = ROOT / "a_card_generation_times.csv"
OUT_DIR = ROOT / "figures"
OUT_PNG = OUT_DIR / "a_card_generation_times_median_range.png"


def main() -> None:
    import matplotlib.pyplot as plt

    if not IN_CSV.is_file():
        raise SystemExit(f"Missing {IN_CSV}. Run scripts/time_generate_ui_a_cards.py first.")

    df = pd.read_csv(IN_CSV)
    df["model"] = df["label"].astype(str).str.split(" · ").str[-1]

    # One timing per model in the current dataset. Still compute generically.
    agg = (
        df.groupby("model", as_index=False)["elapsed_seconds"]
        .agg(median="median", min="min", max="max")
        .set_index("model")
        .reindex(["DermaSensor", "DermGPT", "Tandem"])
        .reset_index()
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    x = list(range(len(agg)))
    y = agg["median"].to_numpy()
    yerr_low = (agg["median"] - agg["min"]).to_numpy()
    yerr_high = (agg["max"] - agg["median"]).to_numpy()

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.errorbar(
        x,
        y,
        yerr=[yerr_low, yerr_high],
        fmt="o",
        capsize=6,
        markersize=7,
        color="#4C78A8",
        ecolor="#4C78A8",
        elinewidth=2,
    )
    ax.set_xticks(x, agg["model"].tolist())
    ax.set_title("UI A card generation time (median and range)")
    ax.set_ylabel("Seconds")
    ax.set_xlabel("")
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.5)

    for xi, yi in zip(x, y):
        ax.annotate(f"{yi:.3f}s", (xi, yi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=200)
    plt.close()

    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()

