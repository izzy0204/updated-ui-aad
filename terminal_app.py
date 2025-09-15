#!/usr/bin/env python3
"""
Terminal-based AI Model Card Generator
This script provides a command-line interface for generating model cards.
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
from ai_extractors.ai_extractor import RateLimitExceededError, QuotaExceededError

def print_header():
    """Print application header"""
    print("=" * 60)
    print("🏥 AI MODEL CARD GENERATOR - TERMINAL VERSION")
    print("=" * 60)
    print("Generate professional model cards for dermatology AI models")
    print()

def get_user_input():
    """Get input from user"""
    print("📝 Please provide the following information:")
    print()
    
    model_name = input("🤖 Model Name: ").strip()
    if not model_name:
        print("❌ Model name is required!")
        return None, None
    
    developer_name = input("🏢 Developer/Organization (optional): ").strip()
    
    return model_name, developer_name

def print_progress(message):
    """Print progress message"""
    print(f"⏳ {message}")

def print_success(message):
    """Print success message"""
    print(f"✅ {message}")

def print_error(message):
    """Print error message"""
    print(f"❌ {message}")

def print_sources_used(chai_card):
    """Print detailed information about sources used for the model card"""
    print("\n" + "=" * 60)
    print("📚 SOURCES USED FOR MODEL CARD GENERATION")
    print("=" * 60)
    
    # Extract source information
    sources_summary = getattr(chai_card, 'sources_summary', {}) or {}
    extraction_summary = getattr(chai_card, 'extraction_summary', {}) or {}
    source_citations = getattr(chai_card, 'source_citations', {}) or {}
    
    # Display source counts
    if extraction_summary.get('sources_discovered'):
        source_counts = extraction_summary['sources_discovered']
        print(f"\n📊 Source Discovery Summary:")
        print(f"   Total sources found: {source_counts.get('total', 0)}")
        if source_counts.get('huggingface', 0) > 0:
            print(f"   • HuggingFace: {source_counts['huggingface']}")
        if source_counts.get('github', 0) > 0:
            print(f"   • GitHub: {source_counts['github']}")
        if source_counts.get('pubmed', 0) > 0:
            print(f"   • PubMed: {source_counts['pubmed']}")
        if source_counts.get('arxiv', 0) > 0:
            print(f"   • arXiv: {source_counts['arxiv']}")
        if source_counts.get('websites', 0) > 0:
            print(f"   • Websites: {source_counts['websites']}")
    
    # Display extraction statistics
    if extraction_summary:
        print(f"\n📈 Content Extraction:")
        print(f"   Content extracted from: {extraction_summary.get('content_extracted', 0)} sources")
        print(f"   Success rate: {extraction_summary.get('success_rate', 'N/A')}")
        print(f"   Source types analyzed: {extraction_summary.get('source_types_analyzed', 0)}")
    
    # Display detailed source citations
    if source_citations:
        print(f"\n🔗 Detailed Source Citations:")
        citation_count = 0
        for field_name, citations in source_citations.items():
            if citations and isinstance(citations, list):
                citation_count += len(citations)
                print(f"\n   📝 {field_name.replace('_', ' ').title()}:")
                for i, citation in enumerate(citations[:3], 1):  # Show max 3 citations per field
                    if isinstance(citation, dict):
                        title = citation.get('title', 'Unknown Title')
                        url = citation.get('url', '')
                        source_type = citation.get('type', 'web')
                        print(f"      {i}. {title}")
                        print(f"         URL: {url}")
                        print(f"         Type: {source_type}")
        
        if citation_count > 0:
            print(f"\n   Total citations: {citation_count}")
    
    # Display sources summary if available
    if sources_summary and isinstance(sources_summary, dict):
        print(f"\n📋 Sources Summary:")
        if sources_summary.get('total_analyzed'):
            print(f"   Sources analyzed: {sources_summary['total_analyzed']}")
        if sources_summary.get('successes'):
            print(f"   Successful extractions: {sources_summary['successes']}")
        if sources_summary.get('success_ratio'):
            print(f"   Success ratio: {sources_summary['success_ratio']:.1%}")
    
    print(f"\n💡 All information in this model card was extracted from the sources listed above.")

def display_model_card(chai_card):
    """Display the generated model card"""
    print("\n" + "=" * 60)
    print("📋 GENERATED MODEL CARD")
    print("=" * 60)
    
    # Basic information
    print(f"\n🤖 Model: {chai_card.model_name}")
    print(f"🏢 Developer: {chai_card.developer_organization}")
    print(f"📅 Version: {chai_card.model_version or 'Not specified'}")
    print(f"📊 Release Stage: {chai_card.model_software_release_stage or 'Not specified'}")
    
    # Summary
    if chai_card.summary:
        print(f"\n📝 Summary:")
        print(f"   {chai_card.summary}")
    
    # Performance metrics
    if hasattr(chai_card, 'performance_metrics') and chai_card.performance_metrics:
        print(f"\n📈 Performance Metrics:")
        for metric in chai_card.performance_metrics:
            print(f"   • {metric}")
    
    # Dataset information
    if hasattr(chai_card, 'dataset_description') and chai_card.dataset_description:
        print(f"\n📊 Dataset:")
        print(f"   {chai_card.dataset_description}")
    
    # Clinical oversight
    if hasattr(chai_card, 'clinical_oversight') and chai_card.clinical_oversight:
        print(f"\n👨‍⚕️ Clinical Oversight:")
        print(f"   {chai_card.clinical_oversight}")
    
    # Regulatory information
    if hasattr(chai_card, 'regulatory_approval') and chai_card.regulatory_approval:
        print(f"\n🏛️ Regulatory Approval:")
        print(f"   {chai_card.regulatory_approval}")
    
    # Additional fields
    if hasattr(chai_card, 'intended_use_and_workflow') and chai_card.intended_use_and_workflow:
        print(f"\n🎯 Intended Use:")
        print(f"   {chai_card.intended_use_and_workflow}")
    
    if hasattr(chai_card, 'primary_intended_users') and chai_card.primary_intended_users:
        print(f"\n👥 Primary Users:")
        print(f"   {chai_card.primary_intended_users}")
    
    if hasattr(chai_card, 'bias_mitigation') and chai_card.bias_mitigation:
        print(f"\n⚖️ Bias Mitigation:")
        print(f"   {chai_card.bias_mitigation}")
    
    # Model type and technical details
    if hasattr(chai_card, 'model_type') and chai_card.model_type:
        print(f"\n🔧 Model Type:")
        print(f"   {chai_card.model_type}")
    
    # Contact information
    if hasattr(chai_card, 'contact') and chai_card.contact:
        print(f"\n📞 Contact:")
        print(f"   {chai_card.contact}")
    
    # Geographic availability
    if hasattr(chai_card, 'geographic_availability') and chai_card.geographic_availability:
        print(f"\n🌍 Geographic Availability:")
        print(f"   {chai_card.geographic_availability}")
    
    # Release date
    if hasattr(chai_card, 'release_date') and chai_card.release_date:
        print(f"\n📅 Release Date:")
        print(f"   {chai_card.release_date}")
    
    print(f"\n✅ Model card generation completed successfully!")
    
    # Display sources used
    print_sources_used(chai_card)

def save_model_card(chai_card):
    """Save model card to file"""
    try:
        # Save to JSON file using the model card's built-in method
        filename = f"model_card_{chai_card.model_name.replace(' ', '_').lower()}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(chai_card.to_json())
        
        print_success(f"Model card saved to: {filename}")
        return filename
        
    except Exception as e:
        print_error(f"Failed to save model card: {str(e)}")
        return None

async def main():
    """Main application function"""
    print_header()
    
    # Check for API key
    if not os.environ.get("GEMINI_API_KEY"):
        print_error("GEMINI_API_KEY environment variable is not set!")
        print("   Set it with: export GEMINI_API_KEY='your_key_here'")
        return
    
    # Get user input
    model_name, developer_name = get_user_input()
    if not model_name:
        return
    
    print(f"\n🚀 Starting model card generation for: {model_name}")
    if developer_name:
        print(f"   Developer: {developer_name}")
    print()
    
    try:
        # Initialize pipeline
        print_progress("Initializing AI pipeline...")
        
        # Generate model card
        print_progress("Discovering sources and analyzing content...")
        print("   This may take a few minutes...")
        
        async with CardGenPipeline() as pipeline:
            chai_card = await pipeline.run_full_pipeline(model_name)
        
        print_success("Model card generation completed!")
        
        # Display results
        display_model_card(chai_card)
        
        # Ask if user wants to save
        print("\n" + "=" * 60)
        save_choice = input("💾 Save model card to file? (y/n): ").strip().lower()
        if save_choice in ['y', 'yes']:
            filename = save_model_card(chai_card)
            if filename:
                print(f"📁 File saved in current directory: {filename}")
        
        print("\n🎉 Thank you for using the AI Model Card Generator!")
        
    except RateLimitExceededError as e:
        print_error("Gemini API rate limit exceeded!")
        print("   Please wait a few minutes and try again.")
        
    except QuotaExceededError as e:
        print_error("Gemini API quota exceeded!")
        print("   Please check your billing and usage limits.")
        
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        print("   Please check your internet connection and try again.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye! Thanks for using the AI Model Card Generator.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
