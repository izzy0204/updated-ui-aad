#!/usr/bin/env python3
"""Quick validation: regenerate DermaSensor alone and check whether the
strengthened evidence prompt now produces multi-source citations."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from pipelines.cardgen_pipeline import CardGenPipeline  # noqa: E402

OUT_DIR = REPO / "scratch_citation_test"


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with CardGenPipeline(out_dir=str(OUT_DIR)) as pipeline:
        print("=== Testing: DermaSensor (citation fix validation) ===", flush=True)
        chai_card, sources, content = await pipeline.generate_model_card(
            model_name="DermaSensor",
            developer_name="DermaSensor",
            application_url="https://www.dermasensor.com/",
            iters=5,
            coverage_target=0.75,
            finalize_policy="not_specified",
            write_files=True,
            file_prefix=None,
        )
        paths = (content or {}).get("paths")
        print("OK: DermaSensor")
        if paths:
            print(f"  json: {paths.json_path}")
            print(f"  cites:{paths.citations_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
