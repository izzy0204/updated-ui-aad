# Model Card Scoring System

## Overview

The Model Card Scoring System provides comprehensive evaluation of generated model cards, including field completion percentages and clinical usability ratings with color-coded feedback (red/yellow/green). This system helps users understand how complete and clinically useful their generated model cards are.

## Features

### **Field Completion Percentage**
- Calculates the percentage of fields that are filled out
- Provides detailed breakdown by category
- Identifies critical missing fields

### 🏥 **Clinical Usability Scoring**
- Evaluates clinical relevance of content
- Assesses quality of clinical terminology
- Identifies missing clinical elements
- Provides weighted scoring based on field importance

### **Color-Coded Ratings**
- **🔴 RED**: Not clinically usable (score < 0.4)
- **🟡 YELLOW**: Partially clinically usable (score 0.4-0.7)
- **🟢 GREEN**: Clinically usable (score > 0.7)

### 📊 **Comprehensive Analysis**
- Individual field scoring
- Category-level analysis
- Quality issue identification
- Actionable recommendations

## Components

### 1. Core Scoring Engine (`src/utils/model_card_scorer.py`)

#### ClinicalUsabilityScorer
- Evaluates clinical relevance of content
- Identifies clinical terminology and requirements
- Scores individual fields for completeness and quality

#### ModelCardScorer
- Orchestrates overall scoring process
- Generates comprehensive reports
- Provides recommendations for improvement

### 2. Integration Points

#### Pipeline Integration (`src/pipelines/cardgen_pipeline.py`)
- Automatically scores generated model cards
- Adds scoring information to pipeline output
- Generates scoring report files

#### Streamlit App Integration (`src/core/app.py`)
- Displays color-coded scoring in UI
- Shows completion percentages
- Highlights critical missing fields

## Scoring Criteria

### Critical Clinical Fields (Weighted)
1. **Intended Use and Workflow** (15%): Clinical indication, workflow, target users
2. **Model Limitations** (12%): Clinical limitations, safety considerations, contraindications
3. **Validation Test Dataset** (12%): Dataset description, performance metrics, validation methodology
4. **Training Data** (10%): Data source, quality, bias considerations
5. **Model Type** (8%): Architecture, modality, clinical domain
6. **Summary** (8%): Clinical purpose, key capabilities, target population
7. **Skin Tone Diversity** (10%): Diversity metrics, bias assessment, fairness considerations
8. **Foundation Models** (8%): Foundation model, fine-tuning, adaptation methods
9. **Uses** (7%): Use cases, clinical scenarios, integration requirements
10. **Warnings** (10%): Safety warnings, risk assessment, monitoring requirements

### Quality Indicators
- **Positive**: Clinical terminology, medical terms, validation data, safety information
- **Negative**: "Not specified", "Unknown", "TBD", placeholder text

## Usage Examples

### Pipeline Integration
```python
from pipelines.cardgen_pipeline import CardGenPipeline

async with CardGenPipeline() as pipeline:
    chai_card, sources, content = await pipeline.generate_model_card(
        model_name="Derm Foundation",
        developer_name="Google Health"
    )
    
    # Scoring information is automatically included
    scoring = sources["scoring"]
    print(f"Completion: {scoring['completion_percentage']}%")
    print(f"Clinical Level: {scoring['clinical_usability_level']}")
    print(f"Rating: {scoring['overall_rating']}")
```

### Direct Scoring
```python
from utils.model_card_scorer import ModelCardScorer, format_score_report

scorer = ModelCardScorer()
score = scorer.score_model_card(model_card_data)

print(format_score_report(score))
```

### Individual Field Scoring
```python
from utils.model_card_scorer import ClinicalUsabilityScorer

scorer = ClinicalUsabilityScorer()
field_score = scorer.score_field("summary", "Model for dermatology...")

print(f"Quality: {field_score.content_quality}")
print(f"Clinical Relevance: {field_score.clinical_relevance}")
print(f"Issues: {field_score.issues}")
```

## Output Formats

### 1. Scoring Summary (JSON)
```json
{
  "completion_percentage": 45.2,
  "clinical_usability_score": 0.234,
  "clinical_usability_level": "yellow",
  "overall_rating": "🟡 FAIR - Needs significant improvements",
  "total_fields": 72,
  "filled_fields": 33,
  "critical_missing_fields": ["Skin Tone Diversity", "Warnings"],
  "recommendations_count": 15,
  "quality_issues_count": 23
}
```

### 2. Detailed Report (Text)
```
============================================================
📊 MODEL CARD SCORING REPORT
============================================================

🎯 OVERALL SCORES:
   Field Completion: 45.2% (33/72 fields)
   Clinical Usability: 0.23 (YELLOW)
   Overall Rating: 🟡 FAIR - Needs significant improvements

🟡 CLINICAL USABILITY: YELLOW

📋 CATEGORY BREAKDOWN:
   Summary:
     Completion: 100.0%
     Quality: 0.45
     Clinical Relevance: 0.23
   ...

🚨 CRITICAL MISSING FIELDS:
   • Skin Tone Diversity
   • Warnings

💡 RECOMMENDATIONS:
   1. 🟡 MODERATE: Model card is partially complete...
   2. 🔴 CRITICAL: Low clinical relevance...
   ...
```

## Test Results

### Derm Foundation Model Test
- **Completion**: 9.7% (7/72 fields)
- **Clinical Usability**: 0.088 (RED)
- **Rating**: 🔴 POOR - Not ready for clinical use
- **Critical Missing**: Skin Tone Diversity, Foundation Models, Uses, Warnings
- **Recommendations**: 20 improvement suggestions

### Sample Data Test
- **Completion**: 100.0% (10/10 fields)
- **Clinical Usability**: 0.224 (YELLOW)
- **Rating**: 🟡 FAIR - Needs significant improvements
- **Recommendations**: 5 improvement suggestions

## File Outputs

The scoring system generates several output files:

1. **`.scoring.txt`**: Detailed scoring report
2. **Pipeline sources**: Scoring summary in JSON format
3. **Streamlit UI**: Color-coded display with recommendations

## Configuration

### Scoring Weights
```python
CRITICAL_CLINICAL_FIELDS = {
    'intended_use_and_workflow': {'weight': 0.15},
    'model_limitations': {'weight': 0.12},
    'validation_test_dataset': {'weight': 0.12},
    # ... other fields
}
```

### Quality Thresholds
```python
# Clinical usability levels
GREEN_THRESHOLD = 0.7    # Clinically usable
YELLOW_THRESHOLD = 0.4   # Partially usable
RED_THRESHOLD = 0.0      # Not usable
```

## Benefits

### For Users
- **Clear Feedback**: Understand model card quality at a glance
- **Actionable Insights**: Specific recommendations for improvement
- **Clinical Focus**: Emphasis on clinical usability and safety
- **Progress Tracking**: Monitor improvements over time

### For Developers
- **Quality Assurance**: Automated evaluation of generated content
- **Debugging**: Identify why model cards aren't fully filled out
- **Optimization**: Focus efforts on high-impact improvements
- **Compliance**: Ensure clinical standards are met

## Integration Points

### 1. Model Card Generation Pipeline
- Automatic scoring after generation
- Scoring data included in pipeline output
- Scoring report files generated

### 2. Streamlit Web Interface
- Color-coded scoring display
- Interactive recommendations
- Progress indicators

### 3. CLI Tools
- Scoring summary in command output
- Detailed reports in generated files
- Integration with existing workflows

## Future Enhancements

1. **Custom Scoring Criteria**: Allow users to define custom scoring weights
2. **Domain-Specific Scoring**: Specialized scoring for different medical domains
3. **Comparative Analysis**: Compare scores across different models
4. **Trend Analysis**: Track scoring improvements over time
5. **Export Options**: Additional output formats (PDF, HTML)

## Troubleshooting

### Common Issues
1. **Low Completion Scores**: Check if model card generation is finding sufficient sources
2. **Poor Clinical Scores**: Verify clinical terminology and validation data are present
3. **Missing Fields**: Review critical field requirements and improve content extraction

### Debug Tools
- Use the caching system to inspect what data was retrieved
- Review individual field scores to identify specific issues
- Check recommendations for targeted improvements

This scoring system provides comprehensive evaluation of model card quality and clinical usability, helping users create better, more complete model cards for clinical applications.
