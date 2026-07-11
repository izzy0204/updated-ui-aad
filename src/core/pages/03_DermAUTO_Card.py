import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import streamlit as st

from core.chai_schema import ClinicalModelCard
from core.source_regulatory import load_citations_for_markdown
from core.dermauto_card_render import (
    is_clinical_markdown,
    regulatory_legend_html,
    render_from_card,
)

_PAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = _PAGE_DIR.parents[3]
PRELOADED_DIRS: Tuple[Path, ...] = (
    _PAGE_DIR / "preloaded_cards",
    REPO_ROOT / "preloaded_cards",
)
OUTPUTS_DIR = REPO_ROOT / "outputs"


def _resolve_card_paths(filename: str) -> Tuple[Optional[Path], Optional[Path]]:
    """Return (json_path, md_path) preferring .clinical.json."""
    stem = Path(filename).stem.replace(".clinical", "")
    for base in PRELOADED_DIRS:
        jp = base / f"{stem}.clinical.json"
        if jp.exists():
            return jp, jp.with_suffix(".clinical.md")
        mp = base / filename
        if mp.exists():
            return mp.with_suffix(".clinical.json") if mp.with_suffix(".clinical.json").exists() else None, mp
    jp = OUTPUTS_DIR / f"{stem}.clinical.json"
    if jp.exists():
        return jp, jp.with_suffix(".clinical.md")
    mp = OUTPUTS_DIR / filename
    if mp.exists():
        return None, mp
    return None, None


st.set_page_config(page_title="DermAUTO-CARD", layout="wide")
st.title("DermAUTO-CARD")
st.caption("Clinician-centered model card viewer (JSON canonical, markdown for upload).")

with st.sidebar:
    st.subheader("Source")
    ordered_sources: List[Tuple[str, str]] = [
        ("A · DermaSensor", "dermasensor-20260501-192348"),
        ("B · DermaSensor", "Dermasensor"),
        ("A · DermGPT", "dermgpt-20260429-173126"),
        ("B · DermGPT", "DermGPT updated"),
        ("A · Tandem", "tandem-20260501-043225"),
        ("B · Tandem", "Tandem updated"),
    ]
    option_to_path: Dict[str, Path] = {}
    for label, stem in ordered_sources:
        for base in PRELOADED_DIRS:
            jp = base / f"{stem}.clinical.json"
            if jp.exists():
                option_to_path[label] = jp
                break

    options = list(option_to_path.keys())
    default_key = "A · DermGPT"
    default_idx = options.index(default_key) if default_key in option_to_path else 0

    selected_path: Optional[Path] = None
    if options:
        selected_key = st.selectbox("Select a model card", options=options, index=min(default_idx, len(options) - 1))
        selected_path = option_to_path.get(selected_key)
    else:
        st.error("No bundled model cards found.")

    uploaded = st.file_uploader("Or upload clinical JSON / markdown", type=["json", "md"])
    hide_citations = st.checkbox("Hide citation markers", value=False)
    color_regulatory = st.checkbox("Color-code regulatory status row", value=False)
    if color_regulatory:
        st.markdown(regulatory_legend_html(), unsafe_allow_html=True)

md_path: Optional[Path] = None
json_path: Optional[Path] = None
source_label = "No file selected"
card: Optional[ClinicalModelCard] = None
md_text = ""
citations_data = None

if uploaded is not None:
    source_label = uploaded.name
    if uploaded.name.endswith(".json"):
        card = ClinicalModelCard.from_dict(__import__("json").loads(uploaded.read().decode("utf-8")))
    else:
        md_text = uploaded.read().decode("utf-8", errors="replace")
elif selected_path and selected_path.exists():
    source_label = next((k for k, v in option_to_path.items() if v == selected_path), selected_path.name)
    if selected_path.suffix == ".json":
        card = ClinicalModelCard.from_dict(__import__("json").loads(selected_path.read_text(encoding="utf-8")))
        citations_data = load_citations_for_markdown(selected_path)
    else:
        md_path = selected_path
        json_path, _ = _resolve_card_paths(selected_path.name)
        if json_path and json_path.exists():
            card = ClinicalModelCard.from_dict(__import__("json").loads(json_path.read_text(encoding="utf-8")))
            citations_data = load_citations_for_markdown(json_path)
        else:
            md_text = selected_path.read_text(encoding="utf-8", errors="replace")
            citations_data = load_citations_for_markdown(selected_path)

if card is None and not md_text.strip():
    st.warning("Pick or upload a model card to render.")
    st.stop()

if card is not None:
    html_out = render_from_card(card, source_label=source_label, hide_citations=hide_citations, citations=citations_data)
    if hasattr(st, "html"):
        st.html(html_out)
    else:
        st.markdown(html_out, unsafe_allow_html=True)
    st.stop()

if is_clinical_markdown(md_text):
    st.error(
        "Clinical markdown upload requires the companion `.clinical.json` bundle. "
        "Upload the JSON file (and optional `.citations.json`) for full rendering."
    )
else:
    st.error(
        "Legacy CHAI v0.3 markdown is no longer supported. "
        "Upload a `clinical-model-card-1.0` JSON file or run the migration script."
    )
st.stop()
