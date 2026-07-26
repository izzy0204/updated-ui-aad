"""Shared clinical model card display helpers for Streamlit and terminal UI."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.card_regulatory import tier_for_regulatory_status
from core.chai_schema import REGULATORY_STATUS_LABELS, iter_field_placements
from core.dermauto_card_render import (
    REGULATORY_ROW_STYLE,
    format_clinical_trial,
    format_contact,
    format_development,
    format_performance_summary,
    format_training_data,
    format_version_with_date,
    regulatory_tooltip_html,
)


def _disclosed(val: Optional[str]) -> str:
    if val is None or not str(val).strip():
        return "Not disclosed"
    return str(val).strip()


def field_value_for_display(card: Any, field_name: str) -> Optional[str]:
    """Plain-text display value for a top-level clinical field."""
    if field_name == "model_name":
        return card.model_name or "Not disclosed"
    if field_name == "developer":
        return card.developer or "Not disclosed"
    if field_name == "regulatory_approval_status":
        return REGULATORY_STATUS_LABELS.get(
            card.regulatory_approval_status, str(card.regulatory_approval_status.value)
        )
    if field_name == "regulatory_approval_date":
        d = card.regulatory_approval_date
        return d.isoformat() if isinstance(d, date) else _disclosed(str(d) if d else None)
    if field_name == "version":
        return format_version_with_date(card.version, card.last_updated)
    if field_name == "last_updated":
        return None
    if field_name == "availability":
        return _disclosed(card.availability)
    if field_name == "training_data":
        return format_training_data(card.training_data)
    if field_name == "model_development_and_validation":
        return format_development(card.model_development_and_validation)
    if field_name == "clinical_trial":
        return format_clinical_trial(card.clinical_trial) if card.clinical_trial else None
    if field_name == "performance":
        return format_performance_summary(card.performance)
    if field_name == "contact":
        return format_contact(card.contact)
    val = getattr(card, field_name, None)
    if val is None or not str(val).strip():
        return "Not disclosed"
    return str(val).strip()


def iter_display_sections(card: Any) -> Iterator[Tuple[str, str, str, str]]:
    """Yield ``(section, field_name, label, display_text)`` in export order."""
    for section, field_name, label in iter_field_placements():
        text = field_value_for_display(card, field_name)
        if field_name in ("clinical_trial", "last_updated") and text is None:
            continue
        yield section, field_name, label, text or "Not disclosed"


def performance_metrics_rows(card: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for m in getattr(getattr(card, "performance", None), "metrics", None) or []:
        rows.append(
            {
                "Metric": (getattr(m, "name", None) or "").strip() or "—",
                "Value": (getattr(m, "value", None) or "").strip() or "—",
                "Population": (getattr(m, "population", None) or "").strip() or "—",
                "95% CI": (getattr(m, "confidence_interval", None) or "").strip() or "—",
            }
        )
    return rows


def regulatory_status_badge_md(status: Any, label: str = "Regulatory Approval Status") -> str:
    """Markdown/HTML badge for regulatory status (colored badge only)."""
    tier = tier_for_regulatory_status(status)
    bg, accent = REGULATORY_ROW_STYLE.get(tier, REGULATORY_ROW_STYLE["gray"])
    text = REGULATORY_STATUS_LABELS.get(status, str(getattr(status, "value", status)))
    return (
        f"**{label}:** "
        f'<span style="background-color:{bg};border:2px solid {accent};'
        f'padding:2px 8px;border-radius:4px;font-weight:700;">{text}</span>'
        f"{regulatory_tooltip_html()}"
    )


def terminal_card_lines(card: Any) -> List[str]:
    """Lines for terminal summary (no v0.3 field names)."""
    lines: List[str] = []
    if card.application_url:
        lines.append(f"Application: {card.application_url}")
    current_section: Optional[str] = None
    for section, field_name, label, text in iter_display_sections(card):
        if section != current_section:
            lines.append("")
            lines.append(section)
            current_section = section
        if field_name == "performance" and performance_metrics_rows(card):
            lines.append(f"  {label}: {text}")
            lines.append("  Performance Metrics:")
            for row in performance_metrics_rows(card):
                lines.append(
                    f"    • {row['Metric']}: {row['Value']} "
                    f"(pop: {row['Population']}, CI: {row['95% CI']})"
                )
        else:
            lines.append(f"  {label}: {text}")
    return lines
