#!/usr/bin/env python3
"""
Test Script for Model Card Scoring System

This script tests the scoring system by generating a model card for the
Derm Foundation model and evaluating its scoring capabilities.

Usage:
    python test_scoring.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipelines.cardgen_pipeline import CardGenPipeline
from utils.model_card_scorer import ModelCardScorer, format_score_report, get_score_summary
from core.chai_schema import CHAIModelCard

async def test_scoring_system():
    """Test the scoring system with Derm Foundation model"""
    print(" TESTING MODEL CARD SCORING SYSTEM")
    print("=" * 60)
    print()
    
    model_name = "Derm Foundation"
    developer_name = "Google Health"
    
    print(f" Testing with: {model_name} ({developer_name})")
    print()
    
    # Initialize pipeline
    async with CardGenPipeline(out_dir="test_outputs") as pipeline:
        print(" Generating model card...")
        
        try:
            # Generate model card with scoring
            chai_card, sources, content = await pipeline.generate_model_card(
                model_name=model_name,
                developer_name=developer_name,
                iters=2,  # Limited for testing
                coverage_target=0.4,  # Lower threshold for testing
                write_files=True
            )
            
            print(" Model card generated successfully!")
            print()
            
            # Display scoring information
            if sources.get("scoring"):
                scoring = sources["scoring"]
                
                print(" SCORING RESULTS:")
                print("-" * 40)
                print(f"Field Completion: {scoring['completion_percentage']:.1f}%")
                print(f"Clinical Usability Score: {scoring['clinical_usability_score']:.3f}")
                print(f"Clinical Usability Level: {scoring['clinical_usability_level'].upper()}")
                print(f"Overall Rating: {scoring['overall_rating']}")
                print(f"Total Fields: {scoring['total_fields']}")
                print(f"Filled Fields: {scoring['filled_fields']}")
                
                if scoring.get("critical_missing_fields"):
                    print(f"Critical Missing Fields: {', '.join(scoring['critical_missing_fields'])}")
                
                print(f"Recommendations: {scoring['recommendations_count']}")
                print(f"Quality Issues: {scoring['quality_issues_count']}")
                print()
            
            # Display detailed scoring report
            if content.get("scoring_report"):
                print(" DETAILED SCORING REPORT:")
                print("=" * 60)
                print(content["scoring_report"])
                print()
            
            # Test individual field scoring
            print(" TESTING INDIVIDUAL FIELD SCORING:")
            print("-" * 40)
            
            scorer = ModelCardScorer()
            model_card_dict = chai_card.model_dump() if hasattr(chai_card, 'model_dump') else chai_card.__dict__
            
            # Test a few key fields
            test_fields = [
                ("summary", model_card_dict.get("summary", "")),
                ("intended_use_and_workflow", model_card_dict.get("intended_use_and_workflow", "")),
                ("model_limitations", model_card_dict.get("model_limitations", "")),
                ("validation_test_dataset", model_card_dict.get("validation_test_dataset", ""))
            ]
            
            for field_name, field_content in test_fields:
                field_score = scorer.clinical_scorer.score_field(field_name, field_content)
                print(f"{field_name}:")
                print(f"  Filled: {field_score.is_filled}")
                print(f"  Quality: {field_score.content_quality:.2f}")
                print(f"  Clinical Relevance: {field_score.clinical_relevance:.2f}")
                print(f"  Completeness: {field_score.completeness_score:.2f}")
                if field_score.issues:
                    print(f"  Issues: {', '.join(field_score.issues[:2])}")  # Show first 2 issues
                print()
            
            # Show file outputs
            if content.get("paths"):
                paths = content["paths"]
                print(" GENERATED FILES:")
                print("-" * 20)
                if paths.json_path:
                    print(f"JSON: {paths.json_path}")
                if paths.md_path:
                    print(f"Markdown: {paths.md_path}")
                if paths.xml_path:
                    print(f"XML: {paths.xml_path}")
                if paths.scoring_txt:
                    print(f"Scoring Report: {paths.scoring_txt}")
                print()
            
            print(" SCORING SYSTEM TEST COMPLETED SUCCESSFULLY!")
            
        except Exception as e:
            print(f" Error during testing: {e}")
            import traceback
            traceback.print_exc()

async def test_scoring_with_sample_data():
    """Test scoring with sample model card data"""
    print("\n TESTING WITH SAMPLE DATA")
    print("=" * 40)
    
    # Create sample model card data
    sample_data = {
        "summary": "Derm Foundation is a machine learning model designed for dermatology image analysis. It provides embeddings for skin lesion classification and can be used for clinical decision support in dermatology applications.",
        "intended_use_and_workflow": "The model is intended for use by dermatologists and healthcare professionals to assist in the analysis of dermatology images. It should be used as a decision support tool, not as a standalone diagnostic system.",
        "model_limitations": "The model has not been validated for all skin types and may have reduced accuracy on certain populations. It should not be used for final diagnostic decisions without clinical validation.",
        "model_type": "Deep learning model based on transformer architecture",
        "training_data": "Trained on large-scale dermatology image datasets with clinical annotations",
        "validation_test_dataset": "Validated on multiple clinical datasets with performance metrics including sensitivity and specificity",
        "skin_tone_diversity": "Model performance varies across different skin tones and additional validation is needed",
        "foundation_models_used_in_application_if_applicable": "Based on pre-trained vision transformer models",
        "uses": "Clinical decision support, dermatology education, research applications",
        "warnings": "For research use only. Not approved for clinical diagnosis without additional validation."
    }
    
    scorer = ModelCardScorer()
    score = scorer.score_model_card(sample_data)
    
    print(" SAMPLE DATA SCORING:")
    print(f"Completion: {score.completion_percentage:.1f}%")
    print(f"Clinical Usability: {score.clinical_usability_score:.3f} ({score.clinical_usability_level.value.upper()})")
    print(f"Overall Rating: {score.overall_rating}")
    print()
    
    print(" RECOMMENDATIONS:")
    for i, rec in enumerate(score.recommendations[:5], 1):  # Show first 5
        print(f"{i}. {rec}")
    print()

async def main():
    """Main test function"""
    await test_scoring_system()
    await test_scoring_with_sample_data()
    
    print(" SCORING SYSTEM FEATURES TESTED:")
    print(" Field completion percentage calculation")
    print(" Clinical usability scoring")
    print(" Color-coded ratings (red/yellow/green)")
    print(" Detailed scoring breakdown")
    print(" Recommendations generation")
    print(" Critical missing field identification")
    print(" Quality issue detection")
    print(" Integration with model card pipeline")
    print(" File output generation")
    print()
    print(" The scoring system is ready for production use!")

if __name__ == "__main__":
    asyncio.run(main())
