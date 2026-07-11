"""Performance metric parsing for migration and pipeline post-fill."""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from core.chai_schema import PerformanceMetric

_FITZPATRICK_CTX = re.compile(r"fitzpatrick|phototype|skin\s+type", re.I)
_METRIC_LINE_RE = re.compile(
    r"(?P<name>sensitivity|specificity)\s+"
    r"(?:estimates?\s+were\s+|for\s+[^:]{0,40}\s+was\s+|was\s+)?"
    r"(?P<value>\d+(?:\.\d+)?%)\s*"
    r"(?:\((?P<fraction>\d+\s*/\s*\d+)\))?",
    re.I,
)


def parse_migration_metrics(*texts: str) -> List[PerformanceMetric]:
    """Extract clinically valid performance metrics; reject skin-type integer false positives."""
    metrics: List[PerformanceMetric] = []
    seen: Set[Tuple[str, str]] = set()
    blob = " ".join((t or "").strip() for t in texts if t)
    for m in _METRIC_LINE_RE.finditer(blob):
        name = m.group("name").title()
        value = m.group("value")
        if not value.endswith("%"):
            continue
        window = blob[max(0, m.start() - 60) : m.end() + 20]
        if _FITZPATRICK_CTX.search(window):
            continue
        try:
            pct = float(value.rstrip("%"))
            if pct > 100 or pct < 1:
                continue
        except ValueError:
            continue
        population = None
        fraction = m.group("fraction")
        context = blob[max(0, m.start() - 80) : m.start()].lower()
        if fraction:
            population = f"n={fraction.replace(' ', '')}"
        elif "biopsied" in context and "un" not in context:
            population = "physician-biopsied lesions"
        elif "un-biopsied" in context or "unbiopsied" in context:
            population = "physician-selected un-biopsied lesions"
        elif "tuning" in context or "algorithm" in context:
            population = "algorithm tuning cohort"
        key = (name.lower(), value)
        if key in seen:
            continue
        seen.add(key)
        metrics.append(PerformanceMetric(name=name, value=value, population=population))
    return metrics
