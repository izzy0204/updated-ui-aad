"""Field-level synthesis and validation for v0.3 → clinical migration."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from core.chai_schema import ClinicalModelCard, Performance, PerformanceMetric
from core.citation_render import strip_inline_citation_markers
from core.migration_metrics import parse_migration_metrics
from utils.sentence_utils import count_sentences, split_sentences

_MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})\b",
    re.I,
)
_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_VERSION_RE = re.compile(r"(?:software\s+version[:\s]*)?(\d+(?:\.\d+)+)", re.I)
_PHONE_RE = re.compile(r"1[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{4}")
_FITZPATRICK_CTX = re.compile(r"fitzpatrick|phototype|skin\s+type", re.I)
_CLASS_II_RE = re.compile(r"\bclass\s*ii\b", re.I)


def _clean(text: str) -> str:
    return strip_inline_citation_markers(text or "").strip()


def _sents(text: str) -> List[str]:
    return [s.strip() for s in split_sentences(_clean(text)) if s.strip()]


def _dedupe_sents(parts: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for part in parts:
        for sent in _sents(part):
            key = re.sub(r"\s+", " ", sent.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(sent)
    return out


def _join_sents(sents: List[str], *, max_sents: Optional[int] = None) -> str:
    picked = sents[:max_sents] if max_sents else sents
    return " ".join(picked).strip()


def _pick_sents(text: str, include: List[str], *, exclude: Optional[List[str]] = None) -> List[str]:
    exclude = exclude or []
    out: List[str] = []
    for sent in _sents(text):
        low = sent.lower()
        if any(x in low for x in exclude):
            continue
        if any(x in low for x in include):
            out.append(sent)
    return out


def _overlap_ratio(a: str, b: str) -> float:
    wa = set(re.findall(r"[a-z0-9]+", a.lower()))
    wb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def parse_regulatory_approval_date(text: str) -> Optional[date]:
    t = _clean(text)
    m = _MONTH_DATE.search(t)
    if m:
        from datetime import datetime

        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}, {m.group(3)}", "%B %d, %Y").date()
        except ValueError:
            pass
    m = _ISO_DATE.search(t)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def regulatory_status_display_text(status_value: str, legacy_regulatory: str) -> Optional[str]:
    """Human-readable regulatory row text preserving source terminology (e.g. De Novo)."""
    reg = _clean(legacy_regulatory)
    if not reg:
        return None
    if re.search(r"\bde\s*novo\b", reg, re.I):
        if status_value == "FDA_CLEARED":
            return "FDA Cleared — FDA De Novo classification (Class II prescription device)"
        return reg[:280]
    if status_value == "FDA_APPROVED" and re.search(r"\bapproved\b", reg, re.I):
        return reg[:280]
    if status_value == "FDA_CLEARED" and re.search(r"\bcleared\b", reg, re.I):
        return reg[:280]
    return None


def synthesize_summary(legacy: Dict[str, str]) -> str:
    pool = _dedupe_sents([legacy.get("summary", ""), legacy.get("intended_use_and_workflow", "")])
    picked: List[str] = []
    for sent in pool:
        low = sent.lower()
        if any(
            k in low
            for k in (
                "optical spectroscopy",
                "elastic scattering",
                "ess",
                "intact skin",
                "dermoscopic",
                "input",
                "image",
            )
        ):
            picked.append(sent)
        elif any(k in low for k in ("monitor", "investigate further", "similarity score", "output", "labels")):
            picked.append(sent)
        elif any(k in low for k in ("melanoma", "referral", "dermatologist", "indicated for use", "purpose")):
            picked.append(sent)
        elif any(k in low for k in ("adjunct", "not a standalone", "not a screening", "clinical assessment")):
            picked.append(sent)
        if len(picked) >= 3:
            break
    if not picked:
        picked = pool[:3]
    return _join_sents(picked, max_sents=3)


def synthesize_medical_purpose(legacy: Dict[str, str]) -> str:
    sents = _pick_sents(
        legacy.get("intended_use_and_workflow", ""),
        include=["indicated for use", "assist", "referral", "melanoma", "basal cell", "squamous"],
        exclude=["how to", "handheld", "battery", "monitor", "investigate further", "similarity score", "optical recordings"],
    )
    return _join_sents(sents[:3]) or _join_sents(_sents(legacy.get("intended_use_and_workflow", ""))[:2])


def _dedupe_near_duplicate_sents(sents: List[str], threshold: float = 0.65) -> List[str]:
    out: List[str] = []
    for sent in sents:
        if any(_overlap_ratio(sent, kept) >= threshold for kept in out):
            continue
        out.append(sent)
    return out


def synthesize_acceptable_input(legacy: Dict[str, str]) -> str:
    sents = _dedupe_sents(
        [
            legacy.get("input_data_source", ""),
            legacy.get("output_input_data_type", ""),
            legacy.get("how_to_use", ""),
        ]
    )
    kept: List[str] = []
    for sent in sents:
        low = sent.lower()
        if any(x in low for x in ("output data type", "monitor", "investigate further", "similarity score", "battery", "base unit", "xenon", "microprocessor", "algorithm analyze")):
            continue
        if any(x in low for x in ("intact skin", "lesion", "spectroscopy", "ess", "wavelength", "input", "gloved", "contact", "primary lesion")):
            kept.append(sent)
    kept = _dedupe_near_duplicate_sents(kept, 0.55)
    ess_seen = False
    final: List[str] = []
    for sent in kept:
        low = sent.lower()
        if "ess spectral" in low or "elastic scattering spectroscopy" in low:
            if ess_seen:
                continue
            ess_seen = True
        final.append(sent)
    return _join_sents(final[:3]) or _join_sents(_pick_sents(legacy.get("input_data_source", ""), include=["lesion", "skin", "spectroscopy"])[:2])


def synthesize_output(legacy: Dict[str, str]) -> str:
    sents = _dedupe_sents([legacy.get("outcomes_and_output", ""), legacy.get("type_and_value_of_solution_output", "")])
    primary = next((s for s in sents if "monitor" in s.lower() or "investigate further" in s.lower()), "")
    similarity = next((s for s in sents if "similarity score" in s.lower()), "")
    if primary and similarity and "similarity score" not in primary.lower():
        return f"{primary.rstrip('.')}. {similarity}"
    if primary:
        return primary
    return _join_sents(sents[:1])


def synthesize_role_in_decision_making(legacy: Dict[str, str]) -> str:
    sents = _pick_sents(
        legacy.get("intended_use_and_workflow", ""),
        include=[
            "adjunct",
            "assist",
            "referral",
            "not intended",
            "not a standalone",
            "replace biopsy",
            "replace clinical decision",
            "clinical assessment",
            "decision",
        ],
        exclude=["class ii", "optical", "monitor", "investigate further", "similarity", "primary purpose"],
    )
    text = _join_sents(sents[:2])
    text = _CLASS_II_RE.sub("", text).strip()
    if not text or "replace" not in text.lower():
        text = (
            "Provides adjunctive referral support for physicians evaluating suspicious lesions; "
            "does not replace clinician judgment, biopsy, or definitive diagnosis."
        )
    return text


def synthesize_known_failure_modes(legacy: Dict[str, str]) -> str:
    sents = _pick_sents(
        legacy.get("model_limitations", ""),
        include=[
            "not been",
            "not evaluated",
            "less data",
            "limited",
            "rare skin cancer",
            "increased risk",
            "immune compromise",
            "photosensitivity",
        ],
        exclude=[
            "training dataset",
            "tuning dataset",
            "table",
            "white:",
            "black or african american",
            "palms",
            "soles",
            "mucosal",
            "nails",
            "tattoo",
            "hairy",
        ],
    )
    equity = _pick_sents(
        legacy.get("skin_type_representation_and_equity", ""),
        include=["less data", "limited representation", "lower sensitivity", "fitzpatrick", "clinical concern"],
        exclude=["training dataset included", "tuning dataset included", "%"],
    )
    combined = sents + equity
    deduped = _dedupe_near_duplicate_sents(combined, 0.6)
    return _join_sents(deduped[:5])


def synthesize_unsupported_clinical_scenarios(legacy: Dict[str, str]) -> str:
    sents = _dedupe_sents(
        _pick_sents(
            legacy.get("model_limitations", ""),
            include=["not tested", "palms", "soles", "mucosal", "genitals", "ears", "nails", "hairy", "tattoo", "scar", "recurrent", "metastatic", "biopsied", "close to the eye"],
        )
        + _pick_sents(
            legacy.get("developer_supplied_warnings", ""),
            include=["close to the eye", "energy-emitting"],
        )
    )
    return _join_sents(sents[:5])


def synthesize_unsupported_use_cases(legacy: Dict[str, str]) -> str:
    blob = _merge_legacy(
        legacy.get("developer_supplied_warnings", ""),
        legacy.get("intended_use_and_workflow", ""),
    ).lower()
    parts: List[str] = []
    if "screening tool" in blob or "not as a screening" in blob:
        parts.append("Not for screening or unsupervised population triage.")
    if "standalone" in blob or "stand-alone" in blob or "stand alone" in blob:
        parts.append("Not a standalone diagnostic device.")
    if "sole diagnostic" in blob or "sole basis" in blob:
        parts.append("Not the sole basis for diagnosis or referral decisions.")
    if "confirm clinical diagnosis" in blob or "confirm a clinical diagnosis" in blob:
        parts.append("Does not confirm a clinical diagnosis of cancer.")
    if "replace biopsy" in blob or "replace clinical decision" in blob:
        parts.append("Does not replace biopsy, pathology review, or clinician decision-making.")
    if parts:
        return " ".join(parts)
    sents = _pick_sents(
        blob,
        include=["not intended", "standalone", "screening tool", "sole diagnostic", "replace biopsy"],
        exclude=["palms", "soles", "mucosal", "tattoo", "hairy"],
    )
    deduped: List[str] = []
    seen: Set[str] = set()
    for sent in sents:
        key = re.sub(r"\s+", " ", sent.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sent)
    return _join_sents(deduped[:3])


def synthesize_required_clinician_oversight(legacy: Dict[str, str]) -> str:
    blob = _merge_legacy(
        legacy.get("primary_intended_users", ""),
        legacy.get("necessary_knowledge_expertise", ""),
        legacy.get("intended_use_and_workflow", ""),
    )
    parts: List[str] = []
    if re.search(r"physician|prescription", blob, re.I):
        parts.append(
            "A prescribing physician (not necessarily a dermatologist) must operate the device and interpret its output."
        )
    if re.search(r"clinical assessment|visual analysis", blob, re.I):
        parts.append(
            "Independent clinical assessment, including visual lesion evaluation, is required before and alongside device use."
        )
    if re.search(r"referral", blob, re.I):
        parts.append("Referral decisions remain with the clinician; device output provides adjunctive support only.")
    parts.append(
        "Definitive diagnosis requires clinician judgment and biopsy or pathology confirmation where clinically indicated."
    )
    return " ".join(parts)


def synthesize_model_type(legacy: Dict[str, str]) -> str:
    sents = _pick_sents(
        _merge_legacy(legacy.get("model_type", ""), legacy.get("ai_system_facts", "")),
        include=["machine learning", "ai/ml", "algorithm", "classifier", "neural", "spectroscopy", "ess"],
        exclude=["handheld", "battery", "base unit", "xenon", "touch-screen", "software version", "calibration"],
    )
    short = _join_sents(sents[:2])
    if short and len(short) <= 220:
        return short
    if re.search(r"ess|elastic scattering", _merge_legacy(legacy.get("model_type", ""), legacy.get("ai_system_facts", "")), re.I):
        return "AI/ML classifier analyzing Elastic Scattering Spectroscopy (ESS) recordings from intact skin lesions."
    return _join_sents(sents[:1]) or "Not disclosed"


def synthesize_performance_summary(legacy: Dict[str, str], metrics: Optional[List[PerformanceMetric]] = None) -> str:
    if metrics:
        parts = []
        for m in metrics:
            pop = f" ({m.population})" if m.population else ""
            parts.append(f"{m.name} {m.value}{pop}")
        summary = "; ".join(parts) + "."
        equity = _pick_sents(
            legacy.get("fairness_equity_result", "") + " " + legacy.get("usefulness_efficacy_interpretation", ""),
            include=["less data", "fitzpatrick", "iv-vi", "subgroup"],
            exclude=["reasonable assurance", "biocompatibility", "class ii"],
        )
        if equity:
            summary += " " + _join_sents(equity[:1])
        return summary.strip()
    _DEMO_TABLE_RE = re.compile(
        r"(?:training|tuning)\s+dataset\s+included|ethnicity/race\s+distribution|"
        r"fitzpatrick\s+phototype\s*\(|demographics\s+for\s+the\s+(?:training|tuning)",
        re.I,
    )
    _BENCH_TEST_RE = re.compile(
        r"biocompatibility|electromagnetic\s+compatib|cybersecurity|shelf\s+life|"
        r"non[- ]clinical/bench|cleaning\s+and\s+disinfection",
        re.I,
    )
    sents = _dedupe_sents(
        [
            legacy.get("usefulness_efficacy_result", ""),
            legacy.get("usefulness_efficacy_interpretation", ""),
            legacy.get("fairness_equity_result", ""),
        ]
    )
    kept = [s for s in sents if not _BENCH_TEST_RE.search(s) and not _DEMO_TABLE_RE.search(s)]
    metric_sents = [s for s in kept if re.search(r"\d+(?:\.\d+)?%", s) and re.search(r"sensitivity|specificity", s, re.I)]
    lead = metric_sents or _pick_sents(
        " ".join(kept),
        include=["sensitivity", "specificity", "tuning", "melanoma"],
        exclude=["biocompatibility", "emc", "cybersecurity", "reasonable assurance"],
    )
    return _join_sents(lead[:3]) or _join_sents(kept[:2]) or "Not disclosed"


def synthesize_performance(legacy: Dict[str, str]) -> Performance:
    metrics = parse_migration_metrics(
        legacy.get("usefulness_efficacy_result", ""),
        legacy.get("usefulness_efficacy_auroc_accuracy_etc", ""),
        legacy.get("usefulness_efficacy_interpretation", ""),
    )
    return Performance(summary=synthesize_performance_summary(legacy, metrics), metrics=metrics)


def synthesize_scheduled_updates(legacy: Dict[str, str], monitoring: Optional[str]) -> Optional[str]:
    raw = _clean(legacy.get("ongoing_maintenance", ""))
    if not raw:
        return None
    schedule_sents = _pick_sents(
        raw,
        include=["update schedule", "scheduled update", "release cadence", "changelog", "version release", "planned update"],
        exclude=["recall", "cybersecurity", "verification", "hazard analysis", "use life", "monitoring"],
    )
    if not schedule_sents:
        return None
    text = _join_sents(schedule_sents[:2])
    if monitoring and _overlap_ratio(text, monitoring) > 0.65:
        return None
    return text or None


def synthesize_contact(legacy: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    raw = _clean(legacy.get("inquiries_or_to_report_an_issue", ""))
    if not raw:
        return None, None
    primary_parts: List[str] = []
    recall_parts: List[str] = []
    for sent in _sents(raw):
        low = sent.lower()
        if "dice@fda" in low or "division of industry and consumer education" in low or "fda's" in low:
            continue
        if "recall" in low or "ryan frieden" in low:
            recall_parts.append(sent)
        elif "dermasensor" in low or _PHONE_RE.search(sent):
            primary_parts.append(sent)
    primary = _join_sents(primary_parts[:2]) or None
    recall = _join_sents(recall_parts[:1]) or None
    if recall and primary:
        recall_clean = re.sub(r"\b01-(\d{3})", r"1-\1", recall)
        return f"{primary} Recall contact: {recall_clean}", None
    return primary or raw.split("For specific recall")[0].strip() or None, None


def synthesize_version(legacy: Dict[str, str]) -> str:
    raw = _clean(legacy.get("version", ""))
    m = _VERSION_RE.search(raw)
    if m:
        return m.group(1)
    return raw or "Not disclosed"


def _merge_legacy(*parts: str) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def densify_citation_sidecar(sidecar: Dict[str, Any]) -> Tuple[Dict[str, Any], List[int]]:
    """Renumber cited references to dense 1..N; archive orphans internally."""
    refs = sidecar.get("references") or {}
    field_cites = sidecar.get("field_citations") or {}
    cited_order: List[str] = []
    seen: Set[str] = set()

    def _track(cid: str) -> None:
        if cid in refs and cid not in seen:
            seen.add(cid)
            cited_order.append(cid)

    for _key in sorted(field_cites.keys()):
        spans = field_cites.get(_key) or []
        if not isinstance(spans, list):
            continue
        for span in spans:
            if not isinstance(span, dict):
                continue
            for raw in span.get("citationIds") or span.get("citation_ids") or []:
                _track(str(raw))

    old_to_new = {old: str(i + 1) for i, old in enumerate(cited_order)}
    new_refs = {old_to_new[old]: refs[old] for old in cited_order if old in refs}
    orphaned = sorted(int(k) for k in refs.keys() if k not in cited_order)

    new_field_cites: Dict[str, Any] = {}
    for key, spans in field_cites.items():
        if not isinstance(spans, list):
            continue
        new_spans = []
        for span in spans:
            if not isinstance(span, dict):
                continue
            ids = []
            for raw in span.get("citationIds") or span.get("citation_ids") or []:
                mapped = old_to_new.get(str(raw))
                if mapped:
                    ids.append(mapped)
            if not ids:
                continue
            entry = dict(span)
            entry["citationIds"] = ids
            entry.pop("citation_ids", None)
            new_spans.append(entry)
        if new_spans:
            new_field_cites[key] = new_spans

    out = dict(sidecar)
    out["references"] = new_refs
    out["field_citations"] = new_field_cites
    if orphaned:
        out["_orphaned_references"] = {str(k): refs[str(k)] for k in orphaned if str(k) in refs}
    return out, orphaned


def attach_metric_citations(
    sidecar: Dict[str, Any],
    metrics: List[PerformanceMetric],
    legacy: Dict[str, str],
) -> None:
    """Add per-metric citation spans from usefulness efficacy source text."""
    blob = _merge_legacy(
        legacy.get("usefulness_efficacy_result", ""),
        legacy.get("usefulness_efficacy_auroc_accuracy_etc", ""),
    )
    if not blob.strip():
        return
    _, spans = __import__("core.citation_render", fromlist=["parse_text_citation_spans"]).parse_text_citation_spans(blob)
    if not spans:
        return
    field_cites = sidecar.setdefault("field_citations", {})
    for i, metric in enumerate(metrics):
        key = f"performance.metrics[{i}]"
        matched = None
        for span in spans:
            txt = str(span.get("text") or "")
            if metric.value.replace("%", "") in txt and metric.name.lower() in txt.lower():
                matched = span
                break
        if matched:
            field_cites[key] = [matched]


def validate_migrated_card(card: ClinicalModelCard, *, monitoring: Optional[str] = None) -> List[str]:
    """Field-level migration validators; returns warning strings."""
    warnings: List[str] = []
    if count_sentences(card.summary) > 3:
        warnings.append("summary_exceeds_three_sentences")
    if _CLASS_II_RE.search(card.role_in_decision_making or ""):
        warnings.append("role_in_decision_making_contains_class_ii")
    if card.scheduled_updates and monitoring and _overlap_ratio(card.scheduled_updates, monitoring) > 0.65:
        warnings.append("scheduled_updates_duplicates_monitoring")
    if card.acceptable_input and any(
        x in card.acceptable_input.lower() for x in ("monitor", "investigate further", "battery recharges")
    ):
        warnings.append("acceptable_input_contains_output_details")
    if card.required_clinician_oversight and not re.search(
        r"clinician|physician|judgment|review|interpret", card.required_clinician_oversight, re.I
    ):
        warnings.append("required_clinician_oversight_missing_review")
    for metric in card.performance.metrics:
        if not re.search(r"%|ratio|auroc|auc\b", metric.value, re.I):
            warnings.append(f"invalid_metric_value:{metric.name}={metric.value}")
    for field_name in ("known_failure_modes", "unsupported_clinical_scenarios", "unsupported_use_cases"):
        text = getattr(card, field_name) or ""
        sents = _sents(text)
        if len(sents) != len(set(s.lower() for s in sents)):
            warnings.append(f"duplicate_sentences_in:{field_name}")
    risk_fields = [
        card.known_failure_modes or "",
        card.unsupported_clinical_scenarios or "",
        card.unsupported_use_cases or "",
    ]
    for i in range(3):
        for j in range(i + 1, 3):
            if _overlap_ratio(risk_fields[i], risk_fields[j]) > 0.55:
                warnings.append(f"high_overlap_between_risk_fields:{i}:{j}")
    return warnings
