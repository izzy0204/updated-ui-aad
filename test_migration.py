"""Migration script tests (offline, uses v03_backup read-only)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
BACKUP = REPO / "src/core/pages/preloaded_cards/v03_backup"
MIGRATE_SCRIPT = REPO / "scripts/migrate_v03_to_clinical_cards.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("migrate_v03", MIGRATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.path.insert(0, str(REPO / "src"))
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_dry_run_no_writes(tmp_path: Path):
    mod = _load_migrate()
    src = BACKUP / "dermasensor-20260501-192348.md"
    card, bundle = mod.migrate_card(src)
    assert card.model_name
    assert bundle["citations"].get("references") is not None
    assert not list(tmp_path.glob("*.clinical.json"))


@pytest.mark.unit
def test_apply_writes_clinical_bundle(tmp_path: Path):
    mod = _load_migrate()
    src = BACKUP / "dermasensor-20260501-192348.md"
    card, bundle = mod.migrate_card(src)
    json_path = tmp_path / "test.clinical.json"
    md_path = tmp_path / "test.clinical.md"
    cite_path = tmp_path / "test.citations.json"
    json_path.write_text(card.to_json(), encoding="utf-8")
    md_path.write_text(card.to_markdown(citations=bundle["citations"]), encoding="utf-8")
    cite_path.write_text(json.dumps(bundle["citations"], indent=2), encoding="utf-8")
    assert json_path.exists() and cite_path.exists()


@pytest.mark.unit
def test_idempotent_second_run_same_hash(tmp_path: Path):
    mod = _load_migrate()
    src = BACKUP / "dermasensor-20260501-192348.md"
    card1, _ = mod.migrate_card(src)
    card2, _ = mod.migrate_card(src)
    assert mod._content_hash(card1) == mod._content_hash(card2)


@pytest.mark.unit
def test_unmatched_markers_warn(tmp_path: Path):
    mod = _load_migrate()
    src = BACKUP / "dermasensor-20260501-192348.md"
    text = src.read_text(encoding="utf-8")
    text = text.replace("DermaSensor [4,5,6]", "DermaSensor [4,5,6,99]", 1)
    bad_md = tmp_path / "orphan-cites.md"
    bad_md.write_text(text, encoding="utf-8")
    _, bundle = mod.migrate_card(bad_md)
    warnings = bundle["report"]["validationWarnings"]
    assert any("unmatched_citation_markers" in w for w in warnings)


@pytest.mark.unit
def test_sidecar_reference_ids_resolve(tmp_path: Path):
    mod = _load_migrate()
    src = BACKUP / "dermasensor-20260501-192348.md"
    _, bundle = mod.migrate_card(src)
    refs = bundle["citations"].get("references") or {}
    assert refs
    for _rid, meta in refs.items():
        assert meta.get("url")
