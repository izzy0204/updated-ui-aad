---
schema_version: clinical-model-card-2.0
---

# [Tandem](http://withtandem.com) — Clinical Model Card

## 1) Metadata
- **Model Name:** Tandem
- **Developer:** Tandem Technology, Inc. Founder & CEO: Sahir Jaggi; Clinical Intelligence led by Adam Harris, MD and Kathleen Alvarez, NP.
- **Regulatory Approval Status:** Not Authorized / Consumer Tool
- **Regulatory Approval Date:** Not disclosed
- **Version:** Not publicly disclosed. Platform undergoes continuous updates and iterative improvement. Company founded 2023.
- **Last Updated:** 2026-07-25
- **Availability:** Available in the United States via website for providers and patients; supports providers across all 50 states; not known to be available outside the U.S.

## 2) Summary
- **Summary:** Tandem is an AI-powered platform that automates the end-to-end medication prior authorization process for physician practices, including PA form generation and submission, appeals, pharmacy routing, and patient affordability support. It integrates with EHRs and provides real-time patient communication, with a human-in-the-loop design requiring provider review before submission.

## 3) Intended Use
- **Medical Purpose:** Automate administrative steps of obtaining prior authorization for prescribed medications, including PA form generation/submission, appeals, enrollment in manufacturer support programs, pharmacy navigation, and patient communication.
- **Acceptable Input:** Electronic prescriptions (structured data), clinical notes (unstructured text/PDFs), patient records, and payer policy data, pulled from the EHR via integration or uploaded manually.
- **Output:** Completed PA forms, appeal letters, enrollment forms, patient SMS notifications, pharmacy routing instructions, and portal dashboard status updates. AI reads clinical documentation and matches it against payer-specific PA requirements to auto-generate PA form content and, if denied, drafts an appeal letter drawing on historical payer-specific strategies; the provider reviews and approves all outputs before submission.
- **Role in Decision-Making:** The platform automates administrative work and does not make clinical decisions; providers review and approve all PA forms and appeal letters before submission.
- **Intended Users:** Physicians, nurse practitioners, and practice staff at outpatient practices across specialties who prescribe medications requiring prior authorization, and patients awaiting those medications. No specialized technical knowledge is required; the provider must be able to e-prescribe.
- **Target Patient Population:** All U.S. patients requiring medications with prior authorization, across all major payers, PBMs, and both retail and specialty drugs; supports millions of patients annually as of 2026.

## 4) Risks and Limitations
- **Known Performance Limitations:** May have limited capability for non-medication PA categories (e.g. procedures, imaging, DME); performance may vary for complex or unusual cases or when patients do not respond to outreach prompts; not a complete replacement for dedicated PA specialists in complex, high-volume, or multi-category environments; requires EHR e-prescribing capability; specific AI model error rates are not publicly disclosed.
- **Skin Type Representation & Equity:** Not applicable: Tandem's platform is administrative and does not analyze clinical images or make diagnoses. Its stated design goal of supporting every drug, insurance plan, and pharmacy is intended to provide equitable access regardless of insurance type, drug cost, or specialty, including financial assistance program navigation for patients facing cost barriers.
- **Required Clinician Oversight:** Human-in-the-loop design: the provider must approve all PA forms and appeal letters before submission; the platform does not make clinical decisions. SOC 2 Type II certified and HIPAA-compliant.

## 5) Mechanism and Development
- **Model Type:** AI-powered workflow automation platform combining NLP (for reading clinical records and generating forms/letters) and machine learning (for predicting PA approval likelihood and appeal strategies), with rules-based payer-specific form completion.
- **Training Data:** Proprietary datasets of prior authorization interactions collected through the platform ('millions of prior authorization interactions'); specific underlying LLMs/foundation models are not publicly disclosed.
- **Model Development & Validation:** No external or independent validation process is publicly disclosed; metrics are developer-reported. Case studies from individual practices (dermatology, gastroenterology, rheumatology, urology) are available on the Tandem blog.
- **Clinical Trial:** Not disclosed
- **Performance:** Developer-reported metrics: +20% higher PA approval rate vs. baseline, +70% faster medication access, ~60 minutes saved per PA on average, ~100% of PAs initiated same-day, <7 days from prescription to PA approval; not independently validated.
- **Performance — PA approval rate improvement:** +20%
- **Performance — Time saved per PA:** ~60 minutes
- **Limitations in Evaluating Performance:** The primary limitation is the lack of peer-reviewed data and independent validation; all performance metrics are developer-reported; performance may vary for complex or unusual cases.

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** The Clinical Intelligence team continuously identifies patterns, adapts to payer policy changes, and refines workflows based on real-world outcomes as the platform scales.
- **Scheduled Updates:** Continuous updates and iterative improvement per the developer.
- **Inquiries / Report an Issue:** providers@withtandem.com
