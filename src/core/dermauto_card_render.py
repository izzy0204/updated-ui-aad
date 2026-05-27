"""Parse CHAI markdown model cards and render HTML for the DermAUTO-CARD Streamlit page."""

from __future__ import annotations

import html
import re
from typing import Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import quote as url_quote

# Full card: wider wrap; inline styles for Streamlit HTML rendering.
WRAP = (
    "max-width:min(100%,920px);margin:0 auto;background:#ffffff;color:#111111;"
    "border:3px solid #111111;padding:16px 18px 14px 18px;"
    "font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "box-sizing:border-box;"
)
DOC_TITLE = "font-weight:900;font-size:28px;line-height:1.15;margin:0 0 12px 0;letter-spacing:-0.02em;"
TITLE = "font-weight:900;font-size:32px;line-height:1;margin:0;letter-spacing:-0.02em;"
SUB = "font-size:13px;margin:6px 0 12px 0;line-height:1.35;"
RULE_THICK = "border-top:10px solid #111111;margin:10px 0 8px 0;width:100%;"
RULE_MED = "border-top:5px solid #111111;margin:12px 0 8px 0;width:100%;"
RULE_THIN = "border-top:1px solid #111111;margin:6px 0;width:100%;"
SECTION = "font-weight:800;font-size:15px;margin:0;padding:6px 0 4px 0;line-height:1.25;"
ROW = "border-top:1px solid #111111;padding:10px 0;"
LBL = "font-weight:800;font-size:13px;margin:0 0 6px 0;"
VAL = "font-weight:600;font-size:13px;line-height:1.5;color:#222222;margin:0;word-wrap:break-word;"
FOOT = "font-size:11px;margin-top:14px;line-height:1.4;color:#444444;"
MONO = "font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px;"
REF_ROW = "font-size:12px;margin:5px 0;line-height:1.4;"

# Pastel regulatory-status row styles (background + left accent); dark text remains readable.
REGULATORY_ROW_STYLE: Dict[str, Tuple[str, str]] = {
    "red": ("#fde8e8", "#c1121f"),
    "orange": ("#ffe5d0", "#e85d04"),
    "yellow": ("#fff9e6", "#d4a017"),
    "green": ("#d8f3dc", "#2d6a4f"),
    "blue": ("#d9e8ff", "#1e6091"),
    "gray": ("#f0f0f0", "#6c757d"),
}

REGULATORY_LEGEND: Tuple[Tuple[str, str], ...] = (
    ("red", "Not Authorized / Consumer Tool"),
    ("orange", "Investigational / Research Use Only"),
    ("yellow", "EUA Authorized"),
    ("green", "FDA Approved or FDA Cleared"),
    ("blue", "CE Marked (authorized in Europe)"),
    ("gray", "Regulatory Status Unknown"),
)

# Backward-compatible alias for any external imports.
PROVENANCE_ROW_STYLE = REGULATORY_ROW_STYLE

CITATION_IN_TEXT = re.compile(r"\[(\s*\d+(?:\s*,\s*\d+)*\s*)\]")
SECTIONLIKE_H1 = re.compile(r"^\s*#\s+\*{0,2}\s*\d+\s*\\?[.)]\s+.+", re.IGNORECASE)
HEADING_BOLD_WRAPPER = re.compile(r"^\s*(\*{1,2})(.+?)\1\s*$")
MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
URL = re.compile(r"(https?://[^\s<>()]+)")
# After markdown links become <a>...</a>, avoid wrapping the same URL again (nested/broken anchors).
_ANCHOR_BLOCKS = re.compile(r"(<a\b[^>]*>.*?</a>)", re.IGNORECASE | re.DOTALL)


def composite_section_field_key(section_name: str, field_name: str) -> str:
    return f"{section_name}|||{field_name}"


def href(url: str) -> str:
    return url_quote(url.strip(), safe="/:?#[]@!$&'()*+,;=-._~%")


def strip_citations(text: str) -> str:
    return re.sub(r"\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text).strip()


def strip_citations_immediately_after_dr(text: str) -> str:
    return re.sub(
        r"(Dr\.)\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\]",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )


def unwrap_latex_inline_delimiters(text: str) -> str:
    return re.sub(r"\\\(([^\\]*?)\\\)", r"(\1)", text)


def normalize_md_for_parsing(md_text: str) -> str:
    md_text = md_text.replace("\\[", "[").replace("\\]", "]")

    out_lines: List[str] = []
    for raw in md_text.splitlines():
        line = raw.rstrip("\n")

        if SECTIONLIKE_H1.match(line):
            h = line.lstrip()[2:].strip()
            m = HEADING_BOLD_WRAPPER.match(h)
            if m:
                h = m.group(2).strip()
            out_lines.append(f"## {h}")
            continue

        if re.match(r"^\s*\*\s+\*\*", line):
            out_lines.append(re.sub(r"^(\s*)\*\s+", r"\1- ", line, count=1))
            continue

        out_lines.append(line)

    return "\n".join(out_lines)


_REF_LINE_MARKDOWN_URL = re.compile(
    r"^\s*\[([^\]]*)\]\((https?://[^)]+)\)\s*$",
)


def normalize_reference_url_value(raw: str) -> str:
    """Turn `[text](https://...)` reference lines into a bare URL for citation hrefs."""
    t = raw.strip()
    m = _REF_LINE_MARKDOWN_URL.match(t)
    if m:
        return m.group(2).strip()
    return t


def parse_references(md_text: str, *, allow_sources_heading: bool = False) -> Dict[int, str]:
    refs: Dict[int, str] = {}
    lines = md_text.splitlines()
    i = 0
    heading_markers = {"## references"}
    if allow_sources_heading:
        heading_markers |= {"## sources", "## source", "## refs", "## citations"}

    while i < len(lines):
        if lines[i].strip().lower() in heading_markers:
            i += 1
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if stripped.startswith("## "):
                    nxt = stripped.lower()
                    if ("reference" in nxt) or (
                        allow_sources_heading and ("source" in nxt or "citation" in nxt or "ref" in nxt)
                    ):
                        pass
                    else:
                        break
                if stripped == "---":
                    break
                m = re.match(r"^\s*\[(\d+)\]\s+(.+)$", line)
                if m:
                    num = int(m.group(1))
                    url = normalize_reference_url_value(m.group(2).strip())
                    refs[num] = url
                i += 1
            break
        i += 1
    return refs


def extract_doc_title(md_text: str) -> Optional[str]:
    for raw in md_text.splitlines():
        line = raw.strip()
        if line.startswith("# ") and not line.startswith("##"):
            return line[2:].strip()
        if line:
            break
    return None


def strip_chai_model_card_suffix(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    t = re.sub(r"\s*[—–-]\s*CHAI Model Card\s*$", "", title.strip(), flags=re.IGNORECASE).strip()
    return t or None


def body_before_references(md_text: str, *, allow_sources_heading: bool) -> str:
    lines = md_text.splitlines()
    heading_markers = {"## references"}
    if allow_sources_heading:
        heading_markers |= {"## sources", "## source", "## refs", "## citations"}
    for i, line in enumerate(lines):
        if line.strip().lower() in heading_markers:
            return "\n".join(lines[:i])
    return md_text


def collect_citation_numbers_in_order(body_md: str) -> List[int]:
    seen: List[int] = []
    seen_set: Set[int] = set()
    for m in CITATION_IN_TEXT.finditer(body_md):
        inner = m.group(1)
        for x in inner.split(","):
            xs = x.strip()
            if xs.isdigit():
                n = int(xs)
                if n not in seen_set:
                    seen_set.add(n)
                    seen.append(n)
    return seen


def build_ref_renumbering(body_md: str, ref_map: Dict[int, str]) -> Tuple[Dict[int, int], Dict[int, str]]:
    if not ref_map:
        return {}, {}

    ordered_old: List[int] = []
    used: Set[int] = set()
    for n in collect_citation_numbers_in_order(body_md):
        if n not in used:
            ordered_old.append(n)
            used.add(n)
    for k in sorted(ref_map.keys()):
        if k not in used:
            ordered_old.append(k)
            used.add(k)

    old_to_new = {old: i + 1 for i, old in enumerate(ordered_old)}
    new_ref_map = {old_to_new[old]: ref_map[old] for old in ordered_old if old in ref_map}
    return old_to_new, new_ref_map


def rewrite_citation_markers(text: str, old_to_new: Dict[int, int]) -> str:
    if not old_to_new:
        return text

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        parts_out: List[str] = []
        for x in inner.split(","):
            xs = x.strip()
            if xs.isdigit():
                n = int(xs)
                parts_out.append(str(old_to_new.get(n, n)))
            elif xs:
                parts_out.append(xs)
        return "[" + ", ".join(parts_out) + "]"

    return CITATION_IN_TEXT.sub(repl, text)


def rewrite_sections_citations(
    sections: Dict[str, Dict[str, str]], old_to_new: Dict[int, int]
) -> Dict[str, Dict[str, str]]:
    if not old_to_new:
        return sections
    out: Dict[str, Dict[str, str]] = {}
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            out[sec_name] = dict(fields)
            continue
        out[sec_name] = {k: rewrite_citation_markers(v, old_to_new) for k, v in fields.items()}
    return out


def linkify_citations(escaped_text: str, refs: Dict[int, str]) -> str:
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
                safe_url = html.escape(href(url), quote=True)
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

    return CITATION_IN_TEXT.sub(repl, escaped_text)


def linkify_urls(escaped_text: str) -> str:
    escaped_text = MD_LINK.sub(
        lambda m: (
            f'<a href="{html.escape(href(m.group(2)), quote=True)}" target="_blank" rel="noopener noreferrer" '
            'style="color:#0b57d0;font-weight:700;text-decoration:underline;">'
            f"{html.escape(m.group(1))}</a>"
        ),
        escaped_text,
    )

    def _url_anchor(m: re.Match[str]) -> str:
        return (
            f'<a href="{html.escape(href(m.group(1)), quote=True)}" target="_blank" rel="noopener noreferrer" '
            'style="color:#0b57d0;font-weight:700;word-break:break-all;text-decoration:underline;">'
            f"{m.group(1)}</a>"
        )

    parts: List[str] = []
    for chunk in _ANCHOR_BLOCKS.split(escaped_text):
        if chunk.lstrip().lower().startswith("<a"):
            parts.append(chunk)
        else:
            parts.append(URL.sub(_url_anchor, chunk))
    return "".join(parts)


def format_field(text: str, refs: Dict[int, str], hide_citations: bool, *, linkify_urls_flag: bool = False) -> str:
    text = strip_citations_immediately_after_dr(text)
    text = unwrap_latex_inline_delimiters(text)
    if hide_citations:
        base = html.escape(strip_citations(text))
        return linkify_urls(base) if linkify_urls_flag else base

    base = html.escape(text)
    if linkify_urls_flag:
        base = linkify_urls(base)
    return linkify_citations(base, refs)


def parse_model_card_md(md_text: str) -> Dict[str, Dict[str, str]]:
    sections: Dict[str, Dict[str, str]] = {}
    current_section = "Unsectioned"
    sections[current_section] = {}
    last_h2_section = current_section

    field_re = re.compile(r"^\s*[-*]\s+\*\*(?:(?P<a>.+?):\*\*|(?P<b>.+?)\*\*:)\s*(?P<val>.*)\s*$")
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


def regulatory_legend_html() -> str:
    parts: List[str] = []
    for tier, label in REGULATORY_LEGEND:
        bg, accent = REGULATORY_ROW_STYLE[tier]
        parts.append(
            f'<div style="display:flex;align-items:flex-start;gap:8px;margin:6px 0;font-size:13px;line-height:1.35;">'
            f'<span style="flex-shrink:0;display:inline-block;width:14px;height:14px;margin-top:2px;border-radius:3px;'
            f"background:{bg};border:2px solid {accent};\"></span>"
            f"<span>{html.escape(label)}</span></div>"
        )
    return "".join(parts)


def block_rich(label: str, value_html: str, *, regulatory_tier: Optional[str] = None, provenance_tier: Optional[str] = None) -> str:
    row_style = ROW
    extra = ""
    tier = regulatory_tier or provenance_tier
    if tier and tier in REGULATORY_ROW_STYLE:
        bg, accent = REGULATORY_ROW_STYLE[tier]
        extra = f"background-color:{bg};border-left:4px solid {accent};padding-left:12px;margin-left:-4px;"
    wrap = f"{row_style}{extra}"
    return (
        f'<div style="{wrap}">'
        f'<div style="{LBL}">{html.escape(label)}</div>'
        f'<div style="{VAL}">{value_html}</div>'
        "</div>"
    )


def section_html(title: str) -> str:
    return (
        f'<div style="{RULE_THICK}"></div>'
        f'<div style="{SECTION}">{html.escape(title)}</div>'
        f'<div style="{RULE_THIN}"></div>'
    )


def references_block(refs: Dict[int, str]) -> str:
    if not refs:
        return ""
    rows: List[str] = []
    for n in sorted(refs.keys()):
        u = refs[n]
        safe_href = html.escape(href(u), quote=True)
        rows.append(
            f'<div style="{REF_ROW}">'
            f'<span style="font-weight:800;">[{n}]</span> '
            f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" '
            'style="color:#0b57d0;font-weight:600;word-break:break-all;text-decoration:underline;">'
            f"{html.escape(u)}"
            f"</a>"
            f"</div>"
        )
    return (
        f'<div style="{RULE_MED}"></div>'
        f'<div style="{SECTION}">References</div>'
        f'<div style="{RULE_THIN}"></div>'
        f'{"".join(rows)}'
    )


def render_full_card_html(
    *,
    sections: Dict[str, Dict[str, str]],
    refs: Dict[int, str],
    doc_title: Optional[str],
    source_label: str,
    hide_citations: bool,
    manual_linkify: bool,
    regulatory_by_key: Optional[Dict[str, str]] = None,
    provenance_by_key: Optional[Dict[str, str]] = None,
) -> str:
    fmt: Callable[[str], str] = lambda t: format_field(t, refs, hide_citations, linkify_urls_flag=manual_linkify)
    parts: List[str] = [
        f'<div style="{WRAP}">',
        f'<div style="{TITLE}">AI Model Card</div>',
        f'<div style="{SUB}">Source · <span style="{MONO}">{html.escape(source_label)}</span></div>',
    ]
    if doc_title:
        parts.append(f'<div style="{DOC_TITLE}">{html.escape(doc_title)}</div>')
    parts.append(f'<div style="{RULE_THICK}"></div>')

    refs_heading_only = "references"
    for sec_name, fields in sections.items():
        if sec_name == "Unsectioned" and not fields:
            continue
        if sec_name.strip().lower() == refs_heading_only and not fields:
            continue
        if not fields:
            continue

        parts.append(section_html(sec_name))
        for field_name, value in fields.items():
            ck = composite_section_field_key(sec_name, field_name)
            tier: Optional[str] = None
            tier_map = regulatory_by_key if regulatory_by_key is not None else provenance_by_key
            if tier_map:
                tier = tier_map.get(ck)
            parts.append(block_rich(field_name, fmt(value), regulatory_tier=tier))

    ref_html = references_block(refs)
    if ref_html:
        parts.append(ref_html)

    parts.append(
        f'<div style="{FOOT}">Citation markers link to numbered URLs when shown.</div>'
    )
    parts.append("</div>")
    return "\n".join(parts)
