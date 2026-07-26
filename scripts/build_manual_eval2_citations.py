#!/usr/bin/env python3
"""One-off: build .citations.json sidecars for the 5 manual eval-2 cards so the
DermAUTO viewer can resolve reference links instead of showing
"Citations unavailable". citationIds map each field's full displayed text to
the numbered source(s) from the original manual markdown document.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard, REGULATORY_STATUS_LABELS  # noqa: E402
from core.dermauto_card_render import (  # noqa: E402
    format_clinical_trial,
    format_contact,
    format_development,
    format_performance_summary,
    format_training_data,
    format_version_with_date,
)

PRELOADED = REPO / "src" / "core" / "pages" / "preloaded_cards"

REFERENCES = {
    "dermasensor": {
        1: "https://www.dermasensor.com/",
        2: "https://www.dermasensor.com/history/",
        3: "https://support.dermasensor.com/",
        4: "https://www.dermasensor.com/contact-us/",
        5: "https://www.dermasensor.com/how-dermasensor-works/",
        6: "https://pmc.ncbi.nlm.nih.gov/articles/PMC11180084/",
        8: "https://www.dermasensor.com/skin-cancer-detection-device/",
        9: "https://www.accessdata.fda.gov/cdrh_docs/pdf23/DEN230008.pdf",
        10: "https://www.dermasensor.com/resource/fda-clearance-granted-for-first-ai-powered-medical-device-to-detect-all-three-common-skin-cancers-melanoma-basal-cell-carcinoma-and-squamous-cell-carcinoma/",
        11: "https://www.nature.com/articles/s41746-024-01161-1",
        12: "https://www.dermasensor.com/resource/two-new-studies-show-dermasensor-devices-consistent-performance-and-improvements-to-physicians-melanoma-detection/",
        13: "https://www.dermasensor.com/contact-us/",
        14: "https://www.dermasensor.com/resource/dermasensors-mission/",
        17: "https://www.dermasensor.com/",
        18: "https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf",
        20: "https://www.dermasensor.com/faq/",
        21: "https://www.dermasensor.com/how-dermasensor-works/",
        22: "https://www.dermasensor.com/resource/dermasensor-study-results-for-skin-cancer-detection-device-performance-across-skin-tones-of-over-1000-patients/",
        23: "https://www.dermasensor.com/",
        27: "https://www.dermasensor.com/resource/advancing-skin-cancer-detection-american-academy-of-dermatology-journal-publishes-dermasensors-breakthrough-melanoma-detection-results-from-a-major-multicenter-trial/",
        28: "https://doi.org/10.1016/j.jdin.2023.10.011",
        29: "https://www.dermasensor.com/team-position/board-of-directors/",
    },
    "tandem": {
        1: "http://withtandem.com",
        2: "https://pear.vc/companies/tandem/",
        3: "https://www.openevidence.com/announcements/openevidence-and-tandem-partner-to-streamline-evidence-based-prescribing-and-prior-authorizations",
        4: "https://techfundingnews.com/tandem-1b-valuation-100m-round/",
        5: "https://yourpractice.withtandem.com/prior-authorization-software",
        6: "https://datamatrixmedical.com/tandem-ai-prior-authorization-reviews-compared-to-prior-authorization-specialists/",
        7: "https://entrepreneurloop.com/tandem-ai-prescription-startup-billion-valuation-2026/",
    },
    "skinanalytics": {
        1: "https://skin-analytics.com/wp-content/uploads/2025/01/SA-001165-LB-v12-DERM-Instructions-for-Use_20Jan2025.pdf",
        2: "https://skin-analytics.com/news/regulatory-certification/derm-class-iii-ce-mark/",
        3: "https://skin-analytics.com/news/regulatory-certification/skin-analytics-achieves-class-iia-ukca-mark-for-derm/",
        4: "https://pubmed.ncbi.nlm.nih.gov/37869160/",
        5: "https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1288521/full",
        6: "https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/",
        7: "https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1264846/full",
        8: "https://pmc.ncbi.nlm.nih.gov/articles/PMC10996444/",
        9: "https://unityinsights.co.uk/our-insights/ai-in-health-and-care-award-skin-analytics-evaluation/",
        10: "https://skin-analytics.com/news/skin-cancer/prospective-study-shows-ai-as-accurate-as-clinical-specialist/",
        11: "https://www.nice.org.uk/consultations/2705/2/committee-discussion",
        12: "https://skin-analytics.com/ai-pathways/derm-performance/",
        13: "https://skin-analytics.com/ai-pathways/equality-of-access/",
        17: "https://clinicaltrials.gov/study/NCT04116983",
        18: "https://clinicaltrials.gov/study/NCT04123678",
        19: "https://clinicaltrials.gov/study/NCT05126173",
    },
    "dermgpt": {
        1: "https://practicaldermatology.com/topics/practice-management/ai-based-dermgpt-focuses-on-improved-clinic-productivity/23990/",
        2: "https://www.mdedge.com/cutis/article/268568/dermgpt-can-help-improve-your-office-productivity",
        4: "https://www.dermgpt.com/derm-gpt-chat",
        6: "https://pubmed.ncbi.nlm.nih.gov/38754096/",
        7: "https://www.medpagetoday.com/video-coverage/atopic-derm-future-focus/107750",
        10: "https://derma.jmir.org/2025/1/e74040",
        11: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12677980/",
    },
    "skinvision": {
        1: "https://www.skinvision.com/getting-started#explore-skinvision",
        2: "https://www.skinvision.com/about/",
        3: "https://www.skinvision.com/contact-us",
        5: "https://www.skinvision.com/instructions-for-use",
        6: "https://www.skinvision.com/scientific-evidence",
        7: "https://www.skinvision.com/press-release/skinvision-earns-europes-top-medical-certification-for-ai-powered-skin-cancer-detection",
        9: "https://www.skinvision.com/press-release/skinvision-achieves-milestone-with-three-certifications",
        10: "https://repub.eur.nl/pub/119322/Repub_119322_O-A.pdf",
        14: "https://content.skinvision.com/website/en/instructions-for-use-6-0-20.pdf",
        15: "https://www.skinvision.com/getting-started",
        16: "https://skinvision-static-content.s3-eu-west-1.amazonaws.com/website/eifu/2.10/Instructions_for_Use_SkinVision_Service_6.0_-_EN_-_v2.10.pdf",
        17: "https://skinvision-static-content.s3-eu-west-1.amazonaws.com/website/en/Privacy_Policy_SkinVision.pdf",
        19: "https://pmc.ncbi.nlm.nih.gov/articles/PMC7027514/",
        20: "https://pubmed.ncbi.nlm.nih.gov/31494983/",
        21: "https://medicalxpress.com/news/2019-09-skinvision-skin-cancer.html",
        23: "https://www.skinvision.com/articles/how-does-skinvisions-algorithm-detect-skin-cancer",
        24: "https://www.skinvision.com/clinical-research",
        26: "https://www.ajmc.com/view/review-examines-pros-and-cons-in-ai-detection-of-skin-cancer",
        28: "https://www.sciencedirect.com/science/article/pii/S0022202X23029640",
        29: "https://medicalfuturist.com/aspiring-dermatology-app-under-the-microscope-the-skinvision-review",
        30: "https://www.solbari.com.au/pages/how-to-skincheck",
        32: "https://www.skinvision.com/articles/how-machine-learning-detects-skin-cancer",
        39: "https://www.business-reporter.com/healthcare/from-wellness-to-medical-device-skinvision-raises-the-bar-for-ai-in-healthcare",
    },
}

# field_name -> list of citation numbers (numbers not present in REFERENCES for
# that model are skipped defensively). Fields omitted here get no citation.
FIELD_CITATIONS = {
    "dermasensor": {
        "model_name": [1],
        "developer": [2],
        "regulatory_approval_status": [8, 9, 10, 11],
        "availability": [12, 13],
        "summary": [14],
        "medical_purpose": [18],
        "acceptable_input": [5, 17],
        "output": [20],
        "role_in_decision_making": [18],
        "intended_users": [5, 17, 20],
        "target_patient_population": [1],
        "known_performance_limitations": [18],
        "skin_type_representation_equity": [21, 22, 23],
        "required_clinician_oversight": [20],
        "model_type": [20],
        "training_data.description": [21],
        "model_development_and_validation.description": [18],
        "clinical_trial": [18],
        "performance.summary": [18],
        "performance_evaluation_limitations": [27, 28],
        "ongoing_monitoring_plan": [20],
        "scheduled_updates": [20],
        "contact": [3, 4],
    },
    "tandem": {
        "model_name": [1],
        "developer": [2],
        "regulatory_approval_status": [5],
        "version": [3, 4],
        "availability": [1],
        "summary": [1, 4],
        "medical_purpose": [1],
        "intended_users": [1, 5],
        "target_patient_population": [1, 3],
        "known_performance_limitations": [6],
        "skin_type_representation_equity": [1],
        "required_clinician_oversight": [5],
        "model_type": [7],
        "training_data.description": [4, 7],
        "model_development_and_validation.description": [1],
        "performance.summary": [1],
        "performance_evaluation_limitations": [6],
        "ongoing_monitoring_plan": [1],
    },
    "skinanalytics": {
        "model_name": [1],
        "developer": [1],
        "regulatory_approval_status": [1, 2, 3],
        "version": [1],
        "availability": [1, 2],
        "summary": [1, 2],
        "medical_purpose": [1],
        "acceptable_input": [1],
        "output": [1],
        "role_in_decision_making": [1],
        "intended_users": [1],
        "target_patient_population": [1],
        "known_performance_limitations": [1],
        "skin_type_representation_equity": [5, 7, 9, 11, 13],
        "required_clinician_oversight": [1],
        "model_type": [1],
        "training_data.description": [1],
        "model_development_and_validation.description": [4],
        "clinical_trial": [17, 18, 19],
        "performance.summary": [5, 6, 8, 9, 10, 12],
        "ongoing_monitoring_plan": [1],
        "scheduled_updates": [6, 7],
        "contact": [1],
    },
    "dermgpt": {
        "model_name": [1],
        "developer": [1],
        "version": [2],
        "summary": [1],
        "medical_purpose": [1],
        "acceptable_input": [2, 4],
        "output": [1],
        "role_in_decision_making": [7],
        "intended_users": [1, 4],
        "known_performance_limitations": [1],
        "required_clinician_oversight": [6],
        "clinical_trial": [10, 11],
        "performance.summary": [2],
        "performance_evaluation_limitations": [7],
        "ongoing_monitoring_plan": [1],
    },
    "skinvision": {
        "model_name": [1],
        "developer": [2],
        "regulatory_approval_status": [7],
        "version": [6],
        "availability": [9],
        "summary": [2],
        "medical_purpose": [10],
        "acceptable_input": [15, 16],
        "output": [29],
        "role_in_decision_making": [30],
        "intended_users": [14, 15],
        "target_patient_population": [15],
        "known_performance_limitations": [19, 20, 21],
        "skin_type_representation_equity": [23, 24],
        "required_clinician_oversight": [15],
        "model_type": [23],
        "training_data.description": [20, 23],
        "model_development_and_validation.description": [7, 20],
        "clinical_trial": [7, 39],
        "performance.summary": [6, 26, 28],
        "performance_evaluation_limitations": [20, 23],
        "ongoing_monitoring_plan": [17, 32],
        "scheduled_updates": [32],
        "contact": [3, 5],
    },
}

SIMPLE_FIELDS = {
    "model_name",
    "developer",
    "availability",
    "summary",
    "medical_purpose",
    "acceptable_input",
    "output",
    "role_in_decision_making",
    "intended_users",
    "target_patient_population",
    "known_performance_limitations",
    "skin_type_representation_equity",
    "required_clinician_oversight",
    "model_type",
    "performance_evaluation_limitations",
    "ongoing_monitoring_plan",
    "scheduled_updates",
}


def displayed_text(card: ClinicalModelCard, field_key: str) -> str:
    if field_key == "regulatory_approval_status":
        return REGULATORY_STATUS_LABELS.get(card.regulatory_approval_status, str(card.regulatory_approval_status.value))
    if field_key == "version":
        return format_version_with_date(card.version, card.last_updated)
    if field_key == "training_data.description":
        return format_training_data(card.training_data)
    if field_key == "model_development_and_validation.description":
        return format_development(card.model_development_and_validation)
    if field_key == "clinical_trial":
        return format_clinical_trial(card.clinical_trial) or ""
    if field_key == "performance.summary":
        return format_performance_summary(card.performance)
    if field_key == "contact":
        return format_contact(card.contact)
    if field_key in SIMPLE_FIELDS:
        return str(getattr(card, field_key) or "")
    return ""


def main() -> int:
    for slug, field_map in FIELD_CITATIONS.items():
        json_path = PRELOADED / f"{slug}-manual-eval-2.clinical.json"
        card = ClinicalModelCard.from_dict(json.loads(json_path.read_text(encoding="utf-8")))

        used_ids: set[int] = set()
        field_citations: dict[str, list[dict]] = {}
        for field_key, ids in field_map.items():
            valid_ids = [i for i in ids if i in REFERENCES[slug]]
            if not valid_ids:
                continue
            text = displayed_text(card, field_key)
            if not text.strip() or text.strip() == "Not disclosed":
                continue
            # sentence_level (not an exact "text" span) so every sentence in the
            # field gets a citation marker, not just one at the very end.
            field_citations[field_key] = [
                {"citationIds": [str(i) for i in valid_ids], "sentence_level": True}
            ]
            used_ids.update(valid_ids)

        references = {
            str(rid): {"url": url, "title": "", "source": ""}
            for rid, url in sorted(REFERENCES[slug].items())
            if rid in used_ids
        }

        sidecar = {
            "schema_version": "clinical-model-card-citations-1.0",
            "references": references,
            "field_citations": field_citations,
        }
        out_path = PRELOADED / f"{slug}-manual-eval-2.citations.json"
        out_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        print(f"Wrote {out_path.name}: {len(references)} references, {len(field_citations)} cited fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
