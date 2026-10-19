"""Look and feel for the Streamlit app (Figma "Medical AI Model Card Website" design).

Everything is injected once per run via ``THEME_CSS``; markup helpers emit ``mc-`` classes.
Streamlit widgets are targeted through their ``key`` (rendered as an ``st-key-<key>`` class).
"""

from __future__ import annotations

import html
from typing import Tuple

from core.dermauto_card_render import plain_preview, truncate

INK = "#1f1f1f"
MUTED = "#5f5f5f"
PAGE_BG = "#fafafa"
SURFACE = "#f0f0f0"
FIELD_BG = "#ebebeb"
RULE = "#cfcfcf"

THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,700&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"] {{ background: {PAGE_BG}; color: {INK}; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, [role="dialog"] {{ font-family: 'Inter', system-ui, sans-serif; }}
header[data-testid="stHeader"] {{ background: transparent; }}
/* Clear Streamlit's fixed toolbar (3.75rem), otherwise it swallows clicks on the nav. */
.block-container {{ max-width: 1280px; padding-top: 4.25rem; }}

/* Header */
.mc-logo {{ display: flex; align-items: center; gap: 10px; text-decoration: none; color: {INK}; }}
.mc-logo img {{ width: 46px; height: 46px; flex-shrink: 0; }}
.mc-logo-text {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 700; font-size: 1.45rem; line-height: 1; white-space: nowrap; }}
[class*="st-key-mc_nav_"] button {{ background: transparent; border: none; box-shadow: none; padding: 0.35rem 0.6rem; }}
[class*="st-key-mc_nav_"] button p {{ font-weight: 700; font-size: 1.05rem; color: {INK}; }}
[class*="st-key-mc_nav_"] button:hover p {{ text-decoration: underline; text-underline-offset: 6px; }}
.st-key-mc_nav_active button p {{ text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 6px; }}
.st-key-mc_menu {{ display: flex; justify-content: flex-end; }}
.st-key-mc_menu button {{ background: transparent; border: none; }}
.st-key-mc_menu button p {{ font-size: 1.7rem; font-weight: 800; color: #8a8a8a; }}
.st-key-mc_menu button [data-testid="stIconMaterial"] {{ display: none; }}

/* Hero */
.mc-hero {{ text-align: center; padding: 3.5rem 1rem 3rem; }}
.mc-hero h1 {{ font-size: clamp(2.4rem, 6vw, 4.6rem); font-weight: 700; line-height: 1.05; letter-spacing: -0.02em;
  max-width: 820px; margin: 0 auto; padding: 0; color: {INK}; }}
.mc-hero p {{ font-size: clamp(1.1rem, 2.2vw, 1.75rem); font-weight: 300; max-width: 640px; margin: 1.4rem auto 0; line-height: 1.3; }}
.mc-hero-compact {{ padding: 2rem 1rem 2.2rem; }}
.mc-hero-compact h1 {{ font-size: clamp(2rem, 4.4vw, 3.4rem); }}
.mc-hero-compact p {{ font-size: clamp(1rem, 1.8vw, 1.35rem); margin-top: 0.9rem; }}
.mc-page-title {{ font-size: 2rem; font-weight: 700; letter-spacing: -0.01em; margin: 0.5rem 0 1rem; }}
.mc-section-title {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.01em; margin: 2.4rem 0 0.6rem; }}

/* Generate page */
.st-key-mc_gen_form {{ background: {SURFACE}; border-radius: 22px; padding: 2rem 2.2rem 2.2rem; }}
.mc-form-title {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 0.4rem; }}
.st-key-mc_gen_form label p {{ font-weight: 700; font-size: 1rem; }}
.st-key-mc_gen_form [data-baseweb] {{ background: {PAGE_BG} !important; border: none !important; border-radius: 999px !important; }}
.st-key-mc_gen_form input {{ background: transparent; min-height: 50px; padding-left: 1.3rem; font-size: 1rem; color: {INK}; }}
.st-key-mc_gen_form input::placeholder {{ color: #777; opacity: 1; }}
.mc-form-note {{ font-size: 0.85rem; line-height: 1.5; color: {MUTED}; margin: 0.4rem 0.2rem 0.6rem; }}
.mc-form-note b {{ color: {INK}; }}
.st-key-mc_generate button {{ min-height: 56px; }}
.st-key-mc_generate button p {{ font-size: 1.1rem; font-weight: 600; }}
.stProgress [role="progressbar"] > div > div > div {{ background: {INK}; }}

.mc-explainer {{ max-width: 1100px; margin: 3.4rem auto 0; }}
.mc-explainer-title {{ text-align: center; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 1.4rem; }}
.mc-steps {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
.mc-step {{ background: {SURFACE}; border-radius: 14px; padding: 1.3rem 1.3rem 1.4rem; }}
.mc-step-num {{ width: 32px; height: 32px; border-radius: 50%; background: {INK}; color: #fff; display: flex;
  align-items: center; justify-content: center; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.9rem; }}
.mc-step-title {{ font-weight: 700; font-size: 1.1rem; margin-bottom: 0.35rem; }}
.mc-step-desc {{ font-size: 0.88rem; line-height: 1.45; color: #3a3a3a; }}
.mc-gets {{ margin-top: 1.6rem; text-align: center; }}
.mc-gets-title {{ font-weight: 700; font-size: 1rem; margin-bottom: 0.7rem; }}
.mc-gets .mc-tags {{ justify-content: center; }}
.mc-gets .mc-tag {{ font-size: 0.85rem; padding: 4px 14px; }}
.mc-gets-note {{ font-size: 0.85rem; color: {MUTED}; margin-top: 0.9rem; }}

.mc-stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
.mc-stat {{ background: {SURFACE}; border-radius: 14px; padding: 1.2rem 1.4rem; }}
.mc-stat-num {{ font-size: 2.6rem; font-weight: 800; line-height: 1.1; }}
.mc-stat-lbl {{ font-size: 0.9rem; color: #3a3a3a; margin-top: 0.2rem; }}
.st-key-mc_card_generated_preview {{ padding: 2rem 2.2rem; }}

/* Search row */
.st-key-mc_search [data-baseweb], .st-key-mc_sort [data-baseweb="select"] > div {{
  background: {FIELD_BG} !important; border: none !important; border-radius: 999px !important; min-height: 54px; }}
.st-key-mc_search input {{ background: transparent; color: {INK}; padding-left: 1.6rem; font-size: 1.1rem; }}
.st-key-mc_search input::placeholder {{ color: #555; opacity: 1; }}
.st-key-mc_sort [data-baseweb="select"] > div {{ padding-left: 1.2rem; font-size: 1.1rem; }}
.st-key-mc_filters button {{ background: {FIELD_BG}; border: none; border-radius: 999px; min-height: 54px; width: 100%; }}
.st-key-mc_filters button p {{ font-size: 1.1rem; }}

/* Form fields on the Generate page */
.stTextInput input {{ border-radius: 12px; }}
.stButton button[kind="primary"] {{ background: {INK}; border-color: {INK}; border-radius: 999px; font-weight: 600; }}
.stDownloadButton button {{ border-radius: 999px; }}
[data-testid="stExpander"] details {{ background: {SURFACE}; border: none; border-radius: 12px; }}

/* Gallery cards */
[class*="st-key-mc_card_"] {{ background: {SURFACE}; border: none !important; border-radius: 14px; padding: 1.4rem 1.6rem 1rem; }}
.mc-card-title {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -0.01em; line-height: 1.1; margin: 0; }}
.mc-card-dev {{ font-size: 0.82rem; color: #3a3a3a; margin: 0.45rem 0 0.7rem; }}
.mc-card-desc {{ font-size: 0.82rem; line-height: 1.45; margin: 1.6rem 0 1.6rem; min-height: 4.4em; }}
.mc-card-foot {{ font-size: 0.82rem; line-height: 1.4; color: #3a3a3a; }}
.mc-card-foot span {{ display: block !important; white-space: nowrap !important; overflow: hidden; text-overflow: ellipsis; }}
.mc-card-dev {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.8em; }}
[class*="st-key-mc_learn_"] {{ display: flex; justify-content: flex-end; }}
[class*="st-key-mc_learn_"] button {{ background: transparent; border: none; padding: 0; min-height: 0; }}
[class*="st-key-mc_learn_"] button p {{ font-size: 0.82rem; color: #3a3a3a; white-space: nowrap; overflow: visible; text-overflow: clip; }}
[class*="st-key-mc_learn_"] button:hover p {{ text-decoration: underline; }}
.mc-empty {{ text-align: center; color: {MUTED}; padding: 3rem 0; }}

/* Tags */
.mc-tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.mc-tag {{ background: #333; color: #fff; border-radius: 999px; padding: 2px 11px; font-size: 0.78rem; font-weight: 500; white-space: nowrap; }}

/* Detail modal */
div[role="dialog"] {{ background: {SURFACE}; border-radius: 22px; }}
.mc-detail {{ color: {INK}; }}
.mc-detail a {{ color: #0b57d0; }}
.mc-detail-head {{ display: flex; gap: 22px; align-items: flex-start; }}
.mc-detail-id {{ flex: 1; min-width: 0; }}
.mc-detail-title {{ font-size: 2.3rem; font-weight: 700; letter-spacing: -0.01em; line-height: 1.1; margin-bottom: 10px; }}
.mc-detail-title a {{ color: {INK} !important; text-decoration: none !important; }}
.mc-detail-title a::after {{ content: " ›"; color: #9a9a9a; font-weight: 400; }}
.mc-meta {{ font-size: 0.88rem; line-height: 1.5; margin-top: 14px; color: #3a3a3a; overflow-wrap: anywhere; }}
.mc-meta a {{ color: #3a3a3a !important; text-decoration: none; }}
.mc-detail-side {{ text-align: right; font-size: 0.88rem; line-height: 1.5; margin-top: 4.4rem; white-space: nowrap; }}
.mc-summary-title {{ font-weight: 700; font-size: 1.1rem; margin: 2.2rem 0 0.4rem; }}
.mc-summary {{ font-size: 1.08rem; line-height: 1.4; }}
.mc-rows {{ margin-top: 1.8rem; border-top: 1px solid {RULE}; }}
.mc-group {{ border-bottom: 1px solid {RULE}; padding: 0.2rem 0 0.4rem; }}
.mc-group-title {{ font-weight: 700; font-size: 1.12rem; padding: 0.85rem 0 0.25rem; }}
.mc-row {{ margin-left: 1.6rem; border-top: 1px solid {RULE}; }}
.mc-group-title + .mc-row {{ border-top: none; }}
.mc-row > summary, .mc-row-static {{ display: flex; align-items: center; gap: 16px; padding: 0.8rem 0.4rem; }}
.mc-row > summary {{ list-style: none; cursor: pointer; }}
.mc-row > summary::-webkit-details-marker {{ display: none; }}
.mc-row-label {{ font-weight: 700; font-size: 1.05rem; flex-shrink: 0; }}
.mc-row-value {{ margin-left: auto; text-align: right; font-size: 1.05rem; }}
.mc-row-hint {{ margin-left: auto; color: {MUTED}; font-size: 0.95rem; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; min-width: 0; max-width: 45%; }}
.mc-row[open] .mc-row-hint {{ visibility: hidden; }}
.mc-chev {{ width: 9px; height: 9px; border-right: 2.5px solid {INK}; border-bottom: 2.5px solid {INK};
  transform: rotate(45deg); margin: -4px 4px 0 0; flex-shrink: 0; transition: transform 0.15s; }}
.mc-row[open] .mc-chev {{ transform: rotate(-135deg); margin-top: 4px; }}
.mc-row-body {{ padding: 0 0.4rem 1rem; font-size: 1rem; line-height: 1.5; }}
.mc-muted {{ color: {MUTED}; }}
.mc-metrics {{ margin-top: 0.8rem; overflow-x: auto; }}
.mc-ref {{ font-size: 0.85rem; margin: 4px 0; overflow-wrap: anywhere; }}
.mc-ref span {{ font-weight: 700; }}
.mc-foot {{ font-size: 0.9rem; line-height: 1.45; margin-top: 2.6rem; }}
.mc-warn {{ color: #8b4513; font-weight: 600; margin-top: 1rem; }}

@media (max-width: 900px) {{
  .mc-steps, .mc-stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
@media (max-width: 720px) {{
  .st-key-mc_gen_form {{ padding: 1.4rem 1.2rem; }}
  .mc-detail-head {{ flex-wrap: wrap; }}
  .mc-detail-side {{ margin-top: 0; text-align: left; }}
  .mc-row {{ margin-left: 0.4rem; }}
}}
</style>
"""

# st.html sanitizes inline <svg>, so the mark ships as a data URI.
_LOGO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'>"
    "<rect width='40' height='40' rx='6' fill='%23111'/>"
    "<g fill='%23fff'><circle cx='14.5' cy='14.5' r='7'/><circle cx='25.5' cy='14.5' r='7'/>"
    "<circle cx='14.5' cy='25.5' r='7'/><circle cx='25.5' cy='25.5' r='7'/></g>"
    "<circle cx='20' cy='20' r='2.2' fill='%23111'/></svg>"
)
LOGO_HTML = f"""
<div class="mc-logo">
  <img src="data:image/svg+xml;utf8,{_LOGO_SVG}" alt="" />
  <div class="mc-logo-text">DermAUTO-CARD</div>
</div>
"""


def hero_html(title: str, subtitle: str, *, compact: bool = False) -> str:
    cls = "mc-hero mc-hero-compact" if compact else "mc-hero"
    return f'<div class="{cls}"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>'


GENERATE_STEPS: Tuple[Tuple[str, str], ...] = (
    ("Find Information", "Search research papers, GitHub repositories, and documentation"),
    ("Extract Details", "Pull out technical specs, performance metrics, and usage info"),
    ("AI Analysis", "Use advanced AI to analyze bias, risks, and clinical considerations"),
    ("Generate Card", "Create a professional model card meeting medical AI standards"),
)
GENERATE_DELIVERABLES: Tuple[str, ...] = (
    "Complete technical documentation",
    "Bias and fairness analysis",
    "Clinical risk assessment",
    "Regulatory compliance information",
    "Ready-to-use model card in multiple formats (JSON, Markdown, XML)",
)


def generate_explainer_html() -> str:
    """"What happens when you click Generate" as numbered step tiles plus a deliverables row."""
    steps = "".join(
        f'<div class="mc-step"><div class="mc-step-num">{i}</div>'
        f'<div class="mc-step-title">{html.escape(title)}</div><div class="mc-step-desc">{html.escape(desc)}</div></div>'
        for i, (title, desc) in enumerate(GENERATE_STEPS, 1)
    )
    return (
        '<div class="mc-explainer">'
        "<div class=\"mc-explainer-title\">What happens when you click 'Generate Model Card'?</div>"
        f'<div class="mc-steps">{steps}</div>'
        '<div class="mc-gets"><div class="mc-gets-title">You Get</div>'
        f"{tags_html(GENERATE_DELIVERABLES)}"
        '<div class="mc-gets-note"><b>Enhanced Discovery:</b> Uses advanced AI to analyze discovered sources '
        "for comprehensive model documentation.</div></div></div>"
    )


def stat_tiles_html(stats: Tuple[Tuple[str, int], ...]) -> str:
    tiles = "".join(
        f'<div class="mc-stat"><div class="mc-stat-num">{value}</div><div class="mc-stat-lbl">{html.escape(label)}</div></div>'
        for label, value in stats
    )
    return f'<div class="mc-stats">{tiles}</div>'


def tags_html(tags: Tuple[str, ...]) -> str:
    return '<div class="mc-tags">' + "".join(f'<span class="mc-tag">{html.escape(t)}</span>' for t in tags) + "</div>"


def gallery_card_html(card, *, tags: Tuple[str, ...]) -> str:
    """Top of one gallery tile (title, developer, tags, summary)."""
    developer = truncate(plain_preview(card.developer or "") or "Not disclosed", 70)
    summary = truncate(plain_preview(card.summary or "") or "No summary available", 170)
    return (
        f'<div class="mc-card-title">{html.escape(truncate(card.model_name or "Unnamed Model", 28))}</div>'
        f'<div class="mc-card-dev">Developed by {html.escape(developer)}</div>'
        f"{tags_html(tags)}"
        f'<div class="mc-card-desc">{html.escape(summary)}</div>'
    )


def gallery_card_footer_html(card, citation_count: int) -> str:
    """Footer beside the tile's "Learn More" button."""
    version = plain_preview(card.version or "") or "Not disclosed"
    last_updated = card.last_updated.isoformat() if hasattr(card.last_updated, "isoformat") else (card.last_updated or "—")
    return (
        '<div class="mc-card-foot">'
        f"<span>Citations: {citation_count}</span>"
        f'<span title="{html.escape(version, quote=True)}">Version: {html.escape(version)}</span>'
        f"<span>Last Updated: {html.escape(str(last_updated))}</span>"
        "</div>"
    )
