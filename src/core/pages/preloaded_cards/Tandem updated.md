# Tandem — CHAI Model Card

## 1) Metadata
- **Model Name:** Tandem [1]
- **Developer:** Tandem Technology, Inc. Founder & CEO is Sahir Jaggi. Clinical Intelligence led by Adam Harris, MD and Kathleen Alvarez, NP. [1,2]
- **Inquiries or to report an issue:** security@withtandem.com
- **Release Stage:** Commercially available. [3]
- **Release Date:** Company founded 2023. [4]
- **Version:** Not disclosed.
- **Regulatory Approval Status, if applicable:** No FDA clearance or approval disclosed or required (administrative workflow automation). Platform is described as HIPAA-compliant and SOC 2 Type II certified; not classified as a medical device by Tandem. [5]
- **Global Availability:** Available in the United States; availability abroad not clearly specified. [1]
- **Summary:** Tandem is an AI-powered platform that automates end-to-end medication access workflows (prior authorization submission, appeals, pharmacy routing, affordability/patient assistance enrollment, and patient communication). Integrates with provider EHRs; offered free to providers and patients (per developer materials). [1]
- **Keywords:** prior authorization; NLP; AI; medication access; pharmacy routing; EHR integration; appeals automation; patient support programs; HIPAA; healthcare workflow automation. [1]

## 2) Uses & Directions
- **Intended Use & Workflow:** Automate steps of obtaining prior authorization for medications, including PA form generation/submission, appeals, pharmacy navigation, and patient communication. [1]
- **Primary Intended Users:** Physicians, nurse practitioners, and practice staff at outpatient practices; also used in workflows involving patients waiting to receive medications. [1]
- **Necessary knowledge/expertise:** No specialized technical knowledge described; requires provider e-prescribing capability. [5]
- **How to Use:** Typical workflow includes e-prescribing to Tandem from the EHR, optional EHR integration for record retrieval, AI-generated PA form creation, provider review/approval, submission and follow-up, appeals generation with provider review, assistance program enrollment, pharmacy routing, and patient text updates. [1,5]
- **Targeted patient population:** U.S. patients requiring medications with prior authorization. [1]
- **Patient consent or disclosure required or suggested?:** Patient opt-in/consent described for participation and communications (SMS/phone outreach). [5]

## 3) Warnings
- **Developer-Supplied Warnings:** No formal warnings disclosed; platform notes include: electronic prescription workflows only; optional EHR integration; manual upload required without integration; provider review/approval before submissions; administrative automation tool that does not replace clinical judgment. [5]
- **Model Limitations:** Described limitations include scope focused on medication PAs (not all categories), variability in performance for complex cases or non-responsive patients, not a full replacement for PA specialists, and limited public disclosure of model error rates. [6]
- **Skin type representation & equity:** Not applicable to core function (administrative workflow); not disclosed. 
- **Clinical Risk Level:** Low-to-moderate; errors/delays could affect medication access; designed with human-in-the-loop provider review. [5]

## 4) Trust Ingredients
- **AI System Facts:** AI-powered workflow automation platform using a human-in-the-loop approach; combines NLP and machine learning with payer/workflow automation. [1,7]
- **Model Type:** Workflow automation / administrative support with human review. [1,5]
- **Interaction with other systems:** Integrates with EHRs (e.g., Epic, athenahealth, eClinicalWorks, ModMed) and interacts with payer/PBM systems and pharmacy routing; partner announcements include OpenEvidence. [5,8]
- **Outcomes & Output:** Completed PA forms, payer follow-up coordination, appeal letters (clinician-approved), enrollment workflows, pharmacy routing, and real-time patient status communications via text; staff dashboards. [1,5]
- **Explanation for how an output is generated:** Pull/ingest patient records and prescription data (via integration or upload), match to payer requirements, generate forms/appeals, require provider approval, submit and follow up, learn from outcomes. [1,5]
- **Foundation Models Used in application, if applicable:** Not disclosed; public statements suggest leveraging existing foundation models rather than training from scratch. [4]
- **Input Data Source:** Electronic prescriptions (structured), clinical records/notes (unstructured), payer rules, insurance data, historical outcomes, and patient communications. [1,5]
- **Output/Input Data Type:** Inputs include structured and unstructured clinical/admin data; outputs include structured forms, letters, routing instructions, portal updates, and SMS messages. [1,5]
- **Dataset Transparency:** Not disclosed; training data described as proprietary “first-party” authorization interaction data. [7]
- **Validation/Test Dataset:** Not disclosed.
- **Ongoing Maintenance:** Continuous improvement described as platform scales. [1]
- **Security and compliance environment practices or accreditations, if applicable:** HIPAA-compliant and SOC 2 Type II certified per developer; encryption and U.S.-based data storage described. [5]
- **Transparency, Intelligibility, and Accountability mechanisms, if applicable:** Human-in-the-loop provider approval; status dashboard; embedded clinical team; no public external audits/model cards disclosed. [5]
- **Funding Source of the technical implementation:** Venture-backed; product offered free to providers/patients; revenue model described as supported by pharma partners. [1]
- **3rd Party Information, if applicable:** Partner announcements (e.g., OpenEvidence); EHR integrations; large-scale deployment case study described for DOCS Dermatology Group; industry/org partnerships described. [8,9,14]

## 5) Key Metrics
### Usefulness / Efficacy
- **Goal of Metric(s):** Improve PA approval speed/likelihood and reduce administrative burden. [1]
- **Result:** Marketing claims include higher PA approval rate, faster medication access, time saved per PA, same-day initiation, and shorter time-to-approval; background context references AMA prior authorization survey. [1,15]
- **Interpretation:** Internal metrics suggest reduced administrative burden; independent validation not publicly disclosed. [1]
- **Test Type:** Internal platform metrics; no peer-reviewed validation disclosed. [1]
- **Testing Data Description:** Not disclosed. [1]
- **Validation Process and Justification:** Not disclosed. [1]

### Fairness & Equity
- **Goal of Metric(s):** Not disclosed; positioning suggests broad coverage across drugs/insurers/pharmacies. [1]
- **Result:** Not disclosed; affordability features described. [1]
- **Interpretation:** Not disclosed.
- **Test Type:** Not disclosed.

### Safety & Reliability
- **Goal of Metric(s):** Security compliance (HIPAA, SOC 2) and safe, provider-approved submission workflows. [5]
- **Result:** HIPAA-compliant; SOC 2 Type II certified; no reported breaches/incidents in cited materials; regulatory context includes CMS interoperability/prior authorization rules. [5,16]
- **Interpretation:** Administrative + human review mitigates clinical risk; security certifications provide assurance of controls. [5]
- **Test Type:** SOC 2 Type II audit; HIPAA compliance program. [5]
- **Validation Process and Justification:** SOC 2 audit described as third-party validation of controls; HIPAA compliance via BAAs and encryption. [5]

## 6) Resources
- **Evaluation References, if available:** No peer-reviewed evaluation studies identified; developer case studies and blog posts referenced; additional case study described for DOCS Dermatology Group. [1,14]
- **Clinical Trial, if available:** None found in cited materials.
- **Peer-Reviewed Publication(s):** None found in cited materials.
- **Reimbursement status, if applicable:** Platform described as free to providers and patients; revenue model described as supported by pharma partners; no reimbursement codes apply. [1,9]
- **Stakeholders consulted during design of solution:** Clinical Intelligence team described; founder background and investor/healthcare council connections referenced. [1,2]

## References
[1] https://withtandem.com/
[2] https://pear.vc/companies/tandem/
[3] https://www.openevidence.com/announcements/openevidence-and-tandem-partner-to-streamline-evidence-based-prescribing-and-prior-authorizations
[4] https://techfundingnews.com/tandem-1b-valuation-100m-round/
[5] https://yourpractice.withtandem.com/prior-authorization-software
[6] https://datamatrixmedical.com/tandem-ai-prior-authorization-reviews-compared-to-prior-authorization-specialists/
[7] https://entrepreneurloop.com/tandem-ai-prescription-startup-billion-valuation-2026/
[8] https://www.businesswire.com/news/home/20260402254260/en/OpenEvidence-and-Tandem-Partner-to-Streamline-Evidence-Based-Prescribing-and-Prior-Authorizations
[9] https://www.linkedin.com/company/withtandem
[10] https://pymnts.com/healthcare/2026/tandem-technology-raise-100-million-dollars-prescription-automation/
[11] https://www.bloomberg.com/news/articles/2026-01-26/ai-for-prescriptions-startup-tandem-lands-1-billion-valuation
[12] https://withtandem.com/blog/why-thousands-of-providers-trust-tandem-inside-tandems-clinical-intelligence-team
[13] https://wellfound.com/company/withtandem
[14] https://withtandem.com/blog/how-docs-dermatology-accelerated-medication-access-across-140-locations
[15] https://www.ama-assn.org/system/files/prior-authorization-survey.pdf
[16] https://www.cms.gov/priorities/burden-reduction/overview/interoperability/policies-regulations/cms-interoperability-prior-authorization-final-rule-cms-0057-f