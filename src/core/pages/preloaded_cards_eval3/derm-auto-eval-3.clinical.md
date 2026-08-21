---
schema_version: clinical-model-card-2.0
---

# [DERM](https://skin-analytics.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** DERM [1]
- **Developer:** Skin Analytics [1]
- **Regulatory Approval Status:** Class III CE marked [3]
- **Regulatory Approval Date:** Not disclosed
- **Version:** DERM denotes Deep Ensemble for the Recognition of Malignancy; device labeling is documented in SA-001165-LB Instructions for Use. [1]
- **Last Updated:** 2026-08-21
- **Availability:** Deployed in NHS pathway settings as an organizational AI dermatology / teledermatology service (not a consumer self-diagnostic app). Specific partner counts and commercial partnerships are not restated here unless supported by non-walled cited sources. [1,4]

## 2) Summary
- **Summary:** DERM is a Class III CE-marked AI medical device. [3]
- **Summary (function):** DERM analyzes dermoscopic images of skin lesions to provide a suspected diagnosis and referral/management recommendation (e.g., refer, discharge, monitor), supporting skin-cancer pathway triage and conservation of dermatologist capacity. [1]

## 3) Intended Use
- **Medical Purpose:** Screening, triage, and assessment of cutaneous lesions suspicious for skin cancer to help route non-cancerous lesions away from cancer pathways and conserve specialist capacity. [1,4]
- **Acceptable Input:** Dermoscopic images captured with approved hardware (camera device, dermoscope, and connection kit, typically a smartphone with an attachment). [1]
- **Acceptable Input (history):** Patient medical history can also be provided via a Patient Initiated Questionnaire in teledermatology deployments. [4]
- **Output:** Suspected diagnosis and referral/management recommendation; outputs can include management instructions such as refer, discharge, or monitor, and lesion class labels (e.g., possible melanoma, probable BCC). [1]
- **Role in Decision-Making:** Autonomous AI medical device capable of issuing management instructions such as discharge without a second clinician read for labeled use cases; can also augment clinician decision-making. [1,4]
- **Intended Users:** Primary care and secondary care clinicians are intended users of DERM outputs in pathway deployments; image capture may involve photographers or patients, but output interpretation is for trained clinical users. [1,4]
- **Target Patient Population:** Patients aged 18 years or over with cutaneous lesions where there is suspicion of skin cancer, in any body location except where specific exclusions apply. [1]

## 4) Risks and Limitations
- **Known Performance Limitations:** Should not be used on patients under 18; for non-cancer skin conditions; for treatment monitoring or staging; or on non-dermoscopic images. Contraindications include open/ulcerated lesions, lesions obscured by hair/tattoos/scars, lesions beneath nails, in eyes, on mucosal surfaces, on soles/palms, and previously biopsied lesions. DERM does not provide a definitive skin-cancer diagnosis. [1]
- **Skin Type Representation & Equity:** Primarily evaluated on Fitzpatrick skin types I–IV; use caution on other skin types. [1]
- **Skin Type Representation & Equity (study mix):** In a prospective UK study cohort reported in Frontiers in Medicine, 96.9% of participants were Fitzpatrick skin types I–III. [5]
- **Required Clinician Oversight:** IFU labeling allows management instructions such as discharge without a second clinician read for labeled use cases. [1]
- **Required Clinician Oversight (regulatory posture):** Class III CE marking communications describe autonomous skin-cancer pathway use. [3]

## 5) Mechanism and Development
- **Model Type:** Artificial intelligence algorithms — Deep Ensemble for the Recognition of Malignancy (DERM). [1]
- **Training Data / Evidence base:** Evidence base includes powered prospective studies run in the UK, US, and Italy on dermoscopic images representing intended-use populations, primarily Fitzpatrick I–IV. [1]
- **Model Development & Validation:** Developed in accordance with Skin Analytics’ ISO 13485:2016 certified Quality Management System and fulfills UK/EU medical-device regulatory provisions described in the IFU. [1]
- **Regulatory classification:** Class III CE-marked AI as a Medical Device (AIaMD). [3]
- **Clinical Trial:** NCT04116983 (DERM-003 / NMSC validation). [8]
- **Clinical Trial:** NCT04123678 (DERM-005 / health-economics / teledermatology pathway study). [9]
- **Clinical Trial:** NCT05126173 (DERM-006 / US and EU validation). [10]
- **Performance:** Manufacturer communications report DERM achieving a 99.8% accuracy rate in ruling out cancer, compared with 98.9% typically attributed to dermatologists in that same communication. [3]
- **Performance — Melanoma pathway sensitivity (independent evaluation):** An NHS AI in Health and Care Award evaluation reported high pathway sensitivity for malignant melanoma (97%). [6]
- **Performance — Prospective study communication:** A Skin Analytics news summary of a prospective study reported that DERM could identify melanoma with similar accuracy to skin cancer specialists in a study of over 1,500 lesions. [7]
- **Limitations in Evaluating Performance:** Manufacturer headline metrics and pathway evaluations should be interpreted alongside study-specific endpoints; evaluation has primarily been on Fitzpatrick I–IV, and some prospective cohorts are heavily skewed toward lighter phototypes. [1,5]

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Developed under an ISO 13485:2016 certified Quality Management System. [1]
- **Plans for Ongoing Monitoring (partner reporting):** G-Cloud service materials describe quarterly business reviews and monthly performance reports covering service usage, exclusions/exceptions, image-quality audits, discharge rates, and outcomes. [4]
- **Scheduled Updates:** Service materials allow limited daily downtime windows and up to eight hours per calendar month of scheduled maintenance, with partners notified at least two working days in advance. Exact daily clock times may vary by contract. [4]
- **Inquiries / Report an Issue:** support@skinanalytics.co.uk

## References
[1] https://skin-analytics.com/wp-content/uploads/2025/04/SA-001165-LB-13-DERM-Instructions-for-Use.pdf
[2] https://skin-analytics.com/wp-content/uploads/2025/01/SA-001165-LB-v12-DERM-Instructions-for-Use_20Jan2025.pdf
[3] https://skin-analytics.com/news/regulatory-certification/derm-class-iii-ce-mark/
[4] https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/422642264464760
[5] https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1288521/full
[6] https://unityinsights.co.uk/our-insights/ai-in-health-and-care-award-skin-analytics-evaluation/
[7] https://skin-analytics.com/news/skin-cancer/prospective-study-shows-ai-as-accurate-as-clinical-specialist/
[8] https://clinicaltrials.gov/study/NCT04116983
[9] https://clinicaltrials.gov/study/NCT04123678
[10] https://clinicaltrials.gov/study/NCT05126173
