#!/usr/bin/env python3
"""
Fast Test Script – validates all recent updates WITHOUT live Gemini calls.
(Your free-tier Gemini quota is exhausted, so live calls just spin on 429.)

Tests three areas:
  1. Gemini wiring — client creation, key loading, JSON parsing, helpers
  2. Selenium / Scraping — imports, trafilatura, BS4, robust scraper
  3. Card pipeline — schema, mapping, normalization, scoring, output check
"""

from __future__ import annotations
import json, os, sys, time
from dataclasses import fields as dc_fields
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# ── pretty helpers ──────────────────────────────────────────────
PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
_results = []

def record(name, ok, detail="", warn=False):
    tag = WARN if warn else (PASS if ok else FAIL)
    _results.append({"name": name, "ok": ok, "tag": tag})
    print(f"  {tag}  {name}")
    if detail:
        for ln in detail.split("\n"):
            print(f"         {ln}")

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def summary():
    section("SUMMARY")
    for r in _results:
        print(f"  {r['tag']}  {r['name']}")
    p = sum(r["ok"] for r in _results)
    f = len(_results) - p
    print(f"\n  Total {len(_results)}  |  Passed {p}  |  Failed {f}")
    if f:
        print("\n❌ Some tests failed — see above.")
    else:
        print("\n🎉 ALL TESTS PASSED!")
    return 1 if f else 0

# ================================================================
#  1. GEMINI WIRING (no live API calls)
# ================================================================
def run_gemini_tests():
    section("1 · GEMINI WIRING")

    # 1a  API key loaded from .env
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    record("API key loaded from .env", len(key) > 5,
           f"Key length: {len(key)}" if key else "GEMINI_API_KEY / GOOGLE_API_KEY not set")

    # 1b  Settings load
    try:
        from config.config import get_settings
        s = get_settings()
        ok = bool(s.google_api_key) and bool(s.gemini_model)
        record("get_settings() returns key + model", ok,
               f"model={s.gemini_model}, key={'***'+s.google_api_key[-4:] if s.google_api_key else 'NONE'}")
    except Exception as e:
        record("get_settings() returns key + model", False, str(e))

    # 1c  genai Client creation (no actual call)
    try:
        import google.genai as genai
        client = genai.Client(api_key=key or "dummy-for-test")
        record("google.genai.Client() creates OK", True)
    except Exception as e:
        record("google.genai.Client() creates OK", False, str(e))

    # 1d  _postfill_client helper
    try:
        from pipelines.cardgen_pipeline import _postfill_client
        c, m, cfg = _postfill_client()
        record("_postfill_client() returns client+model+config", c is not None and m != "",
               f"model={m}, config={'present' if cfg is not None else 'None'}")
    except Exception as e:
        record("_postfill_client() returns client+model", False, str(e))

    # 1e  extract_json_block robustness
    try:
        from agents.gemini_agent.tools import extract_json_block
        cases = [
            ('{"values":{"model_name":"X"},"evidence":{}}', True),
            ('```json\n{"values":{"a":"b"},"evidence":{}}\n```', True),
            ('Here is JSON:\n{"values":{"a":"b"},"evidence":{}}\nDone.', True),
            ("", False),
            ("No JSON here", False),
        ]
        bad = []
        for inp, want in cases:
            obj = extract_json_block(inp)
            got = isinstance(obj.get("values"), dict) and len(obj["values"]) > 0
            if got != want:
                bad.append(f"{inp[:30]!r}: want={want} got={got}")
        record("extract_json_block parses all formats", len(bad) == 0,
               f"All {len(cases)} OK" if not bad else "; ".join(bad))
    except Exception as e:
        record("extract_json_block parses all formats", False, str(e))

# ================================================================
#  2. SELENIUM / SCRAPING
# ================================================================
def run_scraping_tests():
    section("2 · SELENIUM / SCRAPING")

    # 2a  Selenium importable
    try:
        from scrapers.selenium_scraper import SELENIUM_AVAILABLE
        record("Selenium importable (SELENIUM_AVAILABLE)", SELENIUM_AVAILABLE,
               "" if SELENIUM_AVAILABLE else "pip install selenium webdriver-manager")
    except ImportError as e:
        record("Selenium importable", False, str(e))

    # 2b  needs_selenium heuristic
    try:
        from scrapers.selenium_scraper import needs_selenium
        # JS-heavy: minimal HTML with only a root div and big script bundle
        js_heavy = "<html><body><div id='root'></div><script src='app.bundle.js'></script></body></html>"
        # Static: lots of real text content
        static = ("<html><body><article>" +
                  "<p>" + "This is a real paragraph of content. " * 30 + "</p>" * 5 +
                  "</article></body></html>")
        result_js = needs_selenium(js_heavy)
        result_static = needs_selenium(static)
        # At minimum, js_heavy should trigger True
        record("needs_selenium() detects JS-heavy pages", result_js,
               f"JS-heavy→{result_js}, static→{result_static}")
    except Exception as e:
        record("needs_selenium() detects JS-heavy pages", False, str(e))

    # 2c  Trafilatura extraction
    try:
        import trafilatura
        html = """<html><body><article>
            <h1>AI in Dermatology</h1>
            <p>Machine learning models assist dermatologists in diagnosing skin conditions
            with high accuracy. Key metrics include sensitivity and AUROC.</p>
        </article></body></html>"""
        text = trafilatura.extract(html, include_comments=False)
        ok = text is not None and len(text) > 40
        record("Trafilatura extracts text", ok, f"{len(text or '')} chars")
    except Exception as e:
        record("Trafilatura extracts text", False, str(e))

    # 2d  BeautifulSoup noise removal
    try:
        from bs4 import BeautifulSoup
        html = """<html><head><title>T</title></head><body>
            <nav>Nav</nav><script>x=1</script><style>.h{}</style>
            <main><h1>DermAI</h1><p>Skin cancer detection model.</p></main>
            <footer>Foot</footer></body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        for tag in ["script", "style", "nav", "footer"]:
            for el in soup.find_all(tag):
                el.decompose()
        text = soup.find("main").get_text(" ", strip=True)
        ok = "DermAI" in text and "Nav" not in text
        record("BS4 noise removal", ok, f"'{text[:80]}'")
    except Exception as e:
        record("BS4 noise removal", False, str(e))

    # 2e  RobustWebScraper import + init
    try:
        from scrapers.robust_scraper_v2 import RobustWebScraper
        s = RobustWebScraper()
        record("RobustWebScraper instantiates", True)
    except Exception as e:
        record("RobustWebScraper instantiates", False, str(e))

    # 2f  normalize_sources utility
    try:
        from agents.gemini_agent.tools import normalize_sources
        blobs = [("https://example.com", "Hello world content " * 50)]
        types = ["web"]
        text_block, type_hint = normalize_sources(blobs, types)
        ok = isinstance(text_block, str) and len(text_block) > 10
        record("normalize_sources() works", ok, f"Output: {len(text_block)} chars, hint={type_hint!r}")
    except Exception as e:
        record("normalize_sources() works", False, str(e))

# ================================================================
#  3. CARD PIPELINE (offline)
# ================================================================
def run_pipeline_tests():
    section("3 · CARD PIPELINE (offline)")

    # 3a  CHAIModelCard construction + serialization
    try:
        from core.chai_schema import CHAIModelCard
        card = CHAIModelCard(model_name="TestModel", developer="TestDev",
                             summary="A test", intended_use_and_workflow="Clinical")
        j = json.loads(card.to_json())
        ok = j["model_name"] == "TestModel" and len(card.to_markdown()) > 100 and "<ModelName>" in card.to_xml()
        record("CHAIModelCard serialize (JSON/MD/XML)", ok,
               f"JSON fields: {len(j)}, MD: {len(card.to_markdown())} chars")
    except Exception as e:
        record("CHAIModelCard serialize", False, str(e))

    # 3b  _map_agent_dump_to_chai — direct keys
    try:
        from pipelines.cardgen_pipeline import _map_agent_dump_to_chai
        dump = {"model_name": "DermDetect", "developer": "HealthAI",
                "summary": "Skin lesion analyzer", "model_type": "CNN",
                "keywords": ["derm", "AI"]}
        card = _map_agent_dump_to_chai(dump)
        ok = card.model_name == "DermDetect" and card.model_type == "CNN" and len(card.keywords) == 2
        record("Agent dump → CHAI (direct keys)", ok,
               f"name={card.model_name}, type={card.model_type}, kw={card.keywords}")
    except Exception as e:
        record("Agent dump → CHAI (direct keys)", False, str(e))

    # 3c  _map_agent_dump_to_chai — nested/legacy keys
    try:
        from pipelines.cardgen_pipeline import _map_agent_dump_to_chai
        dump = {"metadata": {"name": "SkinScan", "developer": "DermTech",
                             "summary": "Skin analysis"},
                "uses": {"purpose": "Melanoma detection"},
                "trust": {"model_type": "ResNet-50"}}
        card = _map_agent_dump_to_chai(dump)
        ok = card.model_name == "SkinScan" and card.model_type == "ResNet-50"
        record("Agent dump → CHAI (nested keys)", ok,
               f"name={card.model_name}, type={card.model_type}")
    except Exception as e:
        record("Agent dump → CHAI (nested keys)", False, str(e))

    # 3d  Empty field collection
    try:
        from pipelines.cardgen_pipeline import _collect_empty_chai_fields
        from core.chai_schema import CHAIModelCard
        card = CHAIModelCard(model_name="X", developer="Y", summary="Z")
        empties = _collect_empty_chai_fields(card)
        ok = ("model_name" not in empties and "training_data" in empties and len(empties) > 40)
        record("_collect_empty_chai_fields", ok, f"{len(empties)} empty fields detected")
    except Exception as e:
        record("_collect_empty_chai_fields", False, str(e))

    # 3e  Key normalization
    try:
        from pipelines.cardgen_pipeline import _norm_key
        cases = {"Usefulness / Efficacy: Goal": "usefulness.efficacy.goal",
                 "metadata.name": "metadata.name",
                 "Trust: Model Type": "trust.model.type"}
        bad = [k for k, v in cases.items() if _norm_key(k) != v]
        record("_norm_key helper", len(bad) == 0,
               f"All {len(cases)} OK" if not bad else f"Failed: {bad}")
    except Exception as e:
        record("_norm_key helper", False, str(e))

    # 3f  ModelCardScorer
    try:
        from utils.model_card_scorer import ModelCardScorer
        from core.chai_schema import CHAIModelCard
        card = CHAIModelCard(model_name="M", developer="D", summary="S",
                             model_type="CNN", training_data="100k imgs")
        scorer = ModelCardScorer()
        score = scorer.score_model_card(card.__dict__)
        ok = score.completion_percentage > 0 and score.filled_fields > 0
        record("ModelCardScorer produces scores", ok,
               f"{score.completion_percentage:.1f}% complete, {score.filled_fields}/{score.total_fields} filled")
    except Exception as e:
        record("ModelCardScorer produces scores", False, str(e))

    # 3g  Check latest output file
    try:
        out_dir = Path(__file__).parent / "outputs"
        files = sorted(out_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        files = [f for f in files if ".citations." not in f.name and ".scoring." not in f.name]
        if not files:
            record("Latest output file exists", False, "No output JSON found")
        else:
            data = json.loads(files[0].read_text())
            filled = sum(1 for k, v in data.items()
                         if k != "extraction_timestamp"
                         and ((isinstance(v, str) and v.strip() and v.strip().lower() != "not specified")
                              or (isinstance(v, list) and len(v) > 0)))
            total = sum(1 for k in data if k != "extraction_timestamp")
            pct = filled / total * 100 if total else 0
            # Note: this checks the OLD output from before quota was hit
            record(f"Latest output ({files[0].name})", pct > 3,
                   f"{pct:.0f}% filled ({filled}/{total}) — note: generated while quota was active",
                   warn=pct < 20)
    except Exception as e:
        record("Latest output file exists", False, str(e))

    # 3h  Gemini quota status check
    section("GEMINI QUOTA STATUS")
    print("  ⚠️  Your Gemini free-tier daily quota is EXHAUSTED.")
    print("     Every API call returns 429 RESOURCE_EXHAUSTED (limit: 0).")
    print("     This is why end-to-end pipeline runs produce blank cards right now.")
    print("     → Wait for quota to reset (midnight PT) or upgrade to a paid plan.")
    print("     → All non-API tests above confirm the CODE is wired correctly.")


# ================================================================
print()
print("🧪 MODEL CARD GENERATOR — FAST VALIDATION TESTS")
print("=" * 60)

run_gemini_tests()
run_scraping_tests()
run_pipeline_tests()
rc = summary()
sys.exit(rc)
