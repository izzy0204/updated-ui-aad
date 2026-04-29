import html
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote as url_quote

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = REPO_ROOT / "outputs"

# Full card: wider wrap; inline styles for Streamlit HTML rendering.
_WRAP = (
    "max-width:min(100%,920px);margin:0 auto;background:#ffffff;color:#111111;"
    "border:3px solid #111111;padding:16px 18px 14px 18px;"
    "font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "box-sizing:border-box;"
)
_DOC_TITLE = "font-weight:900;font-size:28px;line-height:1.15;margin:0 0 12px 0;letter-spacing:-0.02em;"
_TITLE = "font-weight:900;font-size:32px;line-height:1;margin:0;letter-spacing:-0.02em;"
_SUB = "font-size:13px;margin:6px 0 12px 0;line-height:1.35;"
_RULE_THICK = "border-top:10px solid #111111;margin:10px 0 8px 0;width:100%;"
_RULE_MED = "border-top:5px solid #111111;margin:12px 0 8px 0;width:100%;"
_RULE_THIN = "border-top:1px solid #111111;margin:6px 0;width:100%;"
_SECTION = "font-weight:800;font-size:15px;margin:0;padding:6px 0 4px 0;line-height:1.25;"
_ROW = "border-top:1px solid #111111;padding:10px 0;"
_LBL = "font-weight:800;font-size:13px;margin:0 0 6px 0;"
_VAL = "font-weight:600;font-size:13px;line-height:1.5;color:#222222;margin:0;word-wrap:break-word;"
_FOOT = "font-size:11px;margin-top:14px;line-height:1.4;color:#444444;"
_MONO = "font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px;"
_REF_ROW = "font-size:12px;margin:5px 0;line-height:1.4;"

_CITATION_IN_TEXT = re.compile(r"\[(\s*\d+(?:\s*,\s*\d+)*\s*)\]")
_GEN_FOOTER = re.compile(r"^\s*\*?\s*Generated on\s+.+", re.IGNORECASE)


def _href(url: str) -> str:
    return url_quote(url.strip(), safe="/:?#[]@!$&'()*+,;=-._~%")


def _strip_citations(text: str) -> str:
    return re.sub(r"\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text).strip()


def _parse_references(md_text: str) -> Dict[int, str]:
    refs: Dict[int, str] = {}
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().lower() == "## references":
            i += 1
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped.startswith("## ") and "reference" not in stripped.lower():
                    break
                if stripped == "---":
                    break
                m = re.match(r"^\s*\[(\d+)\]\s+(.+)$", line)
                if m:
                    num = int(m.group(1))
                    url = m.group(2).strip()
                    refs[num] = url
                i += 1
            break
        i += 1
    return refs


def _extract_doc_title(md_text: str) -> Optional[str]:
    for raw in md_text.splitlines():
        line = raw.strip()
        if line.startswith("# ") and not line.startswith("##"):
            return line[2:].strip()
        if line:
            break
    return None


def _extract_generated_line(md_text: str) -> Optional[str]:
    for raw in md_text.splitlines():
        s = raw.strip()
        if _GEN_FOOTER.match(s) or (s.startswith("*") and "generated on" in s.lower()):
            return s.strip("*").strip()
    return None


def _linkify_citations(escaped_text: str, refs: Dict[int, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        raw_nums = [x.strip() for x in inner.split(",") if x.strip()]
        nums: List[int] = []
        for x in raw_nums:
            if x.isdigit():
                nums.append(int(x))
        if not nums:
            return match.group(0)

        pieces: List[str] = []
        for j, n in enumerate(nums):
            if j:
                pieces.append('<span style="color:#111;">,</span>')
            url = refs.get(n)
            if url:
                safe_url = html.escape(_href(url), quote=True)
                pieces.append(
                    f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
                    f'title="Source [{n}]" '
                    'style="color:#0b57d0;font-weight:700;text-decoration:underline;">'
                    f"{n}</a>"
                )
            else:
                pieces.append(f'<span style="color:#666;font-weight:600;" title="No URL for [{n}]">{n}</span>')
        inner_html = "".join(pieces)
        return (
            f'<sup style="font-size:0.72em;white-space:nowrap;line-height:1;">'
            f'<span style="color:#111;">[</span>{inner_html}<span style="color:#111;">]</span>'
            f"</sup>"
        )

    return _CITATION_IN_TEXT.sub(repl, escaped_text)


def _format_field(text: str, refs: Dict[int, str], hide_citations: bool) -> str:
    if hide_citations:
        return html.escape(_strip_citations(text))
    base = html.escape(text)
    return _linkify_citations(base, refs)


def _parse_model_card_md(md_text: str) -> Dict[str, Dict[str, str]]:
    sections: Dict[str, Dict[str, str]] = {}
    current_section = "Unsectioned"
    sections[current_section] = {}
    # Last `##` title — each `###` is `## title — ### title` (do not chain ###).
    last_h2_section = current_section

    field_re = re.compile(
        r"^\s*-\s+\*\*(?:(?P<a>.+?):\*\*|(?P<b>.+?)\*\*:)\s*(?P<val>.*)\s*$"
    )
    heading2_re = re.compile(r"^\s*##\s+(.*)\s*$")
    heading3_re = re.compile(r"^\s*###\s+(.*)\s*$")

    last_key: Optional[Tuple[str, str]] = None

    for raw in md_text.splitlines():
        line = raw.rstrip()

        m2 = heading2_re.match(line)
        if m2:
            current_section = m2.group(1).strip()
            last_h2_section = current_section
            sections.setdefault(current_section, {})
            last_key = None
            continue

        m3 = heading3_re.match(line)
        if m3:
            current_section = f"{last_h2_section} — {m3.group(1).strip()}"
            sections.setdefault(current_section, {})
            last_key = None
            continue

        fm = field_re.match(line)
        if fm:
            field = (fm.group("a") or fm.group("b") or "").strip()
            value = (fm.group("val") or "").strip()
            sections[current_section][field] = value
            last_key = (current_section, field)
            continue

        if last_key and (line.startswith("  ") or line.startswith("\t")) and line.strip():
            sec, field = last_key
            prev = sections[sec].get(field, "")
            joiner = " " if prev else ""
            sections[sec][field] = f"{prev}{joiner}{line.strip()}"
            continue

    return sections


def _block_rich(label: str, value_html: str) -> str:
    return (
        f'<div style="{_ROW}">'
        f'<div style="{_LBL}">{html.escape(label)}</div>'
        f'<div style="{_VAL}">{value_html}</div>'
        "</div>"
    )


def _section(title: str) -> str:
    return (
        f'<div style="{_RULE_THICK}"></div>'
        f'<div style="{_SECTION}">{html.escape(title)}</div>'
        f'<div style="{_RULE_THIN}"></div>'
    )


def _references_block(refs: Dict[int, str]) -> str:
    if not refs:
        return ""
    rows: List[str] = []
    for n in sorted(refs.keys()):
        u = refs[n]
        safe_href = html.escape(_href(u), quote=True)
        rows.append(
            f'<div style="{_REF_ROW}">'
            f'<span style="font-weight:800;">[{n}]</span> '
            f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" '
            'style="color:#0b57d0;font-weight:600;word-break:break-all;text-decoration:underline;">'
            f"{html.escape(u)}"
            f"</a>"
            f"</div>"
        )
    return (
        f'<div style="{_RULE_MED}"></div>'
        f'<div style="{_SECTION}">References</div>'
        f'<div style="{_RULE_THIN}"></div>'
        f'{"".join(rows)}'
    )


def _render_full_card_html(
    *,
    sections: Dict[str, Dict[str, str]],
    refs: Dict[int, str],
    doc_title: Optional[str],
    source_label: str,
    hide_citations: bool,
    generated_footer: Optional[str],
) -> str:
    fmt = lambda t: _format_field(t, refs, hide_citations)
    parts: List[str] = [
        f'<div style="{_WRAP}">',
        f'<div style="{_TITLE}">AI Model Card</div>',
        f'<div style="{_SUB}">Source · <span style="{_MONO}">{html.escape(source_label)}</span></div>',
    ]
    if doc_title:
        parts.append(f'<div style="{_DOC_TITLE}">{html.escape(doc_title)}</div>')
    parts.append(f'<div style="{_RULE_THICK}"></div>')

    refs_heading_only = "references"
    for sec_name, fields in sections.items():
        if sec_name == "Unsectioned" and not fields:
            continue
        # Reference lines are [n] URL; parsed separately — skip empty shell
        if sec_name.strip().lower() == refs_heading_only and not fields:
            continue
        if not fields:
            continue

        parts.append(_section(sec_name))
        for field_name, value in fields.items():
            parts.append(_block_rich(field_name, fmt(value)))

    ref_html = _references_block(refs)
    if ref_html:
        parts.append(ref_html)

    if generated_footer:
        parts.append(f'<div style="{_FOOT}">{html.escape(generated_footer)}</div>')
    parts.append(
        f'<div style="{_FOOT}">'
        "Citation markers link to numbered URLs when shown. "
        "Content is rendered from the markdown model card file."
        "</div>"
    )
    parts.append("</div>")
    return "\n".join(parts)


st.set_page_config(page_title="DermAUTO-CARD", layout="wide")

st.title("DermAUTO-CARD")
st.caption("Full CHAI model card from markdown: every section and field, with citations linked to **References**.")

with st.sidebar:
    st.subheader("Source")

    md_files: List[Path] = []
    if OUTPUTS_DIR.exists():
        md_files = sorted(OUTPUTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    default_name = "dermgpt-20260429-173126.md"
    default_idx = next((i for i, p in enumerate(md_files) if p.name == default_name), 0)

    selected_path: Optional[Path] = None
    if md_files:
        selected = st.selectbox(
            "Select an output markdown file",
            options=md_files,
            index=min(default_idx, len(md_files) - 1),
            format_func=lambda p: p.name,
        )
        selected_path = Path(selected)
    else:
        st.info("No `outputs/*.md` files found.")

    uploaded = st.file_uploader("Or upload a markdown file", type=["md"])

    st.subheader("Display")
    hide_citations = st.checkbox("Hide citation markers", value=False)
    show_raw = st.checkbox("Show raw markdown preview", value=False)

if uploaded is not None:
    md_text = uploaded.read().decode("utf-8", errors="replace")
    source_label = uploaded.name
elif selected_path and selected_path.exists():
    md_text = selected_path.read_text(encoding="utf-8", errors="replace")
    source_label = selected_path.name
else:
    md_text = ""
    source_label = "No file selected"

if not md_text.strip():
    st.warning("Pick or upload a markdown file to render.")
    st.stop()

ref_map = _parse_references(md_text)
sections = _parse_model_card_md(md_text)
doc_title = _extract_doc_title(md_text)
generated_line = _extract_generated_line(md_text)

card_html = _render_full_card_html(
    sections=sections,
    refs=ref_map,
    doc_title=doc_title,
    source_label=source_label,
    hide_citations=hide_citations,
    generated_footer=generated_line,
)

if hasattr(st, "html"):
    st.html(card_html)
else:
    st.markdown(card_html, unsafe_allow_html=True)

if show_raw:
    with st.expander("Raw markdown", expanded=False):
        st.markdown(md_text)
