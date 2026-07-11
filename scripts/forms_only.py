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

# Optional: if your project has ClinicalModelCard dataclass already, we’ll use it.
# If import fails, we’ll fall back to a plain dict with the same fields.
try:
    from core.chai_schema import CLINICAL_AGENT_EXTRACT_FIELDS, ClinicalModelCard  # type: ignore
except Exception:
    CLINICAL_AGENT_EXTRACT_FIELDS = []
    ClinicalModelCard = None  # we’ll build dicts manually


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

CHAI_FIELDS: List[str] = list(CLINICAL_AGENT_EXTRACT_FIELDS) if CLINICAL_AGENT_EXTRACT_FIELDS else [
    "model_name",
    "developer",
    "summary",
    "medical_purpose",
    "acceptable_input",
    "output",
    "role_in_decision_making",
    "intended_users",
    "target_patient_population",
    "known_failure_modes",
    "unsupported_clinical_scenarios",
    "unsupported_use_cases",
    "required_clinician_oversight",
    "model_type",
    "training_data",
    "model_development_and_validation",
    "clinical_trial",
    "performance",
    "performance_evaluation_limitations",
    "regulatory_approval_status",
    "version",
    "availability",
    "ongoing_monitoring_plan",
    "scheduled_updates",
    "contact",
]

def make_card_dict(model_name: str, developer: str, email: str) -> Dict[str, Any]:
    # Default everything to "" or sensible defaults, no LLM
    card: Dict[str, Any] = {k: "" for k in CHAI_FIELDS if k not in {"training_data", "model_development_and_validation", "clinical_trial", "performance", "contact"}}
    card["model_name"] = model_name
    card["developer"] = developer
    card["contact"] = {"email": email, "url": ""}
    card["training_data"] = {"description": "", "dataset_url": None}
    card["model_development_and_validation"] = {"description": "", "publication_url": None}
    card["clinical_trial"] = {"identifier": "", "url": "", "description": ""}
    card["performance"] = {"summary": "", "metrics": []}
    card["summary"] = ""  # leave empty (no LLM in this script)
    return card

def make_card_dataclass(model_name: str, developer: str, email: str):
    if ClinicalModelCard is None:
        return make_card_dict(model_name, developer, email)
    from core.chai_schema import Contact, ModelDevelopmentValidation, Performance, TrainingData

    return ClinicalModelCard(
        model_name=model_name,
        developer=developer,
        contact=Contact(email=email or None, url=None),
        training_data=TrainingData(),
        model_development_and_validation=ModelDevelopmentValidation(),
        performance=Performance(),
    )


# ------------------------ Markdown render -------------------------

def to_markdown(card: Any) -> str:
    if hasattr(card, "to_markdown") and callable(card.to_markdown):
        return card.to_markdown()
    if ClinicalModelCard is not None and isinstance(card, dict):
        try:
            return ClinicalModelCard.from_dict(card).to_markdown()
        except Exception:
            pass

    def val(k: str) -> str:
        v = card.get(k) if isinstance(card, dict) else ""
        if isinstance(v, dict):
            if k == "contact":
                email = str(v.get("email") or "").strip()
                url = str(v.get("url") or "").strip()
                return email or url or "Not specified"
            if k == "training_data":
                return str(v.get("description") or "").strip() or "Not specified"
            if k == "performance":
                return str(v.get("summary") or "").strip() or "Not specified"
            return "Not specified"
        if isinstance(v, list):
            return ", ".join(map(str, v))
        return str(v or "").strip() or "Not specified"

    lines = [
        "---",
        "schema_version: clinical-model-card-1.0",
        "---",
        "",
        f"# {val('model_name')}",
        "",
        "## 1) Metadata",
        f"- **Model Name:** {val('model_name')}",
        f"- **Developer:** {val('developer')}",
        f"- **Summary:** {val('summary')}",
        "",
        "## 2) Intended Use & Workflow",
        f"- **Medical Purpose:** {val('medical_purpose')}",
        f"- **Acceptable Input:** {val('acceptable_input')}",
        f"- **Output:** {val('output')}",
        f"- **Role in Decision-Making:** {val('role_in_decision_making')}",
        f"- **Intended Users:** {val('intended_users')}",
        f"- **Target Patient Population:** {val('target_patient_population')}",
        "",
        "## 3) Warnings & Limitations",
        f"- **Known Failure Modes:** {val('known_failure_modes')}",
        f"- **Unsupported Clinical Scenarios:** {val('unsupported_clinical_scenarios')}",
        f"- **Unsupported Use Cases:** {val('unsupported_use_cases')}",
        f"- **Required Clinician Oversight:** {val('required_clinician_oversight')}",
        "",
        "## 4) Model Development",
        f"- **Model Type:** {val('model_type')}",
        f"- **Training Data:** {val('training_data')}",
        f"- **Performance:** {val('performance')}",
        "",
        "## 5) Regulatory Status",
        f"- **Regulatory Approval Status:** {val('regulatory_approval_status')}",
        "",
        "## 6) Governance and Monitoring",
        f"- **Contact:** {val('contact')}",
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

    if ClinicalModelCard and hasattr(card_obj, "__dataclass_fields__"):
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

        if ClinicalModelCard:
            card = make_card_dataclass(model_name, developer, email)
        else:
            card = make_card_dict(model_name, developer, email)

        base = slugify(model_name)
        print(f"\n→ {model_name}  (developer: {developer or '—'}, contact: {email or '—'})")
        write_artifacts(card, out_dir, base)

    print("\n Done.")

if __name__ == "__main__":
    main()
