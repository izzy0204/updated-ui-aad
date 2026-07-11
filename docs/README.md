# AI Model Card Generator

A system for generating professional model cards for dermatology AI models, featuring automated source discovery, AI-powered content analysis, and CHAI schema compliance.

## Project Structure

```
aad-model-card-generator/
├── src/
│   ├── core/                         # Core application
│   │   ├── app.py                    # Main Streamlit application
│   │   ├── chai_schema.py            # CHAI schema definitions
│   │   ├── card_regulatory.py        # Regulatory text classification
│   │   ├── source_regulatory.py      # Citation/source tier inference
│   │   ├── dermauto_card_render.py   # Markdown → HTML card renderer
│   │   ├── swg_intake.py             # SWG intake form helpers
│   │   └── pages/
│   │       ├── 03_DermAUTO_Card.py   # DermAUTO card viewer page
│   │       └── preloaded_cards/      # Bundled example model cards
│   ├── pipelines/
│   │   └── cardgen_pipeline.py       # Main card generation pipeline
│   ├── agents/gemini_agent/          # Gemini extraction agent
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── tools.py
│   ├── ai_extractors/
│   │   └── ai_extractor.py           # Gemini AI integration
│   ├── scrapers/
│   │   ├── robust_scraper_v2.py      # Production-grade scraper
│   │   └── selenium_scraper.py       # Selenium fallback for JS-heavy pages
│   └── utils/
│       ├── web_search.py             # Search + fetch orchestration
│       ├── cache_system.py           # Result caching
│       ├── enhanced_publication_finder.py
│       ├── fda_discovery.py
│       ├── model_card_scorer.py
│       ├── net.py
│       └── utils.py
├── config/
│   ├── config.py
│   └── swg_intake_field_map.yml
├── scripts/                          # Standalone utilities
├── ragas_eval/                       # RAGAS evaluation tooling
├── docs/
├── run_app.py                        # Web vs terminal launcher
├── terminal_app.py                   # CLI entry point
└── cache_inspector.py                # Cache debug utility
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key
- Dependencies in `pyproject.toml` / `requirements.txt`

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/aad-model-card-generator.git
cd aad-model-card-generator
```

2. Install dependencies:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

4. Run the application:
```bash
streamlit run src/core/app.py --server.port 5000
```

Or use the launcher:
```bash
python run_app.py
```

## Features

### Core Capabilities
- **Automated Source Discovery**: Web search (Google CSE / DuckDuckGo) plus deep scraping
- **AI-Powered Extraction**: Gemini agent fills CHAI fields with per-field evidence
- **CHAI Schema Compliance**: 80+ fields aligned with HTI-1 / 45 CFR 170.315
- **Citations & Provenance**: Inline `[n]` references in markdown, `.citations.json` sidecars, regulatory tier coloring in the UI
- **Multiple Export Formats**: JSON, Markdown, and XML

### Web Scraping
- **RobustWebScraper**: Async HTTP with retries, second-hop link following, PDF extraction
- **Selenium fallback**: For JavaScript-heavy pages when static fetch is insufficient
- **Caching**: SQLite-backed cache to avoid redundant fetches

### Data Processing
- **Pipeline architecture**: `CardGenPipeline` orchestrates discovery → extraction → post-fill → export
- **Regulatory tagging**: Source URLs typed (FDA, clinical trial, PubMed, etc.) and color-coded at render time

## Configuration

Key environment variables (see `config/config.py`):

- `GEMINI_API_KEY`: Required for AI extraction
- `GEMINI_MODEL`: Model name (default: `gemini-2.5-flash`)
- `GEMINI_TEMPERATURE`: Sampling temperature (default: `0.7`)
- `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_CX`: Optional Google Custom Search for discovery

## Usage

### Web Interface

1. Open the Streamlit app
2. Enter model name, developer, and optional application URL
3. Generate the model card
4. View results in the Output tab and export JSON / Markdown / XML

### Programmatic Usage

```python
from pipelines.cardgen_pipeline import CardGenPipeline

async with CardGenPipeline() as pipeline:
    chai_card, sources, content = await pipeline.generate_model_card(
        model_name="Your Model Name",
        developer_name="Developer Organization",
    )
```

## Testing

Root-level test scripts (manual runners):

```bash
python test_regulatory_status.py
python test_source_regulatory.py
python test_scoring.py
python test_updates.py
```

## Documentation

- [Process Walkthrough](PROCESS_WALKTHROUGH.md) — end-to-end pipeline flow
- [Selenium Integration](SELENIUM_BEAUTIFULSOUP_INTEGRATION.md) — scraper fallback behavior
- [Caching System](../CACHING_SYSTEM_README.md) — cache layout and inspector usage
- [Scoring System](../SCORING_SYSTEM_README.md) — model card quality scoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests where appropriate
5. Submit a pull request

## License

This project is designed for dermatology AI model-card generation. Ensure compliance with website terms of service and robots.txt when scraping external content.

## Support

For issues and questions:
1. Check the documentation in `docs/`
2. Review existing issues on GitHub
3. Open a new issue with detailed reproduction steps
