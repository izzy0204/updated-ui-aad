# Dermatology UI card readability analysis

Python 3.11 pipeline to compute **Flesch Reading Ease** and **Flesch–Kincaid grade level** for dermatology AI **UI model cards** (CHAI-style Markdown in `ui_cards/`) and optional structured **JSON** cards. Metrics are reported **per section** and for **all selected fields combined** (`OVERALL_SELECTED_FIELDS`), so aggregate scores do not hide difficult sections.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Where the UI cards are

| Path | What it is |
|------|------------|
| **`ui_cards/`** (repo root) | **Markdown UI cards** — the CHAI `.md` sources this script reads by default. Same directory as [`run_custom_factscore_ui_cards.py`](run_custom_factscore_ui_cards.py) **`--md-dir`**. |
| `factscore_out/ui_cards_custom/` | FactScore **evaluation outputs** (JSON per run). Not used for readability; those files are scores over facts, not section text. |

Default `--input` resolves to **`ui_cards/`** next to `run_readability.py`.

## Input: UI cards (Markdown)

Inputs live in [`ui_cards/`](ui_cards/) — one `.md` file per card (same stems used by [`run_custom_factscore_ui_cards.py`](run_custom_factscore_ui_cards.py)).

Sections are taken from bullet lines such as `- **Summary:** …` and from the **Key Metrics** subsections:

| Logical section (`READABILITY_FIELDS`) | Markdown source |
|----------------------------------------|-----------------|
| `summary` | `- **Summary:**` |
| `intended_use_and_workflow` | `- **Intended Use & Workflow:**` |
| `model_limitations` | `- **Model Limitations:**` |
| `ai_system_facts` | `- **AI System Facts:**` |
| `developer_supplied_warnings` | `- **Developer-Supplied Warnings:**` |
| `clinical_risk_level` | `- **Clinical Risk Level:**` |
| `how_to_use` | `- **How to Use:**` |
| `transparency_information` | `- **Transparency Information:**` |
| `usefulness_efficacy_result` | Under `### Usefulness / Efficacy`, bullets **Goal of Metric(s)**, **Result**, **Interpretation** (concatenated) |
| `fairness_equity_interpretation` | Under `### Fairness & Equity`, same three bullets |
| `safety_reliability_interpretation` | Under `### Safety & Reliability`, same three bullets |

Text after `## References` is ignored. By default, bracket citations like `[1]` are **stripped** before scoring so readability reflects prose rather than citation noise; use `--no-strip-citations` to keep them.

## Input: JSON model cards

If you pass `.json` files (or `--extensions md,json`), each object should expose the same logical keys as string fields. `model_name` is used when present; otherwise the file stem is used.

## Usage

**Defaults (all UI Markdown cards under `ui_cards/`, CSV under `readability_out/`):**

```bash
python run_readability.py
```

Equivalent explicit paths:

```bash
python run_readability.py \
  --input ui_cards \
  --output readability_out/ui_cards_readability.csv
```

**Single card:**

```bash
python run_readability.py --input ui_cards/Tandem\ updated.md --output readability_out/tandem.csv
```

**Include JSON files in a folder scan** (replace `MY_FOLDER` with an actual path — there is no folder literally named `path/to/cards`):

```bash
python run_readability.py --input MY_FOLDER --extensions md,json --output out.csv
```

**Recursive scan** (nested folders, e.g. exported cards under subdirectories):

```bash
python run_readability.py --input MY_FOLDER --recursive --output out.csv
```

**Plots** (heatmaps by model × section, overall dual-axis bars):

```bash
python run_readability.py --plot-dir readability_out/figures/
```

Copy-paste pitfall: tutorial snippets sometimes show `path/to/cards` as a placeholder. That path does not exist on disk unless you create it — use `ui_cards` or another real directory.

## Output CSV columns

| Column | Description |
|--------|-------------|
| `model_name` | Card id (Markdown: file stem; JSON: `model_name` or stem) |
| `file` | Source filename |
| `format` | `md` or `json` |
| `section` | Field name or `OVERALL_SELECTED_FIELDS` |
| `text` | Normalized single-line text used for scoring |
| `word_count` | Word count (`textstat.lexicon_count`, punctuation removed) |
| `sentence_count` | Sentence count |
| `flesch_reading_ease` | Flesch Reading Ease (higher = easier), or empty if not computable |
| `flesch_kincaid_grade` | U.S. grade level estimate, or empty if not computable |

Empty or missing sections do not produce rows. The overall row concatenates only sections that produced rows.

## Programmatic use

```python
from pathlib import Path
from readability_analysis import (
    UI_CARDS_MARKDOWN_DIR,
    analyze_card,
    analyze_folder,
    save_readability_plots,
)

df_one = analyze_card(UI_CARDS_MARKDOWN_DIR / "Tandem updated.md")
df_many = analyze_folder(
    UI_CARDS_MARKDOWN_DIR,
    Path("readability_out/out.csv"),
    extensions=(".md",),
    recursive=False,
)
save_readability_plots(df_many, Path("readability_out/figures"))
```

## Dependencies

- `pandas` — tables and CSV I/O  
- `textstat` — readability formulas (pinned to **0.6.x** so syllable counts do not require NLTK’s `cmudict` download; if you upgrade to `textstat` 0.7+, run `python -c "import nltk; nltk.download('cmudict')"` once or set `NLTK_DATA` to a writable directory)  
- `matplotlib` — optional plots  

## Interpretation notes

- Section-level scores surface dense or technical passages even when the full card averages look acceptable.
- Very short snippets may yield missing metrics (`sentence_count` or edge cases in formulas).
- Flesch Reading Ease is typically interpreted on a 0–100 scale (higher = easier); grade level is an approximate U.S. school grade.
