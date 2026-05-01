# DermaSensor — CHAI Model Card

## 1) Metadata
- **Model Name:** DermaSensor [1]
- **Developer:** DermaSensor Inc. (founders include Dr. Maurice Ferre and Christopher Dewey). Company history describes development of Elastic Scattering Spectroscopy (ESS) and a proprietary machine learning algorithm trained on histopathology-confirmed lesions. [2,5]
- **Inquiries or to report an issue:** General inquiries and support via knowledge base [3]; contact page [4]
- **Release Stage:** FDA-cleared handheld device using ESS + proprietary neural network algorithm; algorithm details not fully public. [5,9]
- **Release Date:** FDA authorization announced January 17, 2024; Breakthrough Device designation in 2021. [6,7]
- **Version:** Handheld device; version not publicly specified.
- **Regulatory Approval Status, if applicable:** FDA De Novo / Class II classification for “Software-aided adjunctive diagnostic devices for use by non-dermatology providers of lesions suspicious for skin cancer.” [8,9,10]
- **Global Availability:** FDA-cleared and available for sale in the U.S.; CE marked; waitlist/limited state availability described publicly. [12,13]
- **Summary:** Connected handheld device intended to help frontline providers assess lesions suspicious for melanoma/BCC/SCC and inform referral decisions, producing results in seconds. [14,18]
- **Keywords:** AI; devices; dermatology; ESS; spectroscopy; skin cancer; sensitivity; specificity; melanoma; BCC; SCC; non-invasive; risk stratification. [15,16]

## 2) Uses & Directions
- **Intended Use & Workflow:** Identified suspicious lesion is scanned with five spectral recordings; algorithm returns “Investigate Further” or “Monitor,” with a 1–10 similarity score for malignancy patterns. Intended for use alongside clinician assessment and not as a screening tool or sole diagnostic criterion. [17,18,20]
- **Primary Intended Users:** Qualified healthcare professionals in clinical settings; marketed for non-dermatology providers in primary care and related outpatient settings. [5,17,20]
- **Necessary knowledge/expertise:** Clinical assessment skills for lesion selection and interpretation; device is an adjunct to clinical judgment. [18,20]
- **How to Use:** Three-step process (identify lesion → apply device/record spectra → receive result). Instructional materials and device instructions for use are referenced by the developer. [17,19,20]
- **Targeted patient population:** Patients (often \(40+\)) with lesions already judged suspicious for melanoma/BCC/SCC where a referral decision is being considered. [18,20]
- **Patient consent or disclosure required or suggested?:** Not clearly specified in public materials; likely follows local clinical/consent practices.

## 3) Warnings
- **Developer-Supplied Warnings:** Use only with totality of clinically relevant information; not a screening tool; not sole diagnostic criterion; false negatives may delay cancer treatment and false positives may lead to unnecessary referrals/procedures; see instructions for use for full risk list. [18,20]
- **Model Limitations:** Performance depends on appropriate lesion selection and workflow context; false negatives/positives possible; study performance may not generalize across settings. [18]
- **Skin type representation & equity:** Pivotal trial demographics and post-market testing requirements for underrepresented populations are discussed in external analysis; details of training set diversity are not fully disclosed publicly. [22,24]
- **Clinical Risk Level:** Potential harms relate to missed malignancy (false negative) or unnecessary escalation (false positive); intended as adjunctive decision support with clinician oversight. [18,20]

## 4) Trust Ingredients
- **AI System Facts:** ESS spectroscopy captures wavelength-dependent backscatter; preprocessing + proprietary neural network compares pattern against training data from histopathology-confirmed lesions; returns risk output to aid referral decisions. [5,18,20,21]
- **Model Type:** Predictive / risk stratification adjunctive device output (Investigate Further vs Monitor) rather than direct diagnosis. [18,20]
- **Interaction with other systems:** Used as a point-of-care device within clinical workflows; no public details on EHR integration.\n+- **Outcomes & Output:** Output includes referral-oriented risk classification and score; intended to improve triage and reduce missed cancers by clinicians in reader studies. [18,20]\n+- **Explanation for how an output is generated:** Broadband light pulses interact with tissue microstructure; backscattered spectra are captured and analyzed by the locked algorithm validated in clinical studies. [5,18,20,21]\n+- **Foundation Models Used in application, if applicable:** Proprietary ML algorithm; foundation model usage not disclosed publicly. [21]\n+- **Input Data Source:** Spectral recordings from the scanned lesion. [17,18]\n+- **Output/Input Data Type:** Input: spectral signal; Output: categorical result + numeric score intended to guide referral decisions. [18,20]\n+- **Dataset Transparency:** Training dataset is proprietary; external reporting discusses limitations and demographic imbalances in pivotal evaluation populations. [23,24]\n+- **Ongoing Maintenance:** Algorithm is described as “locked” with periodic revalidation/updates requiring FDA clearance. [20]\n+- **Security and compliance environment practices or accreditations, if applicable:** Privacy policy is published by the developer. [25]

## 5) Key Metrics
### Usefulness / Efficacy
- **Goal of Metric(s):** Risk stratification of suspicious lesions and support for more timely dermatology referral decisions. [5,18]
- **Result:** FDA pivotal and related studies report device sensitivity and AUROC; reader study results suggest improved clinician referral sensitivity when aided by the device. [18]
- **Interpretation:** Higher sensitivity/NPV may reduce missed cancers; low specificity may still produce substantial “Investigate Further” results (referrals), with PPV improving at higher scores. [18]
- **Test Type:** Prospective diagnostic accuracy and clinical utility studies with histopathology as reference standard. [18]
- **Testing Data Description:** Multicenter studies in primary care and dermatology settings; lesions scanned prior to biopsy; clinicians blinded to histopathology. [18]
- **Validation Process and Justification:** Histopathologic examination as gold standard enables comparison between device output and definitive diagnosis. [18]

### Fairness & Equity
- **Goal of Metric(s):** Comparable usability/performance across skin types and demographics. [22,24]
- **Result:** Sub-analyses by Fitzpatrick skin type have been reported; pivotal trial race distribution and post-market requirements for underrepresented populations are described in external analysis. [22,24]
- **Interpretation:** Dataset and real-world performance equity require ongoing evaluation; limited disclosure of proprietary training data composition. [23,24]
- **Test Type:** Subgroup analysis (e.g., Fitzpatrick I–III vs IV–VI) and post-market evaluation requirements. [22,24]

### Safety & Reliability
- **Goal of Metric(s):** Safe point-of-care use and reliable adjunctive outputs for referral decisions. [18,20]
- **Result:** Public materials and study summaries report no device-related safety issues; primary safety concerns are clinical consequences of false results. [18,20]
- **Interpretation:** Human-in-the-loop clinical judgment remains required; device should be used only as intended. [18,20]
- **Validation Process and Justification:** Locked algorithm validated via prospective studies; updates require re-clearance. [18,20]

## 6) Resources
- **Evaluation References, if available:** See pivotal study summary PDF and related publications. [18,15,16]
- **Clinical Trial, if available:** Study evidence and summaries described in the clinical evidence PDF. [18]
- **Peer-Reviewed Publication(s):** PubMed entry and related publications. [16]
- **Reimbursement status, if applicable:** Not specified / N/A in public sources reviewed.
- **Stakeholders consulted during design of solution:** Board / leadership information listed by the developer. [29]

## References
[1] https://www.dermasensor.com/
[2] https://www.dermasensor.com/history/
[3] https://support.dermasensor.com/
[4] https://www.dermasensor.com/contact-us/
[5] https://www.dermasensor.com/how-dermasensor-works/
[6] https://pmc.ncbi.nlm.nih.gov/articles/PMC11180084/
[7] https://www.biospace.com/dermasensor-inc-announces-successful-completion-of-first-ever-fda-pivotal-studies-for-skin-cancer-detection-device-for-primary-care
[8] https://www.dermasensor.com/skin-cancer-detection-device/
[9] https://www.accessdata.fda.gov/cdrh_docs/pdf23/DEN230008.pdf
[10] https://www.dermasensor.com/resource/fda-clearance-granted-for-first-ai-powered-medical-device-to-detect-all-three-common-skin-cancers-melanoma-basal-cell-carcinoma-and-squamous-cell-carcinoma/
[11] https://www.nature.com/articles/s41746-024-01161-1
[12] https://www.dermasensor.com/resource/two-new-studies-show-dermasensor-devices-consistent-performance-and-improvements-to-physicians-melanoma-detection/
[13] https://www.dermasensor.com/contact-us/#:~:text=The%20DermaSensor%20device%20is%20FDA%2Dcleared,in%20all%20other%20U.S.%20states.&text=*Select%20Practice%20Type
[14] https://www.dermasensor.com/resource/dermasensors-mission/
[15] https://pmc.ncbi.nlm.nih.gov/articles/PMC10746496/
[16] https://pubmed.ncbi.nlm.nih.gov/40470593/
[17] https://www.dermasensor.com/
[18] https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf
[19] https://www.dermasensor.com/resource/how-dermasensor-works/
[20] https://www.dermasensor.com/faq/
[21] https://www.dermasensor.com/how-dermasensor-works/#:~:text=Malignant%20transformation%20alters%20cellular%20and,over%202%2C000%20histopathologically%20confirmed%20lesions.
[22] https://www.dermasensor.com/resource/dermasensor-study-results-for-skin-cancer-detection-device-performance-across-skin-tones-of-over-1000-patients/
[23] https://www.dermasensor.com/#:~:text=The%20DermaSensor%20device%20uses%20a,you%20make%20better%20informed%20decisions.
[24] https://www.nature.com/articles/s41746-024-01161-1
[25] https://www.dermasensor.com/privacy-policy/
[26] https://www.dermasensor.com/resource/dermasensor-secures-16m-to-scale-ai-powered-skin-cancer-detection-in-primary-care/
[27] https://www.dermasensor.com/resource/advancing-skin-cancer-detection-american-academy-of-dermatology-journal-publishes-dermasensors-breakthrough-melanoma-detection-results-from-a-major-multicenter-trial/
[28] https://doi.org/10.1016/j.jdin.2023.10.011
[29] https://www.dermasensor.com/team-position/board-of-directors/
[30] https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfres/res.cfm?id=216559