---
schema_version: clinical-model-card-1.0
---

# DermaSensor — Clinical Model Card

## 1) Metadata
- **Model Name:** DermaSensor
- **Developer:** DermaSensor Inc. (founders include Dr. Maurice Ferre and Christopher Dewey). Company history describes development of Elastic Scattering Spectroscopy (ESS) and a proprietary machine learning algorithm trained on histopathology-confirmed lesions.
- **Regulatory Approval Status:** FDA Cleared
- **Regulatory Approval Date:** Not disclosed
- **Version:** 3.0.2
- **Last Updated:** 2026-07-11
- **Availability:** FDA-cleared and available for sale in the U.S.; CE marked; waitlist/limited state availability described publicly.

## 2) Summary
- **Summary:** Connected handheld device intended to help frontline providers assess lesions suspicious for melanoma/BCC/SCC and inform referral decisions, producing results in seconds. Identified suspicious lesion is scanned with five spectral recordings; algorithm returns “Investigate Further” or “Monitor,” with a 1–10 similarity score for malignancy patterns. Intended for use alongside clinician assessment and not as a screening tool or sole diagnostic criterion.

## 3) Intended Use
- **Medical Purpose:** Identified suspicious lesion is scanned with five spectral recordings; algorithm returns “Investigate Further” or “Monitor,” with a 1–10 similarity score for malignancy patterns. Intended for use alongside clinician assessment and not as a screening tool or sole diagnostic criterion.
- **Acceptable Input:** Spectral recordings from the scanned lesion. Input: spectral signal; Output: categorical result + numeric score intended to guide referral decisions. Three-step process (identify lesion → apply device/record spectra → receive result).
- **Output:** Output includes referral-oriented risk classification and score; intended to improve triage and reduce missed cancers by clinicians in reader studies.
- **Role in Decision-Making:** Provides adjunctive referral support for physicians evaluating suspicious lesions; does not replace clinician judgment, biopsy, or definitive diagnosis.
- **Intended Users:** Qualified healthcare professionals in clinical settings; marketed for non-dermatology providers in primary care and related outpatient settings. Clinical assessment skills for lesion selection and interpretation; device is an adjunct to clinical judgment.
- **Target Patient Population:** Patients (often 40+) with lesions already judged suspicious for melanoma/BCC/SCC where a referral decision is being considered.

## 4) Risks and Limitations
- **Known Failure Modes:** 
- **Unsupported Clinical Scenarios:** 
- **Unsupported Use Cases:** Not for screening or unsupervised population triage. Not the sole basis for diagnosis or referral decisions.
- **Required Clinician Oversight:** Independent clinical assessment, including visual lesion evaluation, is required before and alongside device use. Definitive diagnosis requires clinician judgment and biopsy or pathology confirmation where clinically indicated.

## 5) Mechanism and Development
- **Model Type:** AI/ML classifier analyzing Elastic Scattering Spectroscopy (ESS) recordings from intact skin lesions.
- **Training Data:** Not disclosed
- **Model Development & Validation:** [Publication](PubMed entry and related publications. [16])
- **Clinical Trial:** Study evidence and summaries described in the clinical evidence PDF.
- **Performance:** Public materials and study summaries report no device-related safety issues; primary safety concerns are clinical consequences of false results. Human-in-the-loop clinical judgment remains required; device should be used only as intended.
- **Limitations in Evaluating Performance:** Not disclosed

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Algorithm is described as “locked” with periodic revalidation/updates requiring FDA clearance.
- **Scheduled Updates:** Not disclosed
- **Inquiries / Report an Issue:** General inquiries and support via knowledge base; contact page
