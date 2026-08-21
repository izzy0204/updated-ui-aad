---
schema_version: clinical-model-card-2.0
---

# [Forus](https://forus.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** Forus [1]
- **Developer:** Forus, Inc. (formerly Tandem / Tandem Technology, Inc.), based in New York, NY. [1,2]
- **Regulatory Approval Status:** Not an FDA-authorized medical device; administrative medication-access / prior-authorization workflow platform (consumer/provider tooling). [1]
- **Regulatory Approval Date:** Not disclosed
- **Version:** Not publicly disclosed
- **Last Updated:** 2026-08-21
- **Availability:** Free for providers and patients in the United States; supports practices in all 50 states and works with any EHR. [1,3]

## 2) Summary
- **Summary:** Forus is an AI-powered medication access platform that automates steps from prescription to affordable treatment—prior authorizations, appeals, enrollment forms, benefit verifications, pharmacy routing, affordability programs, and patient communication—so patients can start therapy faster. [1,3]

## 3) Intended Use
- **Medical Purpose:** Accelerate and simplify patient access to prescribed medications by automating administrative medication-access workflows (including pharmacy-benefit and buy-and-bill support) across drugs, insurance plans, and pharmacies. [1,3]
- **Acceptable Input:** Prescription and patient information from the clinician’s EHR workflow (prescribe in the EHR as usual; Forus generates and submits payer-specific prior authorization materials). [1,3]
- **Output:** Automated prior authorizations, customized appeal letters, enrollment forms, pharmacy routing, benefit verifications, affordability/financial assistance options, and patient/provider status updates. [1,3]
- **Role in Decision-Making:** Forus automates administrative work after the clinical decision to prescribe; it does not replace the clinician’s prescribing judgment. Clinicians prescribe the therapy they choose, and Forus handles access logistics. [1,3]
- **Intended Users:** Clinicians and practice staff (including dermatology, allergy, GI, rheumatology, neurology, and other specialties), as well as pharmacies, payers, and biopharma partners connected through the Forus network. [1,2]
- **Target Patient Population:** U.S. patients prescribed medications that require prior authorization or other access support, including specialty and dermatology medications. [1,3]

## 4) Risks and Limitations
- **Known Performance Limitations:** Forus focuses on medication access / prior authorization workflows; it is not a diagnostic or treatment-recommendation clinical AI. Practices that do not e-prescribe may have limited support. Performance can vary by payer, drug, and specialty. Specific model error rates are not publicly disclosed. [1,4]
- **Skin Type Representation & Equity:** Not applicable to core administrative PA automation; skin-tone representation is not a product performance axis for Forus’s medication-access workflows. [1]
- **Required Clinician Oversight:** Yes. Clinicians remain responsible for the clinical decision to prescribe. Forus automates administrative medication-access steps after the prescription is placed. [1,3]

## 5) Mechanism and Development
- **Model Type:** AI-powered workflow automation / medication-access platform (including LLM-assisted PA form answering and appeal generation, with LLM-as-judge verification against patient records). [1,4]
- **Training Data:** Uses first-party prior authorization and medication-access interaction data from the platform network; detailed training corpora and foundation-model identities are not fully disclosed publicly. [2,4]
- **Model Development & Validation:** Forus publishes engineering eval methods for its LLM judge (perturbation-based evaluation of PA answer verification against clinical records). Case studies on forus.com report practice-level access outcomes (e.g., Family Allergy & Asthma; DOCS Dermatology). [1,4,5,6]
- **Clinical Trial:** Not disclosed / not applicable as a drug or device pivotal trial for this administrative platform.
- **Performance:** Provider-facing metrics reported by Forus include ~1.1 median days to prior authorization approval in featured practices, ~3× more authorizations completed per day, and ~2× greater success filling first-line prescriptions. Family Allergy & Asthma reported cutting PA turnaround from 7+ days to 1.1 days and ~70% lower per-patient admin workload; DOCS Dermatology reported same-day submissions with approvals in <1 day. [1,3,5,6]
- **Limitations in Evaluating Performance:** Public metrics are largely case studies / marketing outcomes rather than peer-reviewed diagnostic AUROC-style evaluations; independent validation is limited. [1,4]

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Forus states it is HIPAA-compliant and SOC 2 Type II certified, with end-to-end encryption and US-based enterprise storage; security documentation available via Trust Center / security@forus.com. Clinical Intelligence and engineering teams continuously improve PA automation and judge calibration. [1,4]
- **Scheduled Updates:** Continuous product iteration (not a fixed public release calendar).
- **Inquiries / Report an Issue:** https://forus.com/ | security@forus.com | legal@forus.com

## References
[1] https://forus.com/
[2] https://forus.com/company
[3] https://forus.com/stories
[4] https://build.forus.com/how-we-evaluate-our-llm-judge-a-perturbation-based-approach
[5] https://forus.com/stories/family-allergy-and-asthmas-prior-authorization-transformation
[6] https://forus.com/stories/how-docs-dermatology-accelerated-medication-access-across-140-locations
