# Dermasensor

## 1) Metadata
- **Model Name:**  
   DermaSensor[1]
- **Developer:**  
 Company History: As two leading entrepreneurs and investors in health technology companies, Dr. Maurice Ferre (Co-founder and Chairman) and Christopher Dewey (Co-founder and Director) came to believe that skin cancer is primarily a public health issue that could be addressed by improving access to quality skin cancer care. Due to the limited number of dermatologists, their goal was to use cutting-edge spectroscopy and machine learning technologies to improve frontline providers ability to detect skin cancer early.
  
 They founded DermaSensor in 2009 following discussions with Dr. Irving Bigio, Professor of Biomedical Engineering at Boston University and one of the top spectroscopy researchers in the world. Dr. Bigio is the original inventor and patent holder for Elastic Scattering Spectroscopy (ESS), a key technology employed by the DermaSensor device.
  
 Since Professor Bigio's invention of ESS in 1994, there have been several hundreds of publications on ESS and over 30 publications on the use of ESS in clinical studies. DermaSensor began its own skin-specific studies using this technology in 2011 and began its first study on the current commercial device in 2018.

 DermaSensor was founded in 2009 to improve patient access to effective skin cancer assessments. By harnessing the power of elastic scattering spectroscopy (ESS) we created the world's first skin tissue sampling system that uses hundreds of different wavelengths of light to painlessly and non-invasively scan skin lesions. We use the light to detect properties consistent with malignancy at a cellular and subcellular level. It's like an ultrasound, but using light instead of sound.
  
 When it was first developed, ESS technology was the size of a microwave oven. Today, thanks to a decade of our team's engineering advancement, you can hold it in the palm of your hand.

 Even with cutting-edge ESS technology, there was no way to assess lesions objectively and efficiently. That's why we developed an algorithm using machine learning. To build it, we collected thousands of dermatopathology-confirmed malignant and benign tissue samples. Then we compared the spectral data to the pathology report, testing and fine-tuning the algorithm in a process that continues today, as we constantly indentify and analyse new data, providing ongoing updates to our DermaSensor users.
  
 Today, thanks to our proprietary DermaSensor algorithm, our device processes spectral data in a matter of seconds, rather than waiting days for a physician or labratory to return results.
- **Regulatory Approval Status**
 First FDA cleared skin cancer detection device developed for physicians.[8]

 "FDA concludes that this device should be classified into Class II. This order, therefore, classifies the DermaSensor, and substantially equivalent devices of this generic type, into Class II under the generic name Software-aided adjunctive diagnostic devices for use by non-dermatology providers of lesions suspicious for skin cancer." [9]

 "Achieving this medical milestone is a testament to the 12 years and tens of millions of dollars our company has invested in research and development to bring this powerful technology to market," said Dr. Maurice Ferre, co-founder and chairman of DermaSensor. "We are incredibly grateful to the FDA for their collaboration and dedication to this area starting with our first FDA pre-submission meeting in 2016. Having begun patient enrollment in our FDA pivotal study in mid-2020, we are now ecstatic to have clearance of our FDA-Breakthrough Designated De Novo submission." [10]

 The U.S. Food and Drug Administration's (FDA) recent authorization of DermaSensor, an AI-enabled device for skin cancer detection in primary care, marks a pivotal moment in digital health innovation. [11]
- **Version:**  
 Handheld device, no real "version."
- **Availability:**  
 DermaSensor is currently FDA Cleared, CE Marked, and is available for sale in the U.S. [12]
 The DermaSensor device is FDA-cleared and available for sale in Florida and Pennsylvania. The device is available for joining our waitlist in all other U.S. states. [13]
- **Summary:**  
 DermaSensor Inc. is a Miami-based connected medical device company that seeks to enable healthcare professionals to efficiently check for skin cancer by leveraging cutting-edge technologies. The DermaSensor™ device concept is for an affordable handheld tool that uses artificial intelligence and spectroscopy to evaluate skin lesions for potential cancer in a matter of seconds. By enabling quick and effective skin cancer checks, DermaSensor ultimately hopes to improve skin cancer detection and to save lives. [14]
- **Keywords:**  
 Artificial intelligence, devices, dermatology, elastic-scattering spectroscopy, skin cancer, skin lesions, spectroscopy, AI; DERM-ASSESS III; DermaSensor; ESS; NPV; PPV; artificial intelligence; automated; biopsy; detection; elastic scattering device; elastic scattering spectroscopy; handheld; melanoma; non-invasive; pigmented lesion; sensitivity; skin cancer; specificity; spectroscopic; spectroscopy; technology. (keywords from pubmed article)[15] [16] 

## 2) Intended Use 
- **Medical Purpose**
  The DermaSensor device is indicated for use to evaluate skin lesions suggestive of melanoma, basal cell carcinoma, and/or squamous cell carcinoma in patients aged 40 and above to assist in the decision regarding referral of the patient to a dermatologist. The DermaSensor device should be used in conjunction with the totality of clinically relevant information from the clinical assessment, including visual analysis of the lesion, by physicians who are not dermatologists. The device should be used on lesions already assessed as suspicious for skin cancer and not as a screening tool. The device should not be used as the sole diagnostic criterion nor to confirm clinical diagnosis of skin cancer. [18]
- **Acceptable Input**
 Step 1: Identify lesion suggestive of skin cancer on the patient. [17]
 Step 2: Apply the handheld DermaSensor device to the lesion and initiate first recording. A total of five spectral recordings are taken from the skin lesion to complete the scan. [17]
 Step 3: DermaSensor's algorithm analyzes spectral data and delivers skin cancer risk results in seconds. [17]

 How it works: 
 Light & Tissue Interaction: DermaSensor delivers short pulses (~30 microseconds) of broadband white light spanning 300-900 nm wavelengths. When this light penetrates tissue, photons scatter from refractive-index gradients associated with micro- and nano-scale structures, including nuclear size, chromatin condensation, cellular architecture, and collagen organization. An adjacent collection fiber captures backscattered photons and conveys them to a microspectrometer. [5] 
 Spectral Analysis & AI Pattern Recognition: The system records a spectral signature of backscattered intensity versus wavelength. Malignant transformation alters cellular and subcellular structures, creating distinct optical signatures in the ESS spectrum. Lesions with different morphology, cellular, and subcellular features have different densities. The recorded spectrum undergoes preprocessing (smoothing and downsampling) before analysis by the proprietary neural network machine learning algorithm, which compares the pattern against training data from over 2,000 histopathologically confirmed lesions. [5] 
 Clinical Use & Workflow Integration: Time-gated detection enables the device to function in ambient room light without requiring darkening, making it practical for clinical workflows. The entire measurement takes seconds and requires no tissue preparation. [5] 
- **Output**
 The device does not provide an output that differentiates between a BCC, SCC, or melanoma when signs of malignancy are present. It will provide the objective output of "Investigate Further" with a scale of 1-10 to indicate the degree of similarity to malignant lesions. The likelihood that a positive "Investigate Further" result is cancerous ranged from 6% for a score of 1 to 61% for a score of 10 in the DERM-SUCCESS FDA Pivotal Clinical Study with over 1,000 patients. [20]
- **Role in Decision Making**
 See above. 
 The DermaSensor device should be used in conjunction with the totality of clinically relevant information from the clinical assessment, including visual analysis of the lesion, by physicians who are not dermatologists. The device should be used on lesions already assessed as suspicious for skin cancer and not as a screening tool. The device should not be used as the sole diagnostic criterion nor to confirm clinical diagnosis of skin cancer. [18]
- **Intended Users**
 *DermaSensor is intended for use by qualified healthcare professionals in clinical settings only. It is not intended for at-home or personal use. [5]
 -DermaSensor is a medical device intended for use only by physicians in clinical settings. [20]
 -The device helps speed up the detection of suspicious lesions at the point of care. [17]
 "With integrating DermaSensor's innovative technology into our practice, we can now offer enhanced skin cancer assessment capabilities right in our community, ensuring timely referrals for our patients." -Testimonial [17]
 -The DermaSensor device uses a combination of cutting-edge optical spectroscopy and artificial intelligence to promptly analyze suspicious skin lesions. Our proprietary algorithms, developed and refined over a decade of clinical research, are trained on thousands of diagnosed lesions to help you make better informed decisions. [17]
 - Can be used in Family Medicine, Internal Medicine, Concierge Practice, Health Systems, Walk-In Clinics. [17]
 "Hear from Your Fellow Physicians Nationwide. Miss Less Melanoma With Immediate, Non-Invasive Skin Cancer Risk Results" [17] 
 - No certification is required to use DermaSensor. Instruction and education on proper usage and handling are fully covered in the Instructions For Use that is included in the device packaging and can be provided by our commercial team. Supplemental educational materials (e.g. Quick Reference Guide, videos, and patient education materials) are also available to all customers. [20] 
- **Target Patient Population**
 Medical practices who want to enhance their acuity of diagnosing abnormalities in skin, "Yes, I would recommend it. I don't think physicians (non-derm) learn enough about abnormalities resulting in increased referrals.The device can be used as a guide and the patient will be happier" -Testimonial. Intended by physicians to use on their patient demographics. Cost low to promote affordability and increase timely referrals for patients. [1]

## 3) Risks and Limitations 
- **Known Performance Limitations**
 False-positive and false-negative device results may lead to unnecessary referrals or to a malignant skin lesion not being correctly referred, respectively. For the more clinically harmful risk, a false negative device result, the DERM-SUCCESS study found the overall device sensitivity to be 95.5%, with a lower bound of 91.7%. While the device can produce false negative results, as does gold standard dermatopathology, when the device result is used to aid PCPs in their referral decisions, the reader study showed that the device decreases PCPs' false negatives by half, with the PCPs' false negative rate decreasing from 18.0% without device use to 8.6% with device use. [18]
- **Skin Type Representation & Equity**
 "...The recorded spectrum undergoes preprocessing (smoothing and downsampling) before analysis by the proprietary neural network machine learning algorithm, which compares the pattern against training data from over 2,000 histopathologically confirmed lesions." [21] However, it is unclear whether these 2,000 histopathologiclaly confirmed lesions are from differing skin tones and how skin tones are represented in the training set. 

 In the sub-analysis, patients were divided into two groups based on their Fitzpatrick skin types (FST): FST I-III and FST IV-VI, which are consistent with previous studies defining skin of color.34 Of the 1,005 patients enrolled in the study, 729 (72%) belonged to the FST I-III group, and 276 (28%) were in the FST IV-VI group. Forty-eight skin cancers were detected in subjects with Fitzpatrick skin type IV-VI. Importantly, there was minimal variation in device sensitivity, specificity, and Area under the Receiver Operating Characteristic Curve (AUROC) when comparing patients in the two FST subgroups to each other and to overall study results. The device sensitivity was similar between FST I-III and IV-VI, 96% and 92%, respectively, and AUROC was also similar with results of 0.779 for FST I-III and 0.764 for FST IV-VI. [22]

 "Our mission at DermaSensor has always been to provide access to tools to aid in skin cancer evaluations", said Cody Simmons, CEO of DermaSensor. "The results from the DERM-SUCCESS study suggest that our ESS technology performs comparably regardless of skin type, which could improve providers' ability to assess lesions on all patients and thus increase equitable access to effective skin cancer exams." [22]

 -Full dataset composition that DermaSensor was trained on is not publicly disclosed. The device itself is for all skin tones and skin types, but unsure whether the dataset is representing all ethnicities well since this is unreleased to the public and is proprietary. "The DermaSensor device uses a combination of cutting-edge optical spectroscopy and artificial intelligence to promptly analyze suspicious skin lesions. Our proprietary algorithms, developed and refined over a decade of clinical research, are trained on thousands of diagnosed lesions to help you make better informed decisions." [23]

 -DermaSensor's authorization also comes with notable regulatory conditions. FDA has imposed requirements for post-market performance testing in underrepresented populations, as notably 97.1% of patients in the pivotal DERM-SUCCESS trial were of White race and only 13% were from the most pigmented skin types (Fitzpatrick V/VI). While improving clinical trial diversity is a priority across all FDA-regulated products, the implications are particularly salient in dermatology, where the lack of darker skin tones in images used to train AI models have resulted in poorer diagnostic performance on darker skin phenotypes. [24]
- **Required clinician oversight**
 The device itself should be utilized by physicians not specifically trained in dermatology. 
 DermaSensor should be used in conjunction with the totality of clinically relevant information from the clinical assessment, including visual analysis of the lesion, by physicians who are not dermatologists. The device should be used on lesions already assessed as suspicious for skin cancer and not as a screening tool. The device should not be used as the sole diagnostic criterion nor to confirm clinical diagnosis of skin cancer. It is not intended for consumer or at-home use. The primary risks of DermaSensor are that false negative results (e.g., when a test indicates that a condition is absent when it is actually present) could lead to failure to treat cancer and cancer progression, or false positive results (when a test indicates that a condition is present when it is actually absent) could lead to unnecessary referrals and/or medical procedures. For a complete list of risks, please see the DermaSensor instructions for use. [20]

## 4) Mechanism and Development 
- **Model Type**
 -Predictive / risk stratification model. FDA Cleared device for skin lesion risk assessment available on a monthly rental basis. DermaSensor analyzes spectral patterns to detect cellular changes associated with melanoma, BCC, and SCC, providing an immediate point-of-care result of either "Investigate Further" or "Monitor". It is designed as an adjunctive tool used alongside clinical assessment, not as a replacement for clinical judgment. In FDA-submitted studies, PCP sensitivity increased from 80.5-82.0% unaided to 86.3-91.4% device-aided. The DermaSensor device is not intended to be used for direct diagnosis of skin cancer. It provides objective information to assist physicians in deciding whether a lesion requires further clinical care, such as referral to a dermatologist. [20]
- **Training Data**
 Proprietary algorithm and histopathologically confirmed data set utilized (details not publicly disclosed). [21]
 -Proprietary training algorithm and histopathology dataset not publicly available. The device itself is for all skin tones, but unsure whether the dataset is representing all ethnicities well since this is unreleased to the public. [23]
 -DermaSensor's authorization also comes with notable regulatory conditions. FDA has imposed requirements for post-market performance testing in underrepresented populations, as notably 97.1% of patients in the pivotal DERM-SUCCESS trial were of White race and only 13% were from the most pigmented skin types (Fitzpatrick V/VI). While improving clinical trial diversity is a priority across all FDA-regulated products, the implications are particularly salient in dermatology, where the lack of darker skin tones in images used to train AI models have resulted in poorer diagnostic performance on darker skin phenotypes. [24]
- **Model Development & Validation**
 Summary of DermaSensor Device Safety and Effectiveness Results From Three Clinical Studies: https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf
   -Number needed to biopsy (NNB) reflects the proportion of biopsied lesions to malignant lesions for the given device result. It is calculated as 100%/PPV. For patients aged 40 and above, device melanoma sensitivity was 90.2% (n=41), BCC was 97.8% (n=90), and SCC was 97.7% (n=86).[18]
- **Clinical trial**
   DERM-SUCCESS Prospective Skin Cancer Validation Study
 • Device sensitivity (95.5%) was found to be superior to that of study PCP investigators' (83.0%), p-value<0.0001
 • Additionally, DermaSensor sensitivity was non-inferior to the 90% performance goal (based on literature published sensitivity of dermatologists2-5), p-value <0.0001
 • Device specificity was 20.7%, i.e. the device correctly classified as benign 20.7% of lesions that the PCPs biopsied
 • Overall NPV of the device was 96.6%, meaning a negative "Monitor" device result had a 3.4% chance of being malignant
 • Device AUROC was 0.803 compared to 0.736 for the study PCPs [18]

 DERM-ASSESS III Prospective Melanoma Validation Study
 • Similar device sensitivity to expert dermatologists
 • Device specificity was 32.5%, i.e. the device correctly classified as low risk 32.5% of biopsied lesions
 • DermaSensor NPV was 98.1% for melanoma alone and 93.0% for all high risk melanocytic lesions
 • Device AUROC of 0.758 was comparable to the study dermatologists' AUROC of 0.747 [18]

 DERM-SUCCESS Prospective Clinical Utility Study
 • PCP device use resulted in a significant improvement in both management and diagnostic sensitivity compared to standard of care alone; physician false negative referrals decreased by half,
 from 18.0% to 8.6%
 • PCPs' AUROC was 0.762 when aided by the device and was 0.708 with standard of care alone
 • Nearly all (99%) of PCP participants reported the device would provide at least one benefit, including:
 • "Detecting more skin cancer" (82%)
 • "Providing you with greater confidence in your clinical assessments and management decisions" (81%)
 • "Helping you to prioritize the risk level of concerning lesions to prioritize patient management, e.g. a prioritized dermatology referral" (72%)
 • Increasing your frequency of assessing patients for skin cancer" (63%) [18]
- **Performance**
 DERM-SUCCESS Prospective Skin Cancer Validation Study
 -PPV was 16.6% overall; it increased with increasing scores, with scores of 8-10 that were scanned by PCPs having the highest likelihood of cancer at 39.6% (NNB of 2.5) [18]

 DERM-ASSESS III Prospective Melanoma Validation Study
 -PPV for melanoma was 16.0% overall; it increased with increasing scores, with scores of 8-10 that were scanned by dermatologists having the highest likelihood of melanoma at 47.4% (NNB of 2)[18]  
 All lesions were subsequently subjected to histopathologic examination (gold standard) following biopsy, allowing for direct comparison between device output and definitive diagnosis. [18]
- **Limitations in evaluating performance**
 Training data bias due to proprietary datasets and limited disclosure. 
 Conflicts of Interest: This study ["DERMaSensor Use in the ASSESSment of Skin Lesions Suggestive of Melanoma III (DERM-ASSESS III)", was conducted across 8 United States and 2 Australian sites and was published in JAAD (Journal of the American Academy of Dermatology) International.1] was a company-sponsored study. The institution of Dr. Rebecca Hartman, Dana-Farber Cancer Institute, received funding for the clinical research for this study. Dr. Gary Slatko is an employee of DermaSensor Inc. [27]
 Used this reference: 1. Hartman RI, Trepanowski N, Chang MS, Tepedino K, Gianacas C, McNiff JM, Fung M, Braghiroli NF, Grant-Kels JM, Multicenter Prospective Blinded Melanoma Detection Study with a Handheld Elastic Scattering Spectroscopy Device, JAAD International (2023), doi: https:// doi.org/10.1016/j.jdin.2023.10.011. [28]
 
## 5) Governance and Monitoring 
- **Plans for Ongoing Monitoring**
 Important to note that DermaSensor is NOT continually updated as FDA approval does not allow this, "Does the device's AI keep learning?" "No. We locked the algorithm, per FDA requirements, and validated the performance through multiple prospective clinical studies. We plan to revalidate and periodically update the algorithm every couple of years, as we have to resubmit to the FDA and get clearance every time the algorithm is updated or new algorithms are added." [20]
- **Scheduled Updates**
 See above
- **Process for Inquiries or to Report an Issue**
 If have general inquiries, public relations, medical affairs, product support, and shipping & orders, call us, and knowledge base [3]
 If want to contact DermaSensor [4]

 ## 6) Resources
- **Evaluation References:**  [6]
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10746496/

  https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf 

  https://www.dermasensor.com/resource/published-fda-pivotal-studies-find-dermasensor-has-96-sensitivity-and-cuts-physicians-missed-skin-cancers-by-half/

  https://pubmed.ncbi.nlm.nih.gov/40470593/

- **Clinical Trial, if available:**  
 https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf

 https://pubmed.ncbi.nlm.nih.gov/40470593/

- **Peer-Reviewed Publications:**  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10746496/

  https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf 

  https://www.dermasensor.com/resource/published-fda-pivotal-studies-find-dermasensor-has-96-sensitivity-and-cuts-physicians-missed-skin-cancers-by-half/

  https://pubmed.ncbi.nlm.nih.gov/40470593/

- **Reimbursement status, if applicable:**  
  N/A
- **Stakeholders consulted during design of solutions:**
 https://www.dermasensor.com/team-position/board-of-directors/ [29]

## 7)Sources 
[1]  https://www.dermasensor.com/
[2]  https://www.dermasensor.com/history/ (below are the citations that were used for the company history on the website)
    1 Manolakos D et al. Clinical Validation of a Handheld Elastic Scattering Spectroscopy Artificial Intelligence Device, Presentation at American Academy of Dermatologists Innovation Academy, July 20-24, 2022.

    2 Thames T et al. Clinical Utility of a Handheld Elastic Scattering Spectroscopy Tool and Machine Learning on the Diagnosis and Management of Skin Cancer. Poster Presentation, STFM Annual Spring Conference, April 30-May 4, 2022.

    3 Tepedino M et al. Use of Elastic Scattering Spectroscopy on Patient Selected Lesions that are Concerning for Skin Cancer. Poster Presentation, Innovations in Dermatology, Las Vegas NV, Nov 3-6, 2022.

    4 PPV for spectral score group 8-10.

    5 Hartman R et al. Clinical Validation of a Handheld Elastic Scattering Spectroscopic Device in the Evaluation of Lesions Suggestive of Melanoma, Presentation at the American Academy of Dermatologists Annual Meeting, Mar 24-28th, 2022.

    6 Sample size includes invasive melanoma, melanoma in situ, atypical junctional melanocytic proliferations and highly atypical melanocytic nevi.

    7 Merry SP et al. Clinical Performance of Novel Elastic Scattering Spectroscopy (ESS) in Detection of Skin Cancer: A Blinded, Prospective, Multi-Center Clinical Trial [Initial Results]. Poster Presentation, Innovations in Dermatology, Las Vegas NV, Nov 3-6, 2022

[3]  https://support.dermasensor.com/
[4]  https://www.dermasensor.com/contact-us/
[5]  https://www.dermasensor.com/how-dermasensor-works/
[6]  https://pmc.ncbi.nlm.nih.gov/articles/PMC11180084/
[7]  https://www.biospace.com/dermasensor-inc-announces-successful-completion-of-first-ever-fda-pivotal-studies-for-skin-cancer-detection-device-for-primary-care
[8]  https://www.dermasensor.com/skin-cancer-detection-device/
[9]  https://www.accessdata.fda.gov/cdrh_docs/pdf23/DEN230008.pdf
[10] https://www.dermasensor.com/resource/fda-clearance-granted-for-first-ai-powered-medical-device-to-detect-all-three-common-skin-cancers-melanoma-basal-cell-carcinoma-and-squamous-cell-carcinoma/
[11] https://www.nature.com/articles/s41746-024-01161-1
[12] https://www.dermasensor.com/resource/two-new-studies-show-dermasensor-devices-consistent-performance-and-improvements-to-physicians-melanoma-detection/ (https://www.dermasensor.com/resource/dermasensor-inc-announces-positive-results-from-melanoma-clinical-validation-study-of-skin-cancer-detection-device/ this one is a different version of the same article with differing information about whether or not dermasensor is available abroad the U.S.)
[13] https://www.dermasensor.com/contact-us/#:~:text=The%20DermaSensor%20device%20is%20FDA%2Dcleared,in%20all%20other%20U.S.%20states.&text=*Select%20Practice%20Type
[14] https://www.dermasensor.com/resource/dermasensors-mission/
[15] https://pmc.ncbi.nlm.nih.gov/articles/PMC10746496/
[16] https://www.jaadinternational.org/article/S2666-3287(23)00170-0/fulltext
[17] https://www.dermasensor.com/
[18] https://www.dermasensor.com/wp-content/uploads/Clinical-Evidence-Three-Studies.pdf
[19] https://www.dermasensor.com/resource/how-dermasensor-works/
[20] https://www.dermasensor.com/faq/
[21] https://www.dermasensor.com/how-dermasensor-works/#:~:text=Malignant%20transformation%20alters%20cellular%20and,over%202%2C000%20histopathologically%20confirmed%20lesions.
[22] https://www.dermasensor.com/resource/dermasensor-study-results-for-skin-cancer-detection-device-performance-across-skin-tones-of-over-1000-patients/ (below are the sources used by this study)
  1. Merry SP, et al. Clinical Performance of Novel Elastic Scattering Spectroscopy (ESS) in Detection of Skin Cancer: A Blinded, Prospective, Multi-Center Clinical Trial. JCAD 2023 April: 16(4 Suppl): s16.
  2. Bradford PT. Skin cancer in skin of color. Dermatol Nurs. 2009;21(4):170-178.
  3. Taylor SC, Cook-Bolden F. Defining skin of color. Cutis. 2002;69(6):435-437.
  4. Lopes FCPS, et al, Adamson AS. UV Exposure and the Risk of Cutaneous Melanoma in Skin of Color: A Systematic Review. JAMA Dermatol. 2021;157(2):213-219.
[23] https://www.dermasensor.com/#:~:text=The%20DermaSensor%20device%20uses%20a,you%20make%20better%20informed%20decisions.
[24] https://www.nature.com/articles/s41746-024-01161-1
[25] https://www.dermasensor.com/privacy-policy/
[26] https://www.dermasensor.com/resource/dermasensor-secures-16m-to-scale-ai-powered-skin-cancer-detection-in-primary-care/
[27] https://www.dermasensor.com/resource/advancing-skin-cancer-detection-american-academy-of-dermatology-journal-publishes-dermasensors-breakthrough-melanoma-detection-results-from-a-major-multicenter-trial/
[28] Hartman RI, Trepanowski N, Chang MS, Tepedino K, Gianacas C, McNiff JM, Fung M, Braghiroli NF, Grant-Kels JM, Multicenter Prospective Blinded Melanoma Detection Study with a Handheld Elastic Scattering Spectroscopy Device, JAAD International (2023), doi: https:// doi.org/10.1016/j.jdin.2023.10.011.
[29] https://www.dermasensor.com/team-position/board-of-directors/

Class 2 Device Recall?: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfres/res.cfm?id=216559
