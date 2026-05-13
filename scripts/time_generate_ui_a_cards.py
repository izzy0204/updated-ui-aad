#!/usr/bin/env python3
"""
Time + generate the three UI "A ·" preloaded model cards.

What it does
------------
- Runs CardGenPipeline.generate_model_card(...) for each target model.
- Measures wall-clock duration per card (start/end/elapsed seconds).
- Writes generated artifacts to `outputs/` (pipeline default).
- Copies the generated markdown into the exact UI preloaded filenames under
  `src/core/pages/preloaded_cards/` so the DermAUTO-CARD sidebar "A · ..." cards update.
- Writes a timing report CSV to `ragas_eval/a_card_generation_times.csv`.

Notes
-----
- This uses networked retrieval + LLM calls, so runtime depends heavily on API latency.
- Requires your existing API keys in `.env` (Gemini/Google for generation).
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(REPO_ROOT / ".env")
load_dotenv()

from pipelines.cardgen_pipeline import CardGenPipeline  # noqa: E402


@dataclass
class Target:
    label: str
    model_name: str
    developer_name: str
    out_md_filename: str


TARGETS: list[Target] = [
    Target(
        label="A · DermaSensor",
        model_name="DermaSensor",
        developer_name="DermaSensor, Inc.",
        out_md_filename="dermasensor-20260501-192348.md",
    ),
    Target(
        label="A · DermGPT",
        model_name="DermGPT",
        developer_name="",
        out_md_filename="dermgpt-20260429-173126.md",
    ),
    Target(
        label="A · Tandem",
        model_name="Tandem",
        developer_name="",
        out_md_filename="tandem-20260501-043225.md",
    ),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="outputs", help="Pipeline artifact directory (default: outputs)")
    p.add_argument(
        "--preloaded-dir",
        default=str(REPO_ROOT / "src/core/pages/preloaded_cards"),
        help="Where to copy the final UI markdown files",
    )
    p.add_argument("--iters", type=int, default=3)
    p.add_argument("--coverage", type=float, default=0.60)
    p.add_argument("--finalize", default="not_specified", choices=["not_specified", "none"])
    p.add_argument("--no-discovery", action="store_true", help="Disable web discovery step")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    preloaded_dir = Path(args.preloaded_dir)
    preloaded_dir.mkdir(parents=True, exist_ok=True)

    pipeline = CardGenPipeline(out_dir=str(out_dir), use_web_discovery=not args.no_discovery)

    report_rows: list[dict] = []

    for t in TARGETS:
        start_wall = time.time()
        start_iso = utc_now_iso()

        chai_card, sources, content = asyncio.run(
            pipeline.generate_model_card(
                model_name=t.model_name,
                developer_name=t.developer_name,
                iters=args.iters,
                coverage_target=args.coverage,
                finalize_policy=args.finalize,
                write_files=True,
                file_prefix=t.model_name.lower(),
            )
        )

        end_iso = utc_now_iso()
        elapsed_s = time.time() - start_wall

        md_path: Optional[Path] = None
        outs = content.get("paths")
        if outs and getattr(outs, "md_path", None):
            md_path = Path(outs.md_path)

        copied_to = preloaded_dir / t.out_md_filename
        if md_path and md_path.exists():
            shutil.copyfile(md_path, copied_to)
        else:
            # As a fallback, write markdown from content if available
            md_text = content.get("markdown", "")
            if isinstance(md_text, str) and md_text.strip():
                copied_to.write_text(md_text, encoding="utf-8")

        report_rows.append(
            {
                "label": t.label,
                "model_name": t.model_name,
                "developer_name": t.developer_name,
                "started_utc": start_iso,
                "ended_utc": end_iso,
                "elapsed_seconds": round(elapsed_s, 3),
                "pipeline_md_path": str(md_path) if md_path else "",
                "preloaded_md_path": str(copied_to),
                "sources_count": len((sources or {}).get("citations", {}) or {}),
            }
        )

    import pandas as pd

    out_csv = REPO_ROOT / "ragas_eval" / "a_card_generation_times.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows).to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()

