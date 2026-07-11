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
    clinical_stem: str


TARGETS: list[Target] = [
    Target(
        label="A · DermaSensor",
        model_name="DermaSensor",
        developer_name="DermaSensor, Inc.",
        clinical_stem="dermasensor-20260501-192348",
    ),
    Target(
        label="A · DermGPT",
        model_name="DermGPT",
        developer_name="",
        clinical_stem="dermgpt-20260429-173126",
    ),
    Target(
        label="A · Tandem",
        model_name="Tandem",
        developer_name="",
        clinical_stem="tandem-20260501-043225",
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

        json_path: Optional[Path] = None
        md_path: Optional[Path] = None
        cites_path: Optional[Path] = None
        outs = content.get("paths")
        if outs and getattr(outs, "json_path", None):
            json_path = Path(outs.json_path)
            md_path = Path(outs.md_path) if getattr(outs, "md_path", None) else None
            cites_path = (
                Path(outs.citations_json_path) if getattr(outs, "citations_json_path", None) else None
            )

        stem = t.clinical_stem
        copied_json = preloaded_dir / f"{stem}.clinical.json"
        copied_md = preloaded_dir / f"{stem}.clinical.md"
        copied_cites = preloaded_dir / f"{stem}.citations.json"
        if json_path and json_path.exists():
            shutil.copyfile(json_path, copied_json)
        if md_path and md_path.exists():
            shutil.copyfile(md_path, copied_md)
        elif isinstance(content.get("markdown"), str) and content["markdown"].strip():
            copied_md.write_text(content["markdown"], encoding="utf-8")
        if cites_path and cites_path.exists():
            shutil.copyfile(cites_path, copied_cites)

        report_rows.append(
            {
                "label": t.label,
                "model_name": t.model_name,
                "developer_name": t.developer_name,
                "started_utc": start_iso,
                "ended_utc": end_iso,
                "elapsed_seconds": round(elapsed_s, 3),
                "pipeline_json_path": str(json_path) if json_path else "",
                "preloaded_clinical_json": str(copied_json),
                "preloaded_clinical_md": str(copied_md),
                "preloaded_citations_json": str(copied_cites),
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

