#!/usr/bin/env python3
"""Retry auto-generation for Tandem/Forus alone. Previous attempts either hit a
429 from withtandem.com/forus.com, or (once real search results came through)
collided with the unrelated "Tandem Diabetes Care" company. The company
rebranded from Tandem to Forus, so searching for "Forus" specifically should
avoid that name collision."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from pipelines.cardgen_pipeline import CardGenPipeline  # noqa: E402

OUT_DIR = REPO / "scratch_eval2_generation"


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with CardGenPipeline(out_dir=str(OUT_DIR)) as pipeline:
        print("=== Retrying: Forus (formerly Tandem), starting from /stories ===", flush=True)
        chai_card, sources, content = await pipeline.generate_model_card(
            model_name="Forus",
            developer_name="Forus (formerly Tandem Technology, Inc.)",
            application_url="https://forus.com/stories",
            iters=5,
            coverage_target=0.75,
            finalize_policy="not_specified",
            write_files=True,
            file_prefix=None,
        )
        paths = (content or {}).get("paths")
        print("OK: Forus")
        if paths:
            print(f"  json: {paths.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
