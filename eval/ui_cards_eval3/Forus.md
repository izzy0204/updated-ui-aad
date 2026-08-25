---
schema_version: clinical-model-card-2.0
---

# [Forus](https://forus.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** Forus [1]
- **Developer:** Forus Technology, Inc. (formerly Tandem). Founder & CEO: Sahir Jaggi. Clinical Intelligence led by Adam Harris, MD (former VP of Applied AI at Oscar Health; Clinical Assistant Professor, NYU School of Medicine) and Kathleen Alvarez, NP (Yale School of Nursing). [2]
- **Regulatory Approval Status:** Not Authorized / Consumer Tool [1]
- **Regulatory Approval Date:** Not disclosed
- **Version:** Not publicly disclosed.
- **Last Updated:** 2026-08-21
- **Availability:** Available in the United States. Accessible via website for providers (forus.com). Supports providers across all 50 states. Not known to be available outside the U.S. [1]

## 2) Summary
- **Summary:** Forus is an AI-powered platform that automates the end-to-end medication access process, including prior authorization (PA) submission, appeals, pharmacy routing, affordability/enrollment in patient assistance programs, and patient communication. [1][7][12]

## 3) Intended Use
- **Medical Purpose:** Intended for physician practices and their staff to automate all steps of obtaining prior authorization, from prescribing the medication to the patient actually getting it. This includes PA form generation and submission, appeals, enrollment forms, benefit verifications, PA renewal tracking, and patient communication. [1]
- **Acceptable Input:** Electronic prescriptions (structured data), clinical notes (unstructured text/PDFs), patient records, payer policy data.
- **Output:** Completed PA forms (structured forms), appeal letters (text documents), enrollment forms, patient SMS notifications (text), pharmacy routing instructions, and portal dashboard status updates. Workflow: patient records and prescription data are pulled from the EHR (via integration) or uploaded manually; AI reads clinical documentation and matches it against payer-specific PA requirements and formulary rules; AI auto-generates PA form content within 24 hours; provider reviews and approves the completed PA in the Forus portal; Forus submits to the payer and conducts status follow-ups; if denied, AI analyzes the denial reason and generates an appeal letter drawing on clinical documentation and payer-specific appeal strategies; provider reviews and approves the appeal letter before submission; the system continuously learns from case outcomes.
- **Role in Decision-Making:** The platform automates administrative work and does not make clinical decisions.
- **Intended Users:** Doctors and their staff, including providers of all sizes from 1-2 provider private practices to large physician groups and health systems. Provider must be able to e-prescribe (electronic prescriptions only; Forus does not currently support non-eRx practices). [1][12][5]
- **Target Patient Population:** All U.S. patients who are prescribed medications requiring prior authorization. Forus supports every medication, insurance, and pharmacy, including both retail and specialty drugs. [1]

## 4) Risks and Limitations
- **Known Performance Limitations:** Based on publicly available third-party reviews and developer materials: Forus is designed for medication prior authorizations and may have limited capability for non-medication PA categories (e.g., procedures, imaging, DME). Performance may vary for complex or unusual cases with 'snags from insurance' or when patients do not respond to Forus's outreach prompts. Requires patient engagement (patients must interact with SMS prompts for certain steps). Not a complete replacement for dedicated PA specialists in complex, high-volume, or multi-category authorization environments. Requires EHR e-prescribing capability; does not support fax or phone-based prescribing workflows. Specific AI model limitations and error rates are not publicly disclosed. [6]
- **Skin Type Representation & Equity:** Not formally measured or disclosed. Forus's platform is administrative in nature, so skin tone representation is not directly applicable to its core PA automation function. The platform's design goal of supporting 'every drug, insurance, and pharmacy' implies an intention to provide equitable access across patient populations regardless of insurance type, drug cost, or specialty. The platform includes affordability features — identifying financial assistance programs — intended to improve access for patients who may face cost barriers. [1]
- **Required Clinician Oversight:** Yes. All of Forus's work is administrative and workflow automation, starting after the clinician submits a prescription. Forus automates administrative workflow steps after the prescription is placed to help make sure the patient gets the medication. [1]

## 5) Mechanism and Development
- **Model Type:** AI-powered workflow automation platform using a human-in-the-loop approach, combining natural language processing (NLP) for reading clinical records and generating PA forms and appeal letters, machine learning for predicting PA approval likelihood, identifying optimal appeal strategies, and recognizing payer-specific patterns from historical data. [7] Includes rules-based automation for payer-specific PA form completion and formulary/policy matching. The platform learns from each processed case, with the Clinical Intelligence team (led by Adam Harris, MD) embedded in product design and QA. [2]
- **Training Data:** Not publicly disclosed. The platform — Forus, previously called Tandem — has machine learning models trained on proprietary datasets of prior authorization interactions collected through the platform (described as 'first-party data' and 'millions of prior authorization interactions'). The developer does not publicly specify which large language models or foundation models underlie the NLP capabilities. Forus's specific foundation models are not confirmed publicly. [7]
- **Model Development & Validation:** No external or independent validation process is publicly disclosed. [1] The platform's engineering blog describes how Forus employs LLM-as-judge evaluator systems for quality monitoring. [13] Case studies from individual practices are available on the Forus blog, including how Goodman Dermatology helps patients access medications after denials. [14]
- **Clinical Trial:** Not disclosed
- **Performance:** Traditional model performance metrics are not available; however performance metrics from individual case studies can be found on Forus's website. [1] From Forus's case studies on its blog: at one practice called Family Allergy and Asthma, Forus cut PA turnaround time from 7+ days to 1.1 and reduced per-patient workload by 70%. [15] At another, called DOCS Dermatology, they helped achieve same-day submission and approvals in <1 day. [16]
- **Performance — PA turnaround time (Family Allergy and Asthma):** 1.1 days (from 7+ days)
- **Performance — Per-patient workload reduction (Family Allergy and Asthma):** 70%
- **Performance — PA approval time (DOCS Dermatology):** <1 day (same-day submission)
- **Limitations in Evaluating Performance:** Based on publicly available third-party reviews and developer materials: Forus is designed for medication prior authorizations and may have limited capability for non-medication PA categories (e.g., procedures, imaging, DME). Performance may vary for complex or unusual cases with 'snags from insurance' or when patients do not respond to Forus's outreach prompts. Requires patient engagement (patients must interact with SMS prompts for certain steps). Not a complete replacement for dedicated PA specialists in complex, high-volume, or multi-category authorization environments. Requires EHR e-prescribing capability; does not support fax or phone-based prescribing workflows. The primary limitation for evaluation is the lack of peer-reviewed data. [6]

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Platform undergoes continuous improvement. The Clinical Intelligence team continuously identifies patterns, adapts to payer policy changes, and refines workflows based on real-world outcomes. [2]
- **Scheduled Updates:** Per the developer, platform undergoes continuous updates and iterative improvement.
- **Inquiries / Report an Issue:** provider-support@forus.com | https://forus.com/ [1]

## References
[1] https://forus.com/
[2] https://forus.com/stories/why-thousands-of-providers-trust-forus
[3] https://www.openevidence.com/announcements/openevidence-and-tandem-partner-to-streamline-evidence-based-prescribing-and-prior-authorizations
[4] https://techfundingnews.com/tandem-1b-valuation-100m-round/
[5] https://yourpractice.withtandem.com/prior-authorization-software
[6] https://datamatrixmedical.com/tandem-ai-prior-authorization-reviews-compared-to-prior-authorization-specialists/
[7] https://entrepreneurloop.com/tandem-ai-prescription-startup-billion-valuation-2026/
[8] https://www.businesswire.com/news/home/20260402254260/en/OpenEvidence-and-Tandem-Partner-to-Streamline-Evidence-Based-Prescribing-and-Prior-Authorizations
[9] https://www.linkedin.com/company/withtandem
[10] https://pymnts.com/healthcare/2026/tandem-technology-raise-100-million-dollars-prescription-automation/
[11] https://www.bloomberg.com/news/articles/2026-01-26/ai-for-prescriptions-startup-tandem-lands-1-billion-valuation
[12] https://forus.com/stories/a-field-reps-guide-to-forus
[13] https://build.forus.com/how-we-evaluate-our-llm-judge-a-perturbation-based-approach
[14] https://forus.com/stories
[15] https://forus.com/stories/family-allergy-and-asthmas-prior-authorization-transformation
[16] https://forus.com/stories/how-docs-dermatology-accelerated-medication-access-across-140-locations
