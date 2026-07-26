---
schema_version: clinical-model-card-2.0
---

# [DermaSensor](https://www.dermasensor.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** DermaSensor [5]
- **Developer:** DermaSensor [5]
- **Regulatory Approval Status:** Regulatory Status Unknown
- **Regulatory Approval Date:** Not disclosed
- **Version:** 3.0 [5]
- **Last Updated:** 2026-07-25
- **Availability:** Available for prescription use by physicians in clinical settings; not intended for at-home use.

## 2) Summary
- **Summary:** The DermaSensor device uses optical spectroscopy and an AI/ML algorithm applied non-invasively to intact skin lesions. It provides results as "Monitor" or "Investigate Further," with a similarity score for positive results. This device is intended to assist physicians, particularly non-dermatologists, in evaluating suspicious skin lesions to aid referral decisions, but it is not a standalone diagnostic tool. [5]

## 3) Intended Use
- **Medical Purpose:** To evaluate skin lesions suggestive of melanoma, basal cell carcinoma, and/or squamous cell carcinoma in patients aged 40 and above to assist in the decision regarding referral to a dermatologist. It is used to assist in evaluating suspicious skin lesions in clinical settings, not as a screening tool or standalone diagnostic. [2,3,7]
- **Acceptable Input:** Elastic Scattering Spectroscopy (ESS) spectral recordings from intact primary skin lesions suspected of melanoma, basal cell carcinoma, or squamous cell carcinoma, in patients aged 40 and above. Lesions should not be previously biopsied, recurrent, metastatic, on scars, tattoos, sunburned skin, hairy areas, palms, soles, mucosal surfaces, genitals, ears, within 1 cm of the eye, or under nails. [2,4]
- **Output:** The device provides results as "Monitor" for a negative result or "Investigate Further" for a positive result, based on analysis of backscattered light spectra by a proprietary ML-derived classifier algorithm. For "Investigate Further" results, a Similarity Score of 1-10 is displayed, indicating greater similarity to malignant lesions seen in training data. [2,4]
- **Role in Decision-Making:** The device is an adjunctive, software-aided diagnostic tool intended to assist physicians, particularly those not trained in dermatology, in evaluating suspicious skin lesions and making referral decisions. It is not a standalone diagnostic and does not replace biopsy, pathology, or physician judgment. [2,7]
- **Intended Users:** Physicians and trained healthcare professionals in clinical settings, including primary care physicians, especially those not trained in the clinical diagnosis and management of skin cancer. [2,7]
- **Target Patient Population:** Patients aged 40 and above with skin lesions suggestive of melanoma, basal cell carcinoma, and/or squamous cell carcinoma. The device is for use on primary lesions only, not previously biopsied, recurrent, or metastatic lesions, or lesions on certain anatomical locations like palms, soles, mucosal surfaces, genitals, ears, within 1 cm of the eye, or under nails. [2]

## 4) Risks and Limitations
- **Known Performance Limitations:** Performance has not been specifically evaluated in patients with increased risk for skin cancer (e.g., inherited/drug-induced photosensitivity, genetic predisposition, immune compromise). It is not tested on rare skin cancer types or lesions suggestive of malignancies other than melanoma, BCC, and SCC. It is not for use on lesions previously biopsied, recurrent, or metastatic; on scars, tattoos, sunburned skin, hairy areas; or on palms, soles, mucosal surfaces, genitals, ears, within 1 cm of the eye, or under nails. [2]
- **Skin Type Representation & Equity:** Less data is available for sensitivity of the DermaSensor device for melanoma in Fitzpatrick skin phototypes IV-VI due to lower prevalence of skin cancer in these groups. The decision to refer patients with suspicious pigmented lesions in this group should be primarily based on clinical concern. The training and tuning datasets included a majority of Fitzpatrick phototypes I-III and individuals who self-identified as White. [2]
- **Required Clinician Oversight:** Yes, the device is a prescription device and must be operated by trained healthcare professionals. It is not intended for at-home use and does not replace physician judgment or clinical decision-making. [2,7]

## 5) Mechanism and Development
- **Model Type:** Artificial intelligence/machine learning (AI/ML) based software algorithm utilizing Elastic Scattering Spectroscopy (ESS). The final architecture has 10 neural networks trained on different architectures and training set variations, including feedforward neural networks and deep neural networks based on ResNet-18 architecture. [2,4]
- **Training Data:** The device was trained on an expansive databank of spectral scans of over 2000 lesions from multiple health care settings, comprising over 10,000 readings. The training dataset contained 950 lesions (approximately 4,200 spectra) and included a majority of older patients (age 60-79), Fitzpatrick phototypes I-III, and individuals who self-identified as White. Lesions on the head and neck constituted the majority of the training data. The dataset included BCC, SCC, melanoma (including severely atypical nevi), and various benign lesion mimics. [2,4]
- **Model Development & Validation:** The DermaSensor device utilizes optical spectroscopy and an AI/ML-based software algorithm. Algorithm development involved initial work on ESS technology to identify optimal wavelength range and spectral features. Clinical development included blinded, multicenter clinical studies. A prospective, multicenter clinical validation study was conducted at 4 US investigational sites, enrolling 614 lesions from 394 participants. The device was validated against histopathologic evaluation by expert dermatologists. [Publication](https://www.bu.edu/bmo/files/2024/02/Dermasensor-paper-2.pdf) [2,4]
- **Clinical Trial:** NCT05126173 — The device was evaluated in the DERM-SUCCESS study, an observational study led by the Mayo Clinic across 22 study centers, enrolling over 1000 patients. A companion clinical utility study also investigated DermaSensor’s usage with 108 physicians. [3,4]
- **Performance:** In a clinical validation study, the overall device sensitivity was 97.04% and specificity was 26.22%. No statistically significant difference was found between the device and dermatologist sensitivity (P = .8203). The overall Negative Predictive Value (NPV) was 89.58% and Positive Predictive Value (PPV) was 57.54%. A separate study showed 96% sensitivity across all 224 types of skin cancers and a 97% chance of negative results being benign. [3,4]
- **Performance — Overall Sensitivity:** 97.04% (All lesions in clinical validation study)
- **Performance — Sensitivity:** 96.67% (Melanoma (includes high-risk melanocytic pathologies))
- **Performance — Sensitivity:** 97.22% (Basal Cell Carcinoma (BCC))
- **Performance — Sensitivity:** 97.01% (Squamous Cell Carcinoma (SCC))
- **Performance — Overall Specificity:** 26.22% (All lesions in clinical validation study)
- **Performance — Overall Negative Predictive Value (NPV):** 89.58% (All lesions in clinical validation study)
- **Performance — Overall Positive Predictive Value (PPV):** 57.54% (All lesions in clinical validation study)
- **Performance — Sensitivity:** 96% (Across all 224 types of skin cancers (DERM-SUCCESS study))
- **Performance — Negative Results Chance of Being Benign:** 97% (Across all skin cancers (DERM-SUCCESS study))
- **Limitations in Evaluating Performance:** The overall specificity of the dermatologists was higher than that of the ESS device, assuming all unbiopsied lesions enrolled by dermatologists were benign. FDA requires postmarket surveillance to confirm performance in demographic groups representative of the U.S. population, including those with limited representation of melanomas in premarket studies (e.g., Fitzpatrick skin phototypes IV, V, and VI) or in whom sensitivity was lower than 90%. [1,4]

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Mandated postmarket surveillance by the FDA, including clinical validation performance testing in patients from demographic groups representative of the U.S. population (e.g., Fitzpatrick skin phototypes IV, V, and VI) to assess impact on effectiveness. Progress reports are required annually, or every 6 months if enrollment milestones are not met, until the final study report is submitted three months from study completion.
- **Scheduled Updates:** Not disclosed
- **Inquiries / Report an Issue:** https://www.dermasensor.com/ [6]

## References
[1] https://www.accessdata.fda.gov/cdrh_docs/pdf23/DEN230008.pdf
[2] https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN230008.pdf
[3] https://www.aimatmelanoma.org/ai-powered-diagnostics
[4] https://www.bu.edu/bmo/files/2024/02/Dermasensor-paper-2.pdf
[5] https://www.dermasensor.com/
[6] https://www.dermasensor.com/docs
[7] https://www.dermasensor.com/find-a-physician
