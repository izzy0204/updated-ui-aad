# Derm Foundation — CHAI Model Card (v0.3)

## 1) Metadata
- **Model Name:** Derm Foundation
- **Developer:** Google Health
- **Application URL:** https://developers.google.com/health-ai-developer-foundations/derm-foundation/model-card
- **Inquiries or to report an issue:** See Contact.
- **Release Stage:** Not specified
- **Release Date:** 2023-12-19
- **Version:** Version: 1.0.0
- **Regulatory Approval Status, if applicable:** Not specified
- **Global Availability:** Not specified
- **Summary:** Derm Foundation is a machine learning model designed to accelerate AI development for skin image analysis for dermatology applications. It is pre-trained on large amounts of labeled skin images to produce 6144 dimensional embeddings that capture dense features relevant for analyzing these images.
- **Keywords:** machine learning; dermatology; image analysis; embeddings; skin conditions; classification; severity scoring; image quality

## 2) Uses & Directions
- **Intended Use & Workflow:** Derm Foundation can reduce the training data, compute, and technical expertise necessary to develop task-specific models for skin image analysis. Embeddings can be used for classifying clinical conditions, scoring severity, identifying the body part, and determining image quality.
- **Primary Intended Users:** Businesses and institutions in healthcare and life sciences
- **Necessary knowledge/expertise:** Technical expertise to develop task-specific models for skin image analysis.
- **How to Use:** To use Derm Foundation, download a test image, load the image, format the input, load the model from Hugging Face Hub, call inference, and extract the embedding vector.
- **Targeted patient population:** Not specified
- **Patient consent or disclosure required or suggested?:** Not specified

## 3) Warnings
- **Developer-Supplied Warnings:** Derm Foundation is trained on images with various lightning and noise conditions captured in a real-world environment, but its quality can degrade in extreme conditions. It may not generalize well to data from other countries, patient populations, or image types not used in training.
- **Model Limitations:** Derm Foundation's quality may degrade in extreme lighting and noise conditions. It was trained on data from a limited set of countries and settings (US, Colombia, Australia). It may not generalize well to other countries, patient populations, or image types. The model only generates embeddings and does not generate predictions or diagnosis.
- **Skin type representation & equity:** Not specified
- **Clinical Risk Level:** Not specified

## 4) Trust Ingredients
- **AI System Facts:** Not specified
- **Model Type:** BiT-101x3 CNN (Convolutional Neural Network)
- **Interaction with other systems:** Derm Foundation produces a 6144-dimensional embedding vector as output, which can be used for downstream tasks. It can be used with Google Cloud and Hugging Face.
- **Outcomes & Output:** The model produces a 6144-dimensional embedding vector as output, which can be used for downstream tasks like classifying skin conditions and scoring severity.
- **Type & Value of Solution Output:** Embedding vector of floating point values (Dimensions: 6144)
- **Explanation for how an output is generated:** Derm Foundation is pre-trained on large amounts of labeled skin images to produce 6144 dimensional embeddings that capture dense features relevant for analyzing these images.
- **Foundation Models Used in application, if applicable:** Not specified
- **Input Data Source:** A large number of health-related image-text pairs from the public web, tele-dermatology datasets from the United States and Colombia, a skin cancer dataset from Australia, and additional public images.
- **Output/Input Data Type:** Input: PNG image file 448 x 448 pixels. Output: Embedding vector of floating point values (Dimensions: 6144)
- **Development Data Characterization:** Images from smartphone cameras, other cameras, and dermatoscopes. Images taken by clinicians during consultations or self-captured by patients.
- **Training Data:** Trained in two stages: contrastive learning on image-text pairs from the internet, and fine-tuning for condition classification using clinical datasets from teledermatology services.
- **Exclusion/Inclusion Criteria:** Not specified
- **Demographic representativeness:** The SFT (supervised fine-tuned) model was trained using data from the United States, Colombia, Australia, and public images. It may not generalize well to data from other countries or patient populations not used in training [SOURCE 1]. As with any research, developers should ensure any downstream application is validated to understand performance using data that is appropriately representative of the intended use setting for the specific application (e.g., skin tone/type, age, sex, gender etc.) [SOURCE 1].
- **Dataset (DOI if applicable):** Not specified
- **Dataset Transparency:** The training dataset consists of two stages: A base model pre-trained on a large number of health-related image-text pairs from the public web and an SFT model fine-tuned on tele-dermatology datasets from the United States and Colombia, a skin cancer dataset from Australia, and additional public images [SOURCE 1]. The images come from a mix of device types, including smartphone cameras, other cameras, and dermatoscopes and may have been taken by clinicians or self-captured by patients [SOURCE 1]. Labeling sources vary by dataset, including image-caption pairs from the web, dermatology condition labels from Google-funded dermatologists, and labels provided with clinical datasets [SOURCE 1].
- **Validation/Test Dataset:** Derm Foundation was evaluated for data-efficient accuracy across a range of skin-related classifications tasks [SOURCE 1].
- **Timeline of Data collection:** Not specified
- **Skin tone diversity:** As with any research, developers should ensure any downstream application is validated to understand performance using data that is appropriately representative of the intended use setting for the specific application (e.g., skin tone/type, age, sex, gender etc.) [SOURCE 1].
- **Did the data collection process undergo ethical review:** Not specified
- **Ethical Review Board Oversight:** Not specified
- **IRB Approval:** Not specified
- **Relevance of training data to intended population:** Derm Foundation's SFT model was trained on data from a limited set of countries (United States, Colombia, Australia, public images) and settings (mostly clinical), and may not generalize well to data from other countries, patient populations, or image types not used in training [SOURCE 1].
- **Bias Mitigation Approaches:** Not specified
- **Ongoing Maintenance:** Not specified
- **Security and compliance environment practices or accreditations, if applicable:** Not specified
- **Transparency, Intelligibility, and Accountability mechanisms, if applicable:** Not specified
- **Transparency Information:** Not specified
- **Funding Source of the technical implementation:** Not specified
- **3rd Party Information, if applicable:** Not specified

## 5) Key Metrics
### Usefulness / Efficacy
- **Goal of Metric(s):** Derm Foundation was evaluated for data-efficient accuracy across a range of skin-related classifications tasks. The goal was to improve the efficiency of AI development for skin image analysis with significantly less data and compute than traditional methods [SOURCE 1].
- **Result:** Training a linear classifier on Derm-Foundations embeddings were substantially more performant (10-15% increase in accuracy) than doing the same for a standard BiT-M model across different proportions of training data [SOURCE 1].
- **Interpretation:** The results demonstrate that the Derm Foundation tool can serve as a useful starting point to accelerate skin-related modeling tasks [SOURCE 4].
- **Test Type:** Training a linear classifier on frozen embeddings from BiT-M, Fine-tuned version of BiT-M with an extra dense layer, linear classifier on frozen embeddings from the Derm Foundation API, Fine-tuned version of the model underlying the Derm Foundation API [SOURCE 4].
- **Testing Data Description:** The model was evaluated using teledermatology data with varying dataset sizes (12.5%, 25%, 50%, 100%) to compare embedding-based linear classifiers against fine-tuning [SOURCE 4].
- **Validation Process and Justification:** The modeling variants considered were: A linear classifier on frozen embeddings from BiT-M (a standard pre-trained image model), Fine-tuned version of BiT-M with an extra dense layer for the downstream task, A linear classifier on frozen embeddings from the Derm Foundation API [SOURCE 4].
- **AUROC/Accuracy/etc.:** Not specified

### Fairness & Equity
- **Goal of Metric(s):** Not specified
- **Result:** Not specified
- **Interpretation:** Not specified
- **Test Type:** Not specified
- **Testing Data Description:** Not specified
- **Validation Process and Justification:** Not specified

### Safety & Reliability
- **Goal of Metric(s):** Not specified
- **Result:** Not specified
- **Interpretation:** Not specified
- **Test Type:** Not specified
- **Testing Data Description:** Not specified
- **Validation Process and Justification:** Not specified

## 6) Resources
- **Evaluation References, if available:** Not specified
- **Clinical Trial, if available:** Not specified
- **Peer-Reviewed Publication(s):** Not specified
- **Reimbursement status, if applicable:** Not specified
- **Stakeholders consulted during design of solution:** Not specified

---
*Generated on 2025-10-17T15:18:30.540992 (CHAI Schema v0.3)*
