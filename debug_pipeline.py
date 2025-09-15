#!/usr/bin/env python3
"""
Debug script to analyze why model cards are incomplete
This script runs the pipeline step by step and shows detailed information about each stage.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from pipelines.cardgen_pipeline import CardGenPipeline
from core.chai_schema import CHAIModelCard

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"🔍 {title}")
    print("=" * 60)

def print_subsection(title):
    """Print a subsection header"""
    print(f"\n📋 {title}")
    print("-" * 40)

def analyze_sources(sources):
    """Analyze discovered sources"""
    print_subsection("Source Discovery Analysis")
    
    total_sources = 0
    for platform, source_list in sources.items():
        if isinstance(source_list, list):
            count = len(source_list)
            total_sources += count
            print(f"  {platform}: {count} sources")
            
            # Show first few sources for each platform
            for i, source in enumerate(source_list[:3]):
                title = source.get('title', 'No title')[:50]
                url = source.get('url', 'No URL')[:50]
                print(f"    {i+1}. {title} - {url}")
            if len(source_list) > 3:
                print(f"    ... and {len(source_list) - 3} more")
    
    print(f"\n  Total sources discovered: {total_sources}")
    return total_sources

def analyze_extracted_content(extracted_content):
    """Analyze extracted content"""
    print_subsection("Content Extraction Analysis")
    
    content_by_source = extracted_content.get('content_by_source', {})
    aggregated = extracted_content.get('aggregated_content', {})
    
    print(f"  Sources processed: {len(content_by_source)}")
    
    total_content_pieces = 0
    for source_type, sources in content_by_source.items():
        if isinstance(sources, list):
            count = len(sources)
            total_content_pieces += count
            print(f"    {source_type}: {count} content pieces")
    
    print(f"  Total content pieces: {total_content_pieces}")
    
    # Analyze aggregated content
    print(f"\n  Aggregated content:")
    print(f"    Descriptions: {len(aggregated.get('descriptions', []))}")
    print(f"    Metrics: {len(aggregated.get('metrics', {}))}")
    print(f"    Clinical info: {len(aggregated.get('clinical_info', {}))}")
    print(f"    Technical specs: {len(aggregated.get('technical_specs', {}))}")
    print(f"    References: {len(aggregated.get('references', []))}")
    
    return total_content_pieces

def analyze_model_card(chai_card):
    """Analyze the generated model card"""
    print_subsection("Model Card Analysis")
    
    # Count populated fields
    populated_fields = 0
    total_fields = 0
    empty_fields = []
    
    # Get all fields from the dataclass
    for field_name, field_value in chai_card.__dict__.items():
        total_fields += 1
        if field_value and field_value != "" and field_value != "Not specified":
            populated_fields += 1
        else:
            empty_fields.append(field_name)
    
    completion_rate = (populated_fields / total_fields) * 100 if total_fields > 0 else 0
    
    print(f"  Total fields: {total_fields}")
    print(f"  Populated fields: {populated_fields}")
    print(f"  Completion rate: {completion_rate:.1f}%")
    
    # Show populated fields
    print(f"\n  ✅ Populated fields:")
    for field_name, field_value in chai_card.__dict__.items():
        if field_value and field_value != "" and field_value != "Not specified":
            value_preview = str(field_value)[:50] + "..." if len(str(field_value)) > 50 else str(field_value)
            print(f"    {field_name}: {value_preview}")
    
    # Show empty fields
    print(f"\n  ❌ Empty fields ({len(empty_fields)}):")
    for field_name in empty_fields[:10]:  # Show first 10 empty fields
        print(f"    {field_name}")
    if len(empty_fields) > 10:
        print(f"    ... and {len(empty_fields) - 10} more")
    
    return completion_rate

async def debug_pipeline(model_name):
    """Run the pipeline with detailed debugging"""
    print_section("AI MODEL CARD GENERATOR DEBUG")
    print(f"Model: {model_name}")
    
    try:
        # Initialize pipeline
        print_section("STEP 1: PIPELINE INITIALIZATION")
        pipeline = CardGenPipeline()
        print("✅ Pipeline initialized successfully")
        
        # Step 1: Source Discovery
        print_section("STEP 2: SOURCE DISCOVERY")
        sources = await pipeline.discover_model_sources(model_name)
        source_count = analyze_sources(sources)
        
        if source_count == 0:
            print("❌ No sources discovered! This is likely the main issue.")
            return
        
        # Step 2: Content Extraction
        print_section("STEP 3: CONTENT EXTRACTION")
        extracted_content = await pipeline.extract_content_from_sources(sources)
        content_count = analyze_extracted_content(extracted_content)
        
        if content_count == 0:
            print("❌ No content extracted! This is likely the main issue.")
            return
        
        # Step 3: Model Card Generation
        print_section("STEP 4: MODEL CARD GENERATION")
        chai_card = await pipeline.generate_chai_model_card(model_name, extracted_content)
        completion_rate = analyze_model_card(chai_card)
        
        # Summary
        print_section("SUMMARY")
        print(f"Sources discovered: {source_count}")
        print(f"Content pieces extracted: {content_count}")
        print(f"Model card completion: {completion_rate:.1f}%")
        
        if completion_rate < 50:
            print("\n🚨 DIAGNOSIS: Model card is highly incomplete!")
            print("Possible issues:")
            print("  1. Insufficient source discovery")
            print("  2. Content extraction failures")
            print("  3. AI analysis limitations")
            print("  4. Field mapping problems")
        elif completion_rate < 80:
            print("\n⚠️  DIAGNOSIS: Model card is moderately incomplete")
            print("Consider improving:")
            print("  1. Source discovery coverage")
            print("  2. Content extraction quality")
            print("  3. AI analysis depth")
        else:
            print("\n✅ DIAGNOSIS: Model card is reasonably complete")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Main debug function"""
    print("🔍 AI Model Card Generator Debug Tool")
    print("This tool will help identify why model cards are incomplete")
    print()
    
    # Check for API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY environment variable is not set!")
        print("   Set it with: export GEMINI_API_KEY='your_key_here'")
        return
    
    # Get model name
    model_name = input("Enter model name to debug: ").strip()
    if not model_name:
        print("❌ Model name is required!")
        return
    
    await debug_pipeline(model_name)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Debug session cancelled.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
