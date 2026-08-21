---
schema_version: clinical-model-card-2.0
---

# [DermaSensor](https://www.dermasensor.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** DermaSensor [2]
- **Developer:** DermaSensor, Inc. [2]
- **Regulatory Approval Status:** FDA De Novo granted (DEN230008). [1,2]
- **Regulatory Approval Date:** Not disclosed on the cited FDA summary pages.
- **Version:** Published clinical validation materials report algorithm version 1.0 at study time, later revised to algorithm version 3.0 with reanalysis on the updated device/algorithm. [3]
- **Last Updated:** 2026-08-21
- **Availability:** Available for prescription use by physicians in clinical settings; not intended for at-home use. [2]

## 2) Summary
- **Summary:** The DermaSensor device uses elastic scattering spectroscopy (ESS) and an AI/ML algorithm applied non-invasively to intact skin lesions. It provides results as “Monitor” or “Investigate Further,” with a similarity score for positive results. It is intended to assist physicians, particularly non-dermatologists, with referral decisions and is not a standalone diagnostic tool. [2,3]

## 3) Intended Use
- **Medical Purpose:** To evaluate skin lesions suggestive of melanoma, basal cell carcinoma, and/or squamous cell carcinoma in patients aged 40 and above to assist referral decisions to a dermatologist. Not a population screening tool or standalone diagnostic. [2]
- **Acceptable Input:** ESS spectral recordings from intact primary skin lesions suspected of melanoma, BCC, or SCC in patients aged 40+. Lesions should not be previously biopsied, recurrent, or metastatic; on scars, tattoos, sunburned skin, or hairy areas; or on palms, soles, mucosal surfaces, genitals, ears, within 1 cm of the eye, or under nails. [2]
- **Output:** “Monitor” (negative) or “Investigate Further” (positive), based on analysis of backscattered light spectra by a proprietary ML-derived classifier. For “Investigate Further” results, a Similarity Score of 1–10 is displayed, with higher scores indicating greater similarity to malignant lesions. [2,3]
- **Role in Decision-Making:** Adjunctive, software-aided clinical decision support for physicians (including those not trained in dermatology) making referral decisions. It does not replace biopsy, pathology, or physician judgment. [2]
- **Intended Users:** Physicians and trained healthcare professionals in clinical settings, including primary care physicians not specialized in dermatology. [2]
- **Target Patient Population:** Patients aged 40+ with lesions suggestive of melanoma, BCC, and/or SCC; primary lesions only, subject to labeled anatomic and clinical exclusions. [2]

## 4) Risks and Limitations
- **Known Performance Limitations:** Performance has not been specifically evaluated in patients with increased skin-cancer risk (e.g., inherited/drug-induced photosensitivity, genetic predisposition, immune compromise). Not tested on rare skin cancers outside melanoma/BCC/SCC intent. Not for previously biopsied, recurrent, or metastatic lesions; scars, tattoos, sunburned skin, hairy areas; or palms, soles, mucosa, genitals, ears, within 1 cm of the eye, or under nails. [2]
- **Skin Type Representation & Equity:** Less melanoma sensitivity data are available for Fitzpatrick phototypes IV–VI; referral for suspicious pigmented lesions in these groups should remain driven by clinical concern. Training and tuning datasets included a majority of Fitzpatrick phototypes I–III and individuals who self-identified as White. [2]
- **Required Clinician Oversight:** Yes — prescription device operated by trained healthcare professionals; not for at-home use and does not replace physician judgment. [2]

## 5) Mechanism and Development
- **Model Type:** AI/ML software algorithm using Elastic Scattering Spectroscopy (ESS). Published validation materials describe a final architecture of 10 neural networks trained on different architectures and training-set variations, including a feedforward network and deep networks based on a ResNet-18 architecture adapted for ESS spectral inputs. [3]
- **Training Data:** Published materials describe training on an expansive ESS databank of over 10,000 readings from over 2,000 lesions across multiple health care settings. [3]
- **Training Data (FDA review demographics):** FDA review materials state the training dataset contained 950 lesions contributing ~4,200 spectra, with majority older patients (age 60–79), Fitzpatrick I–III, self-identified White patients, and head/neck lesion predominance. [2]
- **Model Development & Validation:** Prospective, investigator-blinded multicenter clinical validation at 4 U.S. sites enrolled 614 lesions from 394 participants and compared device output with histopathologic evaluation. [3] [Publication](https://www.bu.edu/bmo/files/2024/02/Dermasensor-paper-2.pdf)
- **Clinical Trial:** FDA materials describe the DERM-SUCCESS pivotal clinical study assessing standalone device sensitivity/specificity versus ground-truth diagnosis. [2]
- **Clinical Trial (companion reader study):** FDA materials also describe DERM-SUCCESS companion multi-reader / multi-case studies, including an initial reader study with 108 readers trained in internal medicine or family practice. [2]
- **Performance:** In the published 4-site clinical validation analysis, overall device sensitivity was 97.04% and specificity 26.22%; NPV 89.58% and PPV 57.54%. No statistically significant difference was found between device and dermatologist sensitivity (P = .8203). [3]
- **Performance — Overall Sensitivity:** 97.04% (Published clinical validation cohort) [3]
- **Performance — Sensitivity:** 96.67% (Melanoma, including high-risk melanocytic pathologies) [3]
- **Performance — Sensitivity:** 97.22% (Basal cell carcinoma) [3]
- **Performance — Sensitivity:** 97.01% (Squamous cell carcinoma) [3]
- **Performance — Overall Specificity:** 26.22% (Published clinical validation cohort) [3]
- **Performance — Overall NPV:** 89.58% (Published clinical validation cohort) [3]
- **Performance — Overall PPV:** 57.54% (Published clinical validation cohort) [3]
- **Performance — DERM-SUCCESS overall malignancy sensitivity:** 95.5% (FDA review of pivotal study) [2]
- **Limitations in Evaluating Performance:** In the published validation analysis, dermatologist specificity was higher than device specificity (56.10% vs 26.22%), assuming unbiopsied lesions enrolled by dermatologists were benign. [3]
- **Limitations in Evaluating Performance (postmarket):** FDA requires postmarket surveillance to confirm performance in U.S.-representative demographics, including Fitzpatrick IV–VI groups with limited premarket melanoma representation or subgroups with sensitivity below 90%. [1]

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** FDA-mandated postmarket surveillance, including clinical performance testing in demographic groups representative of the U.S. population (e.g., Fitzpatrick IV–VI). Progress reporting includes enrollment milestones (e.g., first subject within 6 months) and annual reporting thereafter until study completion requirements are met. [1]
- **Scheduled Updates:** Not disclosed in cited FDA materials.
- **Inquiries / Report an Issue:** https://www.dermasensor.com/customer-portal/#Submit-Support-Request

## References
[1] https://www.accessdata.fda.gov/cdrh_docs/pdf23/DEN230008.pdf
[2] https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN230008.pdf
[3] https://www.bu.edu/bmo/files/2024/02/Dermasensor-paper-2.pdf
