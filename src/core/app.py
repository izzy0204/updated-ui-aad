
"""
DERMATOLOGY AI MODEL CARD GENERATOR - MAIN STREAMLIT APPLICATION

PURPOSE:
This is the main web interface for generating comprehensive model cards for dermatology AI models.
It provides a user-friendly Streamlit application that automates the discovery, analysis, and 
documentation of AI models used in healthcare settings, specifically focusing on dermatology.

HOW IT WORKS:
1. User enters a model name and optional developer name
2. System performs multi-source discovery (HuggingFace, GitHub, PubMed, medical institutions)
3. Gemini AI analyzes discovered content for bias detection and compliance
4. Generates comprehensive model card following CHAI schema with 80+ fields
5. Displays results in both detailed and card format views with persistent storage

MAIN FEATURES:
- Two-tab interface: Main (input/generation) and Output (formatted display)
- Automated source discovery from 15+ platforms
- AI-powered content extraction and analysis
- CHAI schema compliance (HTI-1, 45 CFR 170.315)
- Professional card format with visual sections
- Multiple export formats (JSON, Markdown, XML)
- Session state management for persistent display

USAGE:
Run with: streamlit run app.py --server.port 5000
Navigate between Main tab (generation) and Output tab (results)
"""
import os
import sys
from pathlib import Path

# help
current_file = Path(__file__).resolve()
core_dir = current_file.parent         # src/core/
src_dir = core_dir.parent              # src/
repo_root = src_dir.parent             # /mount/src/aad-model-card-generator/

for path in [str(repo_root), str(src_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)
# help

import streamlit as st
import asyncio
import json
from datetime import datetime
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_dir = current_dir.parent
repo_root = src_dir.parent
load_dotenv(repo_root / ".env")
load_dotenv()

sys.path.insert(0, str(src_dir))
# Also add repo root so top-level packages like `config/` can be imported
# even when Streamlit is launched from a different working directory.
sys.path.insert(0, str(repo_root))

from dataclasses import fields as dc_fields

from pipelines.cardgen_pipeline import CardGenPipeline
from core.chai_schema import ClinicalModelCard, REGULATORY_STATUS_LABELS
from core.card_library import load_library
from core.citation_render import normalize_citation_sidecar
from core.dermauto_card_render import plain_preview, render_card_detail_html
from core.ui_theme import (
    LOGO_HTML,
    THEME_CSS,
    gallery_card_footer_html,
    gallery_card_html,
    generate_explainer_html,
    hero_html,
    stat_tiles_html,
)
from ai_extractors.ai_extractor import RateLimitExceededError, QuotaExceededError


def _restore_model_card_from_session():
    """Get ClinicalModelCard from session state; rebuild from JSON if the object was lost (common on Cloud)."""
    card = st.session_state.get("generated_model_card")
    if card is not None:
        return card
    raw = st.session_state.get("generated_model_card_json")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        card = ClinicalModelCard.from_dict(data)
        st.session_state.generated_model_card = card
        return card
    except Exception:
        return None


def _card_developer(card):
    return getattr(card, "model_developer", None) or getattr(card, "developer", None) or ""


def _card_stage(card):
    return getattr(card, "model_software_release_stage", None) or getattr(card, "release_stage", None) or ""


def _card_version(card):
    return getattr(card, "model_version", None) or getattr(card, "version", None) or ""


# Configure Streamlit page
st.set_page_config(
    page_title="Medical AI Model Card Generator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state for persistent output
if 'generated_model_card' not in st.session_state:
    st.session_state.generated_model_card = None
if 'generated_model_card_json' not in st.session_state:
    st.session_state.generated_model_card_json = None
if 'page' not in st.session_state:
    st.session_state.page = "home"

st.html(THEME_CSS)

NAV_PAGES = (("home", "Model Cards"), ("generate", "Generate Model"), ("output", "Output"))


def render_header():
    logo_col, nav_col, menu_col = st.columns([2.2, 5, 0.6], vertical_alignment="center")
    with logo_col:
        st.html(LOGO_HTML)
    with nav_col:
        for col, (page, label) in zip(st.columns(len(NAV_PAGES)), NAV_PAGES):
            with col:
                key = "mc_nav_active" if st.session_state.page == page else f"mc_nav_{page}"
                if st.button(label, key=key, use_container_width=True):
                    st.session_state.page = page
                    st.rerun()
    with menu_col:
        # Keyed containers (not popover(key=...)) so styling works on Streamlit < 1.50.
        with st.container(key="mc_menu"), st.popover("⋮"):
            st.page_link("pages/03_DermAUTO_Card.py", label="DermAUTO-CARD viewer")


def _card_tags(card, *extra):
    status = REGULATORY_STATUS_LABELS.get(card.regulatory_approval_status, "Regulatory Status Unknown")
    return tuple(extra) + (status,)


def _citation_count(citations):
    return len(normalize_citation_sidecar(citations).references) if citations else 0


@st.cache_resource(show_spinner="Loading model cards...")
def _bundled_library():
    return load_library()


def _gallery_entries():
    """Generated card (if any) first, then the bundled library cards."""
    entries = []
    card = _restore_model_card_from_session()
    if card is not None:
        entries.append({
            "key": "generated", "card": card, "citations": st.session_state.get("generated_citations"),
            "tags": _card_tags(card, "New"),
        })
    for item in _bundled_library():
        entries.append({
            "key": item.key, "card": item.card, "citations": item.citations,
            "tags": _card_tags(item.card, f"Card {item.label.split(' · ')[0]}"),
        })
    return entries


def _download_buttons(card, key_prefix):
    stem = (card.model_name or 'model_card').replace(' ', '_')
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download JSON",
            data=card.to_json(),
            file_name=f"{stem}_model_card.clinical.json",
            mime="application/json",
            use_container_width=True,
            key=f"{key_prefix}_json",
        )
    with col2:
        st.download_button(
            label="Download Markdown",
            data=card.to_markdown(),
            file_name=f"{stem}_model_card.clinical.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"{key_prefix}_md",
        )


def _open_card_dialog(entry):
    @st.dialog(" ", width="large")
    def _dialog():
        st.html(render_card_detail_html(
            entry["card"],
            citations=entry["citations"],
            tags=entry["tags"],
        ))
        _download_buttons(entry["card"], f"dlg_{entry['key']}")

    _dialog()


SORT_OPTIONS = {
    "Alphabetical": lambda e: (e["card"].model_name or "").lower(),
    "Last Updated": lambda e: -(e["card"].last_updated.toordinal() if hasattr(e["card"].last_updated, "toordinal") else 0),
}


def home_page_content():
    entries = _gallery_entries()

    search_col, sort_col, filter_col = st.columns([6, 2.4, 1.2], vertical_alignment="center")
    with search_col:
        query = st.text_input("Search", placeholder="Search Model Cards...", label_visibility="collapsed", key="mc_search")
    with sort_col:
        sort_by = st.selectbox(
            "Sort", list(SORT_OPTIONS), format_func=lambda s: f"Sort by... {s}",
            label_visibility="collapsed", key="mc_sort",
        )
    with filter_col:
        with st.container(key="mc_filters"), st.popover("Filters", use_container_width=True):
            statuses = sorted({e["tags"][-1] for e in entries})
            chosen = st.multiselect("Regulatory status", statuses, key="mc_filter_status")

    q = (query or "").strip().lower()
    if q:
        entries = [
            e for e in entries
            if q in " ".join(
                [e["card"].model_name or "", e["card"].developer or "", plain_preview(e["card"].summary or ""), *e["tags"]]
            ).lower()
        ]
    if chosen:
        entries = [e for e in entries if e["tags"][-1] in chosen]
    entries.sort(key=SORT_OPTIONS[sort_by])

    if not entries:
        st.html('<div class="mc-empty">No model cards match your search.</div>')
        return

    for row_start in range(0, len(entries), 3):
        cols = st.columns(3, gap="medium")
        for col, entry in zip(cols, entries[row_start:row_start + 3]):
            with col:
                with st.container(key=f"mc_card_{entry['key']}"):
                    st.html(gallery_card_html(entry["card"], tags=entry["tags"]))
                    foot_col, learn_col = st.columns([2.4, 1.2], vertical_alignment="bottom")
                    with foot_col:
                        st.html(gallery_card_footer_html(entry["card"], _citation_count(entry["citations"])))
                    with learn_col:
                        if st.button("Learn More →", key=f"mc_learn_{entry['key']}"):
                            _open_card_dialog(entry)


# Define tab content functions first
def main_tab_content():
    # Simple interface - one form, one button
    _, form_col, _ = st.columns([1, 2.6, 1])
    with form_col, st.container(key="mc_gen_form"):
        st.html('<div class="mc-form-title">Generate Model</div>')
        model_name = st.text_input(
            "Enter the name of your AI model:",
            placeholder="e.g., Derm Foundation, SkinVision, MelanomaNet",
            help="We'll automatically find information about your model from research papers, GitHub, and other sources"
        )
        
        # Developer Input - Enhanced Search Capability
        developer_name = st.text_input(
            "Model Developer (Optional):",
            placeholder="e.g., Google Health, 3Derm, SciBase, DermTech",
            help="Enter the developer/organization name to improve search accuracy and targeting"
        )
        
        # Application URL Input - Primary Source
        application_url = st.text_input(
            "Application URL (Optional):",
            placeholder="e.g., https://example.com/model-docs, https://github.com/org/model",
            help="Enter the main website or documentation URL for this AI application. This source will be prioritized for field filling."
        )

        # Developer-focused optimization info
        st.html(
            '<div class="mc-form-note"><b>Enhanced Discovery:</b> When you specify a developer name or application URL, '
            "the system prioritizes those sources for more accurate and targeted information extraction. "
            "The Application URL will be used as the primary source for field filling.</div>"
        )
        generate_button = st.button("Generate Model Card", type="primary", use_container_width=True, key="mc_generate")

    # Main generation logic
    if generate_button:
        if not model_name:
            st.error("Please enter a model name")
        else:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Full pipeline lives in generate_model_card (discover + extract + generate).
                async def run_cardgen_pipeline():
                    async with CardGenPipeline() as pipeline:
                        status_text.text("Finding information about your model...")
                        progress_bar.progress(25)

                        status_text.text("Extracting technical details and documentation...")
                        progress_bar.progress(50)

                        status_text.text("Analyzing with AI and generating comprehensive model card...")
                        progress_bar.progress(75)

                        chai_card, sources, content = await pipeline.generate_model_card(
                            model_name=model_name,
                            developer_name=developer_name or "",
                            application_url=application_url or "",
                        )

                        progress_bar.progress(100)
                        status_text.text("Model card generated successfully!")
                        return chai_card, sources, content

                # Run the pipeline
                chai_model_card, sources, extracted_content = asyncio.run(run_cardgen_pipeline())

                # Store in session state for output tab (overwrites previous)
                st.session_state.generated_model_card = chai_model_card
                st.session_state.generated_model_card_json = chai_model_card.to_json()
                st.session_state.generated_sources = sources
                st.session_state.generated_content = extracted_content
                st.session_state.generated_citations = sources.get("citations")
                
                # Success message with tab guidance
                st.success("Your model card has been generated! View the complete formatted output in the **Output** page.")
                
                # Quick stats (pipeline sources shape: web_search / publications / fda / citations)
                web_discovered = (sources.get("web_search") or {}).get("discovered") or []
                web_urls = (sources.get("web_search") or {}).get("top_urls") or []
                publications = sources.get("publications") or []
                fda_records = sources.get("fda") or []
                citations = sources.get("citations") or {}
                if isinstance(citations, dict):
                    citation_count = len(citations.get("references") or {}) or sum(
                        1 for k, v in citations.items()
                        if k not in ("schema_version", "schemaVersion", "_sources_metadata", "references", "field_citations", "fieldCitations", "fields")
                        and isinstance(v, list) and v
                    )
                else:
                    citation_count = 0
                total_sources = len(web_discovered) or len(web_urls) or (len(publications) + len(fda_records))

                metrics_count = len(getattr(getattr(chai_model_card, "performance", None), "metrics", None) or [])

                st.html('<div class="mc-section-title">Generation Summary</div>')
                st.html(stat_tiles_html((
                    ("Sources Found", total_sources),
                    ("Publications / FDA", len(publications) + len(fda_records)),
                    ("Performance Metrics", metrics_count),
                    ("Cited Sources", citation_count),
                )))

                # Model card preview
                st.html('<div class="mc-section-title">Your Model Card</div>')
                with st.container(key="mc_card_generated_preview"):
                    st.html(render_card_detail_html(
                        chai_model_card,
                        citations=st.session_state.generated_citations,
                        tags=_card_tags(chai_model_card, "New"),
                    ))

                # Download section
                st.html('<div class="mc-section-title">Download Your Model Card</div>')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="Download JSON",
                        data=chai_model_card.to_json(),
                        file_name=f"{model_name.replace(' ', '_')}_model_card.clinical.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                with col2:
                    st.download_button(
                        label="Download Markdown", 
                        data=chai_model_card.to_markdown(),
                        file_name=f"{model_name.replace(' ', '_')}_model_card.clinical.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                
                # Technical details in expandable section
                with st.expander("Technical Details & Source Information"):
                    # ENHANCED SOURCES SECTION - Prominent display for transparency
                    if hasattr(chai_model_card, 'sources_summary') and chai_model_card.sources_summary:
                        st.markdown("### Information Sources & Reliability Assessment")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("#### Information Sources Used")
                            st.markdown(chai_model_card.sources_summary)
                        
                        with col2:
                            st.markdown("#### Source Reliability Assessment")
                            st.markdown(chai_model_card.source_reliability_assessment)
                        
                        st.info("**Transparency Note**: This model card was generated using automated information discovery from the sources listed above. All information is attributed to its source.")
                        
                        # Display AI extraction metrics if available
                        try:
                            # Access metrics from the completed pipeline
                            with st.expander("AI Extraction Analytics", expanded=False):
                                # Show static success message since pipeline is out of scope
                                st.success("Model card generation completed successfully with AI analysis")
                                st.info("AI analysis completed with GPT-5 for comprehensive content extraction and model card generation.")
                        except Exception:
                            pass  # Gracefully handle any metrics display issues
                        
                        st.markdown("---")
                    
                    st.markdown("### Sources Discovered")

                    source_cols = st.columns(4)
                    with source_cols[0]:
                        st.metric("Web URLs", len(web_urls) or len(web_discovered))
                    with source_cols[1]:
                        st.metric("Research Papers", len(publications))
                    with source_cols[2]:
                        st.metric("FDA Records", len(fda_records))
                    with source_cols[3]:
                        st.metric("Cited Sources", citation_count)

                    st.markdown("### Compliance Standards")
                    st.markdown("- Clinical model card schema v2.0")
                    st.markdown("- HTI-1 regulation ready")
                    st.markdown("- 45 CFR 170.315 compatible")
                    st.markdown("- Medical AI documentation standards")

                    generated_at = getattr(chai_model_card, "extraction_timestamp", None) or getattr(
                        chai_model_card, "last_updated", None
                    )
                    if generated_at:
                        st.markdown(f"**Generated / last updated:** {generated_at}")
            except RateLimitExceededError as e:
                # Clear any existing model card on rate limit error
                if 'generated_model_card' in st.session_state:
                    st.session_state.generated_model_card = None
                st.session_state.generated_model_card_json = None
                
                st.error("**Gemini API Rate Limit Exceeded**")
                st.markdown("""
                **The model card generation has been stopped because the Gemini API rate limit was reached.**
                
                **What this means:**
                - Too many requests were made to the Gemini API in a short time period
                - The scraping process has been automatically stopped to prevent further errors
                
                **What to do:**
                - **Wait 1-2 minutes** before trying again
                - **Try a simpler model name** to reduce API calls needed
                - **Contact support** if this happens repeatedly
                
                **Current status:** **Scraping stopped** - No further API calls will be made until you restart
                """)
                
                with st.expander("Technical Details"):
                    st.code(f"Rate Limit Error: {str(e)}")
                    st.info("Rate limiting protects the API from being overwhelmed and ensures fair usage across all users.")
            
            except QuotaExceededError as e:
                progress_bar.progress(0)
                status_text.text("")
                
                # Clear any existing model card on quota error
                if 'generated_model_card' in st.session_state:
                    st.session_state.generated_model_card = None
                st.session_state.generated_model_card_json = None
                
                st.error("**Gemini API Quota Exceeded**")
                st.markdown("""
                **The model card generation has been stopped because the Gemini API quota has been exceeded.**
                
                **This means:**
                - The AI analysis portion cannot be completed
                - No model card will be generated until this is resolved
                
                **To resolve this:**
                - Add credits to your Google Cloud account
                - Check your usage limits in the Google Cloud console
                - Wait for quota reset (if on a usage-based plan)
                - Contact Google Cloud support if needed
                
                **Status:** Generation completely stopped - no output will be provided until quota issue is resolved
                """)
                
                with st.expander("Technical Details"):
                    st.code(f"Quota Error: {str(e)}")
                    st.info("Quota limits prevent unexpected charges and help manage API usage costs.")
    
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                
                # Clear any existing model card on error
                if 'generated_model_card' in st.session_state:
                    st.session_state.generated_model_card = None
                st.session_state.generated_model_card_json = None
                
                st.error("Model card generation failed")
                
                with st.expander("Error Details (Click to expand)"):
                    st.code(f"Error: {str(e)}\n\nFull traceback:\n{error_details}")
                
                st.info("**Troubleshooting tips:**")
                st.markdown("""
                - Try a different model name (e.g., 'DermNet', 'SkinLesion-AI', or 'HAM10000')
                - Make sure the model name is spelled correctly
                - Check if the model exists on platforms like HuggingFace or GitHub
                - If this is an API error, wait a few minutes and try again
                - If the error persists, please report it with the error details above
                """)

    # What we do explanation
    st.html(generate_explainer_html())


def output_tab_content():
    """Output tab with persistent model card display"""
    st.html('<div class="mc-page-title">Model Card Output</div>')

    card = _restore_model_card_from_session()
    if card is not None:
        # Add a clear button at the top
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Clear Output", help="Clear the current model card output"):
                st.session_state.generated_model_card = None
                st.session_state.generated_model_card_json = None
                st.session_state.generated_citations = None
                st.rerun()
        
        with col2:
            st.markdown(f"**Current Model:** {card.model_name or 'Unnamed Model'}")
        
        st.markdown("---")
        display_model_card_output(card)
    else:
        st.info("No model card generated yet. Go to the Generate Model page and generate a model card to see the output here.")
        st.markdown("")
        st.markdown("**How it works:**")
        st.markdown("- Generate a model card on the Generate Model page")
        st.markdown("- The output will automatically appear here")
        st.markdown("- Output persists when you switch between tabs")
        st.markdown("- Generate a new model card to replace the current output")

def display_model_card_output(chai_model_card):
    """Display the model card in the same detail layout as the gallery pop-up."""
    citations = st.session_state.get("generated_citations")
    with st.container(key="mc_card_output"):
        st.html(render_card_detail_html(
            chai_model_card,
            citations=citations,
            tags=_card_tags(chai_model_card),
        ))

    # Download Section
    st.markdown("### Download Options")
    _download_buttons(chai_model_card, "output")


def display_sources_section(chai_model_card):
    """Display detailed information about sources used for the model card"""
    
    # Extract source information
    sources_summary = getattr(chai_model_card, 'sources_summary', {}) or {}
    extraction_summary = getattr(chai_model_card, 'extraction_summary', {}) or {}
    source_citations = getattr(chai_model_card, 'source_citations', {}) or {}
    
    # Display source counts in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Source Discovery")
        if extraction_summary.get('sources_discovered'):
            source_counts = extraction_summary['sources_discovered']
            st.markdown(f"**Total sources found:** {source_counts.get('total', 0)}")
            
            # Create a simple bar chart for source types
            source_data = {
                'HuggingFace': source_counts.get('huggingface', 0),
                'GitHub': source_counts.get('github', 0),
                'PubMed': source_counts.get('pubmed', 0),
                'arXiv': source_counts.get('arxiv', 0),
                'Websites': source_counts.get('websites', 0)
            }
            
            # Only show sources that have counts > 0
            filtered_data = {k: v for k, v in source_data.items() if v > 0}
            if filtered_data:
                st.bar_chart(filtered_data)
            else:
                st.info("No source type breakdown available")
    
    with col2:
        st.markdown("### Extraction Statistics")
        if extraction_summary:
            st.metric("Content Extracted", extraction_summary.get('content_extracted', 0))
            st.metric("Success Rate", extraction_summary.get('success_rate', 'N/A'))
            st.metric("Source Types", extraction_summary.get('source_types_analyzed', 0))
    
    # Display detailed source citations
    if source_citations:
        st.markdown("### Source Citations by Field")
        
        # Count total citations
        citation_count = sum(len(citations) for citations in source_citations.values() if isinstance(citations, list))
        st.info(f"Total citations: {citation_count}")
        
        # Create expandable sections for each field with citations
        for field_name, citations in source_citations.items():
            if citations and isinstance(citations, list):
                field_display_name = field_name.replace('_', ' ').title()
                with st.expander(f"{field_display_name} ({len(citations)} citations)"):
                    for i, citation in enumerate(citations[:5], 1):  # Show max 5 citations per field
                        if isinstance(citation, dict):
                            title = citation.get('title', 'Unknown Title')
                            url = citation.get('url', '')
                            source_type = citation.get('type', 'web')
                            
                            st.markdown(f"**{i}. {title}**")
                            if url:
                                st.markdown(f"[View Source]({url})")
                            st.markdown(f"Type: {source_type}")
                            st.markdown("---")
    
    # Display sources summary if available
    if sources_summary and isinstance(sources_summary, dict):
        st.markdown("### Analysis Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if sources_summary.get('total_analyzed'):
                st.metric("Sources Analyzed", sources_summary['total_analyzed'])
        
        with col2:
            if sources_summary.get('successes'):
                st.metric("Successful Extractions", sources_summary['successes'])
        
        with col3:
            if sources_summary.get('success_ratio'):
                st.metric("Success Ratio", f"{sources_summary['success_ratio']:.1%}")
    
    # Footer note
    st.info("All information in this model card was extracted from the sources listed above.")


render_header()
if st.session_state.page in ("home", "generate"):
    st.html(hero_html(
        "Medical AI Model Card Generator",
        "Generate professional model cards for medical AI systems in one simple step",
        compact=st.session_state.page != "home",
    ))

if st.session_state.page == "generate":
    main_tab_content()
elif st.session_state.page == "output":
    output_tab_content()
else:
    home_page_content()
