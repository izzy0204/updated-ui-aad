---
schema_version: clinical-model-card-1.0
---

# DermaSensor — Clinical Model Card

## 1) Metadata
- **Model Name:** DermaSensor
- **Developer:** DermaSensor Inc. (founders include Dr. Maurice Ferre and Christopher Dewey). Company history describes development of Elastic Scattering Spectroscopy (ESS) and a proprietary machine learning algorithm trained on histopathology-confirmed lesions.
- **Regulatory Approval Status:** Regulatory Status Unknown
- **Regulatory Approval Date:** Not disclosed
- **Version:** Software Version: 3.0.2 (Class 2 Device Recall initiated October 13, 2025); handheld device form factor. [9]
- **Last Updated:** 2026-07-11
- **Availability:** FDA-cleared and available for sale in the U.S.; CE marked; waitlist/limited state availability described publicly.

## 2) Summary
- **Summary:** Connected handheld device intended to help frontline providers assess lesions suspicious for melanoma/BCC/SCC and inform referral decisions, producing results in seconds.

## 3) Intended Use
- **Medical Purpose:** Identified suspicious lesion is scanned with five spectral recordings; algorithm returns “Investigate Further” or “Monitor,” with a 1–10 similarity score for malignancy patterns. Intended for use alongside clinician assessment and not as a screening tool or sole diagnostic criterion.
- **Acceptable Input:** Spectral recordings from the scanned lesion. Input: spectral signal; Output: categorical result + numeric score intended to guide referral decisions. Three-step process (identify lesion → apply device/record spectra → receive result). Instructional materials and device instructions for use are referenced by the developer.
- **Output:** Output includes referral-oriented risk classification and score; intended to improve triage and reduce missed cancers by clinicians in reader studies.
- **Role in Decision-Making:** Potential harms relate to missed malignancy (false negative) or unnecessary escalation (false positive); intended as adjunctive decision support with clinician oversight. Identified suspicious lesion is scanned with five spectral recordings; algorithm returns “Investigate Further” or “Monitor,” with a 1–10 similarity score for malignancy patterns. Intended for use alongside clinician assessment and not as a screening tool or sole diagnostic criterion.
- **Intended Users:** Qualified healthcare professionals in clinical settings; marketed for non-dermatology providers in primary care and related outpatient settings. Clinical assessment skills for lesion selection and interpretation; device is an adjunct to clinical judgment.
- **Target Patient Population:** Patients (often 40+) with lesions already judged suspicious for melanoma/BCC/SCC where a referral decision is being considered.

## 4) Risks and Limitations
- **Known Failure Modes:** Performance depends on appropriate lesion selection and workflow context; false negatives/positives possible; study performance may not generalize across settings. Pivotal trial demographics and post-market testing requirements for underrepresented populations are discussed in external analysis; details of training set diversity are not fully disclosed publicly.
- **Unsupported Clinical Scenarios:** Use only with totality of clinically relevant information; not a screening tool; not sole diagnostic criterion; false negatives may delay cancer treatment and false positives may lead to unnecessary referrals/procedures; see instructions for use for full risk list. Performance depends on appropriate lesion selection and workflow context; false negatives/positives possible; study performance may not generalize across settings.
- **Unsupported Use Cases:** Performance depends on appropriate lesion selection and workflow context; false negatives/positives possible; study performance may not generalize across settings.
- **Required Clinician Oversight:** Three-step process (identify lesion → apply device/record spectra → receive result). Instructional materials and device instructions for use are referenced by the developer. Potential harms relate to missed malignancy (false negative) or unnecessary escalation (false positive); intended as adjunctive decision support with clinician oversight. Not clearly specified in public materials; likely follows local clinical/consent practices.

## 5) Mechanism and Development
- **Model Type:** Predictive / risk stratification adjunctive device output (Investigate Further vs Monitor) rather than direct diagnosis. ESS spectroscopy captures wavelength-dependent backscatter; preprocessing + proprietary neural network compares pattern against training data from histopathology-confirmed lesions; returns risk output to aid referral decisions.
- **Training Data:** Not disclosed
- **Model Development & Validation:** [Publication](PubMed entry and related publications. [16])
- **Clinical Trial:** Study evidence and summaries described in the clinical evidence PDF.
- **Performance:** Public materials and study summaries report no device-related safety issues; primary safety concerns are clinical consequences of false results. Human-in-the-loop clinical judgment remains required; device should be used only as intended.
- **Limitations in Evaluating Performance:** Not disclosed

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** Algorithm is described as “locked” with periodic revalidation/updates requiring FDA clearance.
- **Scheduled Updates:** Algorithm is described as “locked” with periodic revalidation/updates requiring FDA clearance.
- **Inquiries / Report an Issue:** General inquiries and support via knowledge base; contact page
