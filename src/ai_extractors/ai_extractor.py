"""
AI-POWERED CONTENT EXTRACTION MODULE

PURPOSE:
Provides intelligent content analysis using Gemini to extract structured information
from web content for model card generation. Focuses on dermatology-specific 
content analysis, bias detection, and compliance information extraction.

HOW IT WORKS:
1. TracingLogger: Monitors API calls, token usage, and costs
2. AIContentExtractor: Main class for Gemini integration
3. Specialized extraction methods for different content types
4. Fallback mechanisms when API limits are reached
5. Performance monitoring and error handling

KEY FEATURES:
- Gemini integration for advanced content understanding
- Dermatology-specific keyword and concept recognition
- Bias detection and clinical risk assessment
- Structured JSON response formatting
- Cost tracking and usage analytics
- Robust error handling with graceful degradation

EXTRACTION CAPABILITIES:
- Basic metadata (model name, developer, version)
- Technical specifications and architecture
- Performance metrics and evaluation data
- Bias and fairness information
- Clinical usage and risk assessment
- Regulatory and compliance details

USAGE:
extractor = AIContentExtractor()
metadata = extractor.extract_basic_metadata_first(content, model_name)
"""

import os
import json
import re
import time
import random
from typing import Dict, List, Any, Optional, Union
import google.generativeai as genai
from datetime import datetime

import sys
import os
from pathlib import Path

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_dir = current_dir.parent
project_root = src_dir.parent
sys.path.insert(0, str(project_root))

from config.config import make_client, DEFAULT_MODEL, DEFAULT_TEMP

# Configuration via environment variables - Gemini pricing
INPUT_COST_PER_1K = float(os.getenv("INPUT_COST_PER_1K", "0.00125"))  # Gemini 1.5 Pro pricing
OUTPUT_COST_PER_1K = float(os.getenv("OUTPUT_COST_PER_1K", "0.005"))   # Gemini 1.5 Pro pricing
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "12000"))


class RateLimitExceededError(Exception):
    """Custom exception for Gemini API rate limit exceeded"""
    def __init__(self, message="Gemini API rate limit exceeded. Please wait before making more requests.", retry_after=None):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class QuotaExceededError(Exception):
    """Custom exception for Gemini API quota exceeded"""
    def __init__(self, message="Gemini API quota exceeded. Please check your billing and usage limits."):
        self.message = message
        super().__init__(self.message)


class TracingLogger:
    """
    Thin tracer for monitoring Gemini API calls, token usage, and response quality
    """
    
    def __init__(self):
        self.calls = []
        self.total_tokens = 0
        self.total_cost = 0.0
        self.start_time = time.time()
    
    def log_call(self, operation: str, model: str, prompt_tokens: int, completion_tokens: int, 
                 response_time: float, success: bool, content_length: int = 0, error_msg: str = ""):
        """Log an AI API call with detailed metrics"""
        
        # Estimate cost using configured pricing
        input_cost = prompt_tokens * (INPUT_COST_PER_1K / 1000.0)
        output_cost = completion_tokens * (OUTPUT_COST_PER_1K / 1000.0)
        call_cost = input_cost + output_cost
        
        call_data = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'response_time_seconds': response_time,
            'success': success,
            'content_length': content_length,
            'estimated_cost': call_cost,
            'error_message': error_msg
        }
        
        self.calls.append(call_data)
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_cost += call_cost
        
        # Real-time logging with PII redaction
        status = "✓" if success else "✗"
        print(f"{status} {operation} | {prompt_tokens}+{completion_tokens}={prompt_tokens + completion_tokens} tokens | {response_time:.2f}s | ${call_cost:.4f}")
        
        if not success and error_msg:
            print(f"   Error: {error_msg}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive tracing summary"""
        elapsed_time = time.time() - self.start_time
        successful_calls = sum(1 for call in self.calls if call['success'])
        failed_calls = len(self.calls) - successful_calls
        
        return {
            'session_duration_seconds': elapsed_time,
            'total_api_calls': len(self.calls),
            'successful_calls': successful_calls,
            'failed_calls': failed_calls,
            'success_rate': (successful_calls / len(self.calls) * 100) if self.calls else 0,
            'total_tokens_used': self.total_tokens,
            'estimated_total_cost': self.total_cost,
            'average_response_time': sum(call['response_time_seconds'] for call in self.calls) / len(self.calls) if self.calls else 0,
            'tokens_per_minute': (self.total_tokens / elapsed_time * 60) if elapsed_time > 0 else 0,
            'operations_breakdown': self._get_operations_breakdown()
        }
    
    def _get_operations_breakdown(self) -> Dict[str, Any]:
        """Break down metrics by operation type"""
        breakdown = {}
        for call in self.calls:
            op = call['operation']
            if op not in breakdown:
                breakdown[op] = {
                    'count': 0,
                    'total_tokens': 0,
                    'total_cost': 0.0,
                    'avg_response_time': 0.0,
                    'success_rate': 0.0
                }
            
            breakdown[op]['count'] += 1
            breakdown[op]['total_tokens'] += call['total_tokens']
            breakdown[op]['total_cost'] += call['estimated_cost']
        
        # Calculate averages - FIX: use correct variable 'op' from items()
        for op, op_data in breakdown.items():
            op_calls = [call for call in self.calls if call['operation'] == op]
            op_data['avg_response_time'] = sum(call['response_time_seconds'] for call in op_calls) / len(op_calls)
            op_data['success_rate'] = sum(1 for call in op_calls if call['success']) / len(op_calls) * 100
        
        return breakdown
    
    def print_summary(self):
        """Print comprehensive tracing summary"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("📊 AI EXTRACTION TRACING SUMMARY")
        print("="*60)
        print(f"Session Duration: {summary['session_duration_seconds']:.1f} seconds")
        print(f"Total API Calls: {summary['total_api_calls']}")
        print(f"Success Rate: {summary['success_rate']:.1f}% ({summary['successful_calls']}/{summary['total_api_calls']})")
        print(f"Total Tokens: {summary.get('total_tokens_used', 0):,}")
        print(f"Estimated Cost: ${summary.get('estimated_total_cost', 0):.4f}")
        print(f"Avg Response Time: {summary.get('average_response_time', 0):.2f}s")
        print(f"Tokens/Minute: {summary.get('tokens_per_minute', 0):.0f}")
        
        print("\n📋 Operations Breakdown:")
        for op, data in summary['operations_breakdown'].items():
            print(f"  {op}:")
            print(f"    Calls: {data['count']}")
            print(f"    Tokens: {data['total_tokens']:,}")
            print(f"    Cost: ${data['total_cost']:.4f}")
            print(f"    Avg Time: {data['avg_response_time']:.2f}s")
            print(f"    Success: {data['success_rate']:.1f}%")
        print("="*60)


class AIContentExtractor:
    """
    AI-powered content extraction for model card generation
    Uses Gemini for intelligent analysis of web content with comprehensive tracing
    """
    
    # Field name canonicalization mapping
    FIELD_MAPPING = {
        'developer': 'model_developer',
        'outcomes_outputs': 'outcomes_and_outputs',
        'regulatory_status': 'regulatory_approval_status',
        'website': 'contact',
        'organization': 'developer_organization',
        'version': 'model_version'
    }
    
    def __init__(self, client=None):
        self.client = client or make_client()
        self.tracer = TracingLogger()
        self.rate_limit_hit = False
        self.quota_exceeded = False
        self.block_until = 0  # epoch seconds
        self.verbose = bool(int(os.getenv("EXTRACTOR_VERBOSE", "1")))
        if self.verbose:
            print("🔍 AI Content Extractor (Gemini) initialized with tracing enabled")

    def reset_api_flags(self):
        self.rate_limit_hit = False
        self.quota_exceeded = False
        self.block_until = 0

    def is_api_available(self):
        if time.time() < self.block_until:
            return False
        return not self.quota_exceeded

    def _should_skip(self):
        return time.time() < self.block_until or self.quota_exceeded

    def _note_skip(self, op, content_len, reason):
        self.tracer.log_call(
            operation=op, model=DEFAULT_MODEL,
            prompt_tokens=0, completion_tokens=0,
            response_time=0.0, success=False,
            content_length=content_len, error_msg=f"SKIPPED: {reason}"
        )

    def _chat_json(self, op_name, user_prompt, sys_prompt=None, max_tokens=1200, temperature=DEFAULT_TEMP, force=False):
        # DISABLED: Blocking logic commented out
        # if (not force) and self._should_skip():
        #     self._note_skip(op_name, len(user_prompt), "Unavailable (rate/quota)")
        #     return {}
        try:
            t0 = time.time()
            
            # Construct prompt for Gemini
            full_prompt = ""
            if sys_prompt:
                full_prompt += f"System: {sys_prompt}\n\nUser: {user_prompt}"
            else:
                full_prompt = user_prompt
            
            # Add JSON format instruction
            full_prompt += "\n\nPlease respond with valid JSON only."
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Generate content with Gemini
            resp = self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            dt = time.time() - t0

            # Extract token usage (approximation since Gemini doesn't provide exact counts)
            prompt_tokens = len(full_prompt.split()) * 1.3  # Rough approximation
            completion_tokens = len(resp.text.split()) * 1.3 if resp.text else 0
            
            self.tracer.log_call(
                operation=op_name, model=DEFAULT_MODEL,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                response_time=dt, success=True,
                content_length=len(user_prompt)
            )
            
            txt = resp.text or "{}"
            # Extract JSON from response text
            json_match = re.search(r'\{.*\}', txt, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(txt)
                
        except Exception as e:
            err = str(e).lower()
            # DISABLED: Flag setting commented out
            # if "rate limit" in err:
            #     self.rate_limit_hit = True
            #     self.block_until = time.time() + 60  # short TTL
            # elif "insufficient_quota" in err or "quota" in err or "billing" in err:
            #     self.quota_exceeded = True

            self.tracer.log_call(
                operation=op_name, model=DEFAULT_MODEL,
                prompt_tokens=0, completion_tokens=0,
                response_time=0, success=False,
                content_length=len(user_prompt), error_msg=str(e)
            )
            return {}
    
    def _redact(self, s: str) -> str:
        """Mask emails and phone numbers for PII-safe logging"""
        if not isinstance(s, str):
            return str(s)
        
        # Redact emails
        s = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', s)
        
        # Redact phone numbers
        s = re.sub(r'(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', '[PHONE]', s)
        
        return s
    
    def _canonicalize_keys(self, obj: Any) -> Any:
        """Canonicalize field names using the mapping"""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                canonical_key = self.FIELD_MAPPING.get(k, k)
                result[canonical_key] = self._canonicalize_keys(v)
            return result
        elif isinstance(obj, list):
            return [self._canonicalize_keys(item) for item in obj]
        else:
            return obj
    
    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Robust JSON parsing with fallback mechanisms"""
        if not text or not isinstance(text, str):
            return None
        
        # Try direct JSON parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in fenced code block
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try minimal balanced-brace match
        brace_match = re.search(r'(\{(?:[^{}]|(?1))*\})', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _with_retries(self, fn, op_name: str, *args, **kwargs) -> Any:
        """Implement exponential backoff with jitter for retries"""
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if this is a retryable error (429, 5xx)
                is_retryable = (
                    "rate limit" in error_str or 
                    "429" in error_str or
                    "500" in error_str or
                    "502" in error_str or
                    "503" in error_str or
                    "504" in error_str
                )
                
                if not is_retryable or attempt == max_retries - 1:
                    # Not retryable or final attempt - set permanent flags and raise
                    if "quota" in error_str or "billing" in error_str or "insufficient" in error_str:
                        self.quota_exceeded = True
                    elif "rate limit" in error_str:
                        self.rate_limit_hit = True
                    raise e
                
                # Calculate delay with exponential backoff and jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                
                # Check for Retry-After header hint (would need to be passed in)
                retry_after = getattr(e, 'retry_after', None)
                if retry_after:
                    delay = max(delay, float(retry_after))
                
                if self.verbose:
                    print(f"Retrying {op_name} in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                
                time.sleep(delay)
        
        raise Exception(f"Max retries exceeded for {op_name}")
    
    def _chat(self, **kwargs):
        """Normalized Gemini chat completion call with parameter mapping"""
        # Map max_completion_tokens to max_tokens if needed
        if 'max_completion_tokens' in kwargs:
            kwargs['max_tokens'] = kwargs.pop('max_completion_tokens')
        
        # Set defaults
        kwargs.setdefault('model', DEFAULT_MODEL)
        kwargs.setdefault('temperature', DEFAULT_TEMP)
        
        # Add system nudge for JSON
        if 'messages' in kwargs and kwargs['messages']:
            kwargs['messages'][-1]['content'] += " Return ONLY valid JSON. No prose."
        
        # Convert messages format for Gemini
        if 'messages' in kwargs:
            messages = kwargs.pop('messages')
            # Combine system and user messages into a single prompt
            full_prompt = ""
            for msg in messages:
                if msg['role'] == 'system':
                    full_prompt += f"System: {msg['content']}\n\n"
                elif msg['role'] == 'user':
                    full_prompt += f"User: {msg['content']}"
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=kwargs.get('temperature', DEFAULT_TEMP),
                max_output_tokens=kwargs.get('max_tokens', 1200),
            )
            
            # Generate content with Gemini
            return self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
        
        # Fallback for direct prompt
        generation_config = genai.types.GenerationConfig(
            temperature=kwargs.get('temperature', DEFAULT_TEMP),
            max_output_tokens=kwargs.get('max_tokens', 1200),
        )
        
        return self.client.generate_content(
            kwargs.get('prompt', ''),
            generation_config=generation_config
        )
    
    def _get_default_response(self, operation: str) -> Dict[str, Any]:
        """Get consistent default response structure for failed extractions"""
        base_defaults = {
            "model_name": "Not specified",
            "model_developer": "Not specified",
            "developer_organization": "Not specified",
            "model_version": "Not specified",
            "release_date": "Not specified",
            "contact": "Not specified",
            "summary": "Not specified",
            "regulatory_approval_status": "Not specified",
            "funding_source": "Not specified"
        }
        
        if operation == "extract_missing_fields":
            base_defaults.update({
                "exclusion_inclusion_criteria": "Not specified",
                "demographics": "Not specified",
                "training_data": "Not specified",
                "bias_mitigation": "Not specified",
                "irb_approval": "Not specified",
                "detailed_metrics": {},
                "publications_references": {}
            })
        elif operation == "extract_clinical_metrics":
            return {
                "performance_metrics": {},
                "validation_studies": "Not specified",
                "clinical_trials": "Not specified",
                "sample_sizes": "Not specified"
            }
        
        return base_defaults
    
    def _build_basic_metadata_prompt(self, content: str, source_type: str) -> List[Dict[str, str]]:
        """Build prompt template for basic metadata extraction"""
        system_msg = """You are a metadata extraction expert specializing in medical AI models. 
Extract only explicitly mentioned information. Focus on finding exact names, dates, and contact information.
Analyze the source type context to bias extraction appropriately."""
        
        user_msg = f"""Source type: {source_type} (e.g., press release / paper / product page)

Extract basic metadata for a medical AI model from this content. Focus ONLY on information explicitly stated:

{{
    "model_name": "exact model name found",
    "model_developer": "who created this",
    "developer_organization": "organization name",
    "release_date": "when released",
    "model_version": "version info",
    "contact": "contact info (emails, websites, forms)",
    "summary": "what the model does in 1-2 sentences",
    "regulatory_approval_status": "FDA status, approvals mentioned",
    "funding_source": "grants, sponsors mentioned"
}}

Content (first {min(len(content), MAX_INPUT_CHARS)} chars):
{content[:MAX_INPUT_CHARS]}

Extract EXACT text found - don't infer. Use "Not specified" if not found."""
        
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    
    def _extract_contact_details(self, content: str) -> Dict[str, str]:
        """Enhanced contact extraction with heuristics"""
        contact_info = {}
        
        # Email extraction
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        if emails:
            contact_info['email'] = emails[0]
        
        # Phone extraction
        phones = re.findall(r'(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', content)
        if phones:
            contact_info['phone'] = phones[0][1] if phones[0][1] else phones[0][0]
        
        # Website extraction (homepage-like URLs)
        websites = re.findall(r'https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/?(?:[^\s]*)?', content)
        homepage_urls = [url for url in websites if any(term in url.lower() for term in ['home', 'about', 'contact', 'www', '.com/', '.org/', '.edu/'])]
        if homepage_urls:
            contact_info['website'] = homepage_urls[0]
        
        # Address extraction (basic US-style)
        address_pattern = r'\d+\s+[A-Za-z\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)[A-Za-z\s,]*\d{5}(?:-\d{4})?'
        addresses = re.findall(address_pattern, content, re.IGNORECASE)
        if addresses:
            contact_info['address'] = addresses[0]
        
        return contact_info
    
    def _fallback_metrics_extraction(self, content: str) -> Dict[str, str]:
        """Enhanced regex patterns for fallback metrics extraction"""
        patterns = {
            'accuracy': r'accuracy\s*[:=]\s*(\d+\.?\d*\s*%?)',
            'sensitivity': r'sensitivity\s*[:=]\s*(\d+\.?\d*\s*%?)',
            'specificity': r'specificity\s*[:=]\s*(\d+\.?\d*\s*%?)', 
            'auroc': r'(?:auroc|auc)\s*[:=]\s*(\d+\.?\d*)',
            'precision': r'precision\s*[:=]\s*(\d+\.?\d*\s*%?)',
            'recall': r'recall\s*[:=]\s*(\d+\.?\d*\s*%?)',
            'f1': r'f1\s*[:=]\s*(\d+\.?\d*)'
        }
        
        metrics = {}
        for metric, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metrics[metric] = match.group(1)
        
        return metrics
    
    def is_api_available(self) -> bool:
        """Check if API is still available (not rate limited or quota exceeded)"""
        return not (self.rate_limit_hit or self.quota_exceeded)
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get current API status information"""
        return {
            "available": self.is_api_available(),
            "rate_limit_hit": self.rate_limit_hit,
            "quota_exceeded": self.quota_exceeded,
            "status_message": self._get_status_message()
        }
    
    def _get_status_message(self) -> str:
        """Get human-readable status message"""
        if self.quota_exceeded:
            return "API quota exceeded - check billing and usage limits"
        elif self.rate_limit_hit:
            return "Rate limit exceeded - please wait before making more requests"
        else:
            return "API available"
    
    def extract_basic_metadata_first(self, content: str, source_type: str = "web", force: bool = False):
        prompt = f"""
You are extracting basic metadata for a medical AI model. Extract EXACT strings only; use "Not specified" if absent.
Content:
{content[:12000]}

Return JSON with keys:
model_name, model_developer, developer_organization, release_date, model_version,
contact, summary, regulatory_approval_status, funding_source
"""
        return self._chat_json(
            "extract_basic_metadata_first",
            user_prompt=prompt,
            sys_prompt="You are a metadata extraction expert. Output strict JSON.",
            max_tokens=1000,
            force=force,
        )

    def extract_basic_metadata_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        """
        Extract basic metadata from multiple content pieces in a single API call
        content_batch: List of dicts with 'content', 'source_type', 'source_id' keys
        Returns: List of extracted metadata dicts in same order
        """
        if not content_batch:
            return []
        
        if not self.is_api_available() and not force:
            if self.verbose:
                print(f"🚫 Skipping batch API call - {self._get_status_message()}")
            return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]
        
        # Prepare batch prompt
        batch_items = []
        for i, item in enumerate(content_batch):
            content = item.get('content', '')[:8000]  # Limit per item to stay within token limits
            source_type = item.get('source_type', 'web')
            source_id = item.get('source_id', f'source_{i}')
            
            batch_items.append(f"""
ITEM {i+1} (ID: {source_id}, Type: {source_type}):
{content}
---END ITEM {i+1}---
""")
        
        batch_content = "\n".join(batch_items)
        
        prompt = f"""
You are extracting basic metadata for medical AI models from multiple sources. 
Extract EXACT strings only; use "Not specified" if absent.

Process each item separately and return a JSON array with one object per item.
Each object should have these keys:
model_name, model_developer, developer_organization, release_date, model_version,
contact, summary, regulatory_approval_status, funding_source

Return format:
[
  {{"model_name": "...", "model_developer": "...", ...}},  // Item 1
  {{"model_name": "...", "model_developer": "...", ...}},  // Item 2
  ...
]

CONTENT TO PROCESS:
{batch_content}
"""
        
        try:
            result = self._chat_json(
                "extract_basic_metadata_batch",
                user_prompt=prompt,
                sys_prompt="You are a metadata extraction expert. Output strict JSON array.",
                max_tokens=min(4000, len(content_batch) * 500),  # Scale tokens with batch size
                force=force,
            )
            
            # Ensure we return a list
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # Single result case - wrap in list
                return [result]
            else:
                # Fallback - return defaults
                return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]
                
        except Exception as e:
            if self.verbose:
                print(f"Batch extraction failed: {e}")
            return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]

    def extract_missing_fields(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        """
        Extract comprehensive Trust Ingredients and missing fields - enhanced for detailed medical AI model cards
        """
        if not self.is_api_available():
            if self.verbose:
                print(f"🚫 Skipping API call - {self._get_status_message()}")
            return self._get_default_response("extract_missing_fields")
        
        def make_api_call():
            system_msg = """You are a medical AI expert specializing in comprehensive model card documentation. 
Extract every relevant detail for Trust Ingredients focusing on dermatology-specific information, 
bias assessment, and regulatory compliance. Return structured JSON data."""
            
            user_msg = f"""Source type: {source_type} (e.g., press release / paper / product page)

Analyze this medical AI content and extract COMPREHENSIVE Trust Ingredients information.
Focus on dermatology-specific details, clinical validation, and regulatory aspects.

Extract ALL available information for these categories:

{{
    "model_name": "exact AI model name",
    "model_developer": "developer/organization",
    "exclusion_inclusion_criteria": "patient/data criteria mentioned",
    "demographics": "age, gender, ethnicity, sample sizes",
    "training_data": "dataset details, size, sources",
    "bias_mitigation": "fairness strategies, bias handling",
    "irb_approval": "ethics approval, IRB details",
    "detailed_metrics": {{
        "performance_goals": "clinical objectives",
        "specific_results": "exact numerical results",
        "auroc_accuracy_metrics": "AUROC, accuracy values"
    }},
    "publications_references": {{
        "evaluation_references": "evaluation papers",
        "peer_reviewed_publications": "academic publications"
    }}
}}

Content (first {min(len(content), MAX_INPUT_CHARS)} chars):
{content[:MAX_INPUT_CHARS]}

Extract information ONLY if explicitly mentioned. Be thorough and detailed."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=5000
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="extract_missing_fields",
                model=DEFAULT_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time=response_time,
                success=True,
                content_length=len(content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "extract_missing_fields")
            
            response_content = response.text
            if not response_content:
                return self._get_default_response("extract_missing_fields")
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                # Try fallback metrics extraction
                fallback_metrics = self._fallback_metrics_extraction(content)
                default_result = self._get_default_response("extract_missing_fields")
                if fallback_metrics:
                    default_result['detailed_metrics'] = {'auroc_accuracy_metrics': fallback_metrics}
                return default_result
            
            # Canonicalize field names
            result = self._canonicalize_keys(result)
            
            if self.verbose:
                found_count = sum(1 for v in result.values() if v and v != "Not specified")
                print(f"Trust Ingredients extraction: {found_count} fields populated")
            
            return result
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="extract_missing_fields",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(content),
                error_msg=str(e)
            )
            
            error_str = str(e).lower()
            if "rate limit" in error_str:
                raise RateLimitExceededError(f"Gemini API rate limit exceeded: {str(e)}")
            elif "quota" in error_str or "billing" in error_str or "insufficient" in error_str:
                raise QuotaExceededError(f"Gemini API quota exceeded: {str(e)}")
            
            if self.verbose:
                print(f"Error in Trust Ingredients extraction: {e}")
            
            # Try fallback extraction
            fallback_metrics = self._fallback_metrics_extraction(content)
            default_result = self._get_default_response("extract_missing_fields")
            if fallback_metrics:
                default_result['detailed_metrics'] = {'auroc_accuracy_metrics': fallback_metrics}
            
            return default_result

    def extract_missing_fields_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        """
        Extract comprehensive Trust Ingredients from multiple content pieces in a single API call
        content_batch: List of dicts with 'content', 'source_type', 'source_id' keys
        Returns: List of extracted field dicts in same order
        """
        if not content_batch:
            return []
        
        if not self.is_api_available() and not force:
            if self.verbose:
                print(f"🚫 Skipping batch API call - {self._get_status_message()}")
            return [self._get_default_response("extract_missing_fields") for _ in content_batch]
        
        # Prepare batch prompt
        batch_items = []
        for i, item in enumerate(content_batch):
            content = item.get('content', '')[:6000]  # Limit per item
            source_type = item.get('source_type', 'web')
            source_id = item.get('source_id', f'source_{i}')
            
            batch_items.append(f"""
ITEM {i+1} (ID: {source_id}, Type: {source_type}):
{content}
---END ITEM {i+1}---
""")
        
        batch_content = "\n".join(batch_items)
        
        def make_api_call():
            system_msg = """You are a medical AI expert specializing in comprehensive model card documentation. 
Extract every relevant detail for Trust Ingredients focusing on dermatology-specific information, 
bias assessment, and regulatory compliance. Return structured JSON data."""
            
            user_msg = f"""Analyze these medical AI content pieces and extract COMPREHENSIVE Trust Ingredients information.
Focus on dermatology-specific details, clinical validation, and regulatory aspects.

Process each item separately and return a JSON array with one object per item.
Each object should extract ALL available information for these categories:

{{
    "model_name": "exact AI model name",
    "model_developer": "developer/organization",
    "exclusion_inclusion_criteria": "patient/data criteria mentioned",
    "demographics": "age, gender, ethnicity, sample sizes",
    "training_data": "dataset details, size, sources",
    "bias_mitigation": "fairness strategies, bias handling",
    "irb_approval": "ethics approval, IRB details",
    "detailed_metrics": {{
        "performance_goals": "clinical objectives",
        "specific_results": "exact numerical results",
        "auroc_accuracy_metrics": "AUROC, accuracy values"
    }},
    "publications_references": {{
        "evaluation_references": "evaluation papers",
        "peer_reviewed_publications": "academic publications"
    }}
}}

Return format:
[
  {{"model_name": "...", "model_developer": "...", ...}},  // Item 1
  {{"model_name": "...", "model_developer": "...", ...}},  // Item 2
  ...
]

CONTENT TO PROCESS:
{batch_content}

Extract information ONLY if explicitly mentioned. Be thorough and detailed."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=min(6000, len(content_batch) * 800)  # Scale tokens with batch size
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="extract_missing_fields_batch",
                model=DEFAULT_MODEL,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                response_time=response_time,
                success=True,
                content_length=len(batch_content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "extract_missing_fields_batch")
            
            response_content = response.text
            if not response_content:
                return [self._get_default_response("extract_missing_fields") for _ in content_batch]
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                return [self._get_default_response("extract_missing_fields") for _ in content_batch]
            
            # Ensure we return a list
            if isinstance(result, list):
                # Canonicalize field names for each result
                return [self._canonicalize_keys(item) for item in result]
            elif isinstance(result, dict):
                # Single result case - wrap in list
                return [self._canonicalize_keys(result)]
            else:
                return [self._get_default_response("extract_missing_fields") for _ in content_batch]
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="extract_missing_fields_batch",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(batch_content),
                error_msg=str(e)
            )
            
            if self.verbose:
                print(f"Batch missing fields extraction failed: {e}")
            
            return [self._get_default_response("extract_missing_fields") for _ in content_batch]

    def extract_comprehensive_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        """
        Comprehensive batch extraction that combines basic metadata, missing fields, and model information
        in a single optimized API call
        content_batch: List of dicts with 'content', 'source_type', 'source_id' keys
        Returns: List of comprehensive extraction dicts in same order
        """
        if not content_batch:
            return []
        
        if not self.is_api_available() and not force:
            if self.verbose:
                print(f"🚫 Skipping comprehensive batch API call - {self._get_status_message()}")
            return [self._get_default_response("extract_comprehensive") for _ in content_batch]
        
        # Prepare batch prompt
        batch_items = []
        for i, item in enumerate(content_batch):
            content = item.get('content', '')[:5000]  # Limit per item for comprehensive extraction
            source_type = item.get('source_type', 'web')
            source_id = item.get('source_id', f'source_{i}')
            
            batch_items.append(f"""
ITEM {i+1} (ID: {source_id}, Type: {source_type}):
{content}
---END ITEM {i+1}---
""")
        
        batch_content = "\n".join(batch_items)
        
        def make_api_call():
            system_msg = """You are a comprehensive medical AI model analysis expert. Extract ALL relevant information 
for model card generation in a single pass. Focus on dermatology-specific details, clinical validation, 
regulatory compliance, and technical specifications. Return structured JSON data."""
            
            user_msg = f"""Analyze these medical AI content pieces and extract COMPREHENSIVE information for model cards.
Process each item separately and return a JSON array with one object per item.

Each object should extract ALL available information for these categories:

BASIC METADATA:
{{
    "model_name": "exact AI model name",
    "model_developer": "developer/organization", 
    "developer_organization": "organization name",
    "release_date": "when released",
    "model_version": "version info",
    "contact": "contact info (emails, websites, forms)",
    "summary": "what the model does in 1-2 sentences",
    "regulatory_approval_status": "FDA status, approvals mentioned",
    "funding_source": "grants, sponsors mentioned"
}}

TRUST INGREDIENTS:
{{
    "exclusion_inclusion_criteria": "patient/data criteria mentioned",
    "demographics": "age, gender, ethnicity, sample sizes",
    "training_data": "dataset details, size, sources",
    "bias_mitigation": "fairness strategies, bias handling",
    "irb_approval": "ethics approval, IRB details",
    "detailed_metrics": {{
        "performance_goals": "clinical objectives",
        "specific_results": "exact numerical results",
        "auroc_accuracy_metrics": "AUROC, accuracy values"
    }},
    "publications_references": {{
        "evaluation_references": "evaluation papers",
        "peer_reviewed_publications": "academic publications"
    }}
}}

TECHNICAL INFORMATION:
{{
    "model_architecture": "technical architecture details",
    "input_output_specs": "input/output specifications",
    "training_methodology": "training approach, methods", 
    "validation_approach": "validation methodology",
    "deployment_context": "how/where it's deployed",
    "limitations": "known limitations, constraints",
    "clinical_integration": "clinical workflow integration",
    "performance_benchmarks": "benchmark results, comparisons"
}}

CLINICAL METRICS:
{{
    "performance_metrics": {{
        "accuracy": "value with percentage",
        "sensitivity": "value with percentage",
        "specificity": "value with percentage", 
        "auc_roc": "AUROC value",
        "precision": "precision value",
        "recall": "recall value"
    }},
    "validation_studies": "validation methodology description",
    "clinical_trials": "clinical trial information",
    "sample_sizes": "training/validation sample sizes",
    "confidence_intervals": "confidence intervals for metrics"
}}

Return format:
[
  {{"model_name": "...", "model_developer": "...", "exclusion_inclusion_criteria": "...", ...}},  // Item 1
  {{"model_name": "...", "model_developer": "...", "exclusion_inclusion_criteria": "...", ...}},  // Item 2
  ...
]

CONTENT TO PROCESS:
{batch_content}

Extract information ONLY if explicitly mentioned. Be thorough and comprehensive."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=min(8000, len(content_batch) * 1000)  # Scale tokens with batch size
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="extract_comprehensive_batch",
                model=DEFAULT_MODEL,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                response_time=response_time,
                success=True,
                content_length=len(batch_content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "extract_comprehensive_batch")
            
            response_content = response.text
            if not response_content:
                return [self._get_default_response("extract_comprehensive") for _ in content_batch]
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                return [self._get_default_response("extract_comprehensive") for _ in content_batch]
            
            # Ensure we return a list
            if isinstance(result, list):
                # Canonicalize field names for each result
                return [self._canonicalize_keys(item) for item in result]
            elif isinstance(result, dict):
                # Single result case - wrap in list
                return [self._canonicalize_keys(result)]
            else:
                return [self._get_default_response("extract_comprehensive") for _ in content_batch]
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="extract_comprehensive_batch",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(batch_content),
                error_msg=str(e)
            )
            
            if self.verbose:
                print(f"Comprehensive batch extraction failed: {e}")
            
            return [self._get_default_response("extract_comprehensive") for _ in content_batch]

    def extract_model_information(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        """
        Extract comprehensive model information with enhanced prompting
        """
        if not self.is_api_available():
            if self.verbose:
                print(f"🚫 Skipping API call - {self._get_status_message()}")
            return self._get_default_response("extract_model_information")
        
        def make_api_call():
            system_msg = """You are an AI model analysis expert. Extract comprehensive technical and clinical information 
about AI models from various source types. Focus on architecture, performance, validation, and clinical deployment."""
            
            user_msg = f"""Source type: {source_type} (e.g., press release / paper / product page)

Extract comprehensive model information:

{{
    "model_architecture": "technical architecture details",
    "input_output_specs": "input/output specifications",
    "training_methodology": "training approach, methods", 
    "validation_approach": "validation methodology",
    "deployment_context": "how/where it's deployed",
    "limitations": "known limitations, constraints",
    "clinical_integration": "clinical workflow integration",
    "performance_benchmarks": "benchmark results, comparisons"
}}

Content (first {min(len(content), MAX_INPUT_CHARS)} chars):
{content[:MAX_INPUT_CHARS]}

Focus on technical and clinical details. Extract only explicitly mentioned information."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=3000
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="extract_model_information",
                model=DEFAULT_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time=response_time,
                success=True,
                content_length=len(content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "extract_model_information")
            
            response_content = response.text
            if not response_content:
                return {"model_architecture": "Not specified", "limitations": "Not specified"}
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                return {"model_architecture": "Not specified", "limitations": "Not specified"}
            
            # Canonicalize field names
            result = self._canonicalize_keys(result)
            
            return result
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="extract_model_information",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(content),
                error_msg=str(e)
            )
            
            error_str = str(e).lower()
            if "rate limit" in error_str:
                raise RateLimitExceededError(f"Gemini API rate limit exceeded: {str(e)}")
            elif "quota" in error_str or "billing" in error_str or "insufficient" in error_str:
                raise QuotaExceededError(f"Gemini API quota exceeded: {str(e)}")
            
            return {"model_architecture": "Not specified", "limitations": "Not specified"}

    def extract_clinical_metrics(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        """
        Extract clinical performance metrics and validation information
        """
        if not self.is_api_available():
            if self.verbose:
                print(f"🚫 Skipping API call - {self._get_status_message()}")
            return self._get_default_response("extract_clinical_metrics")
        
        def make_api_call():
            system_msg = """You are a medical AI validation expert. Extract precise quantitative metrics, 
clinical trial data, and validation studies with exact numerical values."""
            
            user_msg = f"""Source type: {source_type} (e.g., press release / paper / product page)

Extract clinical performance metrics:

{{
    "performance_metrics": {{
        "accuracy": "value with percentage",
        "sensitivity": "value with percentage",
        "specificity": "value with percentage", 
        "auc_roc": "AUROC value",
        "precision": "precision value",
        "recall": "recall value"
    }},
    "validation_studies": "validation methodology description",
    "clinical_trials": "clinical trial information",
    "sample_sizes": "training/validation sample sizes",
    "confidence_intervals": "confidence intervals for metrics"
}}

Content (first {min(len(content), MAX_INPUT_CHARS)} chars):
{content[:MAX_INPUT_CHARS]}

Focus on exact numerical values and statistical measures."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=2000
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="extract_clinical_metrics",
                model=DEFAULT_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time=response_time,
                success=True,
                content_length=len(content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "extract_clinical_metrics")
            
            response_content = response.text
            if not response_content:
                return self._get_default_response("extract_clinical_metrics")
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                # Try fallback metrics extraction
                fallback_metrics = self._fallback_metrics_extraction(content)
                if fallback_metrics:
                    return {
                        "performance_metrics": fallback_metrics,
                        "validation_studies": "Not specified"
                    }
                return self._get_default_response("extract_clinical_metrics")
            
            # Canonicalize field names
            result = self._canonicalize_keys(result)
            
            return result
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="extract_clinical_metrics",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(content),
                error_msg=str(e)
            )
            
            error_str = str(e).lower()
            if "rate limit" in error_str:
                raise RateLimitExceededError(f"Gemini API rate limit exceeded: {str(e)}")
            elif "quota" in error_str or "billing" in error_str or "insufficient" in error_str:
                raise QuotaExceededError(f"Gemini API quota exceeded: {str(e)}")
            
            # Try fallback metrics extraction
            fallback_metrics = self._fallback_metrics_extraction(content)
            if fallback_metrics:
                return {
                    "performance_metrics": fallback_metrics,
                    "validation_studies": "Not specified"
                }
            
            return self._get_default_response("extract_clinical_metrics")

    def generate_regulatory_compliance_info(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        """
        Extract regulatory and compliance information for medical AI
        """
        if not self.is_api_available():
            if self.verbose:
                print(f"🚫 Skipping API call - {self._get_status_message()}")
            return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}
        
        def make_api_call():
            system_msg = """You are a medical device regulatory expert specializing in AI compliance. 
Focus on FDA approvals, clinical oversight, and healthcare regulation compliance."""
            
            user_msg = f"""Source type: {source_type} (e.g., press release / paper / product page)

Extract regulatory compliance information:

{{
    "regulatory_approvals": "FDA, CE mark, other approvals",
    "clinical_oversight": "dermatologist involvement", 
    "compliance_standards": "healthcare standards",
    "quality_management": "quality assurance processes",
    "clinical_workflow_integration": "clinical practice integration",
    "human_oversight_requirements": "required supervision",
    "cfr_compliance": "45 CFR 170.315 compliance info"
}}

Content (first {min(len(content), MAX_INPUT_CHARS)} chars):
{content[:MAX_INPUT_CHARS]}

Focus on specific regulatory approvals and compliance measures."""
            
            start_time = time.time()
            
            response = self._chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=1500
            )
            
            response_time = time.time() - start_time
            
            # Safe access to usage - Gemini doesn't provide exact token counts
            prompt_tokens = len(system_msg.split()) * 1.3 + len(user_msg.split()) * 1.3
            completion_tokens = len(response.text.split()) * 1.3 if response.text else 0
            
            # Log the API call
            self.tracer.log_call(
                operation="generate_regulatory_compliance_info",
                model=DEFAULT_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time=response_time,
                success=True,
                content_length=len(content)
            )
            
            return response
        
        try:
            response = self._with_retries(make_api_call, "generate_regulatory_compliance_info")
            
            response_content = response.text
            if not response_content:
                return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}
            
            # Parse JSON with fallback
            result = self._parse_json(response_content)
            if result is None:
                return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}
            
            # Canonicalize field names
            result = self._canonicalize_keys(result)
            
            return result
            
        except Exception as e:
            # Log the error
            self.tracer.log_call(
                operation="generate_regulatory_compliance_info",
                model=DEFAULT_MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0,
                success=False,
                content_length=len(content),
                error_msg=str(e)
            )
            
            error_str = str(e).lower()
            if "rate limit" in error_str:
                raise RateLimitExceededError(f"Gemini API rate limit exceeded: {str(e)}")
            elif "quota" in error_str or "billing" in error_str or "insufficient" in error_str:
                raise QuotaExceededError(f"Gemini API quota exceeded: {str(e)}")
            
            return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}

    def _fallback_extraction(self, content: str) -> Dict[str, Any]:
        """
        Enhanced fallback extraction using pattern matching when AI fails
        """
        # Enhanced pattern matching
        fallback_metrics = self._fallback_metrics_extraction(content)
        contact_details = self._extract_contact_details(content)
        
        extracted = {
            "model_name": "Not specified",
            "model_developer": "Not specified", 
            "performance_metrics": fallback_metrics,
            "limitations": "Not specified",
            "contact": '; '.join([f"{k}: {v}" for k, v in contact_details.items()]) if contact_details else "Not specified"
        }
        
        return extracted
    
    def extract_field_value_enhanced(self, content: str, field_name: str, model_name: str, context: Dict[str, Any] = None) -> str:
        """Enhanced field extraction with context awareness"""
        
        # Create domain-specific prompts
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
            
            'intended_use': f"""
            Determine the intended use and workflow for {model_name} from the following content.
            Focus on: clinical applications, target users, integration with clinical workflows.
            """
        }
        
        # Use enhanced prompt
        prompt = field_prompts.get(field_name, f"Extract {field_name} for {model_name}")
        enhanced_prompt = f"{dermatology_context}\n\n{prompt}\n\nContent:\n{content}"
        
        return self._chat_completion(enhanced_prompt)
    
    async def extract_structured_content_enhanced(self, content: str, model_name: str) -> Dict[str, Any]:
        """Enhanced structured content extraction with multiple passes"""
        
        # Pass 1: Basic extraction
        basic_extraction = await self.extract_structured_content(content, model_name)
        
        # Pass 2: Domain-specific extraction
        domain_extraction = await self._extract_dermatology_specific_info(content, model_name)
        
        # Pass 3: Technical validation
        technical_validation = await self._validate_technical_info(content, model_name)
        
        # Pass 4: Clinical context
        clinical_context = await self._extract_clinical_context(content, model_name)
        
        # Combine results
        enhanced_extraction = {
            **basic_extraction,
            **domain_extraction,
            **technical_validation,
            **clinical_context
        }
        
        return enhanced_extraction
    
    async def _extract_dermatology_specific_info(self, content: str, model_name: str) -> Dict[str, Any]:
        """Extract dermatology-specific information"""
        prompt = f"""
        Extract dermatology-specific information for {model_name} from the following content:
        
        Focus on:
        1. Skin cancer types (melanoma, basal cell carcinoma, squamous cell carcinoma)
        2. Dermatological imaging modalities (dermoscopy, total body photography, etc.)
        3. Clinical validation in dermatology settings
        4. Bias considerations in skin tone representation
        5. Integration with dermatology workflows
        6. Regulatory approval for dermatology applications
        
        Content: {content}
        """
        
        return await self._chat_completion(prompt)
    
    async def _validate_technical_info(self, content: str, model_name: str) -> Dict[str, Any]:
        """Validate technical information"""
        prompt = f"""
        Validate technical information for {model_name} from the following content:
        
        Check for:
        1. Model architecture details
        2. Training methodology
        3. Performance metrics validation
        4. Technical limitations
        5. Data requirements
        
        Content: {content}
        """
        
        return await self._chat_completion(prompt)
    
    async def _extract_clinical_context(self, content: str, model_name: str) -> Dict[str, Any]:
        """Extract clinical context information"""
        prompt = f"""
        Extract clinical context for {model_name} from the following content:
        
        Focus on:
        1. Clinical workflow integration
        2. User training requirements
        3. Clinical decision support
        4. Patient safety considerations
        5. Clinical evidence base
        
        Content: {content}
        """
        
        return await self._chat_completion(prompt)
    
    async def extract_structured_content(self, content: str, model_name: str) -> Dict[str, Any]:
        """Basic structured content extraction"""
        prompt = f"""
        Extract structured information for {model_name} from the following content:
        
        Return JSON with keys:
        - model_architecture
        - performance_metrics
        - limitations
        - clinical_applications
        
        Content: {content}
        """
        
        return await self._chat_completion(prompt)
    
    async def _chat_completion(self, prompt: str) -> Dict[str, Any]:
        """Simple chat completion wrapper"""
        try:
            return self._chat_json("chat_completion", prompt, max_tokens=1000)
        except Exception as e:
            return {"error": str(e)}




if __name__ == "__main__":
    ext = AIContentExtractor()
    result = ext._chat_json(
        "smoke_test",
        user_prompt='Return {"ok":true} as JSON only.',
        sys_prompt='You must return {"ok": true} as JSON.',
        max_tokens=5,
        force=True,
    )
    print("Smoke:", result)
    ext.tracer.print_summary()