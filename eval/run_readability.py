"""CLI to run readability analysis on dermatology UI card Markdown and JSON model cards."""

from __future__ import annotations

import argparse
from pathlib import Path

from readability_analysis import (
    DEFAULT_UI_CARDS_READABILITY_CSV,
    UI_CARDS_MARKDOWN_DIR,
    add_display_labels,
    analyze_card,
    analyze_folder,
    save_readability_plots,
)

EVAL_ROOT = Path(__file__).resolve().parent


def _parse_extensions(spec: str) -> tuple[str, ...]:
    parts = [p.strip().lower() for p in spec.split(",") if p.strip()]
    out: list[str] = []
    for p in parts:
        if not p.startswith("."):
            p = "." + p
        out.append(p)
    return tuple(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run readability analysis on CHAI UI card Markdown (ui_cards/*.md) "
            "and/or structured JSON model cards."
        ),
    )

    parser.add_argument(
        "--input",
        default=str(UI_CARDS_MARKDOWN_DIR),
        help=(
            "Path to a single .md/.json card or a directory of cards. "
            f"Default: Markdown UI cards under {UI_CARDS_MARKDOWN_DIR} "
            "(same folder as run_custom_factscore_ui_cards.py --md-dir)."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_UI_CARDS_READABILITY_CSV),
        help=(
            "Path to output CSV file. "
            f"Default: {DEFAULT_UI_CARDS_READABILITY_CSV}"
        ),
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When input is a directory, include matching files in subfolders.",
    )

    parser.add_argument(
        "--extensions",
        default="md",
        metavar="LIST",
        help=(
            "Comma-separated file extensions to scan in directory mode: md, json "
            '(default: "md" for UI cards). Example: --extensions md,json'
        ),
    )

    parser.add_argument(
        "--no-strip-citations",
        action="store_true",
        help="Keep bracket reference markers like [1] in Markdown-derived section text.",
    )

    parser.add_argument(
        "--plot-dir",
        default=None,
        metavar="DIR",
        help="If set, save matplotlib figures (heatmaps + overall bar chart) to this directory.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    strip_citations = not args.no_strip_citations
    extensions = _parse_extensions(args.extensions)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        df = analyze_card(input_path, strip_citations=strip_citations)
        df.to_csv(out_path, index=False)
    elif input_path.is_dir():
        df = analyze_folder(
            input_path,
            out_path,
            recursive=args.recursive,
            extensions=extensions,
            strip_citations=strip_citations,
        )
    else:
        hint = ""
        raw = str(args.input).lower()
        if "path/to" in raw:
            hint = (
                "\n  Hint: replace placeholder paths like `path/to/cards` with a real directory "
                f"(for this repo, Markdown UI cards live under `{UI_CARDS_MARKDOWN_DIR}`), "
                "or omit `--input` to use that default."
            )
        raise FileNotFoundError(f"Input path does not exist: {input_path}{hint}")

    print(f"Saved readability results to {out_path}")

    # Add standardized names for plotting and downstream grouping
    df = add_display_labels(df)

    display_cols = [
        "model_label",
        "model_name",
        "format",
        "section",
        "word_count",
        "sentence_count",
        "flesch_reading_ease",
        "flesch_kincaid_grade",
    ]
    cols = [c for c in display_cols if c in df.columns]
    if df.empty:
        print("(No sections extracted — check Markdown bullets / JSON keys vs READABILITY_FIELDS.)")
    else:
        print(df[cols].to_string())

    if args.plot_dir:
        # Plot with standardized labels (Dermasensor (Manual), Dermasensor (Auto), etc.)
        plot_paths = save_readability_plots(df, args.plot_dir, model_col="model_label")
        print(f"Saved plots to {args.plot_dir}:")
        for p in plot_paths:
            print(f"  - {p}")

        # Also emit the same plots but restricted to Auto cards only.
        auto_df = df[df.get("card_variant", "") == "Auto"].copy()
        if not auto_df.empty:
            auto_plot_paths = save_readability_plots(
                auto_df,
                args.plot_dir,
                model_col="model_label",
                filename_suffix="_auto_only",
            )
            print("Saved auto-only plots:")
            for p in auto_plot_paths:
                print(f"  - {p}")


if __name__ == "__main__":
    main()
