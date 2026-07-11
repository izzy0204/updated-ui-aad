"""Conservative sentence counting for clinical model card validation."""

from __future__ import annotations

import re
from typing import List

# Placeholders for protected spans during sentence splitting.
_PLACEHOLDER_PREFIX = "\x00SENT"
_PLACEHOLDER_SUFFIX = "\x00"

_PROTECTED_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bU\.S\.", re.I),
    re.compile(r"\be\.g\.", re.I),
    re.compile(r"\bet al\.", re.I),
    re.compile(r"\bDr\.", re.I),
    re.compile(r"\bvs\.", re.I),
    re.compile(r"\betc\.", re.I),
    re.compile(r"\d+\.\d+%"),  # e.g. 95.5%
    re.compile(r"\d+\.\d+"),  # decimal values
    re.compile(r"https?://[^\s]+", re.I),
    re.compile(r"\b[A-Z]{2,}\b"),  # abbreviations like CNN, FDA
]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def _protect_spans(text: str) -> tuple[str, List[str]]:
    protected: List[str] = []
    out = text

    def _repl(m: re.Match[str]) -> str:
        idx = len(protected)
        val = m.group(0)
        protected.append(val)
        # Preserve sentence boundary after abbreviations like U.S.
        suffix = "." if val.rstrip().endswith(".") else ""
        return f"{_PLACEHOLDER_PREFIX}{idx}{_PLACEHOLDER_SUFFIX}{suffix}"

    for pat in _PROTECTED_PATTERNS:
        out = pat.sub(_repl, out)
    return out, protected


def _restore_spans(text: str, protected: List[str]) -> str:
    out = text
    for i, val in enumerate(protected):
        out = out.replace(f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}", val)
    return out


def split_sentences(text: str) -> List[str]:
    """Split text into sentences with conservative abbreviation/URL handling."""
    raw = (text or "").strip()
    if not raw:
        return []

    protected_text, protected = _protect_spans(raw)
    parts = _SENTENCE_END.split(protected_text)
    sentences: List[str] = []
    for part in parts:
        s = _restore_spans(part.strip(), protected)
        if s:
            sentences.append(s)
    if not sentences and raw:
        sentences = [raw]
    return sentences


def count_sentences(text: str) -> int:
    return len(split_sentences(text))
