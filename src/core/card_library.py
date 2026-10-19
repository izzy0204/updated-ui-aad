"""Bundled model cards shown in the home-page gallery and the DermAUTO-CARD viewer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.chai_schema import ClinicalModelCard
from core.citation_render import ensure_clickable_citations
from core.source_regulatory import load_citations_for_markdown

_CORE_DIR = Path(__file__).resolve().parent
PAGES_DIR = _CORE_DIR / "pages"
PRELOADED_DIRS: Tuple[Path, ...] = (
    PAGES_DIR / "preloaded_cards_eval3",
    PAGES_DIR / "preloaded_cards",
    _CORE_DIR.parents[1] / "preloaded_cards",
)

# Stems may mix eval rounds; labels never mention eval-2 / eval-3.
BUNDLED_CARDS: Tuple[Tuple[str, str], ...] = (
    ("A · DermaSensor", "dermasensor-auto-eval-3"),
    ("B · DermaSensor", "dermasensor-manual-eval-3"),
    ("A · Forus", "tandem-auto-eval-3"),
    ("B · Forus", "tandem-manual-eval-3"),
    ("A · DERM", "derm-auto-eval-3"),
    ("B · DERM", "derm-manual-eval-3"),
    ("A · DermGPT", "dermgpt-auto-eval-3"),
    ("B · DermGPT", "dermgpt-manual-eval-3"),
    ("A · Skin Vision", "skinvision-auto-eval-2"),
    ("B · Skin Vision", "skinvision-manual-eval-2"),
)


@dataclass
class LibraryCard:
    key: str
    label: str
    card: ClinicalModelCard
    citations: Optional[Dict[str, Any]]


def companion_clinical_md(path: Path) -> Optional[Path]:
    """Resolve ``*.clinical.md`` next to a clinical JSON / citations path."""
    name = path.name
    if name.endswith(".clinical.json"):
        md = path.with_name(name.replace(".clinical.json", ".clinical.md"))
    elif name.endswith(".citations.json"):
        md = path.with_name(name.replace(".citations.json", ".clinical.md"))
    elif name.endswith(".clinical.md"):
        md = path
    else:
        md = path.with_suffix(".clinical.md")
    return md if md.is_file() else None


def bundled_card_paths() -> Dict[str, Path]:
    """Label -> clinical JSON path for every bundled card found on disk."""
    found: Dict[str, Path] = {}
    for label, stem in BUNDLED_CARDS:
        for base in PRELOADED_DIRS:
            jp = base / f"{stem}.clinical.json"
            if jp.exists():
                found[label] = jp
                break
    return found


def load_card_bundle(json_path: Path) -> Tuple[ClinicalModelCard, Optional[Dict[str, Any]]]:
    card = ClinicalModelCard.from_dict(json.loads(json_path.read_text(encoding="utf-8")))
    citations = load_citations_for_markdown(json_path)
    citations = ensure_clickable_citations(citations, md_path=companion_clinical_md(json_path))
    return card, citations


def load_library() -> List[LibraryCard]:
    out: List[LibraryCard] = []
    for label, path in bundled_card_paths().items():
        card, citations = load_card_bundle(path)
        out.append(LibraryCard(path.name.replace(".clinical.json", ""), label, card, citations))
    return out
