---
schema_version: clinical-model-card-2.0
---

# [DermGPT](https://www.dermgpt.com/) — Clinical Model Card

## 1) Metadata
- **Model Name:** DermGPT
- **Developer:** Faranak (Fara) Kamangar, MD, Department Chair, Palo Alto Medical Foundation. The model was developed under the Palo Alto Medical Foundation.
- **Regulatory Approval Status:** Regulatory Status Unknown
- **Regulatory Approval Date:** Not disclosed
- **Version:** Not specified
- **Last Updated:** 2026-05-08
- **Availability:** DermGPT is accessible via a web-based platform (dermgpt.com) and was used by dermatologists at the University of California, Irvine, and University of California, Davis for a study, suggesting availability within the US. Global availability is not explicitly stated.

## 2) Summary
- **Summary:** DermGPT is an advanced web-based AI assistant designed to help healthcare providers, particularly dermatologists, with clinical tasks to increase productivity. The tool offers AI-powered skin analysis via image classification (using models like MobileNet, ResNet, ViT), providing high-accuracy detection of various skin conditions (rashes, moles, lesions). Leveraging GPT-4, it provides natural language insights, explanations of detected conditions, treatment recommendations, care suggestions, and follow-up questions for dermatologist consultation.

## 3) Intended Use
- **Medical Purpose:** DermGPT is intended to assist health care providers, especially dermatologists, with clinical tasks to enhance office productivity and de-escalate tasks from moderate to difficult to easy.
- **Acceptable Input:** The input data sources for DermGPT include: For prompt-based queries, users can input questions such as writing insurance denial letters, seeking differential diagnoses, or inquiring about necessary lab checks for medications.
- **Output:** DermGPT is designed to improve office productivity for healthcare providers by assisting with clinical tasks.
- **Role in Decision-Making:** Provides adjunctive referral support for physicians evaluating suspicious lesions; does not replace clinician judgment, biopsy, or definitive diagnosis.
- **Intended Users:** Health care providers; Physicians; Dermatologists; Board-certified dermatologists; Dermatology residents; Dermatology fellows; Medical students Users, specifically health care providers, are expected to have a foundational understanding of dermatology. The developer, Dr. Kamangar, stresses the importance of proofreading all AI-generated content due to potential inaccuracies, implying that users need sufficient expertise to verify the information. For advanced use, understanding of prompts for specific dermatology-related queries is beneficial.
- **Target Patient Population:** While the tool is designed for healthcare providers in dermatology, the underlying knowledge base and applications are relevant to a broad range of dermatological conditions affecting patients. Specific patient populations mentioned in use cases include patients with atopic dermatitis or those presenting with blisters. The skin analysis feature targets various dermatological conditions (rashes, moles, lesions).

## 4) Risks and Limitations
- **Known Performance Limitations:** 
- **Skin Type Representation & Equity:** Not disclosed
- **Required Clinician Oversight:** A prescribing physician (not necessarily a dermatologist) must operate the device and interpret its output. Definitive diagnosis requires clinician judgment and biopsy or pathology confirmation where clinically indicated.

## 5) Mechanism and Development
- **Model Type:** AI/ML classifier analyzing Elastic Scattering Spectroscopy (ESS) recordings from intact skin lesions.
- **Training Data:** DermGPT's training data primarily consists of: [Dataset](Not specified)
- **Model Development & Validation:** A comparative study evaluated DermGPT against ChatGPT using a double-blind method. Two dermatology residents authored a list of questions, which were then posed to each LLM. The models' answers for each question were paired and randomized as A or B. A survey was distributed to dermatologists at the University of California, Irvine, and the University of California, Davis. The raters, comprising 13 attending physicians and 6 residents/fellows (total n=19), were blinded to which model produced which response and were asked to choose preferred answers based on quality, suitability for patient care, or accuracy. Three questions where DermGPT issued disclaimers instead of direct answers were excluded from the evaluation. [Publication](Bhargav Patel, Aneri, Driscoll, William, Lee, Conan H, Zachary, Cameron, Golbari, Nicole M, & Smith, Janellen. [1] (2025). [1] Comparing DermGPT and ChatGPT for Dermatology-Related Queries: Comparative Study. [1] JMIR Dermatology, 8, e74040. [1] doi:10.2196/74040 [1])
- **Clinical Trial:** A double-blind study compared DermGPT's responses to ChatGPT's for dermatology-related queries. The study involved a voluntary, anonymous survey distributed to dermatologists (faculty and residents) at the University of California, Irvine, and the University of California, Davis. A total of 19 responses were received, comprising 13 attending physicians and 6 residents or fellows, corresponding to an overall response rate of approximately 20%. Participants were blinded to which model produced which response and asked to choose preferred answers based on quality, suitability for patient care, or accuracy. Overall, DermGPT's answers (48.1%) were preferred over ChatGPT's (28.4%) with a statistically significant χ2 test (P=.04). However, the study was constrained by a small rater sample (n=19) and multiple ratings per rater and question, so P values are considered exploratory rather than confirmatory, limiting generalizability.
- **Performance:** In a comparative study, ChatGPT's references were preferred overall (46%) over DermGPT's (23.5%), though the χ2 test for references was not significant (P=.50). In the attending group, ChatGPT references were preferred (48.2%) over DermGPT (23.1%), and similarly in the resident group (ChatGPT: 41.1% vs..
- **Limitations in Evaluating Performance:** Not disclosed

## 6) Governance and Monitoring
- **Plans for Ongoing Monitoring:** While no explicit maintenance schedule is provided, the existence of a GitHub repository for 'dermGPT' with development commands, code quality tools (Black, isort, flake8, mypy, bandit, pre-commit), and testing commands (make test, make test-cov) implies an active development and maintenance process. The project uses Mamba for environment management and suggests processes for updating the environment.
- **Scheduled Updates:** Not disclosed
- **Inquiries / Report an Issue:** For questions and support, users are directed to open an issue in the GitHub repository at https://github.com/kfenggg/dermGPT.
