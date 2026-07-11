---
schema_version: clinical-model-card-1.0
---

# Tandem — Clinical Model Card

## 1) Metadata
- **Model Name:** Tandem
- **Developer:** Tandem Technology, Inc. Founder & CEO is Sahir Jaggi. Clinical Intelligence led by Adam Harris, MD and Kathleen Alvarez, NP.
- **Regulatory Approval Status:** Regulatory Status Unknown
- **Regulatory Approval Date:** Not disclosed
- **Version:** Not specified.
- **Last Updated:** 2026-07-11
- **Availability:** Available in the United States; availability abroad not clearly specified.

## 2) Summary
- **Summary:** Tandem is an AI-powered platform that automates end-to-end medication access workflows (prior authorization submission, appeals, pharmacy routing, affordability/patient assistance enrollment, and patient communication). Integrates with provider EHRs; offered free to providers and patients (per developer materials).

## 3) Intended Use
- **Medical Purpose:** Automate steps of obtaining prior authorization for medications, including PA form generation/submission, appeals, pharmacy navigation, and patient communication.
- **Acceptable Input:** Electronic prescriptions (structured), clinical records/notes (unstructured), payer rules, insurance data, historical outcomes, and patient communications. Inputs include structured and unstructured clinical/admin data; outputs include structured forms, letters, routing instructions, portal updates, and SMS messages. Typical workflow includes e-prescribing to Tandem from the EHR, optional EHR integration for record retrieval, AI-generated PA form creation, provider review/approval, submission and follow-up, appeals generation with provider review, assistance program enrollment, pharmacy routing, and patient text updates.
- **Output:** Completed PA forms, payer follow-up coordination, appeal letters (clinician-approved), enrollment workflows, pharmacy routing, and real-time patient status communications via text; staff dashboards.
- **Role in Decision-Making:** Low-to-moderate; errors/delays could affect medication access; designed with human-in-the-loop provider review. Automate steps of obtaining prior authorization for medications, including PA form generation/submission, appeals, pharmacy navigation, and patient communication.
- **Intended Users:** Physicians, nurse practitioners, and practice staff at outpatient practices; also used in workflows involving patients waiting to receive medications. No specialized technical knowledge described; requires provider e-prescribing capability.
- **Target Patient Population:** U.S. patients requiring medications with prior authorization.

## 4) Risks and Limitations
- **Known Failure Modes:** Described limitations include scope focused on medication PAs (not all categories), variability in performance for complex cases or non-responsive patients, not a full replacement for PA specialists, and limited public disclosure of model error rates. Not applicable to core function (administrative workflow); not specified.
- **Unsupported Clinical Scenarios:** No formal warnings specified; platform notes include: electronic prescription workflows only; optional EHR integration; manual upload required without integration; provider review/approval before submissions; administrative automation tool that does not replace clinical judgment. Described limitations include scope focused on medication PAs (not all categories), variability in performance for complex cases or non-responsive patients, not a full replacement for PA specialists, and limited public disclosure of model error rates.
- **Unsupported Use Cases:** Described limitations include scope focused on medication PAs (not all categories), variability in performance for complex cases or non-responsive patients, not a full replacement for PA specialists, and limited public disclosure of model error rates.
- **Required Clinician Oversight:** Typical workflow includes e-prescribing to Tandem from the EHR, optional EHR integration for record retrieval, AI-generated PA form creation, provider review/approval, submission and follow-up, appeals generation with provider review, assistance program enrollment, pharmacy routing, and patient text updates. Low-to-moderate; errors/delays could affect medication access; designed with human-in-the-loop provider review. Patient opt-in/consent described for participation and communications (SMS/phone outreach).

## 5) Mechanism and Development
- **Model Type:** Workflow automation / administrative support with human review. AI-powered workflow automation platform using a human-in-the-loop approach; combines NLP and machine learning with payer/workflow automation.
- **Training Data:** Not disclosed
- **Model Development & Validation:** Not specified. [Publication](Not specified.)
- **Clinical Trial:** Not specified.
- **Performance:** HIPAA-compliant; SOC 2 Type II certified; no reported breaches/incidents in cited materials; regulatory context includes CMS interoperability/prior authorization rules. Administrative + human review mitigates clinical risk; security certifications provide assurance of controls.
- **Limitations in Evaluating Performance:** Not disclosed

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Continuous improvement described as platform scales.
- **Scheduled Updates:** Continuous improvement described as platform scales.
- **Inquiries / Report an Issue:** security@withtandem.com
