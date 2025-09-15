# Complete Model Card Generation Process Walkthrough

## 🚀 **ENTIRE PROCESS FROM START TO FINISH**

### **Entry Point**
**File**: `terminal_app.py` or `src/core/app.py`
**Method**: `main()` function
**Variable**: `model_name` (user input)

---

## **STEP 1: INITIALIZATION**

### **1.1 Pipeline Setup**
**File**: `src/pipelines/cardgen_pipeline.py`
**Method**: `CardGenPipeline.__init__()`
**Variables Created**:
- `self.session = None` (aiohttp session)
- `self.ai_extractor = AIContentExtractor()` (Gemini AI integration)
- `self.publication_finder = EnhancedPublicationFinder()` (PubMed/arXiv search)
- `self.scraper = None` (web scraper)
- `self.scraper_config = ScraperConfig()` (scraping configuration)

### **1.2 Main Pipeline Call**
**File**: `src/pipelines/cardgen_pipeline.py`
**Method**: `run_full_pipeline(model_name: str)`
**Variable**: `model_name` (user input)

---

## **STEP 2: SOURCE DISCOVERY**

### **2.1 Discover Model Sources**
**File**: `src/pipelines/cardgen_pipeline.py`
**Method**: `discover_model_sources(model_name: str, developer_name: str = "")`
**Variables Created**:
```python
discovery_results = {
    'model_name': model_name,
    'developer_name': developer_name,
    'huggingface': [],
    'github': [],
    'pubmed': [],
    'arxiv': [],
    'websites': [],
    'discovery_timestamp': datetime.now().isoformat()
}
```

### **2.2 Platform-Specific Searches**

#### **2.2.1 HuggingFace Search**
**Method**: `_search_huggingface_models(model_name: str)`
**Variables**:
- `hf_urls = [...]` (list of HuggingFace URLs to search)
- `hf_results = []` (discovered HuggingFace models)

#### **2.2.2 GitHub Search**
**Method**: `_search_github_repos(model_name: str, developer_name: str = "")`
**Variables**:
- `github_urls = [...]` (GitHub search URLs)
- `github_results = []` (discovered repositories)

#### **2.2.3 PubMed Search**
**File**: `src/utils/enhanced_publication_finder.py`
**Method**: `EnhancedPublicationFinder.search_pubmed_papers(query: str)`
**Variables**:
- `pubmed_results = []` (research papers)

#### **2.2.4 ArXiv Search**
**File**: `src/utils/enhanced_publication_finder.py`
**Method**: `EnhancedPublicationFinder.search_arxiv_papers(query: str)`
**Variables**:
- `arxiv_results = []` (preprints)

#### **2.2.5 Website Search**
**Method**: `_search_general_websites(model_name: str)`
**Variables**:
- `website_results = []` (general websites)

---

## **STEP 3: CONTENT EXTRACTION**

### **3.1 Extract Content from Sources**
**File**: `src/pipelines/cardgen_pipeline.py`
**Method**: `extract_content_from_sources(sources: Dict[str, Any])`
**Variables Created**:
```python
extracted_content = {
    'model_name': sources['model_name'],
    'extraction_timestamp': datetime.now().isoformat(),
    'content_by_source': {'all': []},
    'aggregated_content': {
        'descriptions': [],
        'metrics': {},
        'clinical_info': {},
        'technical_specs': {},
        'bias_info': {},
        'references': []
    }
}
```

### **3.2 Web Scraping**
**File**: `src/scrapers/robust_scraper_v2.py`
**Class**: `RobustWebScraper`
**Method**: `extract_content_from_url(url: str)`
**Variables**:
- `result = {...}` (scraped content with title, text, metadata)

### **3.3 AI Content Analysis**
**File**: `src/ai_extractors/ai_extractor.py`
**Class**: `AIContentExtractor`
**Method**: `extract_structured_content(content: str, model_name: str)`
**Variables**:
- `structured_data = {...}` (AI-extracted structured information)

### **3.4 Content Aggregation**
**Method**: `_aggregate_content_from_source(source: Dict, content: Dict)`
**Variables Updated**:
- `extracted_content['aggregated_content']['descriptions'].append(...)`
- `extracted_content['aggregated_content']['metrics'].update(...)`
- `extracted_content['aggregated_content']['clinical_info'].update(...)`

---

## **STEP 4: MODEL CARD GENERATION**

### **4.1 Generate CHAI Model Card**
**File**: `src/pipelines/cardgen_pipeline.py`
**Method**: `generate_chai_model_card(model_name: str, extracted_content: Dict[str, Any], developer_name: str = "")`
**Variables Created**:
```python
chai_card = CHAIModelCard()  # Empty model card
```

### **4.2 Basic Metadata Population**
**Method**: `_populate_basic_metadata_priority(chai_card: CHAIModelCard, extracted_content: Dict)`
**Variables Set**:
- `chai_card.model_name = model_name`
- `chai_card.model_developer = developer_name`
- `chai_card.extraction_timestamp = datetime.now().isoformat()`

### **4.3 Field Population**
**Method**: `_populate_missing_fields(chai_card: CHAIModelCard, extracted_content: Dict)`

#### **4.3.1 AI-Powered Field Extraction**
**File**: `src/ai_extractors/ai_extractor.py`
**Method**: `extract_field_value(content: str, field_name: str, model_name: str)`
**Variables**:
- `field_value = "..."` (AI-extracted field value)

#### **4.3.2 Specific Field Methods**
**Methods** (all in `cardgen_pipeline.py`):
- `_generate_intended_use_workflow(content: str, model_name: str)`
- `_generate_primary_users(content: str, model_name: str)`
- `_generate_targeted_population(content: str, model_name: str)`
- `_generate_bias_considerations(content: str, model_name: str)`
- `_generate_risks_limitations(content: str, model_name: str)`
- `_generate_model_type_description(content: str, model_name: str)`

### **4.4 Targeted Questioning System**
**File**: `src/utils/targeted_questions.py`
**Class**: `TargetedQuestioningSystem`
**Method**: `fill_missing_fields(model_card: CHAIModelCard, content: Dict)`
**Variables**:
- `filled_fields = {...}` (additional field values)

---

## **STEP 5: FINALIZATION**

### **5.1 Source Summary Generation**
**Method**: `_generate_sources_summary(extracted_content: Dict[str, Any])`
**Variables Created**:
```python
sources_summary = {
    'total_analyzed': len(all_sources),
    'successes': successful_extractions,
    'success_ratio': success_rate,
    'source_types_analyzed': len(source_types)
}
```

### **5.2 Model Card Completion**
**Variables Set**:
- `chai_card.sources_summary = sources_summary`
- `chai_card.extraction_summary = {...}`

---

## **STEP 6: OUTPUT GENERATION**

### **6.1 Display in Terminal**
**File**: `terminal_app.py`
**Method**: `display_model_card(chai_card: CHAIModelCard)`
**Variables Accessed**:
- `chai_card.model_name`
- `chai_card.developer_organization`
- `chai_card.model_version`
- `chai_card.model_software_release_stage`
- `chai_card.summary`
- `chai_card.performance_metrics`
- `chai_card.intended_use_and_workflow`
- `chai_card.primary_intended_users`
- `chai_card.bias_mitigation`

### **6.2 File Export**
**File**: `terminal_app.py`
**Method**: `save_model_card(chai_card: CHAIModelCard)`
**Variables**:
- `filename = f"model_card_{chai_card.model_name.replace(' ', '_').lower()}.json"`
- `chai_card.to_json()` (serialized model card)

---

## **🔍 KEY VARIABLES THROUGHOUT THE PROCESS**

### **Input Variables**
- `model_name: str` (user input)
- `developer_name: str` (optional user input)

### **Intermediate Variables**
- `discovery_results: Dict` (source discovery results)
- `extracted_content: Dict` (scraped and analyzed content)
- `chai_card: CHAIModelCard` (final model card object)

### **Output Variables**
- `chai_card` (complete model card)
- `filename` (exported JSON file)

---

## **🚨 WHY MODEL CARDS ARE INCOMPLETE**

### **Potential Issues**:

1. **Limited Source Discovery**: Not all platforms are being searched effectively
2. **Content Extraction Failures**: Web scraping may fail on many sources
3. **AI Analysis Limitations**: Gemini may not extract all relevant information
4. **Field Mapping Issues**: Not all CHAI fields are being populated
5. **Source Quality**: Low-quality sources may not contain comprehensive information

### **Debugging Steps**:

1. **Check Source Discovery**: Verify `discovery_results` contains expected sources
2. **Check Content Extraction**: Verify `extracted_content` has meaningful data
3. **Check AI Analysis**: Verify AI is extracting structured information
4. **Check Field Population**: Verify all CHAI fields are being set
5. **Check Source Quality**: Verify sources contain relevant information

This walkthrough shows the complete data flow from user input to final model card output.
