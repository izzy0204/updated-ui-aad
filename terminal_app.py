#!/usr/bin/env python3
"""
Terminal-based AI Model Card Generator (updated)

- Uses CardGenPipeline.generate_model_card(...)
- Works with GOOGLE_API_KEY (preferred) or GEMINI_API_KEY
- Prints a concise summary of the CHAI model card
- Shows where artifacts were written (JSON/MD/XML/Citations)

Run:
  python terminal_app.py --model-name "DermNetX" --developer "ACME Health" --application-url "https://example.com/model-docs"
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
import argparse
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env from repo root before importing pipeline / web_search.
CURRENT_DIR = Path(__file__).parent
load_dotenv(CURRENT_DIR / ".env")
load_dotenv()

# Add src/ to the path so local packages import cleanly
SRC_DIR = CURRENT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pipelines.cardgen_pipeline import CardGenPipeline
from core.chai_schema import CHAIModelCard           # noqa: E402


# ----------------------------- UI helpers -----------------------------

def print_header() -> None:
    print("=" * 60)
    print("AI MODEL CARD GENERATOR — TERMINAL")
    print("=" * 60)
    print("Generate CHAI-aligned model cards for dermatology AI models.\n")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def info(msg: str) -> None:
    print(f"[...] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def err(msg: str) -> None:
    print(f"[ERROR] {msg}")


# ----------------------------- Content helpers -----------------------------

def _safe_get(obj: Any, name: str, default: str = "") -> str:
    try:
        v = getattr(obj, name, default)
        if v is None:
            return default
        if isinstance(v, list):
            return ", ".join(str(x).strip() for x in v if str(x).strip())
        return str(v).strip()
    except Exception:
        return default


def _print_if(value: str, title: str) -> None:
    if value and value.strip() and value.strip().lower() != "not specified":
        print(f"   {title}: {value}")


def print_card_summary(card: CHAIModelCard) -> None:
    """Pretty-print a concise summary using common CHAI fields (safe if missing)."""
    print("\n" + "=" * 60)
    print("GENERATED MODEL CARD (summary)")
    print("=" * 60)

    # Headline
    model_name = _safe_get(card, "model_name", "Unknown model")
    developer = _safe_get(card, "developer", "Not specified")
    print(f"\nModel: {model_name}")
    print(f"Developer: {developer}")

    # Metadata
    version = _safe_get(card, "version")
    release_stage = _safe_get(card, "release_stage")
    release_date = _safe_get(card, "release_date")
    _print_if(version, "Version")
    _print_if(release_stage, "Release Stage")
    _print_if(release_date, "Release Date")

    # Summary
    summary = _safe_get(card, "summary")
    if summary:
        print("\nSummary:")
        print("   " + summary.replace("\n", "\n   "))

    # Use & workflow
    intended_use = _safe_get(card, "intended_use_and_workflow")
    primary_users = _safe_get(card, "primary_intended_users")
    how_to_use = _safe_get(card, "how_to_use")
    if intended_use or primary_users or how_to_use:
        print("\nIntended Use:")
        _print_if(intended_use, "Workflow")
        _print_if(primary_users, "Primary Users")
        _print_if(how_to_use, "How to Use")

    # Technical
    model_type = _safe_get(card, "model_type")
    foundation_models = _safe_get(card, "foundation_models_used_in_application_if_applicable")
    _print_if(model_type, "Model Type")
    _print_if(foundation_models, "Foundation Models")

    # Data
    training_data = _safe_get(card, "training_data")
    validation_ds = _safe_get(card, "validation_test_dataset")
    skin_tones = _safe_get(card, "skin_tone_diversity")
    _print_if(training_data, "Training Data")
    _print_if(validation_ds, "Validation/Test Dataset")
    _print_if(skin_tones, "Skin Tone Diversity")

    # Limitations / risk
    limitations = _safe_get(card, "model_limitations")
    clinical_risk = _safe_get(card, "clinical_risk_level")
    if limitations or clinical_risk:
        print("\nLimitations & Risk:")
        _print_if(limitations, "Limitations")
        _print_if(clinical_risk, "Clinical Risk Level")


def print_sources_summary(sources: dict) -> None:
    """Show a small digest of discovery + enrichment."""
    print("\n" + "=" * 60)
    print("SOURCES / DISCOVERY")
    print("=" * 60)

    web = (sources or {}).get("web_search", {})
    pubs = (sources or {}).get("publications", []) or []
    fda = (sources or {}).get("fda", []) or []
    postfill = (sources or {}).get("postfill", {}) or {}

    discovered = web.get("discovered", []) or []
    top_urls = web.get("top_urls", []) or []

    print(f"\nWeb discovery results: {len(discovered)}")
    if top_urls:
        print("   Top URLs used:")
        for u in top_urls[:5]:
            print(f"   • {u}")

    if pubs:
        print(f"\nPublications collected: {len(pubs)} (Crossref + ArXiv)")
        for p in pubs[:3]:
            title = (p.get("title") or "").strip() or "Untitled"
            journal = (p.get("journal") or p.get("type") or "").strip()
            url = (p.get("url") or p.get("doi_url") or "").strip()
            print(f"   • {title} [{journal}]")
            if url:
                print(f"     {url}")

    if fda:
        print(f"\nFDA 510(k) matches: {len(fda)}")
        for r in fda[:3]:
            kn = (r.get("k_number") or r.get("kNumber") or "").strip()
            dec = (r.get("decision") or r.get("decision_date") or "").strip()
            app = (r.get("applicant") or r.get("applicant_name") or "").strip()
            print(f"   • {kn} — decision: {dec} — applicant: {app}")

    print(f"\nPost-fill pass ran: {bool(postfill.get('ran'))}")


def print_artifacts(paths: Optional[Any]) -> None:
    """Display paths to artifacts written by the pipeline."""
    if not paths:
        warn("No artifacts written (write_files=False).")
        return
    print("\n" + "=" * 60)
    print("ARTIFACTS")
    print("=" * 60)
    if getattr(paths, "json_path", None):
        print(f"   JSON:      {paths.json_path}")
    if getattr(paths, "md_path", None):
        print(f"   Markdown:  {paths.md_path}")
    if getattr(paths, "xml_path", None):
        print(f"   XML:       {paths.xml_path}")
    if getattr(paths, "citations_json_path", None):
        print(f"   Citations: {paths.citations_json_path}")
    if getattr(paths, "scoring_txt", None):
        print(f"   Scoring:   {paths.scoring_txt}")


def print_scoring_summary(sources: dict, paths: Optional[Any]) -> None:
    """Display model card scoring summary."""
    scoring = (sources or {}).get("scoring")
    if not scoring:
        return
    
    print("\n" + "=" * 60)
    print("MODEL CARD SCORING")
    print("=" * 60)
    
    completion = scoring.get("completion_percentage", 0)
    usability_level = scoring.get("clinical_usability_level", "unknown").upper()
    overall_rating = scoring.get("overall_rating", "N/A")
    filled = scoring.get("filled_fields", 0)
    total = scoring.get("total_fields", 0)
    
    print(f"\n   Field Completion: {completion}% ({filled}/{total} fields)")
    print(f"   Clinical Usability: {usability_level}")
    print(f"   Overall Rating: {overall_rating}")
    
    critical_missing = scoring.get("critical_missing_fields", [])
    if critical_missing:
        print(f"\n     Critical Missing Fields ({len(critical_missing)}):")
        for field in critical_missing[:5]:  # Show first 5
            print(f"      • {field}")
        if len(critical_missing) > 5:
            print(f"      ... and {len(critical_missing) - 5} more")
    
    recommendations_count = scoring.get("recommendations_count", 0)
    quality_issues_count = scoring.get("quality_issues_count", 0)
    
    if recommendations_count or quality_issues_count:
        print(f"\n    Recommendations: {recommendations_count}")
        print(f"     Quality Issues: {quality_issues_count}")
    
    if paths and getattr(paths, "scoring_txt", None):
        print(f"\n    Full report: {paths.scoring_txt}")


# ----------------------------- CLI / main -----------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a CHAI model card via Gemini agent (terminal)")
    p.add_argument("--model-name", "-m", required=False, help="Model name (e.g., 'DermNetX')")
    p.add_argument("--developer", "-d", default="", help="Developer/organization name")
    p.add_argument("--application-url", "-u", default="", help="Application URL (primary source for field filling)")
    p.add_argument("--iters", type=int, default=5, help="Max agent iters")
    p.add_argument("--coverage", type=float, default=0.75, help="Coverage target [0..1]")
    p.add_argument("--finalize", default="not_specified", choices=["not_specified", "none"],
                   help="Finalize policy for missing fields")
    p.add_argument("--out-dir", default="outputs", help="Artifacts output directory")
    p.add_argument("--no-write", action="store_true", help="Do not write artifacts to disk")
    p.add_argument("--no-discovery", action="store_true", help="Disable web discovery step")
    return p


def ensure_api_key_or_exit() -> None:
    # Your config.get_settings() reads GOOGLE_API_KEY for the Gemini client.
    # We also accept GEMINI_API_KEY as a fallback for convenience.
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        err("No API key found.")
        print("   Set one of:")
        print("     export GOOGLE_API_KEY='your_key_here'   # preferred (matches config.get_settings())")
        print("     or export GEMINI_API_KEY='your_key_here'")
        sys.exit(1)


async def run(args: argparse.Namespace) -> int:
    print_header()
    ensure_api_key_or_exit()

    model_name = args.model_name
    developer = args.developer
    application_url = args.application_url

    # Prompt interactively if not provided via flags
    if not model_name:
        try:
            model_name = input("Model Name: ").strip()
        except EOFError:
            model_name = ""
    if not model_name:
        err("Model name is required.")
        return 2

    if not developer:
        try:
            developer = input("Developer/Organization: ").strip()
        except EOFError:
            developer = ""

    if not application_url:
        try:
            application_url = input("Application URL (optional): ").strip()
        except EOFError:
            application_url = ""

    info("Initializing pipeline...")
    async with CardGenPipeline(out_dir=args.out_dir, use_web_discovery=not args.no_discovery) as pipeline:
        info("Discovering sources and analyzing content (this can take a few minutes)...")
        chai_card, sources, content = await pipeline.generate_model_card(
            model_name=model_name,
            developer_name=developer,
            application_url=application_url,
            iters=args.iters,
            coverage_target=args.coverage,
            finalize_policy=args.finalize,
            write_files=not args.no_write,
            file_prefix=None,
        )

    ok("Model card generation completed.")
    print_card_summary(chai_card)
    print_sources_summary(sources)
    print_artifacts((content or {}).get("paths"))
    print_scoring_summary(sources, (content or {}).get("paths"))

    print("\nDone.")
    return 0


def main() -> None:
    parser = build_argparser()
    args = parser.parse_args()
    try:
        rc = asyncio.run(run(args))
        sys.exit(rc)
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(130)
    except Exception as e:
        err(f"Unexpected error: {e}")
        print(f"\nDebug info:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error details: {repr(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
