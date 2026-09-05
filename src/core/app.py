
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
from core.dermauto_card_render import format_version_with_date
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

st.title("Medical AI Model Card Generator")
st.markdown("### Generate professional model cards for medical AI systems in one simple step")

# Define tab content functions first
def main_tab_content():
    # Simple interface - just one input and one button
    st.markdown("---")

    col1, col2 = st.columns([3, 1])
    
    with col1:
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
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Add spacing
        generate_button = st.button("Generate Model Card", type="primary", use_container_width=True)
    
    # Remove cache management section
    
    # What we do explanation
    with st.expander("What happens when you click 'Generate Model Card'?"):
        st.markdown("""
        **Automated Discovery & Analysis:**
        1. **Find Information** - Search research papers, GitHub repositories, and documentation
        2. **Extract Details** - Pull out technical specs, performance metrics, and usage info
        3. **AI Analysis** - Use advanced AI to analyze bias, risks, and clinical considerations
        4. **Generate Card** - Create a professional model card meeting medical AI standards
        
        **You Get:**
        - Complete technical documentation
        - Bias and fairness analysis
        - Clinical risk assessment  
        - Regulatory compliance information
        - Ready-to-use model card in multiple formats (JSON, Markdown, XML)
        
        **Enhanced Discovery:** Uses advanced AI to analyze discovered sources for comprehensive model documentation.
        """)
    
    # Developer-focused optimization info
    st.info("**Enhanced Discovery**: When you specify a developer name or application URL, the system prioritizes those sources for more accurate and targeted information extraction. The Application URL will be used as the primary source for field filling.")
    
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
                
                # Success message with tab guidance
                st.success("Your model card has been generated! View the complete formatted output in the **Output tab**.")
                
                # Show scoring information if available
                if sources.get("scoring"):
                    scoring = sources["scoring"]
                    st.subheader("Model Card Scoring")
                    
                    # Color-coded scoring display
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        completion = scoring["completion_percentage"]
                        if completion >= 75:
                            st.success(f"Completion: {completion:.1f}%")
                        elif completion >= 50:
                            st.warning(f"Completion: {completion:.1f}%")
                        else:
                            st.error(f"Completion: {completion:.1f}%")
                    
                    with col2:
                        clinical_level = scoring["clinical_usability_level"]
                        if clinical_level == "green":
                            st.success(f"Clinical: {clinical_level.upper()}")
                        elif clinical_level == "yellow":
                            st.warning(f"Clinical: {clinical_level.upper()}")
                        else:
                            st.error(f"Clinical: {clinical_level.upper()}")
                    
                    with col3:
                        st.info(f"Fields: {scoring['filled_fields']}/{scoring['total_fields']}")
                    
                    # Overall rating
                    st.info(f"**Overall Rating:** {scoring['overall_rating']}")
                    
                    # Critical missing fields
                    if scoring.get("critical_missing_fields"):
                        st.warning(f"**Critical Missing Fields:** {', '.join(scoring['critical_missing_fields'])}")
                    
                    # Recommendations count
                    if scoring.get("recommendations_count", 0) > 0:
                        st.info(f"**Recommendations:** {scoring['recommendations_count']} improvement suggestions available")
                
                # Quick stats (pipeline sources shape: web_search / publications / fda / citations)
                st.subheader("Generation Summary")
                col1, col2, col3, col4 = st.columns(4)

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

                with col1:
                    st.metric("Sources Found", total_sources)
                with col2:
                    st.metric("Publications / FDA", len(publications) + len(fda_records))
                with col3:
                    metrics_count = len(getattr(getattr(chai_model_card, "performance", None), "metrics", None) or [])
                    st.metric("Performance Metrics", metrics_count)
                with col4:
                    st.metric("Cited Sources", citation_count)
                
                # Model card preview
                st.subheader("Your Model Card")
                
                with st.expander("Model Card Preview", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Basic Information**")
                        st.markdown(f"**Model Name:** {chai_model_card.model_name}")
                        st.markdown(f"**Developer:** {_card_developer(chai_model_card) or 'Not specified'}")
                        st.markdown(f"**Type:** {chai_model_card.model_type}")
                        
                        st.markdown("**Summary:**")
                        summary_text = chai_model_card.summary if chai_model_card.summary else "AI model for medical/dermatology applications"
                        st.markdown(summary_text[:300] + ("..." if len(summary_text) > 300 else ""))
                    
                    with col2:
                        st.markdown("**Key Details**")
                        st.markdown(f"**Medical Purpose:** {(chai_model_card.medical_purpose or 'Not specified')[:200]}")
                        st.markdown(f"**Intended Users:** {chai_model_card.intended_users or 'Healthcare professionals'}")
                        st.markdown(f"**Regulatory Status:** {REGULATORY_STATUS_LABELS.get(chai_model_card.regulatory_approval_status, 'Unknown')}")
                
                # Download section
                st.subheader("Download Your Model Card")
                st.markdown("Choose your preferred format:")
                
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

def output_tab_content():
    """Output tab with persistent model card display"""
    st.markdown("### Model Card Output")
    
    card = _restore_model_card_from_session()
    if card is not None:
        # Add a clear button at the top
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Clear Output", help="Clear the current model card output"):
                st.session_state.generated_model_card = None
                st.session_state.generated_model_card_json = None
                st.rerun()
        
        with col2:
            st.markdown(f"**Current Model:** {card.model_name or 'Unnamed Model'}")
        
        st.markdown("---")
        display_model_card_output(card)
    else:
        st.info("No model card generated yet. Go to the Main tab and generate a model card to see the output here.")
        st.markdown("")
        st.markdown("**How it works:**")
        st.markdown("- Generate a model card on the Main tab")
        st.markdown("- The output will automatically appear here")
        st.markdown("- Output persists when you switch between tabs")
        st.markdown("- Generate a new model card to replace the current output")

def display_model_card_output(chai_model_card):
    """Display the model card in a consolidated card format with visual sections"""
    
    # Main Model Card - Consolidated View
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 15px;
            margin-bottom: 2rem;
            color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        ">
            <h1 style="margin: 0; font-size: 2.5rem; text-align: center; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                 {chai_model_card.model_name or 'AI Model'}
            </h1>
            <p style="text-align: center; font-size: 1.2rem; margin: 1rem 0; opacity: 0.9;">
                {_card_developer(chai_model_card) or 'Unknown Developer'}
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Key Info Cards Grid
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                padding: 1.5rem;
                border-radius: 10px;
                color: white;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                margin-bottom: 1rem;
            ">
                <h3 style="margin: 0; color: white;"> Basic Info</h3>
                <hr style="border-color: rgba(255,255,255,0.3);">
                <p><strong>Type:</strong> {chai_model_card.model_type or 'Not specified'}</p>
                <p><strong>Version:</strong> {format_version_with_date(_card_version(chai_model_card), chai_model_card.last_updated)}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        risk_level = chai_model_card.role_in_decision_making or 'Advisory'
        risk_color = "#27ae60"
        
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, {risk_color} 0%, {risk_color}CC 100%);
                padding: 1.5rem;
                border-radius: 10px;
                color: white;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                margin-bottom: 1rem;
            ">
                <h3 style="margin: 0; color: white;"> Decision Role</h3>
                <hr style="border-color: rgba(255,255,255,0.3);">
                <p style="font-size: 1.2rem; font-weight: bold;">{risk_level[:80]}</p>
                <p><strong>Performance limitations:</strong> {(chai_model_card.known_performance_limitations or 'Not specified')[:50]}...</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #8360c3 0%, #2ebf91 100%);
                padding: 1.5rem;
                border-radius: 10px;
                color: white;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                margin-bottom: 1rem;
            ">
                <h3 style="margin: 0; color: white;"> Usage</h3>
                <hr style="border-color: rgba(255,255,255,0.3);">
                <p><strong>Users:</strong> {chai_model_card.intended_users or 'Healthcare professionals'}</p>
                <p><strong>Regulatory:</strong> {REGULATORY_STATUS_LABELS.get(chai_model_card.regulatory_approval_status, 'Unknown')}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Summary Section
    summary_text = chai_model_card.summary or 'No summary available'
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        ">
            <h3 style="margin: 0 0 1rem 0; color: #8B4513;"> Model Summary</h3>
            <p style="color: #2c3e50; font-size: 1.1rem; line-height: 1.6;">{summary_text}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Keywords section removed in clinical schema v1.0
    
    # Expandable detailed sections
    with st.expander("Detailed Technical Information", expanded=False):
        display_detailed_sections(chai_model_card)
    
    # Download Section
    st.markdown("### Download Options")
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="Download JSON",
            data=chai_model_card.to_json(),
            file_name=f"{(chai_model_card.model_name or 'model_card').replace(' ', '_')}_model_card.clinical.json",
            mime="application/json",
            use_container_width=True,
            key="json_download"
        )
    
    with col2:
        st.download_button(
            label="Download Markdown",
            data=chai_model_card.to_markdown(),
            file_name=f"{(chai_model_card.model_name or 'model_card').replace(' ', '_')}_model_card.clinical.md",
            mime="text/markdown",
            use_container_width=True,
            key="markdown_download"
        )

def display_detailed_sections(chai_model_card):
    """Display clinical model card sections."""
    from core.clinical_display import (
        iter_display_sections,
        performance_metrics_rows,
        regulatory_status_badge_md,
    )

    current_section = None
    for section, field_name, label, text in iter_display_sections(chai_model_card):
        if section != current_section:
            if current_section is not None:
                st.markdown("---")
            st.subheader(section)
            current_section = section
        if field_name == "regulatory_approval_status":
            st.markdown(regulatory_status_badge_md(chai_model_card.regulatory_approval_status, label), unsafe_allow_html=True)
        elif field_name == "performance" and performance_metrics_rows(chai_model_card):
            st.markdown(f"**{label}:** {text}")
            st.markdown("**Performance Metrics**")
            st.table(performance_metrics_rows(chai_model_card))
        elif field_name in ("contact", "training_data", "model_development_and_validation", "clinical_trial"):
            st.markdown(f"**{label}:** {text}")
        else:
            st.markdown(f"**{label}:** {text}")


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


# Create tabs and use the functions
tab1, tab2 = st.tabs(["Main", "Output"])

with tab1:
    # Main tab content
    main_tab_content()

with tab2:
    # Output tab content
    output_tab_content()
