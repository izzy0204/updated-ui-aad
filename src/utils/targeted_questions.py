"""
TARGETED QUESTIONING SYSTEM - INTELLIGENT GAP FILLING

PURPOSE:
Uses structured AI questioning to extract specific information when broader 
searches fail to populate model card fields. Employs targeted prompts to find
missing critical information like regulatory status, bias mitigation, and 
technical specifications.

HOW IT WORKS:
1. Gap Analysis: Identifies missing fields in model card
2. Question Selection: Chooses relevant questions for missing categories
3. AI-Powered Extraction: Uses Gemini to answer specific questions from content
4. Field Population: Maps answers back to CHAI schema fields
5. Quality Validation: Ensures extracted information meets quality standards

QUESTION CATEGORIES:
- Metadata: Developer contact, funding, dataset DOI
- Uses & Directions: Clinical workflow, user requirements, deployment
- Warnings: Limitations, failure modes, risk assessment
- Trust Ingredients: Data sources, bias mitigation, ethical review
- Metrics: Performance data, validation studies, fairness assessment
- Resources: Publications, regulatory approvals, compliance

KEY FEATURES:
- CHAI schema aligned question blocks
- Medical AI compliance focused queries
- Hierarchical questioning (general to specific)
- Content-adaptive question selection
- Quality scoring and validation

USAGE:
questioning_system = TargetedQuestioningSystem()
filled_fields = await questioning_system.fill_missing_fields(model_card, content)
"""

import json
from typing import Dict, List, Any, Optional
import sys
import os
from pathlib import Path

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from ai_extractors.ai_extractor import AIContentExtractor


class TargetedQuestioningSystem:
    """
    System that uses targeted AI questions to fill gaps in model card information
    """
    
    def __init__(self):
        self.ai_extractor = AIContentExtractor()
        
        # Enhanced CHAI-aligned question blocks focusing on frequently missing fields
        self.question_blocks = {
            "metadata_missing": [
                "Where can users report issues, get support, or contact the developers (email, GitHub, support portal, documentation)?",
                "What is the DOI, citation, reference, or identifier for the training dataset used?",
                "What funding sources, grants, or institutions supported the model development?"
            ],
            
            "uses_and_directions": [
                "What is the specific purpose of this model (diagnosis, classification, screening, etc.)?",
                "What level of human oversight is required (full supervision, oversight only in development, etc.)?",
                "What are the specific clinical use cases this model supports?",
                "What clinical gap or problem does this model address?",
                "Who are the primary intended users and what expertise do they need?",
                "What are the different ways users can access and deploy this model?",
                "How can the model be run locally, deployed online, or used in batch processing?",
                "What technical knowledge or expertise is required to use this model?",
                "What patient populations or clinical settings is this model designed for?",
                "What are the explicitly cautioned or out-of-scope use cases?",
                "Is this model intended as a diagnostic tool or for other purposes?"
            ],
            
            "warnings": [
                "What specific warnings or contraindications has the developer explicitly provided?",
                "What are the documented technical and clinical limitations of this model?",
                "What are the known failure modes and conditions where the model performs poorly?",
                "How does performance degrade under extreme conditions (lighting, image quality, etc.)?",
                "What subgroup analysis data exists for Fitzpatrick skin types, age, gender, or lesion types?",
                "What geographic or population limitations exist in the training data?",
                "What known or potential biases have been identified in the model?",
                "What is the clinical risk level associated with using this model?",
                "Are there specific patient populations or settings where the model should not be used?",
                "What happens when the model encounters data outside its training domain?"
            ],
            
            "trust_ingredients_missing": [
                "What foundation models, pre-trained models, or base models does this system use or build upon?",
                "Did the data collection process undergo ethical review, IRB approval, or ethics committee oversight?",
                "Which ethical review board, IRB, or ethics committee provided oversight for this research?",
                "Was IRB approval obtained and if so, from which institution or review board?",
                "What security protocols, HIPAA compliance, or data protection measures are in place?",
                "What funding sources, research grants, or institutional support funded this work?",
                "What was the timeline and process for data collection?",
                "What dermatology-specific considerations were included in data collection?",
                "Was there ethical review board oversight or IRB approval?",
                "How relevant is the training data to the intended target population?",
                "What specific bias mitigation approaches were implemented?",
                "What is the ongoing maintenance plan and update process?",
                "What security certifications or compliance frameworks are followed?",
                "What funding sources and stakeholder involvement supported development?"
            ],
            
            "key_metrics_missing": [
                "What was the specific goal or objective of the usefulness/efficacy testing?",
                "What were the actual numerical results (percentages, values) from efficacy testing?",
                "How should the efficacy results be interpreted clinically or practically?",
                "What type of test was conducted (cross-validation, hold-out, clinical trial, etc.)?",
                "What testing data was used for evaluation (dataset description, size, characteristics)?",
                "What validation process and justification was used to ensure robust evaluation?",
                "What specific AUROC, accuracy, sensitivity, specificity, or other performance metrics were achieved?",
                "What was the goal of fairness and equity testing?",
                "What were the fairness testing results across different demographic groups?",
                "What type of fairness evaluation was conducted?",
                "What testing data was used to evaluate fairness and equity?",
                "What was the goal of safety and reliability evaluation?",
                "What were the safety testing results and outcomes?",
                "What type of safety evaluation was performed?",
                "What testing data was used for safety evaluation?",
                "What is the regulatory approval status (FDA, CE mark, etc.)?",
                "What privacy and security protocols are implemented for data protection?"
            ],
            
            "resources_missing": [
                "What evaluation references, papers, or studies specifically evaluate this model's performance?",
                "What peer-reviewed publications, journal articles, or conference papers describe this model?",
                "Where can technical documentation, implementation guides, or user manuals be found?",
                "Are there clinical trials, real-world evidence studies, or validation studies available?",
                "What code repositories, GitHub links, or implementation examples are accessible?"
            ]
        }
    
    async def identify_gaps(self, model_card_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Identify gaps in model card data and determine which targeted questions to ask
        """
        gaps = {}
        
        for section, questions in self.question_blocks.items():
            section_gaps = []
            
            # Check if section exists and has meaningful content
            section_data = model_card_data.get(section, {})
            
            if not section_data or (isinstance(section_data, str) and len(section_data.strip()) < 50):
                # Section is missing or has minimal content
                section_gaps = questions
            else:
                # Check for specific missing fields within the section
                section_gaps = await self._identify_specific_gaps(section_data, questions)
            
            if section_gaps:
                gaps[section] = section_gaps
        
        return gaps
    
    async def _identify_specific_gaps(self, section_data: Any, questions: List[str]) -> List[str]:
        """
        Use AI to identify which specific questions aren't answered in existing data
        """
        if not section_data:
            return questions
        
        try:
            # Convert section data to text for analysis
            if isinstance(section_data, dict):
                text = json.dumps(section_data, indent=2)
            else:
                text = str(section_data)
            
            # Use AI to determine which questions aren't answered
            gap_analysis_prompt = f"""
            Analyze the following model card section content and determine which of these questions are NOT adequately answered:
            
            Section Content:
            {text}
            
            Questions to check:
            {json.dumps(questions, indent=2)}
            
            Return a JSON list of questions that are NOT answered or only partially answered in the content.
            Only include questions where the answer is completely missing or insufficient.
            """
            
            # Use the extractor's _chat_json method which handles Gemini API
            result = self.ai_extractor._chat_json(
                "gap_analysis",
                gap_analysis_prompt,
                "You are an expert at analyzing medical AI model documentation for completeness. Return only valid JSON."
            )
            
            response_data = json.loads(result.choices[0].message.content)
            missing_questions = response_data.get('missing_questions', [])
            
            return missing_questions
            
        except Exception as e:
            print(f"Error in gap analysis: {e}")
            return []
    
    async def fill_gaps_with_targeted_questions(self, 
                                              model_name: str, 
                                              discovered_content: str, 
                                              gaps: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Use targeted AI questions to fill identified gaps in model card data
        """
        filled_data = {}
        
        for section, questions in gaps.items():
            print(f"Filling gaps in {section} section with {len(questions)} targeted questions...")
            
            section_data = {}
            
            for question in questions:
                try:
                    # Ask targeted question with context
                    answer = await self._ask_targeted_question(
                        model_name, 
                        discovered_content, 
                        question,
                        section
                    )
                    
                    if answer and answer.strip():
                        # Create a clean field name from the question
                        field_name = self._question_to_field_name(question)
                        section_data[field_name] = answer
                
                except Exception as e:
                    print(f"Error answering question '{question}': {e}")
                    continue
            
            if section_data:
                filled_data[section] = section_data
        
        return filled_data
    
    async def _ask_targeted_question(self, 
                                   model_name: str, 
                                   context: str, 
                                   question: str,
                                   section: str) -> str:
        """
        Ask a specific targeted question using AI with available context
        """
        prompt = f"""
        You are analyzing information about the medical AI model "{model_name}" to create a comprehensive model card.
        
        Based on all available information about this model, answer the following specific question:
        
        Question: {question}
        
        Available Context:
        {context}
        
        Instructions:
        1. Provide a specific, factual answer based on the available information
        2. If the information is not available in the context, clearly state "Information not available in sources"
        3. Focus on medical AI and dermatology context
        4. Be concise but comprehensive
        5. Include specific details like numbers, dates, organizations when available
        6. For regulatory questions, be specific about approval status and agencies
        
        Answer:
        """
        
        try:
            # Use the extractor's _chat_json method which handles Gemini API
            result = self.ai_extractor._chat_json(
                "targeted_question",
                prompt,
                f"You are an expert medical AI analyst creating detailed model cards for the {section} section. Provide factual, specific answers based on available information.",
                max_tokens=500
            )
            
            answer = result.get('answer', '') if isinstance(result, dict) else str(result).strip()
            
            # Filter out non-informative responses
            if any(phrase in answer.lower() for phrase in [
                "information not available",
                "not specified",
                "not mentioned",
                "cannot be determined",
                "insufficient information"
            ]):
                return ""
            
            return answer
            
        except Exception as e:
            print(f"Error in targeted questioning: {e}")
            return ""
    
    def _question_to_field_name(self, question: str) -> str:
        """
        Convert a question to a clean field name
        """
        # Remove question words and punctuation
        field = question.lower()
        field = field.replace("what is", "").replace("what are", "").replace("how", "")
        field = field.replace("does", "").replace("is", "").replace("are", "")
        field = field.replace("?", "").replace("the model's", "").replace("this model", "")
        
        # Clean up and format
        field = field.strip()
        field = field.replace(" ", "_")
        field = field.replace("'", "")
        field = field.replace("-", "_")
        
        # Remove extra underscores
        while "__" in field:
            field = field.replace("__", "_")
        
        field = field.strip("_")
        
        return field if field else "additional_info"
    
    async def enhance_model_card_with_targeted_questions(self, 
                                                       model_name: str,
                                                       initial_model_card: Dict[str, Any],
                                                       discovered_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main method to enhance a model card using targeted questioning
        """
        print(f"Enhancing model card for {model_name} with targeted questioning...")
        
        # Combine all discovered content into context
        context_parts = []
        for source in discovered_sources:
            if source.get('content') or source.get('clean_text'):
                content = source.get('content') or source.get('clean_text')
                source_type = source.get('type', 'unknown')
                context_parts.append(f"Source ({source_type}): {content}")
        
        combined_context = "\n\n".join(context_parts)
        
        # Identify gaps in the initial model card
        gaps = await self.identify_gaps(initial_model_card)
        
        if not gaps:
            print("No significant gaps identified in model card")
            return initial_model_card
        
        print(f"Identified gaps in {len(gaps)} sections: {list(gaps.keys())}")
        
        # Fill gaps using targeted questions
        filled_data = await self.fill_gaps_with_targeted_questions(
            model_name, 
            combined_context, 
            gaps
        )
        
        # Merge filled data with initial model card
        enhanced_card = initial_model_card.copy()
        for section, data in filled_data.items():
            if section in enhanced_card:
                if isinstance(enhanced_card[section], dict) and isinstance(data, dict):
                    enhanced_card[section].update(data)
                else:
                    enhanced_card[section] = data
            else:
                enhanced_card[section] = data
        
        print(f"Enhanced model card with targeted questioning for {len(filled_data)} sections")
        return enhanced_card