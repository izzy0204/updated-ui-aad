# src/ai_extractors/ai_extractor.py
from __future__ import annotations

import json
import re
import time
import random
from typing import Dict, List, Any, Optional
from datetime import datetime

from google import genai
from config.config import get_settings


# --------------------------- Exceptions ---------------------------

class RateLimitExceededError(Exception):
    def __init__(self, message="Gemini API rate limit exceeded. Please wait before making more requests.", retry_after=None):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)

class QuotaExceededError(Exception):
    def __init__(self, message="Gemini API quota exceeded. Please check your billing and usage limits."):
        self.message = message
        super().__init__(self.message)


# --------------------------- Tracing ---------------------------

class TracingLogger:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.total_tokens = 0
        self.total_cost = 0.0
        self.start_time = time.time()

    def log_call(
        self,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        response_time: float,
        success: bool,
        content_length: int = 0,
        error_msg: str = "",
        input_cost_per_1k: float = 0.0,
        output_cost_per_1k: float = 0.0,
    ):
        input_cost = prompt_tokens * (input_cost_per_1k / 1000.0)
        output_cost = completion_tokens * (output_cost_per_1k / 1000.0)
        call_cost = input_cost + output_cost

        call_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "response_time_seconds": response_time,
            "success": success,
            "content_length": content_length,
            "estimated_cost": call_cost,
            "error_message": error_msg,
        }
        self.calls.append(call_data)
        self.total_tokens += call_data["total_tokens"]
        self.total_cost += call_cost

        status = "✓" if success else "✗"
        print(f"{status} {operation} | {prompt_tokens}+{completion_tokens}={call_data['total_tokens']} tokens | {response_time:.2f}s | ${call_cost:.4f}")
        if not success and error_msg:
            print(f"   Error: {error_msg}")

    def _get_operations_breakdown(self) -> Dict[str, Any]:
        breakdown: Dict[str, Any] = {}
        for call in self.calls:
            op = call["operation"]
            d = breakdown.setdefault(op, {"count": 0, "total_tokens": 0, "total_cost": 0.0, "avg_response_time": 0.0, "success_rate": 0.0})
            d["count"] += 1
            d["total_tokens"] += call["total_tokens"]
            d["total_cost"] += call["estimated_cost"]
        for op, d in breakdown.items():
            op_calls = [c for c in self.calls if c["operation"] == op]
            d["avg_response_time"] = sum(c["response_time_seconds"] for c in op_calls) / len(op_calls)
            d["success_rate"] = (sum(1 for c in op_calls if c["success"]) / len(op_calls)) * 100
        return breakdown

    def get_summary(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        total = len(self.calls)
        successful = sum(1 for c in self.calls if c["success"])
        return {
            "session_duration_seconds": elapsed,
            "total_api_calls": total,
            "successful_calls": successful,
            "failed_calls": total - successful,
            "success_rate": (successful / total * 100) if total else 0,
            "total_tokens_used": self.total_tokens,
            "estimated_total_cost": self.total_cost,
            "average_response_time": (sum(c["response_time_seconds"] for c in self.calls) / total) if total else 0,
            "tokens_per_minute": (self.total_tokens / elapsed * 60) if elapsed > 0 else 0,
            "operations_breakdown": self._get_operations_breakdown(),
        }

    def print_summary(self):
        s = self.get_summary()
        print("\n" + "=" * 60)
        print("📊 AI EXTRACTION TRACING SUMMARY")
        print("=" * 60)
        print(f"Session Duration: {s['session_duration_seconds']:.1f} seconds")
        print(f"Total API Calls: {s['total_api_calls']}")
        print(f"Success Rate: {s['success_rate']:.1f}% ({s['successful_calls']}/{s['total_api_calls']})")
        print(f"Total Tokens: {s.get('total_tokens_used', 0):,}")
        print(f"Estimated Cost: ${s.get('estimated_total_cost', 0):.4f}")
        print(f"Avg Response Time: {s.get('average_response_time', 0):.2f}s")
        print(f"Tokens/Minute: {s.get('tokens_per_minute', 0):.0f}")
        print("\n📋 Operations Breakdown:")
        for op, data in s["operations_breakdown"].items():
            print(f"  {op}:")
            print(f"    Calls: {data['count']}")
            print(f"    Tokens: {data['total_tokens']:,}")
            print(f"    Cost: ${data['total_cost']:.4f}")
            print(f"    Avg Time: {data['avg_response_time']:.2f}s")
            print(f"    Success: {data['success_rate']:.1f}%")
        print("=" * 60)


# -------- OpenAI-style compatibility shim for legacy calls --------

class _OpenAIResponse:
    def __init__(self, text: str):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": text})()})]

class _OpenAIChatCompletions:
    def __init__(self, gclient: genai.Client, default_model: str):
        self._gclient = gclient
        self._model = default_model

    def create(self, model: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, **kwargs):
        m = model or self._model
        msgs = messages or []
        resp = self._gclient.responses.generate(model=m, input=msgs)
        text = getattr(resp, "output_text", "") or ""
        return _OpenAIResponse(text)

class _OpenAIChat:
    def __init__(self, comps: _OpenAIChatCompletions):
        self.completions = comps

class _OpenAICompatClient:
    def __init__(self, gclient: genai.Client, default_model: str):
        self.chat = _OpenAIChat(_OpenAIChatCompletions(gclient, default_model))


# --------------------------- Main Extractor ---------------------------

class AIContentExtractor:
    FIELD_MAPPING = {
        "developer": "developer",
        "outcomes_outputs": "outcomes_and_output",
        "regulatory_status": "regulatory_approval_status_if_applicable",
        "website": "contact",
        "organization": "developer",
        "version": "version",
    }

    def __init__(self, client: Optional[genai.Client] = None):
        s = get_settings()
        self._genai = client or genai.Client(api_key=s.google_api_key)
        self._model = s.gemini_model
        self._temp = s.gemini_temperature
        self._timeout = s.http_timeout
        # pricing/limits/verbosity from centralized config
        self._input_cost_per_1k = s.input_cost_per_1k
        self._output_cost_per_1k = s.output_cost_per_1k
        self._max_input_chars = s.max_input_chars
        self.verbose = bool(s.extractor_verbose)

        # legacy-compatible handle (cardgen_pipeline uses this)
        self.client = _OpenAICompatClient(self._genai, self._model)

        self.tracer = TracingLogger()
        self.rate_limit_hit = False
        self.quota_exceeded = False
        self.block_until = 0

        if self.verbose:
            print("🔍 AI Content Extractor (Gemini) initialized with tracing enabled")

    # ---------------- state helpers ----------------

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

    def _note_skip(self, op: str, content_len: int, reason: str):
        self.tracer.log_call(
            operation=op,
            model=self._model,
            prompt_tokens=0,
            completion_tokens=0,
            response_time=0.0,
            success=False,
            content_length=content_len,
            error_msg=f"SKIPPED: {reason}",
            input_cost_per_1k=self._input_cost_per_1k,
            output_cost_per_1k=self._output_cost_per_1k,
        )

    # ---------------- low-level chat helpers ----------------

    def _estimate_tokens(self, text: str) -> int:
        # crude but consistent estimate for cost tracking
        return int(len(text.split()) * 1.3)

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not isinstance(text, str):
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m2 = re.search(r'(\{(?:[^{}]|(?1))*\})', text, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _chat_json(
        self,
        op_name: str,
        user_prompt: str,
        sys_prompt: Optional[str] = None,
        max_tokens: int = 1200,
        temperature: Optional[float] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        if (not force) and self._should_skip():
            self._note_skip(op_name, len(user_prompt), "Unavailable (rate/quota)")
            return {}

        t0 = time.time()
        try:
            msgs: List[Dict[str, str]] = []
            if sys_prompt:
                msgs.append({"role": "system", "content": sys_prompt})
            up = f"{user_prompt}\n\nReturn ONLY valid JSON. No prose."
            msgs.append({"role": "user", "content": up})

            resp = self._genai.responses.generate(model=self._model, input=msgs)
            dt = time.time() - t0
            text = getattr(resp, "output_text", "") or "{}"

            prompt_tokens = self._estimate_tokens(up)
            completion_tokens = self._estimate_tokens(text)

            self.tracer.log_call(
                operation=op_name,
                model=self._model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time=dt,
                success=True,
                content_length=len(user_prompt),
                input_cost_per_1k=self._input_cost_per_1k,
                output_cost_per_1k=self._output_cost_per_1k,
            )

            data = self._parse_json(text)
            return data or {}
        except Exception as e:
            self.tracer.log_call(
                operation=op_name,
                model=self._model,
                prompt_tokens=0,
                completion_tokens=0,
                response_time=0.0,
                success=False,
                content_length=len(user_prompt),
                error_msg=str(e),
                input_cost_per_1k=self._input_cost_per_1k,
                output_cost_per_1k=self._output_cost_per_1k,
            )
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                self.rate_limit_hit = True
            if "quota" in err or "billing" in err or "insufficient" in err:
                self.quota_exceeded = True
            return {}

    def _with_retries(self, fn, op_name: str, *args, **kwargs) -> Any:
        max_retries = 5
        base = 1.0
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_err = e
                s = str(e).lower()
                retryable = any(t in s for t in ["rate", "429", "500", "502", "503", "504", "temporar"])
                if not retryable or attempt == max_retries - 1:
                    raise e
                delay = base * (2 ** attempt) + random.uniform(0, 1)
                if self.verbose:
                    print(f"Retrying {op_name} in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
        if last_err:
            raise last_err

    # ---------------- canonicalization & fallbacks ----------------

    def _canonicalize_keys(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                key = self.FIELD_MAPPING.get(k, k)
                out[key] = self._canonicalize_keys(v)
            return out
        if isinstance(obj, list):
            return [self._canonicalize_keys(i) for i in obj]
        return obj

    def _extract_contact_details(self, content: str) -> Dict[str, str]:
        info: Dict[str, str] = {}
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', content)
        if emails:
            info["email"] = emails[0]
        phones = re.findall(r'(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', content)
        if phones:
            info["phone"] = phones[0][1] if phones[0][1] else phones[0][0]
        websites = re.findall(r'https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/?(?:[^\s]*)?', content)
        home = [u for u in websites if any(t in u.lower() for t in ["home", "about", "contact", "www", ".com/", ".org/", ".edu/"])]
        if home:
            info["website"] = home[0]
        return info

    def _fallback_metrics_extraction(self, content: str) -> Dict[str, str]:
        pats = {
            "accuracy": r"accuracy\s*[:=]\s*(\d+\.?\d*\s*%?)",
            "sensitivity": r"sensitivity\s*[:=]\s*(\d+\.?\d*\s*%?)",
            "specificity": r"specificity\s*[:=]\s*(\d+\.?\d*\s*%?)",
            "auroc": r"(?:auroc|auc)\s*[:=]\s*(\d+\.?\d*)",
            "precision": r"precision\s*[:=]\s*(\d+\.?\d*\s*%?)",
            "recall": r"recall\s*[:=]\s*(\d+\.?\d*\s*%?)",
            "f1": r"f1\s*[:=]\s*(\d+\.?\d*)",
        }
        out: Dict[str, str] = {}
        for name, pat in pats.items():
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                out[name] = m.group(1)
        return out

    def _get_default_response(self, op: str) -> Dict[str, Any]:
        base = {
            "model_name": "Not specified",
            "model_developer": "Not specified",
            "developer_organization": "Not specified",
            "model_version": "Not specified",
            "release_date": "Not specified",
            "contact": "Not specified",
            "summary": "Not specified",
            "regulatory_approval_status": "Not specified",
            "funding_source": "Not specified",
        }
        if op == "extract_missing_fields":
            base.update({
                "exclusion_inclusion_criteria": "Not specified",
                "demographics": "Not specified",
                "training_data": "Not specified",
                "bias_mitigation": "Not specified",
                "irb_approval": "Not specified",
                "detailed_metrics": {},
                "publications_references": {},
            })
        if op == "extract_clinical_metrics":
            return {
                "performance_metrics": {},
                "validation_studies": "Not specified",
                "clinical_trials": "Not specified",
                "sample_sizes": "Not specified",
            }
        return base

    # ---------------- public extraction methods ----------------

    def extract_basic_metadata_first(self, content: str, source_type: str = "web", force: bool = False):
        s = get_settings()
        prompt = f"""
You are extracting basic metadata for a medical AI model. Extract EXACT strings only; use "Not specified" if absent.
Content (first {min(len(content), self._max_input_chars)} chars):
{content[: self._max_input_chars]}

Return JSON with keys:
model_name, model_developer, developer_organization, release_date, model_version,
contact, summary, regulatory_approval_status, funding_source
"""
        return self._chat_json(
            "extract_basic_metadata_first",
            user_prompt=prompt,
            sys_prompt="You are a metadata extraction expert. Output strict JSON.",
            max_tokens=s.max_output_tokens,
            force=force,
        )

    def extract_basic_metadata_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        if not content_batch:
            return []
        if not self.is_api_available() and not force:
            if self.verbose:
                print("🚫 Skipping batch API call - API unavailable")
            return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]

        items = []
        for i, item in enumerate(content_batch):
            c = item.get("content", "")[: min(8000, self._max_input_chars)]
            st = item.get("source_type", "web")
            sid = item.get("source_id", f"source_{i}")
            items.append(f"ITEM {i+1} (ID: {sid}, Type: {st}):\n{c}\n---END ITEM {i+1}---")
        batch_content = "\n".join(items)

        prompt = f"""
You are extracting basic metadata for medical AI models from multiple sources.
Extract EXACT strings only; use "Not specified" if absent.

Process each item separately and return a JSON array with one object per item.
Each object keys: model_name, model_developer, developer_organization, release_date, model_version, contact, summary, regulatory_approval_status, funding_source.

CONTENT TO PROCESS:
{batch_content}
"""
        s = get_settings()
        try:
            data = self._chat_json(
                "extract_basic_metadata_batch",
                user_prompt=prompt,
                sys_prompt="You are a metadata extraction expert. Output strict JSON array.",
                max_tokens=min(s.max_output_tokens * 2, 4000),
                force=force,
            )
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]
        except Exception:
            return [self._get_default_response("extract_basic_metadata_first") for _ in content_batch]

    def extract_missing_fields(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        if not self.is_api_available():
            if self.verbose:
                print("🚫 Skipping API call - API unavailable")
            return self._get_default_response("extract_missing_fields")

        def call():
            system_msg = "You are a medical AI expert. Return structured JSON only."
            user_msg = f"""Source type: {source_type}

Analyze this content and extract comprehensive Trust Ingredients:

{{
  "model_name": "", "model_developer": "",
  "exclusion_inclusion_criteria": "", "demographics": "",
  "training_data": "", "bias_mitigation": "", "irb_approval": "",
  "detailed_metrics": {{"performance_goals": "", "specific_results": "", "auroc_accuracy_metrics": ""}},
  "publications_references": {{"evaluation_references": "", "peer_reviewed_publications": ""}}
}}

Content (first {min(len(content), self._max_input_chars)} chars):
{content[: self._max_input_chars]}

Extract ONLY what is explicitly stated."""
            return self._chat_json(
                "extract_missing_fields",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=get_settings().max_output_tokens,
            )

        try:
            result = self._with_retries(call, "extract_missing_fields")
            if not result:
                # fallback
                fm = self._fallback_metrics_extraction(content)
                d = self._get_default_response("extract_missing_fields")
                if fm:
                    d["detailed_metrics"] = {"auroc_accuracy_metrics": fm}
                return d
            return self._canonicalize_keys(result)
        except Exception as e:
            err = str(e).lower()
            if "rate" in err:
                raise RateLimitExceededError(str(e))
            if any(t in err for t in ["quota", "billing", "insufficient"]):
                raise QuotaExceededError(str(e))
            fm = self._fallback_metrics_extraction(content)
            d = self._get_default_response("extract_missing_fields")
            if fm:
                d["detailed_metrics"] = {"auroc_accuracy_metrics": fm}
            return d

    def extract_missing_fields_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        if not content_batch:
            return []
        if not self.is_api_available() and not force:
            if self.verbose:
                print("🚫 Skipping batch API call - API unavailable")
            return [self._get_default_response("extract_missing_fields") for _ in content_batch]

        items = []
        for i, item in enumerate(content_batch):
            c = item.get("content", "")[: min(6000, self._max_input_chars)]
            st = item.get("source_type", "web")
            sid = item.get("source_id", f"source_{i}")
            items.append(f"ITEM {i+1} (ID: {sid}, Type: {st}):\n{c}\n---END ITEM {i+1}---")
        batch_content = "\n".join(items)

        def call():
            system_msg = "You are a medical AI expert. Return JSON array only."
            user_msg = f"""Analyze these items and extract Trust Ingredients per-item with the schema from the single-item call.

CONTENT TO PROCESS:
{batch_content}"""
            return self._chat_json(
                "extract_missing_fields_batch",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=min(get_settings().max_output_tokens * 3, 6000),
            )

        try:
            result = self._with_retries(call, "extract_missing_fields_batch")
            if isinstance(result, list):
                return [self._canonicalize_keys(x) for x in result]
            if isinstance(result, dict):
                return [self._canonicalize_keys(result)]
            return [self._get_default_response("extract_missing_fields") for _ in content_batch]
        except Exception:
            return [self._get_default_response("extract_missing_fields") for _ in content_batch]

    def extract_comprehensive_batch(self, content_batch: List[Dict[str, Any]], force: bool = False) -> List[Dict[str, Any]]:
        if not content_batch:
            return []
        if not self.is_api_available() and not force:
            if self.verbose:
                print("🚫 Skipping comprehensive batch API call - API unavailable")
            return [self._get_default_response("extract_comprehensive") for _ in content_batch]

        items = []
        for i, item in enumerate(content_batch):
            c = item.get("content", "")[: min(5000, self._max_input_chars)]
            st = item.get("source_type", "web")
            sid = item.get("source_id", f"source_{i}")
            items.append(f"ITEM {i+1} (ID: {sid}, Type: {st}):\n{c}\n---END ITEM {i+1}---")
        batch_content = "\n".join(items)

        def call():
            system_msg = "You are a comprehensive medical AI model analysis expert. Return JSON array only."
            user_msg = f"""For each item, extract BASIC METADATA, TRUST INGREDIENTS, TECHNICAL INFORMATION, and CLINICAL METRICS (as per prior schema).
CONTENT TO PROCESS:
{batch_content}"""
            return self._chat_json(
                "extract_comprehensive_batch",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=min(get_settings().max_output_tokens * 4, 8000),
            )

        try:
            result = self._with_retries(call, "extract_comprehensive_batch")
            if isinstance(result, list):
                return [self._canonicalize_keys(x) for x in result]
            if isinstance(result, dict):
                return [self._canonicalize_keys(result)]
            return [self._get_default_response("extract_comprehensive") for _ in content_batch]
        except Exception:
            return [self._get_default_response("extract_comprehensive") for _ in content_batch]

    def extract_model_information(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        if not self.is_api_available():
            if self.verbose:
                print("🚫 Skipping API call - API unavailable")
            return self._get_default_response("extract_model_information")

        def call():
            system_msg = "You are an AI model analysis expert. Return strict JSON."
            user_msg = f"""Source type: {source_type}
Extract:
{{
  "model_architecture": "", "input_output_specs": "", "training_methodology": "",
  "validation_approach": "", "deployment_context": "", "limitations": "",
  "clinical_integration": "", "performance_benchmarks": ""
}}

Content (first {min(len(content), self._max_input_chars)} chars):
{content[: self._max_input_chars]}"""
            return self._chat_json(
                "extract_model_information",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=get_settings().max_output_tokens,
            )

        try:
            result = self._with_retries(call, "extract_model_information")
            return self._canonicalize_keys(result) if result else {"model_architecture": "Not specified", "limitations": "Not specified"}
        except Exception as e:
            err = str(e).lower()
            if "rate" in err:
                raise RateLimitExceededError(str(e))
            if any(t in err for t in ["quota", "billing", "insufficient"]):
                raise QuotaExceededError(str(e))
            return {"model_architecture": "Not specified", "limitations": "Not specified"}

    def extract_clinical_metrics(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        if not self.is_api_available():
            if self.verbose:
                print("🚫 Skipping API call - API unavailable")
            return self._get_default_response("extract_clinical_metrics")

        def call():
            system_msg = "You are a medical AI validation expert. Return strict JSON."
            user_msg = f"""Source type: {source_type}
Extract clinical metrics:
{{
  "performance_metrics": {{"accuracy": "", "sensitivity": "", "specificity": "", "auc_roc": "", "precision": "", "recall": ""}},
  "validation_studies": "", "clinical_trials": "", "sample_sizes": "", "confidence_intervals": ""
}}

Content (first {min(len(content), self._max_input_chars)} chars):
{content[: self._max_input_chars]}"""
            return self._chat_json(
                "extract_clinical_metrics",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=get_settings().max_output_tokens,
            )

        try:
            result = self._with_retries(call, "extract_clinical_metrics")
            if not result:
                fm = self._fallback_metrics_extraction(content)
                if fm:
                    return {"performance_metrics": fm, "validation_studies": "Not specified"}
                return self._get_default_response("extract_clinical_metrics")
            return self._canonicalize_keys(result)
        except Exception as e:
            err = str(e).lower()
            if "rate" in err:
                raise RateLimitExceededError(str(e))
            if any(t in err for t in ["quota", "billing", "insufficient"]):
                raise QuotaExceededError(str(e))
            fm = self._fallback_metrics_extraction(content)
            if fm:
                return {"performance_metrics": fm, "validation_studies": "Not specified"}
            return self._get_default_response("extract_clinical_metrics")

    def generate_regulatory_compliance_info(self, content: str, source_type: str = "web") -> Dict[str, Any]:
        if not self.is_api_available():
            if self.verbose:
                print("🚫 Skipping API call - API unavailable")
            return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}

        def call():
            system_msg = "You are a medical device regulatory expert. Return strict JSON."
            user_msg = f"""Source type: {source_type}
Extract regulatory info:
{{
  "regulatory_approvals": "", "clinical_oversight": "", "compliance_standards": "",
  "quality_management": "", "clinical_workflow_integration": "", "human_oversight_requirements": "",
  "cfr_compliance": ""
}}

Content (first {min(len(content), self._max_input_chars)} chars):
{content[: self._max_input_chars]}"""
            return self._chat_json(
                "generate_regulatory_compliance_info",
                user_prompt=user_msg,
                sys_prompt=system_msg,
                max_tokens=get_settings().max_output_tokens,
            )

        try:
            result = self._with_retries(call, "generate_regulatory_compliance_info")
            return self._canonicalize_keys(result) if result else {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}
        except Exception as e:
            err = str(e).lower()
            if "rate" in err:
                raise RateLimitExceededError(str(e))
            if any(t in err for t in ["quota", "billing", "insufficient"]):
                raise QuotaExceededError(str(e))
            return {"regulatory_approvals": "Not specified", "clinical_oversight": "Not specified"}


# --------------------------- smoke test ---------------------------

if __name__ == "__main__":
    ext = AIContentExtractor()
    res = ext._chat_json(
        "smoke_test",
        user_prompt='Return {"ok": true} as JSON only.',
        sys_prompt='You must return {"ok": true} as JSON.',
        max_tokens=16,
        force=True,
    )
    print("Smoke:", res)
    ext.tracer.print_summary()
