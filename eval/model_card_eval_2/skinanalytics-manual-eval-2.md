Skin Analytics

1) Metadata  
- Model name:  
  [https://skin-analytics.com/](https://skin-analytics.com/)   
- Developer:   
  Skin Analytics, headquartered in the UK. \[1\]  
- Regulatory Approval Status:  
  Deep Ensemble for the Recognition of Malignancy (DERM) is a Class III CE marked AI as a Medical Device (AIaMD) \[1\]\[2\] and UKCA Class IIa certification. \[3\]  
- Version:   
  SA-001165-LB \[1\]. DERM-vA (version A) was released July 2021\. \[1\]  
- Availability:   
  The Skin Analytics app is associated with the medical device, DERM, and is not publicly available, but rather can be accessed through insurance pathways (the UK's national NHS or private insurance networks) after referral by a GP or dermatologist. To use it, organizations register for a DERM account with Skin Analytics, which then integrates with physicians' teledermatology and EHR systems via API for image submission, result delivery, and automated clinical workflow triggers. \[1\] It is available in the United Kingdom and European Union. \[1\]\[2\]   
- Summary:  
  DERM (Deep Ensemble for the Recognition of Malignancy), which is Skin Analytics' Class III CE marked AI as a Medical Device (AIaMD), \[1\]\[2\] is built around the company's custom teledermatology platform to help triage patients to the right place, at the right time to use dermatologist resources most efficiently. \[1\] DERM assesses dermoscopic images of skin lesions submitted by primary cares and dermatologists seeing patients \[1\]\[2\] and gives a suspected diagnosis along with a referral recommendation based on the suspected diagnosis. This ensures patients with non-cancerous lesions are safely triaged away from cancer pathways to make space for patients who need them. \[1\]  
2) Intended Use  
- Medical Purpose:  
  DERM is an AI-based skin lesion analysis device intended for use in the screening, triage and assessment of skin lesions suspicious for skin cancer \[1\]. DERM analyzes dermoscopic images of skin lesions and gives a suspected diagnosis, and relevant referral recommendation. This helps ensure that patients with non-cancerous lesions are not sent down cancer pathways and dermatologist resources are used most effectively. \[1\]  
- Acceptable Input:  
  Physicians, including primary care doctors and dermatologists, submit dermatoscopic images of lesions suspicious for cancer from patients they are evaluating Dermoscopic images must be captured using approved dermoscopy devices. \[1\] Skin Analytics is integrated with physicians' teledermatology and EHR systems via API for image submission, result delivery, and automated clinical workflow triggers. \[1\]  
- Output:  
  Structured clinical assessment and referral guidance: for each lesion assessment, the results returned by DERM include the suspected diagnosis, referral recommendation, referral recommendation guidance, and analysis explanation. DERM completes image analysis in less than 20 seconds using the DERM AI model trained on skin lesion data. \[1\]  
- Role in Decision-Making:  
  Users may use DERM and its outputs as an automated clinical management tool or to augment other clinical data points to support clinical decision-making. \[1\]  
- Intended Users:   
  DERM is intended to be used by primary care clinicians/providers and specialty care providers (e.g. dermatologists). \[1\] Necessary knowledge/expertise: Clinical training in skin lesion assessment and dermoscopy, and adherence to the DERM Instructions for Use and local clinical pathways. \[1\]  
- Targeted Patient population:   
  Adults 18 years or older with skin lesions suspicious for skin cancer. \[1\]  
3) Risks and Limitations  
- Known Performance Limitations:  
  DERM's performance depends on the quality of the image provided, correct usage of hardware, and the settings configured on the device. \[1\] DERM does not provide a definitive diagnosis and does not assess rare malignant lesions not listed in the device's list of possible outputs. \[1\] DERM should not be used on: patients under age 18, for assessing non-cancer skin conditions (e.g. rashes, eczema, infectious diseases, lupus), for monitoring treatment, for staging disease, for images other than dermoscopic images of skin lesions, for images of skin lesions from anyone other than the identified patient, for open or ulcerated skin lesions, for skin lesions unable to be entirely imaged by the dermatoscope, skin lesions obscured by hair, tattoos or scars, skin lesions beneath nails, in eyes or on mucosal surfaces or on soles of feet or palms of hands, and skin lesions which have previously been biopsied. \[1\]  
- Skin type representation & Equity:  
  DERM has been tested on images of skin lesions that represent the population of patients and lesions DERM may be used on in prospective studies run in the UK, US, and Italy. \[1\] DERM has primarily been evaluated on patients with Fitzpatrick skin types I-IV. \[1\] DERM should be used with caution on other skin types. \[1\] In one study looked at real-world deployment data across 170,000 patients across all Fitzpatrick skin types (I-VI), darker skin types were underrepresented relative to their representation in the population. \[5\]\[13\] In this study, DERM correctly identified all melanomas, SCCs, and BCCs in patients with Fitzpatrick V and VI skin types since 2020\. \[13\] In another study, subgroup analysis showed age, skin type, and deprivation did not change the expected distribution of cases assessed by DERM, indicating that DERM demonstrated equitable performance across different skin types with no difference in performance quality for darker skin tones in the populations studied. \[9\]\[13\] However, the limitation is that darker skin types are underrepresented in the dataset (only 2.2% Fitzpatrick IV-VI in DERM-003 study), \[5\]\[7\] so generalizability for these populations is limited. DERM cannot currently assess palmoplantar and subungual lesions, which disproportionately affect darker-skinned patients where melanoma more commonly occurs in these locations. \[7\]\[11\]  
- Required Clinician Oversight:  
  Skin Analytics is approved to make autonomous clinical decisions without direct clinician oversight. Use of the platform can only be done via a clinician through medical referral (not directly or publicly by patients). \[1\]  
4) Mechanism and Development  
- Model Type:   
  Deep ensemble machine-learning architecture for dermoscopic image analysis. \[1\]  
- Training Data:  
  Training dataset not specified. \[1\]  
- Model Development & Validation:  
  [https://pubmed.ncbi.nlm.nih.gov/37869160/](https://pubmed.ncbi.nlm.nih.gov/37869160/) \[4\] [https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/](https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/) \[6\]  
- Clinical Trial:  
  [https://clinicaltrials.gov/study/NCT04116983](https://clinicaltrials.gov/study/NCT04116983) \[17\]  
  [https://clinicaltrials.gov/study/NCT04123678](https://clinicaltrials.gov/study/NCT04123678) \[18\]  
  [https://clinicaltrials.gov/study/NCT05126173](https://clinicaltrials.gov/study/NCT05126173) \[19\]  
- Performance:  
  Result 1: DERM achieved AUROC of 91.8-95.8% for melanoma detection across different camera devices \[10\], with 99.8% negative predictive value (NPV) for correctly excluding melanoma \[10\], outperforming dermatologists' NPV of 98.9%. \[10\] For non-melanoma skin cancers, DERM achieved AUROC of 0.85-0.89 for squamous cell carcinoma and 0.87-0.89 for basal cell carcinoma across multiple devices. \[5\] In real-world deployment, DERM demonstrated 97% pathway sensitivity for malignant melanoma \[9\]\[12\], exceeding the 95% target rate. \[9\] DERM meets or exceeds clinical performance benchmarks for skin cancer detection \[5\]\[10\] and demonstrates diagnostic accuracy comparable to or better than dermatologists. \[10\] The high NPV indicates DERM can safely identify patients who do not have cancer, allowing them to be discharged without specialist review. \[10\]\[12\]   
  Result 2: DERM has been deployed across patients with all Fitzpatrick skin types (I-VI) \[13\]. Real-world data shows 6-8% of cases assessed had Fitzpatrick type V-VI skin, \[13\] compared to 4.5% of NHS urgent suspected skin cancer pathway patients from Black, Asian, or mixed ethnicities. \[13\] DERM correctly identified all melanomas, SCCs, and BCCs in patients with Fitzpatrick V and VI skin types since 2020\. \[13\] Subgroup analysis showed age, skin type, and deprivation did not change the expected distribution of cases assessed by DERM.  \[9\] DERM demonstrates equitable performance across different skin types with no difference in performance quality for darker skin tones in the populations studied \[9\]\[13\]. However, the limitation is that darker skin types are underrepresented in the dataset (only 2.2% Fitzpatrick IV-VI in DERM-003 study) \[5\]\[7\], limiting generalizability for these populations. \[5\]\[7\] DERM cannot currently assess palmoplantar and subungual lesions, \[7\]\[11\] which disproportionately affects darker-skinned patients where melanoma more commonly occurs in these locations. \[7\]\[11\]  
  Result 3: DERM is designated as safe by independent evaluation \[8\]\[12\], with sensitivity maintained at 91-92.5% (matching clinician benchmarks) \[8\]\[9\] while achieving significantly higher specificity for identifying lesions not requiring biopsy or urgent referral \[8\]\[9\]. In University of Exeter evaluation, DERM demonstrated it, showing it is in line with performance targets \[12\]. High-risk skin cancer detection rates increased by 26.5% versus local published rates \[12\]. No adverse safety events or missed high-risk cancers have been reported in published real-world deployment data covering 170,000+ patients. \[13\] DERM maintains high sensitivity to ensure malignant lesions are not missed while safely discharging patients with benign lesions \[6\]\[8\], reducing unnecessary referrals without compromising patient safety \[6\]\[8\]\[12\]. The system's performance remains consistent with pre-deployment validation studies in real-world settings \[6\]\[7\]. Initial deployments included a "second-read" safety net where dermatologists reviewed DERM decisions until performance at or above expected targets was demonstrated. \[6\]\[9\]  
- Limitations in evaluating performance:  
  Not specified.  
5) Governance and Monitoring  
- Plans for Ongoing Maintenance:   
  Centralized updates, monitoring, and ongoing product quality management by Skin Analytics. \[1\]  
- Scheduled Updates:  
  Validation includes ongoing post-market surveillance (PMS) with transparent reporting of real-world performance data \[6\]\[7\], systematic processes to identify and analyze performance errors \[6\], and continuous monitoring for software updates or algorithm changes \[6\].   
- Process for inquiries or to report an issue:  
  [support@skinanalytics.co.uk](mailto:support@skinanalytics.co.uk)  \[1\]  
6) References  
1. [https://skin-analytics.com/wp-content/uploads/2025/01/SA-001165-LB-v12-DERM-Instructions-for-Use\_20Jan2025.pdf](https://skin-analytics.com/wp-content/uploads/2025/01/SA-001165-LB-v12-DERM-Instructions-for-Use_20Jan2025.pdf)  
2. [https://skin-analytics.com/news/regulatory-certification/derm-class-iii-ce-mark/](https://skin-analytics.com/news/regulatory-certification/derm-class-iii-ce-mark/)  
3. [https://skin-analytics.com/news/regulatory-certification/skin-analytics-achieves-class-iia-ukca-mark-for-derm/](https://skin-analytics.com/news/regulatory-certification/skin-analytics-achieves-class-iia-ukca-mark-for-derm/)  
4. [https://pubmed.ncbi.nlm.nih.gov/37869160/](https://pubmed.ncbi.nlm.nih.gov/37869160/)  
5. [https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1288521/full](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1288521/full)  
6. [https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/](https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/)  
7. [https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1264846/full](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1264846/full)  
8. [https://pmc.ncbi.nlm.nih.gov/articles/PMC10996444/](https://pmc.ncbi.nlm.nih.gov/articles/PMC10996444/)  
9. [https://unityinsights.co.uk/our-insights/ai-in-health-and-care-award-skin-analytics-evaluation/](https://unityinsights.co.uk/our-insights/ai-in-health-and-care-award-skin-analytics-evaluation/)  
10. [https://skin-analytics.com/news/skin-cancer/prospective-study-shows-ai-as-accurate-as-clinical-specialist/](https://skin-analytics.com/news/skin-cancer/prospective-study-shows-ai-as-accurate-as-clinical-specialist/)  
11. [https://www.nice.org.uk/consultations/2705/2/committee-discussion](https://www.nice.org.uk/consultations/2705/2/committee-discussion)  
12. [https://skin-analytics.com/ai-pathways/derm-performance/](https://skin-analytics.com/ai-pathways/derm-performance/)  
13. [https://skin-analytics.com/ai-pathways/equality-of-access/](https://skin-analytics.com/ai-pathways/equality-of-access/)  
14. [https://skin-analytics.com/ai-pathways/certifications/](https://skin-analytics.com/ai-pathways/certifications/)  
15. [https://www.medicaldevice-network.com/news/nhs-report-touts-effectiveness-of-skin-analytics-derm-ai-melanoma-tool/](https://www.medicaldevice-network.com/news/nhs-report-touts-effectiveness-of-skin-analytics-derm-ai-melanoma-tool/)  
16. [https://skin-analytics.com/faq/](https://skin-analytics.com/faq/)  
17. [https://clinicaltrials.gov/study/NCT04116983](https://clinicaltrials.gov/study/NCT04116983)   
18. [https://clinicaltrials.gov/study/NCT04123678](https://clinicaltrials.gov/study/NCT04123678)   
19. [https://clinicaltrials.gov/study/NCT05126173](https://clinicaltrials.gov/study/NCT05126173) 
