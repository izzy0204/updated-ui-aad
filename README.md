# AAD Model Card Generator

A pipeline that generates clinical/regulatory-style "model cards" for dermatology AI products. Point it at a model name (and optionally a developer name and product URL), and it discovers sources on the web, scrapes and reads them, has Gemini extract structured facts field-by-field, and writes out a cited, scored model card as Markdown/JSON.

This README is aimed at a new collaborator: how card generation works end to end, how the scraping and source-prioritization work, and how to get the app running locally.

## 1. How card generation works, start to finish

Entry points: `terminal_app.py` (CLI) or `streamlit run src/core/app.py` (web UI), both of which drive `src/pipelines/cardgen_pipeline.py::CardGenPipeline.generate_model_card()`. That method is the whole pipeline:

1. **Seed the application URL (if given).** If the user supplies a product/application URL, it's scraped first via `RobustWebScraper.extract_content_with_second_hop()` (see §2) and inserted as the highest-priority seed page, tagged `priority: "user_inputted"`.

2. **Web discovery.** `utils.web_search.discover_and_fetch()` runs a batch of targeted search queries (site-specific, regulatory, clinical — see §3) and fetches the top-ranked results into "seed pages" (URL + clean text).

3. **Gemini agent loop** (`src/agents/gemini_agent/agent.py::run()`). This is the core extraction loop, and it iterates up to `max_iters` times (default 5, adaptively increased if there are a lot of sources):
   - **Plan** (`_plan_targets`): asks Gemini what additional sources to fetch (HuggingFace, GitHub, general web) and which CHAI/clinical fields to prioritize, given the model name/developer and whatever seed context is already available.
   - **Gather** (`_gather_targets_async`): fetches each planned target (HF/GitHub READMEs, web pages/PDFs) concurrently.
   - **Extract** (`_extract_fields`): batches of ~15 fields at a time are sent to Gemini with the fetched text as context; Gemini returns `{values, evidence}` — the field values plus `{url, snippet}` citations for each.
   - **Validate** (`_validate_patch`): Gemini reviews the current partial card and reports which fields are still `missing`/`weak`, plus suggested follow-up fetches (`next_fetch`).
   - **Re-target**: follow-up queries/URLs become the next iteration's fetch targets.
   - Loop stops early once coverage of fields (weighted toward a fixed list of critical fields like `model_name`, `summary`, `medical_purpose`, `performance`) crosses `coverage_target` (default 0.75), or `max_iters` is reached.

4. **Publications + FDA enrichment.** In parallel with/after the agent loop, `EnhancedPublicationFinder` searches PubMed/Crossref/arXiv, and (if the model looks clinical — dermatology/skin/lesion/diagnosis keywords) `utils.fda_discovery.find_510k_for_product()` looks up FDA 510(k) records. Both contribute additional seed pages and citations, and FDA records specifically drive regulatory-status classification.

5. **Map to schema.** The agent's flat/nested dict output is mapped onto `ClinicalModelCard` (`src/core/chai_schema.py`), the CHAI-aligned dataclass schema for the card, via `pipelines/clinical_card_mapper.py`.

6. **Post-fill passes.** Any clinical field still empty after the agent loop gets additional, more targeted attempts (`_postfill_missing_fields`, then `_postfill_one_critical_field` for a fixed list of critical fields like `medical_purpose`, `performance`, `training_data`), using the accumulated seed pages + citations as context for one Gemini call per field.

7. **Citation & regulatory tagging.** Every substantive field is guaranteed at least one citation (falling back to the top discovered URL if nothing else was attached). Each citation URL is classified into a source type (`fda_approval`, `clinical_trial`, `pubmed_paper`, `github_repo`, `web`, etc. — see §3) and a regulatory "tier" for UI color-coding.

8. **Finalize & score.** Summary length is enforced (rewritten via Gemini if too long), the card is validated against the schema, and `ModelCardScorer` (`src/utils/model_card_scorer.py`) computes a completion percentage and a red/yellow/green "clinical usability" rating (see `SCORING_SYSTEM_README.md`).

9. **Write outputs.** `<slug>-<timestamp>.clinical.json`, `.clinical.md`, `.citations.json`, and `.scoring.txt` are written to `outputs/`.

Every network call in this path (search, fetch, Gemini calls) goes through the shared cache first (see `CACHING_SYSTEM_README.md`) — re-running the same model name is fast and won't re-hit the same URLs or re-spend Gemini tokens within the cache TTL.

## 2. How the web scraping works

Two scrapers exist, used for different jobs:

- **`src/utils/web_search.py`** — lightweight fetch used during discovery and by the Gemini agent's `_gather_targets_async`. Async `aiohttp` fetch with retry/backoff, HTML→text via `trafilatura`, PDF→text via `pypdf`. Falls back to Selenium (see below) if the extracted text is under 200 chars and `ENABLE_SELENIUM=1`.

- **`src/scrapers/robust_scraper_v2.py::RobustWebScraper`** — the heavier, production-grade scraper, used specifically for the user-supplied application URL (`extract_content_with_second_hop`). It adds:
  - **robots.txt compliance** (`RobotChecker`, cached per host) and HTTPS-only normalization; credentialed URLs (containing `token=`, `auth=`, etc.) are rejected outright.
  - **Per-host rate limiting** — 1 req/s for a fixed list of medical/regulatory domains (`aad.org`, `fda.gov`, `nih.gov`, `who.int`, `cdc.gov`, ...), 5 req/s otherwise — plus per-host concurrency caps and exponential backoff with jitter on 429/5xx.
  - **SQLite HTTP cache** with ETag/If-Modified-Since support, separate from the pipeline-level cache described in §1.
  - **Noise stripping** (scripts, nav, footers, hidden elements) then main-content extraction via `trafilatura`, falling back to common content-container selectors, falling back to `<body>` text.
  - **Selenium fallback**: if extracted text is short (<500 chars), the page shows JS-framework fingerprints (`__NEXT_DATA__`, `data-reactroot`, etc.), or the domain is a known JS-heavy site, it retries with Selenium (`src/scrapers/selenium_scraper.py`) and keeps whichever result has more text.
  - **PDF extraction** via `pypdf` (metadata + text per page).
  - **JSON-LD structured data** and regex-based pattern extraction for performance metrics (AUC/sensitivity/specificity/etc.), version strings, regulatory markers (510(k), CE mark, FDA cleared), and DOIs.
  - **Second-hop crawling**: for the application URL only, it follows up to 5 internal links whose anchor text/URL matches a relevant-keyword list (`documentation`, `clinical`, `bias`, `limitations`, `training`, ...) and appends their content to the primary page's text — this is what lets a single product URL pull in linked docs/about/methodology pages without a second general web search.

## 3. How sources are prioritized

Prioritization happens at three layers:

1. **Explicit user input wins.** A developer-supplied application URL is always fetched first, marked `priority: "user_inputted"`, and the agent's planning prompt is explicitly told: *"treat it as the most authoritative source and prefer its content... when other sources conflict with it"* (`agent.py::_prep_seed_context`).

2. **Discovery query design + scoring** (`utils/web_search.py`). `discover_model_sources()` runs ~25+ queries per model (official site, documentation, dermatology AI, papers, FDA clearance, clinical trials, IRB approval, plus `site:pubmed.ncbi.nlm.nih.gov`, `site:fda.gov`, `site:clinicaltrials.gov`, `site:github.com`, `site:arxiv.org` scoped searches). Each result gets a `quality_score` from `_score_source_quality()`:
   - +0.4 if title/URL looks official (`official`, `homepage`, `product page`, `company`)
   - +0.3 if it looks like documentation (`docs`, `guide`, `tutorial`)
   - +0.2 if the model name appears in the title/description, +0.1 more if the developer name does
   - +0.1 if the domain is `.edu`/`.gov`/`.org`/PubMed/arXiv/GitHub

   Results are sorted by `priority_score` (5.0–10.0, quality-weighted) and the top 25 are kept; `discover_and_fetch()` then fetches the top `top_k` (5 for the first pass, 10 more added afterward) into seed pages.

3. **Regulatory tiering for display** (`src/core/source_regulatory.py`). Independent of discovery ranking, every citation URL attached to a field is classified by `infer_source_type()` into a tier used for color-coding in the UI/markdown:

   | source_type | tier |
   |---|---|
   | `fda_approval` (fda.gov) | green |
   | `ema_approval` / `ce_marking` (EU regulators) | blue |
   | `eua` (emergency use authorization) | yellow |
   | `clinical_trial` / `investigational` | orange |
   | `pubmed_paper`, `arxiv_paper`, `github_repo`/HuggingFace, generic `web` | gray |

   FDA 510(k) records are explicitly attached to the `regulatory_approval_status` field with tier `green` regardless of where else they were discovered. Only the regulatory-approval-status row is tiered non-gray by default (`compute_regulatory_tiers_for_card` is "enum-first" — it doesn't try to tier every field, just that one, from the merged evidence).

## 3.5 Google CSE vs. DuckDuckGo

Search defaults to DuckDuckGo HTML scraping (no key required). If `GOOGLE_CSE_CX` is set (plus either `GOOGLE_CSE_API_KEY` or a service-account JSON key), Google Custom Search is used instead and results are cached separately per provider. See `config/config.py` / `src/utils/web_search.py` for the exact precedence.

## 4. Getting started on your own machine

### Prerequisites

- Python 3.11 (the repo was built/tested on 3.11.14; `pyproject.toml` allows >=3.10)
- A **Gemini API key** (required — this is the only hard dependency; everything else degrades gracefully)
- Chrome/Chromium if you want the Selenium fallback to actually work (optional)

### Install

```bash
git clone <this-repo-url>
cd aad-model-card-generator
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, for running tests
```

### Configure

Create a `.env` file in the repo root:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

That's the only required variable. Everything else in `config/config.py` has a default and is optional:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model used for planning/extraction/validation |
| `GEMINI_TEMPERATURE` | `0.7` | Sampling temperature |
| `GEMINI_THINKING_BUDGET` | `2048` | Gemini 2.5 "thinking" token budget |
| `GEMINI_MAX_CONCURRENT` | `10` | Cap on concurrent Gemini calls (semaphore) |
| `GOOGLE_CSE_CX` / `GOOGLE_CSE_API_KEY` | unset | Switch discovery search from DuckDuckGo to Google Custom Search |
| `ENABLE_SELENIUM` | unset | Force-enable the Selenium fallback in `web_search.py`'s lightweight fetcher |
| `HTTP_TIMEOUT` | `30` | Generic HTTP timeout |

### Run it

Web UI (Streamlit):

```bash
streamlit run src/core/app.py --server.port 5000
# or: python run_app.py   (interactive menu: web vs. terminal)
```

Then enter a model name (and optionally developer + application URL) and generate a card from the browser.

Terminal:

```bash
python terminal_app.py
```

Programmatically:

```python
import asyncio
from pipelines.cardgen_pipeline import CardGenPipeline

async def main():
    async with CardGenPipeline() as pipeline:
        chai_card, sources, content = await pipeline.generate_model_card(
            model_name="DermaSensor",
            developer_name="DermaSensor Inc.",
        )
        print(content["markdown"])

asyncio.run(main())
```

(Note: the codebase imports things like `from pipelines...` and `from core...` as top-level packages under `src/`. `sitecustomize.py` at the repo root auto-adds `src/` to `sys.path` for any script run from the repo root, so this works out of the box — no manual `PYTHONPATH` needed. `pytest.ini` does the same for the test suite via `pythonpath = src`.)

### Run the tests

```bash
pytest                       # default suite: offline unit tests only (see pytest.ini)
pytest -m integration        # tests that hit the network / live Gemini API
pytest --cov=src --cov-report=term-missing
```

There are also standalone manual-run scripts at the repo root (`test_regulatory_status.py`, `test_scoring.py`, etc.) that can be run directly with `python <file>.py` for quick checks outside pytest.

### Debugging an incomplete card

Every fetch/search/Gemini call is cached in SQLite under `cache/` (pipeline-level cache) and `.scraper_cache/` (HTTP-level cache for `RobustWebScraper`). Use `cache_inspector.py` to see what was actually retrieved for a given model — this is the fastest way to tell whether a missing field is a scraping failure, a search-discovery miss, or a Gemini extraction miss. Details in `CACHING_SYSTEM_README.md`.

## Further reading

- [`docs/PROCESS_WALKTHROUGH.md`](docs/PROCESS_WALKTHROUGH.md) — file/method/variable-level trace through the pipeline (older but useful for debugging call chains)
- [`docs/SELENIUM_BEAUTIFULSOUP_INTEGRATION.md`](docs/SELENIUM_BEAUTIFULSOUP_INTEGRATION.md) — Selenium fallback details
- [`CACHING_SYSTEM_README.md`](CACHING_SYSTEM_README.md) — cache architecture and `cache_inspector.py` usage
- [`SCORING_SYSTEM_README.md`](SCORING_SYSTEM_README.md) — completion % and clinical usability scoring
- [`src/core/chai_schema.py`](src/core/chai_schema.py) — the model card schema itself (source of truth for field names)
