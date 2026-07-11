"""
Model Card Scoring System

This module provides comprehensive scoring for generated model cards, including:
1. Field completion percentage
2. Clinical usability score
3. Color-coded ratings (red/yellow/green)
4. Detailed scoring breakdown
5. Recommendations for improvement

The scoring system evaluates both completeness and clinical relevance
to help users understand the quality and usability of their model cards.
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import re

from utils.sentence_utils import count_sentences

logger = logging.getLogger(__name__)

class ClinicalUsabilityLevel(Enum):
    """Clinical usability levels"""
    RED = "red"      # Not clinically usable
    YELLOW = "yellow"  # Partially clinically usable
    GREEN = "green"    # Clinically usable

@dataclass
class FieldScore:
    """Score for an individual field"""
    field_name: str
    is_filled: bool
    content_quality: float  # 0.0 to 1.0
    clinical_relevance: float  # 0.0 to 1.0
    completeness_score: float  # 0.0 to 1.0
    issues: List[str]

@dataclass
class CategoryScore:
    """Score for a category of fields"""
    category_name: str
    fields: List[FieldScore]
    completion_percentage: float
    average_quality: float
    clinical_relevance: float
    overall_score: float

@dataclass
class ModelCardScore:
    """Overall model card score"""
    total_fields: int
    filled_fields: int
    completion_percentage: float
    clinical_usability_score: float
    clinical_usability_level: ClinicalUsabilityLevel
    category_scores: Dict[str, CategoryScore]
    overall_rating: str
    recommendations: List[str]
    critical_missing_fields: List[str]
    quality_issues: List[str]

_RAW_FIELD_POINTS: Dict[str, int] = {
    "medical_purpose": 12,
    "role_in_decision_making": 12,
    "required_clinician_oversight": 10,
    "known_failure_modes": 10,
    "performance": 12,
    "regulatory_approval_status": 8,
    "acceptable_input": 8,
    "output": 8,
    "summary": 8,
    "unsupported_clinical_scenarios": 8,
    "target_patient_population": 6,
    "intended_users": 6,
    "model_type": 4,
    "training_data": 4,
    "model_development_and_validation": 4,
    "performance_evaluation_limitations": 4,
    "unsupported_use_cases": 4,
    "ongoing_monitoring_plan": 2,
    "scheduled_updates": 2,
    "contact": 2,
    "developer": 2,
    "model_name": 2,
    "version": 2,
    "last_updated": 1,
    "availability": 1,
}
_POINTS_TOTAL = sum(_RAW_FIELD_POINTS.values())

_FALSE_CERTAINTY_PATTERNS = [
    re.compile(r"\bfda\s+(cleared|approved)\b", re.IGNORECASE),
    re.compile(r"\bce\s+marked\b", re.IGNORECASE),
    re.compile(r"\beua\s+authorized\b", re.IGNORECASE),
]

_METRICS_BONUS_CAP = 0.10
_SUMMARY_PENALTY = 0.05
_FALSE_CERTAINTY_PENALTY = 0.08


class ClinicalUsabilityScorer:
    """Scores model cards for clinical usability"""

    RAW_FIELD_POINTS = _RAW_FIELD_POINTS

    # Critical fields for clinical use (normalized weights)
    CRITICAL_CLINICAL_FIELDS = {
        k: {"weight": v / _POINTS_TOTAL, "required_elements": ["clinical"]}
        for k, v in _RAW_FIELD_POINTS.items()
    }
    
    # Quality indicators for clinical content
    CLINICAL_QUALITY_INDICATORS = {
        'positive': [
            'clinical', 'medical', 'diagnosis', 'treatment', 'patient', 'physician', 'healthcare',
            'dermatology', 'skin', 'lesion', 'biopsy', 'pathology', 'sensitivity', 'specificity',
            'accuracy', 'validation', 'study', 'trial', 'evidence', 'peer-reviewed', 'FDA',
            'regulatory', 'safety', 'efficacy', 'bias', 'fairness', 'diversity', 'demographics',
            'population', 'cohort', 'prospective', 'retrospective', 'multicenter', 'blinded'
        ],
        'negative': [
            'not specified', 'unknown', 'tbd', 'to be determined', 'placeholder', 'example',
            'test', 'demo', 'prototype', 'experimental', 'research only', 'not for clinical use',
            'limitations not specified', 'validation pending', 'under development'
        ]
    }
    
    def __init__(self):
        self.field_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, Dict[str, re.Pattern]]:
        """Compile regex patterns for field analysis"""
        patterns = {}
        
        for field_name, config in self.CRITICAL_CLINICAL_FIELDS.items():
            patterns[field_name] = {
                'positive': [re.compile(rf'\b{indicator}\b', re.IGNORECASE) 
                            for indicator in self.CLINICAL_QUALITY_INDICATORS['positive']],
                'negative': [re.compile(rf'\b{indicator}\b', re.IGNORECASE) 
                            for indicator in self.CLINICAL_QUALITY_INDICATORS['negative']]
            }
        
        return patterns
    
    def score_field(self, field_name: str, content: str) -> FieldScore:
        """Score an individual field"""
        if not content or content.strip() in ['', 'Not specified', 'N/A', 'None']:
            return FieldScore(
                field_name=field_name,
                is_filled=False,
                content_quality=0.0,
                clinical_relevance=0.0,
                completeness_score=0.0,
                issues=['Field is empty or not specified']
            )
        
        content = content.strip()
        is_filled = len(content) > 10  # Minimum meaningful content
        
        # Calculate content quality
        content_quality = self._calculate_content_quality(content)
        
        # Calculate clinical relevance
        clinical_relevance = self._calculate_clinical_relevance(field_name, content)
        
        # Calculate completeness
        completeness_score = self._calculate_completeness(field_name, content)
        
        # Identify issues
        issues = self._identify_field_issues(field_name, content)
        
        return FieldScore(
            field_name=field_name,
            is_filled=is_filled,
            content_quality=content_quality,
            clinical_relevance=clinical_relevance,
            completeness_score=completeness_score,
            issues=issues
        )
    
    def _calculate_content_quality(self, content: str) -> float:
        """Calculate content quality score (0.0 to 1.0)"""
        if not content:
            return 0.0
        
        score = 0.0
        
        # Length factor (longer content generally better, but with diminishing returns)
        length_score = min(len(content) / 500, 1.0) * 0.2
        score += length_score
        
        # Clinical terminology presence
        clinical_terms = sum(1 for pattern in self.CLINICAL_QUALITY_INDICATORS['positive'] 
                            if re.search(rf'\b{pattern}\b', content, re.IGNORECASE))
        clinical_score = min(clinical_terms / 10, 1.0) * 0.3
        score += clinical_score
        
        # Avoidance of negative indicators
        negative_terms = sum(1 for pattern in self.CLINICAL_QUALITY_INDICATORS['negative'] 
                           if re.search(rf'\b{pattern}\b', content, re.IGNORECASE))
        negative_penalty = min(negative_terms / 5, 1.0) * 0.2
        score -= negative_penalty
        
        # Structure indicators (lists, numbers, specific details)
        structure_score = 0.0
        if re.search(r'\d+', content):  # Contains numbers
            structure_score += 0.1
        if re.search(r'[•\-\*]\s', content):  # Contains bullet points
            structure_score += 0.1
        if re.search(r'\b(?:and|or|but|however|therefore)\b', content, re.IGNORECASE):  # Complex sentences
            structure_score += 0.1
        
        score += structure_score
        
        return max(0.0, min(1.0, score))
    
    def _calculate_clinical_relevance(self, field_name: str, content: str) -> float:
        """Calculate clinical relevance score (0.0 to 1.0)"""
        if field_name not in self.CRITICAL_CLINICAL_FIELDS:
            return 0.5  # Neutral for non-critical fields
        
        config = self.CRITICAL_CLINICAL_FIELDS[field_name]
        required_elements = config['required_elements']
        
        # Check for required clinical elements
        element_score = 0.0
        for element in required_elements:
            element_pattern = element.replace("_", r"\s+")
            if re.search(rf'\b{element_pattern}\b', content, re.IGNORECASE):
                element_score += 1.0
        
        element_score = element_score / len(required_elements)
        
        # Check for clinical terminology
        clinical_terms = sum(1 for pattern in self.CLINICAL_QUALITY_INDICATORS['positive'] 
                            if re.search(rf'\b{pattern}\b', content, re.IGNORECASE))
        clinical_score = min(clinical_terms / 5, 1.0)
        
        # Combine scores
        return (element_score * 0.6 + clinical_score * 0.4)
    
    def _calculate_completeness(self, field_name: str, content: str) -> float:
        """Calculate completeness score (0.0 to 1.0)"""
        if field_name not in self.CRITICAL_CLINICAL_FIELDS:
            return 1.0 if content else 0.0
        
        config = self.CRITICAL_CLINICAL_FIELDS[field_name]
        required_elements = config['required_elements']
        
        # Check for required elements
        found_elements = 0
        for element in required_elements:
            element_pattern = element.replace('_', r'\s+')
            if re.search(rf'\b{element_pattern}\b', content, re.IGNORECASE):
                found_elements += 1
        
        return found_elements / len(required_elements)
    
    def _identify_field_issues(self, field_name: str, content: str) -> List[str]:
        """Identify issues with field content"""
        issues = []
        
        if not content or len(content.strip()) < 10:
            issues.append("Content too short or empty")
        
        # Check for negative indicators
        for pattern in self.CLINICAL_QUALITY_INDICATORS['negative']:
            if re.search(rf'\b{pattern}\b', content, re.IGNORECASE):
                issues.append(f"Contains non-clinical language: '{pattern}'")
        
        # Check for required elements in critical fields
        if field_name in self.CRITICAL_CLINICAL_FIELDS:
            config = self.CRITICAL_CLINICAL_FIELDS[field_name]
            required_elements = config['required_elements']
            
            missing_elements = []
            for element in required_elements:
                element_pattern = element.replace('_', r'\s+')
                if not re.search(rf'\b{element_pattern}\b', content, re.IGNORECASE):
                    missing_elements.append(element)
            
            if missing_elements:
                issues.append(f"Missing required elements: {', '.join(missing_elements)}")
        
        return issues

class ModelCardScorer:
    """Main scoring system for model cards"""
    
    def __init__(self):
        self.clinical_scorer = ClinicalUsabilityScorer()
    
    def score_model_card(self, model_card_data: Dict[str, Any]) -> ModelCardScore:
        """Score a complete model card"""
        logger.info("Starting model card scoring")
        
        # Organize fields by category
        categories = self._organize_fields_by_category(model_card_data)
        
        # Score each category
        category_scores = {}
        total_fields = 0
        filled_fields = 0
        weighted_clinical_score = 0.0
        total_weight = 0.0
        
        for category_name, fields in categories.items():
            category_score = self._score_category(category_name, fields)
            category_scores[category_name] = category_score
            
            total_fields += len(fields)
            filled_fields += sum(1 for field_score in category_score.fields if field_score.is_filled)
            
            # Weight clinical score by field importance
            if category_name in self.clinical_scorer.CRITICAL_CLINICAL_FIELDS:
                weight = self.clinical_scorer.CRITICAL_CLINICAL_FIELDS[category_name]['weight']
                weighted_clinical_score += category_score.clinical_relevance * weight
                total_weight += weight
        
        # Calculate overall scores
        completion_percentage = (filled_fields / total_fields * 100) if total_fields > 0 else 0.0
        clinical_usability_score = (weighted_clinical_score / total_weight) if total_weight > 0 else 0.0

        metrics_bonus = self._metrics_bonus(model_card_data)
        clinical_usability_score = min(1.0, clinical_usability_score + metrics_bonus)

        summary_text = str(model_card_data.get("summary") or "")
        if count_sentences(summary_text) > 3:
            clinical_usability_score = max(0.0, clinical_usability_score - _SUMMARY_PENALTY)

        if self._has_false_regulatory_certainty(model_card_data):
            clinical_usability_score = max(0.0, clinical_usability_score - _FALSE_CERTAINTY_PENALTY)

        clinical_usability_score = max(0.0, min(1.0, clinical_usability_score))
        
        # Determine clinical usability level
        clinical_usability_level = self._determine_clinical_level(clinical_usability_score, completion_percentage)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(category_scores, completion_percentage, clinical_usability_score)
        
        # Identify critical missing fields
        critical_missing = self._identify_critical_missing_fields(category_scores)
        
        # Identify quality issues
        quality_issues = self._identify_quality_issues(category_scores)
        
        # Determine overall rating
        overall_rating = self._determine_overall_rating(completion_percentage, clinical_usability_score)
        
        return ModelCardScore(
            total_fields=total_fields,
            filled_fields=filled_fields,
            completion_percentage=completion_percentage,
            clinical_usability_score=clinical_usability_score,
            clinical_usability_level=clinical_usability_level,
            category_scores=category_scores,
            overall_rating=overall_rating,
            recommendations=recommendations,
            critical_missing_fields=critical_missing,
            quality_issues=quality_issues
        )
    
    def _organize_fields_by_category(self, model_card_data: Dict[str, Any]) -> Dict[str, List[Tuple[str, str]]]:
        """Organize model card fields by category"""
        categories = {
            "summary": [],
            "medical_purpose": [],
            "acceptable_input": [],
            "output": [],
            "role_in_decision_making": [],
            "intended_users": [],
            "target_patient_population": [],
            "known_failure_modes": [],
            "unsupported_clinical_scenarios": [],
            "unsupported_use_cases": [],
            "required_clinician_oversight": [],
            "model_type": [],
            "training_data": [],
            "model_development_and_validation": [],
            "performance": [],
            "performance_evaluation_limitations": [],
            "regulatory_approval_status": [],
            "metadata": [],
        }

        camel_to_snake = {
            "modelName": "model_name",
            "medicalPurpose": "medical_purpose",
            "acceptableInput": "acceptable_input",
            "roleInDecisionMaking": "role_in_decision_making",
            "intendedUsers": "intended_users",
            "targetPatientPopulation": "target_patient_population",
            "knownFailureModes": "known_failure_modes",
            "regulatoryApprovalStatus": "regulatory_approval_status",
            "performanceEvaluationLimitations": "performance_evaluation_limitations",
        }

        for field_name, field_value in model_card_data.items():
            fname = camel_to_snake.get(field_name, field_name)
            if fname == "schemaVersion" or fname == "schema_version":
                continue
            if isinstance(field_value, str):
                if fname in categories:
                    categories[fname].append((fname, field_value))
                else:
                    categories["metadata"].append((fname, field_value))
            elif isinstance(field_value, dict):
                if fname == "trainingData" or fname == "training_data":
                    desc = field_value.get("description", "")
                    if desc:
                        categories["training_data"].append(("training_data.description", str(desc)))
                elif fname == "performance":
                    summ = field_value.get("summary", "")
                    if summ:
                        categories["performance"].append(("performance.summary", str(summ)))
                    for i, metric in enumerate(field_value.get("metrics") or []):
                        if not isinstance(metric, dict):
                            continue
                        name = str(metric.get("name") or "").strip()
                        value = str(metric.get("value") or "").strip()
                        if name and value:
                            categories["performance"].append(
                                (f"performance.metrics[{i}]", f"{name}: {value}")
                            )
                elif fname in categories:
                    categories[fname].append((fname, json.dumps(field_value)))
            elif field_value is not None:
                if fname in categories:
                    categories[fname].append((fname, str(field_value)))
        
        return categories

    def _metrics_bonus(self, model_card_data: Dict[str, Any]) -> float:
        perf = model_card_data.get("performance") or {}
        if not isinstance(perf, dict):
            return 0.0
        meaningful = 0
        for metric in perf.get("metrics") or []:
            if not isinstance(metric, dict):
                continue
            if str(metric.get("name") or "").strip() and str(metric.get("value") or "").strip():
                meaningful += 1
        if meaningful == 0:
            return 0.0
        return min(_METRICS_BONUS_CAP, 0.03 * meaningful)

    def _has_false_regulatory_certainty(self, model_card_data: Dict[str, Any]) -> bool:
        status = (
            model_card_data.get("regulatoryApprovalStatus")
            or model_card_data.get("regulatory_approval_status")
            or ""
        )
        if str(status).upper() != "UNKNOWN":
            return False
        corpus = " ".join(
            str(v)
            for v in model_card_data.values()
            if isinstance(v, str) and v.strip()
        )
        return any(pat.search(corpus) for pat in _FALSE_CERTAINTY_PATTERNS)
    
    def _score_category(self, category_name: str, fields: List[Tuple[str, str]]) -> CategoryScore:
        """Score a category of fields"""
        field_scores = []
        
        for field_name, field_value in fields:
            field_score = self.clinical_scorer.score_field(field_name, field_value)
            field_scores.append(field_score)
        
        # Calculate category metrics
        completion_percentage = (sum(1 for f in field_scores if f.is_filled) / len(field_scores) * 100) if field_scores else 0.0
        average_quality = sum(f.content_quality for f in field_scores) / len(field_scores) if field_scores else 0.0
        clinical_relevance = sum(f.clinical_relevance for f in field_scores) / len(field_scores) if field_scores else 0.0
        
        # Overall category score
        overall_score = (completion_percentage * 0.4 + average_quality * 0.3 + clinical_relevance * 0.3) / 100
        
        return CategoryScore(
            category_name=category_name,
            fields=field_scores,
            completion_percentage=completion_percentage,
            average_quality=average_quality,
            clinical_relevance=clinical_relevance,
            overall_score=overall_score
        )
    
    def _determine_clinical_level(self, clinical_score: float, completion_percentage: float) -> ClinicalUsabilityLevel:
        """Determine clinical usability level"""
        # Weighted combination of clinical score and completion
        combined_score = (clinical_score * 0.7 + (completion_percentage / 100) * 0.3)
        
        if combined_score >= 0.7:
            return ClinicalUsabilityLevel.GREEN
        elif combined_score >= 0.4:
            return ClinicalUsabilityLevel.YELLOW
        else:
            return ClinicalUsabilityLevel.RED
    
    def _generate_recommendations(self, category_scores: Dict[str, CategoryScore], 
                                completion_percentage: float, clinical_score: float) -> List[str]:
        """Generate recommendations for improvement"""
        recommendations = []
        
        # Overall completion recommendations
        if completion_percentage < 50:
            recommendations.append("[CRITICAL] Less than 50% of fields are filled. Focus on completing basic model information first.")
        elif completion_percentage < 75:
            recommendations.append("[MODERATE] Model card is partially complete. Add missing field details to improve usability.")
        else:
            recommendations.append("[GOOD] Model card has good field completion. Focus on improving content quality.")
        
        # Clinical usability recommendations
        if clinical_score < 0.3:
            recommendations.append("[CRITICAL] Low clinical relevance. Add clinical terminology, validation data, and safety information.")
        elif clinical_score < 0.6:
            recommendations.append("[MODERATE] Moderate clinical relevance. Enhance clinical details and validation information.")
        else:
            recommendations.append("[GOOD] High clinical relevance. Consider adding more specific clinical use cases.")
        
        # Category-specific recommendations
        for category_name, category_score in category_scores.items():
            if category_score.completion_percentage < 50:
                recommendations.append(f"Complete {category_name.replace('_', ' ').title()} section with detailed information")
            
            if category_score.clinical_relevance < 0.4:
                recommendations.append(f"Add clinical context to {category_name.replace('_', ' ').title()} section")
        
        return recommendations
    
    def _identify_critical_missing_fields(self, category_scores: Dict[str, CategoryScore]) -> List[str]:
        """Identify critically missing fields"""
        critical_missing = []
        
        critical_fields = self.clinical_scorer.CRITICAL_CLINICAL_FIELDS
        
        for category_name, category_score in category_scores.items():
            if category_name in critical_fields and category_score.completion_percentage < 30:
                critical_missing.append(category_name.replace('_', ' ').title())
        
        return critical_missing
    
    def _identify_quality_issues(self, category_scores: Dict[str, CategoryScore]) -> List[str]:
        """Identify quality issues across categories"""
        quality_issues = []
        
        for category_name, category_score in category_scores.items():
            for field_score in category_score.fields:
                if field_score.content_quality < 0.3:
                    quality_issues.append(f"Low quality content in {field_score.field_name}")
                
                if field_score.issues:
                    quality_issues.extend([f"{field_score.field_name}: {issue}" for issue in field_score.issues])
        
        return quality_issues
    
    def _determine_overall_rating(self, completion_percentage: float, clinical_score: float) -> str:
        """Determine overall rating"""
        combined_score = (completion_percentage / 100) * 0.4 + clinical_score * 0.6
        
        if combined_score >= 0.8:
            return "EXCELLENT - Ready for clinical use"
        elif combined_score >= 0.6:
            return "GOOD - Suitable with minor improvements"
        elif combined_score >= 0.4:
            return "FAIR - Needs significant improvements"
        else:
            return "POOR - Not ready for clinical use"

def format_score_report(score: ModelCardScore) -> str:
    """Format a comprehensive score report"""
    report = []
    
    # Header
    report.append("=" * 60)
    report.append("MODEL CARD SCORING REPORT")
    report.append("=" * 60)
    
    # Overall scores
    report.append("\nOVERALL SCORES:")
    report.append(f"   Field Completion: {score.completion_percentage:.1f}% ({score.filled_fields}/{score.total_fields} fields)")
    report.append(f"   Clinical Usability: {score.clinical_usability_score:.2f} ({score.clinical_usability_level.value.upper()})")
    report.append(f"   Overall Rating: {score.overall_rating}")
    
    # Color-coded summary
    level_tag = {"red": "[RED]", "yellow": "[YELLOW]", "green": "[GREEN]"}.get(
        score.clinical_usability_level.value, ""
    )
    report.append(f"\n{level_tag} CLINICAL USABILITY: {score.clinical_usability_level.value.upper()}")
    
    # Category breakdown
    report.append("\nCATEGORY BREAKDOWN:")
    for category_name, category_score in score.category_scores.items():
        if category_score.fields:  # Only show categories with fields
            report.append(f"   {category_name.replace('_', ' ').title()}:")
            report.append(f"     Completion: {category_score.completion_percentage:.1f}%")
            report.append(f"     Quality: {category_score.average_quality:.2f}")
            report.append(f"     Clinical Relevance: {category_score.clinical_relevance:.2f}")
    
    # Critical issues
    if score.critical_missing_fields:
        report.append("\nCRITICAL MISSING FIELDS:")
        for field in score.critical_missing_fields:
            report.append(f"   • {field}")
    
    # Quality issues
    if score.quality_issues:
        report.append("\nQUALITY ISSUES:")
        for issue in score.quality_issues[:10]:  # Limit to top 10 issues
            report.append(f"   • {issue}")
        if len(score.quality_issues) > 10:
            report.append(f"   ... and {len(score.quality_issues) - 10} more issues")
    
    # Recommendations
    report.append("\nRECOMMENDATIONS:")
    for i, rec in enumerate(score.recommendations, 1):
        report.append(f"   {i}. {rec}")
    
    report.append("\n" + "=" * 60)
    
    return "\n".join(report)

def get_score_summary(score: ModelCardScore) -> Dict[str, Any]:
    """Get a summary of scores for API/JSON output"""
    return {
        "completion_percentage": round(score.completion_percentage, 1),
        "clinical_usability_score": round(score.clinical_usability_score, 3),
        "clinical_usability_level": score.clinical_usability_level.value,
        "overall_rating": score.overall_rating,
        "total_fields": score.total_fields,
        "filled_fields": score.filled_fields,
        "critical_missing_fields": score.critical_missing_fields,
        "recommendations_count": len(score.recommendations),
        "quality_issues_count": len(score.quality_issues)
    }
