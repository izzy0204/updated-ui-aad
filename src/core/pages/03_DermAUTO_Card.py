import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Streamlit Cloud (and some launch configs) do not load repo-root `sitecustomize.py`;
# ensure `src/` is importable as package root `core`.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import streamlit as st

from core.card_provenance import compute_provenance_for_sections
from core.dermauto_card_render import (
    body_before_references,
    build_ref_renumbering,
    extract_doc_title,
    normalize_md_for_parsing,
    parse_model_card_md,
    parse_references,
    render_full_card_html,
    rewrite_sections_citations,
    strip_chai_model_card_suffix,
)
from core.swg_intake import (
    default_field_map_path,
    default_forms_xlsx,
    load_column_field_map_yaml,
    match_survey_row_for_title,
    read_xlsx_first_sheet,
    survey_reported_composite_keys,
)

# Resolve repo root from this file: .../src/core/pages/<this>.py -> parents[3] == repo root.
_PAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = _PAGE_DIR.parents[3]
# Bundled presets live NEXT TO this page so Streamlit Cloud always finds them (no cwd guessing).
# Also check legacy repo-root `preloaded_cards/` for backwards compatibility.
PRELOADED_DIRS: Tuple[Path, ...] = (
    _PAGE_DIR / "preloaded_cards",
    REPO_ROOT / "preloaded_cards",
)
OUTPUTS_DIR = REPO_ROOT / "outputs"


def _resolve_md_path(filename: str) -> Optional[Path]:
    """Prefer `pages/preloaded_cards/`, then repo-root `preloaded_cards/`, then local `outputs/`."""
    for base in PRELOADED_DIRS:
        p = base / filename
        if p.exists():
            return p
    p = OUTPUTS_DIR / filename
    if p.exists():
        return p
    return None


def _provenance_legend_html() -> str:
    """Sidebar legend with pastel swatches matching PROVENANCE_ROW_STYLE."""
    rows = [
        ("#d8f3dc", "#2d6a4f", "Public source + industry survey reported"),
        ("#d9e8ff", "#1e6091", "Public source, not in industry survey"),
        ("#fff9e6", "#d4a017", "Industry survey only, not publicly available"),
        ("#fde8e8", "#c1121f", "Not reported publicly or in industry survey"),
    ]
    parts = []
    for bg, ac, label in rows:
        parts.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px;">'
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;'
            f"background:{bg};border:2px solid {ac};\"></span>"
            f"<span>{label}</span></div>"
        )
    return "".join(parts)


st.set_page_config(page_title="DermAUTO-CARD", layout="wide")

st.title("DermAUTO-CARD")
st.caption("Full CHAI model card from markdown: every section and field, with citations linked to **References**.")

with st.sidebar:
    st.subheader("Source")

    # Sidebar order: DermaSensor A/B, DermGPT A/B, Tandem A/B. Labels are UI-only; filenames are on disk.
    ordered_sources: List[Tuple[str, str]] = [
        ("A · DermaSensor", "dermasensor-20260501-192348.md"),
        ("B · DermaSensor", "Dermasensor.md"),
        ("A · DermGPT", "dermgpt-20260429-173126.md"),
        ("B · DermGPT", "DermGPT updated.md"),
        ("A · Tandem", "tandem-20260501-043225.md"),
        ("B · Tandem", "Tandem updated.md"),
    ]
    option_to_path: Dict[str, Path] = {}
    for label, fname in ordered_sources:
        p = _resolve_md_path(fname)
        if p:
            option_to_path[label] = p

    options = list(option_to_path.keys())

    default_key = "A · DermGPT"
    default_idx = options.index(default_key) if default_key in option_to_path else 0

    selected_path: Optional[Path] = None
    if options:
        selected_key = st.selectbox(
            "Select a model card",
            options=options,
            index=min(default_idx, len(options) - 1),
        )
        selected_path = option_to_path.get(selected_key)
    else:
        st.error("No bundled model cards found.")
        st.caption(
            "Expected 5 `.md` files under `src/core/pages/preloaded_cards/`. "
            "If you deploy from Git, push that folder and redeploy."
        )
        with st.expander("Path check (debug)"):
            st.code(
                "\n".join(
                    f"{d} exists={d.is_dir()} → {(d / 'dermgpt-20260429-173126.md').exists()}"
                    for d in PRELOADED_DIRS
                )
                + f"\n{OUTPUTS_DIR} (outputs/) exists={OUTPUTS_DIR.is_dir()}"
            )

    uploaded = st.file_uploader("Or upload a markdown file", type=["md"])

    st.subheader("Display")
    hide_citations = st.checkbox("Hide citation markers", value=False)
    show_raw = st.checkbox("Show raw markdown preview", value=False)
    color_provenance = st.checkbox("Color-code statement provenance", value=False)
    if color_provenance:
        st.markdown(
            "<div style='margin-top:6px;font-weight:600;font-size:12px;'>Legend</div>"
            + _provenance_legend_html(),
            unsafe_allow_html=True,
        )

if uploaded is not None:
    md_text = uploaded.read().decode("utf-8", errors="replace")
    source_label = uploaded.name
elif selected_path and selected_path.exists():
    md_text = selected_path.read_text(encoding="utf-8", errors="replace")
    # Preserve the A/B label shown in the selectbox.
    source_label = next((k for k, v in option_to_path.items() if v == selected_path), selected_path.name)
else:
    md_text = ""
    source_label = "No file selected"

if not md_text.strip():
    st.warning("Pick or upload a markdown file to render.")
    st.stop()

md_for_parse = normalize_md_for_parsing(md_text)
is_manual = source_label.strip().lower().startswith("b ·")
ref_map = parse_references(md_for_parse, allow_sources_heading=is_manual)
body_md = body_before_references(md_for_parse, allow_sources_heading=is_manual)
_old_to_new, ref_map = build_ref_renumbering(body_md, ref_map)
sections = parse_model_card_md(md_for_parse)
sections = rewrite_sections_citations(sections, _old_to_new)
doc_title = extract_doc_title(md_for_parse)
# UI-only: autogenerated sidebar cards (A ·) use CHAI H1 "… (v0.3)"; strip for display.
if doc_title and not is_manual:
    doc_title = re.sub(r"\s*\(v0\.3\)\s*$", "", doc_title, flags=re.IGNORECASE).strip() or None
doc_title = strip_chai_model_card_suffix(doc_title)

provenance_by_key = None
if color_provenance:
    column_map = load_column_field_map_yaml(default_field_map_path())
    survey_row = None
    xlsx_path = default_forms_xlsx()
    if xlsx_path.exists():
        _, data_rows = read_xlsx_first_sheet(xlsx_path)
        survey_row = match_survey_row_for_title(data_rows, doc_title)
    survey_keys = survey_reported_composite_keys(
        survey_row=survey_row,
        column_to_fields=column_map,
    )
    provenance_by_key = compute_provenance_for_sections(
        sections,
        ref_map,
        survey_keys if survey_row is not None else None,
    )

card_html = render_full_card_html(
    sections=sections,
    refs=ref_map,
    doc_title=doc_title,
    source_label=source_label,
    hide_citations=hide_citations,
    manual_linkify=is_manual,
    provenance_by_key=provenance_by_key,
)

if hasattr(st, "html"):
    st.html(card_html)
else:
    st.markdown(card_html, unsafe_allow_html=True)

if show_raw:
    with st.expander("Raw markdown", expanded=False):
        st.markdown(md_text)
