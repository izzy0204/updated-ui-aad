Tandem

1) Metadata  
- Model name:   
  [withtandem.com](http://withtandem.com)   
- Developer:   
  Tandem Technology, Inc. Founder & CEO: Sahir Jaggi. Clinical Intelligence led by Adam Harris, \[2\] MD (former VP of Applied AI at Oscar Health; Clinical Assistant Professor, NYU School of Medicine) and Kathleen Alvarez, NP (Yale School of Nursing).  
- Regulatory Approval Status:  
  No FDA clearance or approval disclosed or required for this administrative workflow automation tool. Platform is HIPAA-compliant and SOC 2 Type II certified. Not classified as a medical device by the developer. \[5\]  
- Version:   
  Not publicly disclosed. Platform undergoes continuous updates and iterative improvement. Company founded 2023\. Product commercially available 2023-2024. As of early 2026, supports millions of patients annually. \[3,4\]  
- Availability:   
  Available in the United States. Accessible via website for providers (withtandem.com) and patients (withtandem.com/patients). Supports providers across all 50 states. Not known to be available outside the U.S. \[1\]  
- Summary:  
  Tandem is an AI-powered platform that automates the end-to-end medication access process, including prior authorization (PA) submission, appeals, pharmacy routing, affordability/enrollment in patient assistance programs, and real-time patient communication. It integrates with provider EHRs (including Epic, athenahealth, eClinicalWorks, ModMed, and others) and is offered free of charge to providers and patients. Tandem is backed by major investors and reported a \~$1B valuation as of January 2026\. \[1,4\]  
2) Intended Use  
- Medical Purpose:  
  Intended for physician practices and their staff to automate all steps of obtaining prior authorization for prescribed medications, including PA form generation and submission, appeals, enrollment in manufacturer support programs, pharmacy navigation, and patient communication. \[1\] Also intended for patients to receive real-time updates and support throughout the medication access process.  
- Acceptable Input:  
  Electronic prescriptions (structured data), clinical notes (unstructured text/PDFs), patient records, payer policy data.  
- Output:  
  Completed PA forms (structured forms), appeal letters (text documents), enrollment forms, patient SMS notifications (text), pharmacy routing instructions, portal dashboard status updates.  
  How output is generated:  
  1\. Patient records and prescription data are pulled from the EHR (via integration) or uploaded manually. 2\. AI reads clinical documentation and matches it against payer-specific PA requirements and formulary rules. 3\. AI auto-generates PA form content within 24 hours. 4\. Provider reviews and approves the completed PA in the Tandem portal. 5\. Tandem submits to the payer and conducts status follow-ups. 6\. If denied, AI analyzes the denial reason and generates an appeal letter drawing on clinical documentation and payer-specific appeal strategies learned from historical data. 7\. Provider reviews and approves appeal letter before submission. 8\. The system continuously learns from case outcomes to improve future predictions and form generation.  
- Role in Decision-Making:  
  The platform automates administrative work and does not make clinical decisions.  
- Intended Users:   
  Physicians, nurse practitioners, and practice staff at outpatient physician practices (all specialties, including dermatology, rheumatology, gastroenterology, urology, and others) who prescribe medications requiring prior authorization. Also available directly to patients waiting to receive those medications. \[1\] No specialized technical knowledge required. Designed for clinical and administrative staff in physician practices. Provider must be able to e-prescribe (electronic prescriptions only; Tandem does not currently support non-eRx practices). \[5\]  
- Targeted Patient population:   
  All U.S. patients requiring medications with prior authorization. Tandem supports every drug, insurance plan, and pharmacy with no restrictions — including both retail and specialty drugs. Supports all major payers and PBMs. As of 2026, Tandem supports millions of patients annually. \[1,3\]  
3) Risks and Limitations  
- Known Performance Limitations:  
  Based on publicly available third-party reviews and developer materials: Tandem is designed for medication prior authorizations and may have limited capability for non-medication PA categories (e.g., procedures, imaging, DME). \[6\] Performance may vary for complex or unusual cases with 'snags from insurance' or when patients do not respond to Tandem's outreach prompts. Requires patient engagement (patients must interact with SMS prompts for certain steps). Not a complete replacement for dedicated PA specialists in complex, high-volume, or multi-category authorization environments. Requires EHR e-prescribing capability; does not support fax or phone-based prescribing workflows. Specific AI model limitations and error rates are not publicly disclosed.  
- Skin type representation & Equity:  
  Not formally measured or disclosed. Tandem's platform is administrative in nature (does not analyze clinical images or make clinical diagnoses), so skin tone representation is not directly applicable to its core PA automation function. The platform's design goal of supporting 'every drug, every insurance, and every pharmacy' implies an intention to provide equitable access across patient populations regardless of insurance type, drug cost, or specialty. \[1\] The platform includes affordability features — identifying financial assistance programs, cash options, and patient assistance programs — intended to improve access for patients who may face cost barriers.  
- Required Clinician Oversight:  
  The platform's administrative nature and human-in-the-loop design (provider must approve all PA forms and appeal letters) mitigate clinical risk. Security certifications provide assurance of data protection. The platform does not make clinical decisions. \[5\]  
4) Mechanism and Development  
- Model Type:  
  AI-powered workflow automation platform using a human-in-the-loop approach, combining natural language processing (NLP) for reading clinical records and generating PA forms and appeal letters, machine learning for predicting PA approval likelihood, identifying optimal appeal strategies, and recognizing payer-specific patterns from historical data. \[7\] Includes rules-based automation for payer-specific PA form completion and formulary/policy matching. The platform learns from each processed case, with the Clinical Intelligence team (led by Adam Harris, MD) embedded in product design and QA.   
- Training Data:  
  Not publicly disclosed. The platform's machine learning models are trained on proprietary datasets of prior authorization interactions collected through the platform (described as 'first-party data' and 'millions of prior authorization interactions'). \[7\] The developer does not publicly specify which large language models or foundation models underlie the NLP capabilities. The CTO of Tandem (a different European entity with the same name) noted that competitive advantage comes from product design and iteration rather than training proprietary models from scratch, suggesting use of existing LLM infrastructure, but withtandem.com's specific foundation models are not confirmed publicly. \[4\]  
- Model Development & Validation:  
  No external or independent validation process is publicly disclosed. Metrics are developer-reported. Case studies from individual practices (dermatology, gastroenterology, rheumatology, urology) are available on the Tandem blog \[1\], including: How Goodman Dermatology helps patients access medications after denials, How Nimbus Health prescribes complex medications at scale with Tandem, How a GI Innovator (GI Partners of Illinois) Transformed Practice Operations with AI, Dermatology Specialists of Fort Worth PLLC case study, MedicoCX GPO case study.  
- Clinical Trial:  
  None identified. No peer-reviewed publications found.  
- Performance:  
  From Tandem's website and marketing materials: \+20% higher PA approval rate compared to baseline, \+70% faster medication access for PA prescriptions, 60 minutes saved per PA on average, \~100% of PAs initiated same-day, \<7 days from prescription to PA approval (practice-level metric), Reduction from \~1 month to days for patient medication receipt (cited by Texas Gastroenterology practice testimonial), Platform supports millions of patients annually across all 50 states, Clinicians across thousands of practices rely on Tandem daily \[1\].   
- Limitations in evaluating performance:  
  Based on publicly available third-party reviews and developer materials: Tandem is designed for medication prior authorizations and may have limited capability for non-medication PA categories (e.g., procedures, imaging, DME). \[6\] Performance may vary for complex or unusual cases with 'snags from insurance' or when patients do not respond to Tandem's outreach prompts. Requires patient engagement (patients must interact with SMS prompts for certain steps). Not a complete replacement for dedicated PA specialists in complex, high-volume, or multi-category authorization environments. \[6\] Requires EHR e-prescribing capability; does not support fax or phone-based prescribing workflows. The primary limitation for evaluation is the lack of peer-reviewed data.  
5) Governance and Monitoring  
- Plans for Ongoing Maintenance:   
  Platform undergoes continuous improvement. The Clinical Intelligence team continuously identifies patterns, adapts to payer policy changes, and refines workflows based on real-world outcomes. As the platform scales, edge cases from individual practices become system-wide improvements. \[1\]  
- Scheduled Updates:  
  Per the developer, platform undergoes continuous updates and iterative improvement.   
- Process for inquiries or to report an issue:  
  [security@withtandem.com](mailto:security@withtandem.com)  (security issues)  
  [providers@withtandem.com](mailto:providers@withtandem.com)  (provider inquiries)   
6) References  
- 1\. [https://withtandem.com/](https://withtandem.com/) — Tandem. withtandem.com — AI for Prior Authorizations & Medication Access Support.  
- 2\. [https://pear.vc/companies/tandem/](https://pear.vc/companies/tandem/) — Pear VC. Tandem Company Profile.  
- 3\. [https://www.openevidence.com/announcements/openevidence-and-tandem-partner-to-streamline-evidence-based-prescribing-and-prior-authorizations](https://www.openevidence.com/announcements/openevidence-and-tandem-partner-to-streamline-evidence-based-prescribing-and-prior-authorizations) — OpenEvidence. OpenEvidence and Tandem Partner to Streamline Evidence-Based Prescribing and Prior Authorizations. April 2, 2026\.  
- 4\. [https://techfundingnews.com/tandem-1b-valuation-100m-round/](https://techfundingnews.com/tandem-1b-valuation-100m-round/) — TechFundingNews. Accel to Lead $100M for Healthcare AI Tandem at Unicorn Level. January 27, 2026\.  
- 5\. [https://yourpractice.withtandem.com/prior-authorization-software](https://yourpractice.withtandem.com/prior-authorization-software) — Tandem Practice Portal. Automate Prior Authorizations — Save Hours Every Week.  
- 6\. [https://datamatrixmedical.com/tandem-ai-prior-authorization-reviews-compared-to-prior-authorization-specialists/](https://datamatrixmedical.com/tandem-ai-prior-authorization-reviews-compared-to-prior-authorization-specialists/) — DataMatrix Medical. Tandem AI Compared to Prior Authorization Specialists. November 22, 2025\.  
- 7\. [https://entrepreneurloop.com/tandem-ai-prescription-startup-billion-valuation-2026/](https://entrepreneurloop.com/tandem-ai-prescription-startup-billion-valuation-2026/) — EntrepreneurLoop. Tandem AI Prescription Startup Reaches $1 Billion Valuation. January 27, 2026\.  
- 8\. [https://www.businesswire.com/news/home/20260402254260/en/OpenEvidence-and-Tandem-Partner-to-Streamline-Evidence-Based-Prescribing-and-Prior-Authorizations](https://www.businesswire.com/news/home/20260402254260/en/OpenEvidence-and-Tandem-Partner-to-Streamline-Evidence-Based-Prescribing-and-Prior-Authorizations) — Business Wire. OpenEvidence and Tandem Partner to Streamline Evidence-Based Prescribing and Prior Authorizations. April 2, 2026\.  
- 9\. [https://www.linkedin.com/company/withtandem](https://www.linkedin.com/company/withtandem) — Tandem LinkedIn. Company Page and Updates.  
- 10\. [https://pymnts.com/healthcare/2026/tandem-technology-raise-100-million-dollars-prescription-automation/](https://pymnts.com/healthcare/2026/tandem-technology-raise-100-million-dollars-prescription-automation/) — PYMNTS. Tandem Technology to Raise $100 Million for Prescription Automation. January 26, 2026\.  
- 11\. [https://www.bloomberg.com/news/articles/2026-01-26/ai-for-prescriptions-startup-tandem-lands-1-billion-valuation](https://www.bloomberg.com/news/articles/2026-01-26/ai-for-prescriptions-startup-tandem-lands-1-billion-valuation) — Bloomberg. AI-for-Prescriptions Startup Tandem Lands $1 Billion Valuation. January 26, 2026\.  
- 
