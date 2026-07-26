"""
Generate Auto vs Manual evaluation boxplots from pasted summary numbers.

This uses the same "boxplots + dedicated stats panel" style as the readability plot.
"""

from __future__ import annotations

from pathlib import Path

from readability_analysis import plot_mode_comparison_boxplots


def main() -> None:
    # Values are percentages (0-100), grouped by model within each mode.
    sourcecheckup_manual = [80.6, 91.3, 84.8]  # DermGPT, Dermasensor, Tandem updated
    sourcecheckup_auto = [59.1, 68.1, 92.3]  # DermGPT auto, Dermasensor, Tandem

    factscore_strict_manual = [80.95, 49.18, 70.00]
    factscore_strict_auto = [35.85, 53.85, 52.94]

    factscore_partial_manual = [88.10, 63.93, 72.50]
    factscore_partial_auto = [50.00, 57.21, 55.88]

    out = plot_mode_comparison_boxplots(
        sourcecheckup_manual=sourcecheckup_manual,
        sourcecheckup_auto=sourcecheckup_auto,
        factscore_strict_manual=factscore_strict_manual,
        factscore_strict_auto=factscore_strict_auto,
        factscore_partial_manual=factscore_partial_manual,
        factscore_partial_auto=factscore_partial_auto,
        output_path=Path("figures") / "ui_cards" / "sourcecheckup_factscore_auto_vs_manual_boxplots.png",
        title="Auto vs Manual: SourceCheckup + FactScore-style (from summary numbers)",
    )

    print(f"Saved plot to {out}")


if __name__ == "__main__":
    main()

