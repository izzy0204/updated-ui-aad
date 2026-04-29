# scripts/form_only_cardgen.py
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Optional: if your project has CHAIModelCard dataclass already, we’ll use it.
# If import fails, we’ll fall back to a plain dict with the same fields.
try:
    from core.chai_schema import CHAIModelCard  # type: ignore
except Exception:
    CHAIModelCard = None  # we’ll build dicts manually


# ---------------------------- Helpers ----------------------------

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-") or "unnamed"

def clean_email(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    # Remove leading punctuation and stray delimiters sometimes pasted into the sheet
    s = re.sub(r"^[;:,]+", "", s).strip()
    # If multiple separated by commas/semicolons, take the first
    parts = re.split(r"[;,]\s*", s)
    return (parts[0] or "").strip()

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ------------------------ CHAI card builders ----------------------

CHAI_FIELDS: List[str] = [
    "model_name",
    "developer",
    "inquiries_or_to_report_an_issue",
    "release_stage",
    "release_date",
    "version",
    "regulatory_approval_status_if_applicable",
    "global_availability",
    "summary",
    "keywords",
    "intended_use_and_workflow",
    "primary_intended_users",
    "necessary_knowledge_expertise",
    "how_to_use",
    "targeted_patient_population",
    "patient_consent_or_disclosure_required_or_suggested",
    "developer_supplied_warnings",
    "model_limitations",
    "skin_type_representation_and_equity",
    "clinical_risk_level",
    "ai_system_facts",
    "model_type",
    "interaction_with_other_systems",
    "outcomes_and_output",
    "type_and_value_of_solution_output",
    "explanation_for_how_an_output_is_generated",
    "foundation_models_used_in_application_if_applicable",
    "input_data_source",
    "output_input_data_type",
    "development_data_characterization",
    "training_data",
    "exclusion_inclusion_criteria",
    "demographic_representativeness",
    "dataset_doi_if_applicable",
    "dataset_transparency",
    "validation_test_dataset",
    "timeline_of_data_collection",
    "skin_tone_diversity",
    "did_the_data_collection_process_undergo_ethical_review",
    "ethical_review_board_oversight",
    "irb_approval",
    "relevance_of_training_data_to_intended_population",
    "bias_mitigation_approaches",
    "ongoing_maintenance",
    "security_and_compliance_environment_practices_or_accreditations_if_applicable",
    "transparency_intelligibility_and_accountability_mechanisms_if_applicable",
    "transparency_information",
    "funding_source_of_the_technical_implementation",
    "third_party_information_if_applicable",
    "usefulness_efficacy_goal_of_metrics",
    "usefulness_efficacy_result",
    "usefulness_efficacy_interpretation",
    "usefulness_efficacy_test_type",
    "usefulness_efficacy_testing_data_description",
    "usefulness_efficacy_validation_process_and_justification",
    "usefulness_efficacy_auroc_accuracy_etc",
    "fairness_equity_goal_of_metrics",
    "fairness_equity_result",
    "fairness_equity_interpretation",
    "fairness_equity_test_type",
    "fairness_equity_testing_data_description",
    "fairness_equity_validation_process_and_justification",
    "safety_reliability_goal_of_metrics",
    "safety_reliability_result",
    "safety_reliability_interpretation",
    "safety_reliability_test_type",
    "safety_reliability_testing_data_description",
    "safety_reliability_validation_process_and_justification",
    "evaluation_references_if_available",
    "clinical_trial_if_available",
    "peer_reviewed_publications",
    "reimbursement_status_if_applicable",
    "stakeholders_consulted_during_design_of_solution",
    "extraction_timestamp",
]

def make_card_dict(model_name: str, developer: str, email: str) -> Dict[str, Any]:
    # Default everything to "" or sensible defaults, no LLM
    card: Dict[str, Any] = {k: "" for k in CHAI_FIELDS}
    card["model_name"] = model_name
    card["developer"] = developer
    card["inquiries_or_to_report_an_issue"] = email
    card["summary"] = ""  # leave empty (no LLM in this script)
    card["foundation_models_used_in_application_if_applicable"] = []
    card["keywords"] = []
    card["extraction_timestamp"] = now_iso()
    return card

def make_card_dataclass(model_name: str, developer: str, email: str):
    # Only used if CHAIModelCard import succeeded and its ctor allows default empties
    card_dict = make_card_dict(model_name, developer, email)
    # Keep only keys accepted by the dataclass (avoid mismatch)
    accepted = {f: card_dict.get(f, "") for f in CHAI_FIELDS}
    return CHAIModelCard(**accepted)  # type: ignore


# ------------------------ Markdown render -------------------------

def to_markdown(card: Dict[str, Any]) -> str:
    def val(k: str) -> str:
        v = card.get(k)
        if isinstance(v, list):
            return ", ".join(map(str, v))
        return str(v or "").strip() or "Not specified"

    lines = [
        f"# Model Card — {val('model_name')}",
        "",
        f"**Developer:** {val('developer')}",
        f"**Contact:** {val('inquiries_or_to_report_an_issue')}",
        f"**Extracted:** {val('extraction_timestamp')}",
        "",
        "## Summary",
        val("summary"),
        "",
        "## Intended Use & Workflow",
        val("intended_use_and_workflow"),
        "",
        "## Model Type",
        val("model_type"),
        "",
        "## Training Data",
        val("training_data"),
        "",
        "## Validation / Test Dataset",
        val("validation_test_dataset"),
        "",
        "## Limitations",
        val("model_limitations"),
        "",
    ]
    return "\n".join(lines).strip()


# ----------------------------- Main -------------------------------

def load_sheet(
    path: Path,
    sheet: Optional[str] = None,
    header_row: int = 0,
) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet or 0, header=header_row)
    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def process_rows(
    df: pd.DataFrame,
    *,
    name_col: str = "name",
    email_col: str = "email",
    developer_col: str = "short text 1",
    status_col: str = "status",
    require_status_yes: bool = True,
) -> List[Dict[str, str]]:
    needed = {name_col, email_col, developer_col}
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing} (got: {list(df.columns)})")

    rows: List[Dict[str, str]] = []
    for _, r in df.iterrows():
        status_val = str(r.get(status_col, "")).strip().lower() if status_col in df.columns else ""
        if require_status_yes and status_val not in ("yes", "y", "true", "1"):
            continue

        name = str(r.get(name_col, "")).strip()
        developer = str(r.get(developer_col, "")).strip()
        email = clean_email(r.get(email_col, ""))

        if not name:
            continue

        rows.append({"model_name": name, "developer": developer, "email": email})
    return rows

def write_artifacts(card_obj: Any, out_dir: Path, basename: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{basename}.json"
    md_path = out_dir / f"{basename}.md"

    if CHAIModelCard and hasattr(card_obj, "__dataclass_fields__"):
        card_dict = asdict(card_obj)
    else:
        card_dict = card_obj

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(card_dict, f, ensure_ascii=False, indent=2)

    md = to_markdown(card_dict)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md)

    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")

def main():
    ap = argparse.ArgumentParser(description="Generate CHAI model cards from intake form (no web/LLM).")
    ap.add_argument("--in", dest="input_path", required=True, help="Path to Excel intake form")
    ap.add_argument("--sheet", default=None, help="Sheet name or index (default: first sheet)")
    ap.add_argument("--out-dir", default="outputs/forms", help="Output directory")
    ap.add_argument("--all", action="store_true", help="Process all rows (ignore Status column)")
    ap.add_argument("--name-col", default="Name")
    ap.add_argument("--email-col", default="Email")
    ap.add_argument("--developer-col", default="Short text 1", help="Mapped to CHAI 'developer'")
    ap.add_argument("--status-col", default="Status")
    args = ap.parse_args()

    input_path = Path(args.input_path)
    out_dir = Path(args.out_dir)

    print(" Loading intake form…")
    df = load_sheet(input_path, sheet=args.sheet)

    rows = process_rows(
        df,
        name_col=args.name_col.lower(),
        email_col=args.email_col.lower(),
        developer_col=args.developer_col.lower(),
        status_col=args.status_col.lower(),
        require_status_yes=not args.all,
    )

    if not rows:
        print("  No eligible rows found (did you mean to pass --all?).")
        return

    print(f" Found {len(rows)} eligible request(s). Writing cards to {out_dir} …")
    for r in rows:
        model_name = r["model_name"]
        developer = r["developer"]
        email = r["email"]

        if CHAIModelCard:
            card = make_card_dataclass(model_name, developer, email)
        else:
            card = make_card_dict(model_name, developer, email)

        base = slugify(model_name)
        print(f"\n→ {model_name}  (developer: {developer or '—'}, contact: {email or '—'})")
        write_artifacts(card, out_dir, base)

    print("\n Done.")

if __name__ == "__main__":
    main()
