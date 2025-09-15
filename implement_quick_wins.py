#!/usr/bin/env python3
"""
Quick Wins Implementation Script
This script implements immediate improvements to the model card generator.
"""

import os
import sys
from pathlib import Path

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

def implement_search_improvements():
    """Implement enhanced search queries"""
    print("🔍 Implementing enhanced search queries...")
    
    pipeline_file = src_path / "pipelines" / "cardgen_pipeline.py"
    
    # Read current file
    with open(pipeline_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add enhanced search method
    enhanced_search_method = '''
    def _generate_enhanced_search_queries(self, model_name: str, developer_name: str = "") -> List[str]:
        """Generate comprehensive search queries with dermatology-specific terms"""
        base_queries = [model_name]
        
        # Add dermatology-specific terms
        dermatology_terms = [
            f"{model_name} dermatology",
            f"{model_name} skin cancer",
            f"{model_name} melanoma",
            f"{model_name} skin lesion",
            f"{model_name} dermatoscope",
            f"{model_name} teledermatology",
            f"{model_name} dermoscopy"
        ]
        
        # Add AI/ML terms
        ai_terms = [
            f"{model_name} AI",
            f"{model_name} machine learning",
            f"{model_name} deep learning",
            f"{model_name} computer vision",
            f"{model_name} neural network",
            f"{model_name} convolutional neural network"
        ]
        
        # Add clinical terms
        clinical_terms = [
            f"{model_name} clinical trial",
            f"{model_name} FDA approval",
            f"{model_name} medical device",
            f"{model_name} diagnostic",
            f"{model_name} screening",
            f"{model_name} validation"
        ]
        
        # Add developer-specific terms if provided
        developer_terms = []
        if developer_name and developer_name.strip():
            developer_terms = [
                f"{developer_name} {model_name}",
                f"{developer_name} dermatology",
                f"{developer_name} AI"
            ]
        
        return base_queries + dermatology_terms + ai_terms + clinical_terms + developer_terms
'''
    
    # Insert the method before the existing methods
    if "_generate_enhanced_search_queries" not in content:
        # Find a good insertion point
        insertion_point = content.find("def _search_huggingface")
        if insertion_point != -1:
            content = content[:insertion_point] + enhanced_search_method + "\n" + content[insertion_point:]
            
            # Write back to file
            with open(pipeline_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Enhanced search queries implemented")
        else:
            print("❌ Could not find insertion point for search improvements")
    else:
        print("✅ Enhanced search queries already implemented")

def implement_field_population_improvements():
    """Implement enhanced field population"""
    print("📊 Implementing enhanced field population...")
    
    pipeline_file = src_path / "pipelines" / "cardgen_pipeline.py"
    
    # Read current file
    with open(pipeline_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add enhanced field population method
    enhanced_field_method = '''
    def _populate_critical_fields(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]):
        """Populate critical fields that are often missing"""
        print("Populating critical fields...")
        
        aggregated = extracted_content.get('aggregated_content', {})
        all_text = " ".join(aggregated.get('descriptions', []))
        
        # Populate summary if missing
        if not chai_card.summary or chai_card.summary == "Not specified":
            summary = self._extract_summary_from_content(all_text, chai_card.model_name)
            if summary and summary != "Not specified":
                chai_card.summary = summary
                print(f"  ✓ Populated summary: {summary[:50]}...")
        
        # Populate model type if missing
        if not chai_card.model_type or chai_card.model_type == "Not specified":
            model_type = self._extract_model_type_from_content(all_text, chai_card.model_name)
            if model_type and model_type != "Not specified":
                chai_card.model_type = model_type
                print(f"  ✓ Populated model_type: {model_type}")
        
        # Populate performance metrics if missing
        if not chai_card.performance_metrics or chai_card.performance_metrics == "Not specified":
            metrics = self._extract_performance_metrics_from_content(all_text, chai_card.model_name)
            if metrics and metrics != "Not specified":
                chai_card.performance_metrics = metrics
                print(f"  ✓ Populated performance_metrics: {metrics[:50]}...")
        
        # Populate intended use if missing
        if not chai_card.intended_use_and_workflow or chai_card.intended_use_and_workflow == "Not specified":
            intended_use = self._extract_intended_use_from_content(all_text, chai_card.model_name)
            if intended_use and intended_use != "Not specified":
                chai_card.intended_use_and_workflow = intended_use
                print(f"  ✓ Populated intended_use_and_workflow: {intended_use[:50]}...")
        
        # Populate primary users if missing
        if not chai_card.primary_intended_users or chai_card.primary_intended_users == "Not specified":
            primary_users = self._extract_primary_users_from_content(all_text, chai_card.model_name)
            if primary_users and primary_users != "Not specified":
                chai_card.primary_intended_users = primary_users
                print(f"  ✓ Populated primary_intended_users: {primary_users}")
        
        # Populate contact if missing
        if not chai_card.contact or chai_card.contact == "Not specified":
            contact = self._extract_contact_from_content(all_text, chai_card.model_name)
            if contact and contact != "Not specified":
                chai_card.contact = contact
                print(f"  ✓ Populated contact: {contact}")
        
        # Populate geographic availability if missing
        if not chai_card.geographic_availability or chai_card.geographic_availability == "Not specified":
            geo_availability = self._extract_geographic_availability_from_content(all_text, chai_card.model_name)
            if geo_availability and geo_availability != "Not specified":
                chai_card.geographic_availability = geo_availability
                print(f"  ✓ Populated geographic_availability: {geo_availability}")
    
    def _extract_summary_from_content(self, content: str, model_name: str) -> str:
        """Extract model summary from content"""
        if not content or len(content) < 100:
            return "Not specified"
        
        # Use AI to extract summary
        try:
            prompt = f"Extract a concise summary (2-3 sentences) about {model_name} from the following content:\\n\\n{content[:2000]}"
            summary = self.ai_extractor._chat_completion(prompt)
            return summary if summary and len(summary) > 20 else "Not specified"
        except:
            return "Not specified"
    
    def _extract_model_type_from_content(self, content: str, model_name: str) -> str:
        """Extract model type from content"""
        content_lower = content.lower()
        
        # Check for common model types
        if "deep learning" in content_lower or "neural network" in content_lower:
            return "Deep Learning Model"
        elif "machine learning" in content_lower:
            return "Machine Learning Model"
        elif "computer vision" in content_lower:
            return "Computer Vision Model"
        elif "ai" in content_lower or "artificial intelligence" in content_lower:
            return "AI Model"
        else:
            return "Not specified"
    
    def _extract_performance_metrics_from_content(self, content: str, model_name: str) -> str:
        """Extract performance metrics from content"""
        import re
        
        # Look for common performance metrics
        metrics_patterns = [
            r'accuracy[:\s]*(\d+\.?\d*%)',
            r'sensitivity[:\s]*(\d+\.?\d*%)',
            r'specificity[:\s]*(\d+\.?\d*%)',
            r'AUC[:\s]*(\d+\.?\d*)',
            r'ROC[:\s]*(\d+\.?\d*)',
            r'precision[:\s]*(\d+\.?\d*%)',
            r'recall[:\s]*(\d+\.?\d*%)'
        ]
        
        found_metrics = []
        for pattern in metrics_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                metric_name = pattern.split('[')[0]
                found_metrics.append(f"{metric_name}: {matches[0]}")
        
        return "; ".join(found_metrics) if found_metrics else "Not specified"
    
    def _extract_intended_use_from_content(self, content: str, model_name: str) -> str:
        """Extract intended use from content"""
        content_lower = content.lower()
        
        # Check for dermatology-specific uses
        if "skin cancer" in content_lower or "melanoma" in content_lower:
            return "Skin cancer detection and diagnosis"
        elif "dermatology" in content_lower:
            return "Dermatological analysis and diagnosis"
        elif "skin lesion" in content_lower:
            return "Skin lesion analysis and classification"
        elif "diagnostic" in content_lower:
            return "Diagnostic assistance for medical professionals"
        else:
            return "Not specified"
    
    def _extract_primary_users_from_content(self, content: str, model_name: str) -> str:
        """Extract primary users from content"""
        content_lower = content.lower()
        
        # Check for user types
        if "dermatologist" in content_lower:
            return "Dermatologists"
        elif "clinician" in content_lower:
            return "Clinicians"
        elif "physician" in content_lower:
            return "Physicians"
        elif "doctor" in content_lower:
            return "Doctors"
        elif "medical professional" in content_lower:
            return "Medical Professionals"
        else:
            return "Not specified"
    
    def _extract_contact_from_content(self, content: str, model_name: str) -> str:
        """Extract contact information from content"""
        import re
        
        # Look for email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, content)
        if emails:
            return emails[0]
        
        # Look for website URLs
        url_pattern = r'https?://[^\\s]+'
        urls = re.findall(url_pattern, content)
        if urls:
            return urls[0]
        
        return "Not specified"
    
    def _extract_geographic_availability_from_content(self, content: str, model_name: str) -> str:
        """Extract geographic availability from content"""
        content_lower = content.lower()
        
        # Check for geographic terms
        if "usa" in content_lower or "united states" in content_lower:
            return "United States"
        elif "europe" in content_lower or "eu" in content_lower:
            return "Europe"
        elif "global" in content_lower or "worldwide" in content_lower:
            return "Global"
        elif "canada" in content_lower:
            return "Canada"
        elif "uk" in content_lower or "united kingdom" in content_lower:
            return "United Kingdom"
        else:
            return "Not specified"
'''
    
    # Insert the method
    if "_populate_critical_fields" not in content:
        # Find insertion point
        insertion_point = content.find("def _populate_missing_fields")
        if insertion_point != -1:
            content = content[:insertion_point] + enhanced_field_method + "\n" + content[insertion_point:]
            
            # Write back to file
            with open(pipeline_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Enhanced field population implemented")
        else:
            print("❌ Could not find insertion point for field population improvements")
    else:
        print("✅ Enhanced field population already implemented")

def implement_ai_prompt_improvements():
    """Implement enhanced AI prompts"""
    print("🤖 Implementing enhanced AI prompts...")
    
    ai_extractor_file = src_path / "ai_extractors" / "ai_extractor.py"
    
    # Read current file
    with open(ai_extractor_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add enhanced prompt method
    enhanced_prompt_method = '''
    def extract_field_value_enhanced(self, content: str, field_name: str, model_name: str, context: Dict[str, Any] = None) -> str:
        """Enhanced field extraction with dermatology-specific context"""
        
        # Create dermatology-specific context
        dermatology_context = """
        You are analyzing content about a dermatology AI model. Focus on:
        - Skin cancer detection and diagnosis
        - Dermatological imaging and analysis
        - Clinical validation and performance metrics
        - Regulatory approval for medical devices
        - Bias considerations in skin tone representation
        - Clinical workflow integration
        """
        
        # Create field-specific prompts
        field_prompts = {
            'performance_metrics': f"""
            Extract performance metrics for {model_name} from the following content.
            Look for: accuracy, sensitivity, specificity, AUC, ROC curves, precision, recall, F1-score.
            Format as: "Accuracy: 95.2%, Sensitivity: 92.1%, Specificity: 97.8%"
            """,
            
            'bias_considerations': f"""
            Analyze bias considerations for {model_name} from the following content.
            Focus on: skin tone bias, demographic representation, fairness metrics, bias mitigation strategies.
            """,
            
            'clinical_validation': f"""
            Extract clinical validation information for {model_name} from the following content.
            Look for: clinical trials, validation studies, FDA approval, CE marking, clinical evidence.
            """,
            
            'intended_use_and_workflow': f"""
            Determine the intended use and workflow for {model_name} from the following content.
            Focus on: clinical applications, target users, integration with clinical workflows.
            """,
            
            'primary_intended_users': f"""
            Identify the primary intended users for {model_name} from the following content.
            Look for: dermatologists, clinicians, physicians, medical professionals, healthcare workers.
            """,
            
            'model_type': f"""
            Determine the model type for {model_name} from the following content.
            Look for: deep learning, machine learning, computer vision, neural network, AI model.
            """,
            
            'summary': f"""
            Create a concise summary (2-3 sentences) for {model_name} from the following content.
            Focus on: what the model does, its main purpose, and key capabilities.
            """
        }
        
        # Use enhanced prompt
        prompt = field_prompts.get(field_name, f"Extract {field_name} for {model_name}")
        enhanced_prompt = f"{dermatology_context}\\n\\n{prompt}\\n\\nContent:\\n{content[:3000]}"
        
        try:
            return self._chat_completion(enhanced_prompt)
        except Exception as e:
            print(f"Error in enhanced field extraction: {e}")
            return "Not specified"
'''
    
    # Insert the method
    if "extract_field_value_enhanced" not in content:
        # Find insertion point
        insertion_point = content.find("def extract_field_value")
        if insertion_point != -1:
            content = content[:insertion_point] + enhanced_prompt_method + "\n" + content[insertion_point:]
            
            # Write back to file
            with open(ai_extractor_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Enhanced AI prompts implemented")
        else:
            print("❌ Could not find insertion point for AI prompt improvements")
    else:
        print("✅ Enhanced AI prompts already implemented")

def main():
    """Main implementation function"""
    print("🚀 Implementing Quick Wins for Model Card Generator")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not (src_path / "pipelines" / "cardgen_pipeline.py").exists():
        print("❌ Error: Please run this script from the project root directory")
        return
    
    # Implement improvements
    implement_search_improvements()
    implement_field_population_improvements()
    implement_ai_prompt_improvements()
    
    print("\n" + "=" * 60)
    print("✅ Quick wins implementation completed!")
    print("\nNext steps:")
    print("1. Test the improvements with: python debug_pipeline.py")
    print("2. Run a model card generation to see the improvements")
    print("3. Check the PROCESS_WALKTHROUGH.md for detailed information")
    print("4. Review IMPROVEMENTS_GUIDE.md for more advanced improvements")

if __name__ == "__main__":
    main()
