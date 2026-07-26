#!/usr/bin/env python3
"""One-off driver: generate clinical model cards for the eval-2 model set via the
live CardGenPipeline (real web discovery + Gemini extraction), given explicit
model name / developer / application URL for each model.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from pipelines.cardgen_pipeline import CardGenPipeline  # noqa: E402

OUT_DIR = REPO / "scratch_eval2_generation"

MODELS = [
    ("Tandem", "Tandem Technology, Inc.", "https://forus.com/"),
    ("Skin Analytics", "Skin Analytics", "https://skin-analytics.com/"),
    ("DermGPT", 'Dr. Faranak "Fara" Kamangar MD', "https://www.dermgpt.com/"),
    ("Skin Vision", "SkinVision", "https://www.skinvision.com/en-us"),
]


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with CardGenPipeline(out_dir=str(OUT_DIR)) as pipeline:
        for model_name, developer_name, application_url in MODELS:
            print(f"\n=== Generating: {model_name} ===", flush=True)
            try:
                chai_card, sources, content = await pipeline.generate_model_card(
                    model_name=model_name,
                    developer_name=developer_name,
                    application_url=application_url,
                    iters=5,
                    coverage_target=0.75,
                    finalize_policy="not_specified",
                    write_files=True,
                    file_prefix=None,
                )
                paths = (content or {}).get("paths")
                print(f"OK: {model_name}")
                if paths:
                    print(f"  json: {paths.json_path}")
                    print(f"  md:   {paths.md_path}")
                    print(f"  cites:{paths.citations_json_path}")
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR generating {model_name}: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
