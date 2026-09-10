"""Conservative sentence counting for clinical model card validation."""

from __future__ import annotations

import re
from typing import List

# Placeholders for protected spans during sentence splitting.
_PLACEHOLDER_PREFIX = "\x00SENT"
_PLACEHOLDER_SUFFIX = "\x00"

# Abbreviations where a following capital is often a real new sentence (e.g. "U.S. Then…").
_BOUNDARY_ABBREV_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bU\.S\.", re.I),
    re.compile(r"\be\.g\.", re.I),
    re.compile(r"\bet al\.", re.I),
    re.compile(r"\bvs\.", re.I),
    re.compile(r"\betc\.", re.I),
]

# Honorifics / titles: never treat the period as a sentence boundary ("Dr. Faranak…").
_TITLE_ABBREV_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bDr\.", re.I),
    re.compile(r"\bMr\.", re.I),
    re.compile(r"\bMrs\.", re.I),
    re.compile(r"\bMs\.", re.I),
    re.compile(r"\bProf\.", re.I),
]

_OTHER_PROTECTED_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\d+\.\d+%"),  # e.g. 95.5%
    re.compile(r"\d+\.\d+"),  # decimal values
    re.compile(r"https?://[^\s]+", re.I),
    re.compile(r"\b[A-Z]{2,}\b"),  # abbreviations like CNN, FDA
]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def _protect_spans(text: str) -> tuple[str, List[str], List[bool]]:
    protected: List[str] = []
    had_suffix: List[bool] = []
    out = text

    def _repl(m: re.Match[str], *, keep_boundary: bool) -> str:
        idx = len(protected)
        val = m.group(0)
        protected.append(val)
        # For U.S./e.g./etc., re-add a period so a following capital can still end a sentence.
        # Do not do this for Dr./Mr./… or the honorific becomes "Dr.." and falsely splits.
        # val already ends with "." for every boundary-abbrev match, so this suffix is only
        # a marker for the split regex and must be dropped (not duplicated) on restore.
        suffix = "." if keep_boundary and val.rstrip().endswith(".") else ""
        had_suffix.append(bool(suffix))
        return f"{_PLACEHOLDER_PREFIX}{idx}{_PLACEHOLDER_SUFFIX}{suffix}"

    for pat in _TITLE_ABBREV_PATTERNS:
        out = pat.sub(lambda m: _repl(m, keep_boundary=False), out)
    for pat in _BOUNDARY_ABBREV_PATTERNS:
        out = pat.sub(lambda m: _repl(m, keep_boundary=True), out)
    for pat in _OTHER_PROTECTED_PATTERNS:
        out = pat.sub(lambda m: _repl(m, keep_boundary=False), out)
    return out, protected, had_suffix


def _restore_spans(text: str, protected: List[str], had_suffix: List[bool]) -> str:
    out = text
    for i, val in enumerate(protected):
        placeholder = f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}"
        if had_suffix[i]:
            # Consume the marker period along with the placeholder; val already ends in ".".
            out = out.replace(f"{placeholder}.", val)
        out = out.replace(placeholder, val)
    return out


def split_sentences(text: str) -> List[str]:
    """Split text into sentences with conservative abbreviation/URL handling."""
    raw = (text or "").strip()
    if not raw:
        return []

    protected_text, protected, had_suffix = _protect_spans(raw)
    parts = _SENTENCE_END.split(protected_text)
    sentences: List[str] = []
    for part in parts:
        s = _restore_spans(part.strip(), protected, had_suffix)
        if s:
            sentences.append(s)
    if not sentences and raw:
        sentences = [raw]
    return sentences


def count_sentences(text: str) -> int:
    return len(split_sentences(text))
