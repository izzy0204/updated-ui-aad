"""Regression tests for batched Gemini extraction and fetch hardening."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.gemini_agent.agent import (
    _gather_targets_async,
    _log_batch_failure,
    _normalize_extractor_output,
    _prep_seed_context,
)
from agents.gemini_agent.prompts import EXTRACTOR_HEAD, build_extractor_prompt
from utils.enhanced_publication_finder import EnhancedPublicationFinder
from utils.web_search import _classify_and_extract_text, _ddg_search_once


@pytest.mark.unit
def test_build_extractor_prompt_literal_description_json_no_keyerror():
  """Unescaped nested JSON examples must not break prompt building."""
  prompt = build_extractor_prompt(
      field_paths='["training_data"]',
      allowed_fields='["training_data"]',
      manifest="[SOURCE 1] web https://example.com",
      sources='Page says {"description": "dermatology embeddings"} and more text.',
  )
  assert "training_data" in prompt
  assert '{"description": "dermatology embeddings"}' in prompt
  assert "{allowed_fields}" not in prompt


@pytest.mark.unit
def test_prep_seed_context_tags_application_url_as_primary_source():
  """The user-provided Application URL must be marked so the model prioritizes it."""
  pages = [
      {"url": "https://example.com/app", "text": "App page content.", "priority": "user_inputted"},
      {"url": "https://other.com/page", "text": "Other discovered content."},
  ]
  ctx, urls = _prep_seed_context(pages)
  assert "PRIMARY SOURCE" in ctx
  assert ctx.index("PRIMARY SOURCE") < ctx.index("[SEED 2]")
  assert urls == ["https://example.com/app", "https://other.com/page"]


@pytest.mark.unit
def test_prep_seed_context_no_primary_tag_without_priority_flag():
  pages = [{"url": "https://other.com/page", "text": "Other discovered content."}]
  ctx, _urls = _prep_seed_context(pages)
  assert "PRIMARY SOURCE" not in ctx


@pytest.mark.unit
def test_extractor_prompt_includes_field_guidance_and_source_priority():
  assert "SOURCE PRIORITY" in EXTRACTOR_HEAD
  assert "FIELD GUIDANCE" in EXTRACTOR_HEAD
  assert "clinicaltrials.gov" in EXTRACTOR_HEAD
  assert "peer-reviewed" in EXTRACTOR_HEAD
  assert "underrepresented" in EXTRACTOR_HEAD


@pytest.mark.unit
def test_planner_prompt_includes_source_priority_guardrail_when_primary_present(tmp_path):
  from agents.gemini_agent import agent as agent_module
  from utils.cache_system import cache_context

  captured = {}
  orig = agent_module._gemini_json

  async def fake_gemini_json(client, model_name, *, prompt):
    captured["prompt"] = prompt
    return {"targets": [], "fields_priority": []}

  async def _run():
    async with cache_context(str(tmp_path / "test_cache")):
      agent_module._gemini_json = fake_gemini_json
      try:
        await agent_module._plan_targets(
            None,
            "TestModel",
            "TestModel",
            developer="",
            seed_context=(
                "[SEED 1] URL: https://example.com/app — PRIMARY SOURCE "
                "(developer-provided Application URL)\nCONTENT:\nhi\n"
            ),
        )
      finally:
        agent_module._gemini_json = orig

  asyncio.run(_run())

  assert "SOURCE PRIORITY" in captured["prompt"]


@pytest.mark.unit
def test_normalize_extractor_training_data_missing_description():
  raw = {"values": {"training_data": {"dataset_url": "https://example.com/ds"}}, "evidence": {}}
  values, evidence = _normalize_extractor_output(raw, ["training_data"])
  assert "training_data" in values
  assert isinstance(values["training_data"], dict)
  assert "description" not in values["training_data"] or not values["training_data"].get("description")
  assert evidence == {}


@pytest.mark.unit
def test_normalize_extractor_malformed_without_description():
  raw = {"values": {"model_name": "Derm Foundation"}, "evidence": {}}
  values, evidence = _normalize_extractor_output(raw, ["training_data", "summary"])
  assert values.get("model_name") == "Derm Foundation"
  assert "training_data" not in values
  assert evidence == {}


@pytest.mark.unit
def test_classify_html_body_from_pdf_url():
  html_body = b"<html><body><h1>Not a PDF</h1><p>Model card page.</p></body></html>"
  kind, text = _classify_and_extract_text(
      raw=html_body,
      content_type="application/pdf",
      url="https://example.com/paper.pdf",
  )
  assert kind == "html"
  assert "Model card" in text or "Not a PDF" in text


@pytest.mark.unit
def test_classify_pdf_magic_bytes():
  pdf_bytes = b"%PDF-1.4\n%fake minimal pdf body"
  kind, _text = _classify_and_extract_text(
      raw=pdf_bytes,
      content_type="text/html",
      url="https://example.com/doc",
  )
  assert kind == "pdf"


@pytest.mark.unit
def test_ddg_202_returns_empty_results():
  class _Resp:
      status = 202

      async def text(self):
          return "<html>challenge</html>"

  class _Ctx:
      async def __aenter__(self):
          return _Resp()

      async def __aexit__(self, *_args):
          return False

  class _Session:
      def get(self, *_args, **_kwargs):
          return _Ctx()

  results = asyncio.run(_ddg_search_once(_Session(), "https://duckduckgo.com/html/", "derm foundation"))
  assert results == []


@pytest.mark.unit
def test_publication_finder_retries_connection_closed():
  async def _run():
      finder = EnhancedPublicationFinder()
      finder.session = MagicMock()

      call_count = {"n": 0}

      class _Resp:
          status = 200

      class _Ctx:
          async def __aenter__(self):
              return _Resp()

          async def __aexit__(self, *_args):
              return False

      def flaky_request(*_args, **_kwargs):
          call_count["n"] += 1
          if call_count["n"] < 3:
              raise ConnectionResetError("Connection closed")
          return _Ctx()

      finder.session.request = flaky_request
      result = await finder._request("GET", "https://export.arxiv.org/api/query", tries=4, backoff_base=0.01)
      assert result is not None
      assert call_count["n"] == 3

  asyncio.run(_run())


@pytest.mark.unit
def test_gather_continues_when_one_source_fails():
  async def _run():
      targets = [
          {"type": "huggingface", "id": "google/derm-foundation"},
          {"type": "github", "id": "Google-Health/derm-foundation"},
          {"type": "web", "url": "https://developers.google.com/health-ai-developer-foundations/derm-foundation"},
          {"type": "web", "url": "https://example.invalid/fail"},
      ]

      async def fake_fetch_many(urls, **kwargs):
          out = []
          for u in urls:
              if "invalid" in u:
                  out.append({"url": u, "status": 0, "text": "", "error": "connection failed"})
              else:
                  out.append({"url": u, "status": 200, "text": f"Content from {u}", "type": "html"})
          return out

      with patch("agents.gemini_agent.agent.fetch_hf_readme", return_value=("https://hf", "HF README text")):
          with patch("agents.gemini_agent.agent.fetch_github_readme", return_value=("https://gh", "GitHub README text")):
              with patch("agents.gemini_agent.agent.fetch_many", side_effect=fake_fetch_many):
                  return await _gather_targets_async(targets, concurrency=2)

  blobs, types = asyncio.run(_run())

  assert len(blobs) == 3
  assert len(types) == 3
  urls = {b[0] for b in blobs}
  assert "https://hf" in urls
  assert "https://gh" in urls
  assert any("developers.google.com" in u for u in urls)


@pytest.mark.unit
def test_log_batch_failure_includes_traceback(capsys):
  try:
      raise KeyError("description")
  except KeyError as exc:
      _log_batch_failure(2, ["training_data", "summary"], exc, resp=None)
  captured = capsys.readouterr().out
  assert "Batch 2 failed" in captured or "Batch 2" in captured
  assert "KeyError" in captured
  assert "training_data" in captured
  assert "Traceback" in captured or "traceback" in captured.lower()
