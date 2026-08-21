---
schema_version: clinical-model-card-2.0
---

# [DERM](https://skin-analytics.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** DERM
- **Developer:** SkinAnalytics
- **Regulatory Approval Status:** Class III CE marked
- **Regulatory Approval Date:** Not disclosed
- **Version:** SA-001165-LB. DERM-vA (version A) was released July 2021.
- **Last Updated:** 2026-08-21
- **Availability:** The SkinAnalytics app is associated with the medical device, DERM, and is not publicly available, but rather can be accessed through insurance pathways (the UK's national NHS or private insurance networks) after referral by a GP or dermatologist. To use it, organizations register for a DERM account with SkinAnalytics, which then integrates with physicians' teledermatology and EHR systems via API for image submission, result delivery, and automated clinical workflow triggers. It is available in the United Kingdom and European Union.

## 2) Summary
- **Summary:** DERM (Deep Ensemble for the Recognition of Malignancy), which is SkinAnalytics' Class III CE marked AI as a Medical Device (AIaMD), is built around the company's custom teledermatology platform to help triage patients to the right place, at the right time to use dermatologist resources most efficiently. DERM assesses dermoscopic images of skin lesions submitted by primary care and dermatologists seeing patients and gives a suspected diagnosis along with a referral recommendation based on the suspected diagnosis. This ensures patients with non-cancerous lesions are safely triaged away from cancer pathways to make space for patients who need them.

## 3) Intended Use
- **Medical Purpose:** DERM is an AI-based skin lesion analysis device intended for use in the screening, triage and assessment of skin lesions suspicious for skin cancer. DERM analyzes dermoscopic images of skin lesions and gives a suspected diagnosis, and relevant referral recommendation. This helps ensure that patients with non-cancerous lesions are not sent down cancer pathways and dermatologist resources are used most effectively.
- **Acceptable Input:** Physicians, including primary care doctors and dermatologists, submit dermatoscopic images of lesions suspicious for cancer from patients they are evaluating. Dermoscopic images must be captured using approved dermoscopy devices. SkinAnalytics is integrated with physicians' teledermatology and EHR systems via API for image submission, result delivery, and automated clinical workflow triggers.
- **Output:** Structured clinical assessment and referral guidance: for each lesion assessment, the results returned by DERM include the suspected diagnosis, referral recommendation, referral recommendation guidance, and analysis explanation. DERM completes image analysis in less than 20 seconds using the DERM AI model trained on skin lesion data.
- **Role in Decision-Making:** Users may use DERM and its outputs as an automated clinical management tool or to augment other clinical data points to support clinical decision-making.
- **Intended Users:** DERM is intended to be used by primary care clinicians/providers and specialty care providers (e.g. dermatologists). Necessary knowledge/expertise: clinical training in skin lesion assessment and dermoscopy, and adherence to the DERM Instructions for Use and local clinical pathways.
- **Target Patient Population:** Adults 18 years or older with skin lesions suspicious for skin cancer.

## 4) Risks and Limitations
- **Known Performance Limitations:** DERM's performance depends on the quality of the image provided, correct usage of hardware, and the settings configured on the device. DERM does not provide a definitive diagnosis and does not assess rare malignant lesions not listed in the device's list of possible outputs. DERM should not be used on: patients under age 18, for assessing non-cancer skin conditions (e.g. rashes, eczema, infectious diseases, lupus), for monitoring treatment, for staging disease, for images other than dermoscopic images of skin lesions, for images of skin lesions from anyone other than the identified patient, for open or ulcerated skin lesions, for skin lesions unable to be entirely imaged by the dermatoscope, skin lesions obscured by hair, tattoos or scars, skin lesions beneath nails, in eyes or on mucosal surfaces or on soles of feet or palms of hands, and skin lesions which have previously been biopsied.
- **Skin Type Representation & Equity:** DERM has been deployed across patients with all Fitzpatrick skin types (I-VI). Real-world data shows 6-8% of cases assessed had Fitzpatrick type V-VI skin, compared to 4.5% of NHS urgent suspected skin cancer pathway patients from Black, Asian, or mixed ethnicities. DERM correctly identified all melanomas, SCCs, and BCCs in patients with Fitzpatrick V and VI skin types since 2020. Subgroup analysis showed age, skin type, and deprivation did not change the expected distribution of cases assessed by DERM; however it is worth noting that the sample size within subgroups is limited. Darker skin types are underrepresented in the dataset (only 2.2% Fitzpatrick IV-VI in DERM-003 study), limiting generalizability for these populations. DERM cannot currently assess palmoplantar and subungual lesions, which disproportionately affects darker-skinned patients.
- **Required Clinician Oversight:** SkinAnalytics is approved to make autonomous clinical decisions without direct clinician oversight. Use of the platform can only be done via a clinician through medical referral (not directly or publicly by patients).

## 5) Mechanism and Development
- **Model Type:** Deep ensemble machine-learning architecture for dermoscopic image analysis.
- **Training Data:** Training dataset not found.
- **Model Development & Validation:** Peer-reviewed validation studies have been published on DERM's performance. [Publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/)
- **Clinical Trial:** NCT04116983 — [ClinicalTrials.gov](https://clinicaltrials.gov/study/NCT04116983) — Additional related trials: NCT04123678, NCT05126173.
- **Performance:** DERM achieved AUROC of 91.8-95.8% for melanoma detection across different camera devices, with 99.8% negative predictive value (NPV) for correctly excluding melanoma, outperforming dermatologists' NPV of 98.9%. For non-melanoma skin cancers, DERM achieved AUROC of 0.85-0.88 for squamous cell carcinoma and 0.87-0.89 for basal cell carcinoma across multiple devices. In real-world deployment, DERM demonstrated 97% pathway sensitivity for malignant melanoma, exceeding the 95% target rate. In the University of Exeter evaluation, DERM demonstrated its safety, showing high-risk cancer detection rates 26.5% higher than local published rates.
- **Performance — AUROC (melanoma):** 91.8-95.8%
- **Performance — NPV (melanoma):** 99.8%
- **Performance — AUROC (SCC):** 0.85-0.88
- **Performance — AUROC (BCC):** 0.87-0.89
- **Performance — Pathway sensitivity (malignant melanoma):** 97%
- **Performance — High-risk cancer detection vs local rates (University of Exeter):** +26.5%
- **Limitations in Evaluating Performance:** Not disclosed

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Centralized updates, monitoring, and ongoing product quality management by SkinAnalytics.
- **Scheduled Updates:** Validation includes ongoing post-market surveillance (PMS) with transparent reporting of real-world performance data, systematic processes to identify and analyze performance errors, and continuous monitoring for software updates or algorithm changes.
- **Inquiries / Report an Issue:** support@skinanalytics.co.uk | https://skin-analytics.com/

