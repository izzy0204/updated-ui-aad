#!/usr/bin/env python3
"""
Infer SWG intake spreadsheet column -> CHAI markdown composite keys (section|||field).

Reads bundled model cards and forms/SWG_Intake_Form*.xlsx; writes config/swg_intake_field_map.yml.
Re-run after updating intake export or cards; hand-edit YAML when needed.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Repo root (scripts/ -> parents[1])
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from core.dermauto_card_render import (  # noqa: E402
    composite_section_field_key,
    normalize_md_for_parsing,
    parse_model_card_md,
)
from core.swg_intake import read_xlsx_first_sheet, resolve_vendor_family  # noqa: E402


BUNDLED: List[Tuple[str, Path]] = [
    ("tandem", REPO_ROOT / "src/core/pages/preloaded_cards/tandem-20260501-043225.md"),
    ("dermasensor", REPO_ROOT / "src/core/pages/preloaded_cards/dermasensor-20260501-192348.md"),
    ("dermgpt", REPO_ROOT / "src/core/pages/preloaded_cards/dermgpt-20260429-173126.md"),
]

FORM_XLSX = REPO_ROOT / "forms" / "SWG_Intake_Form_-_AI_Industry_Partnerships_1758725525 (1).xlsx"
OUT_YAML = REPO_ROOT / "config" / "swg_intake_field_map.yml"

def _token_set(text: str) -> Set[str]:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def overlap_score(cell: str, val: str) -> float:
    cell_n, val_n = cell.strip().lower(), val.strip().lower()
    if len(cell_n) < 8 or len(val_n) < 8:
        return 0.0
    if cell_n[: min(len(cell_n), 200)] in val_n or cell_n in val_n:
        return 4.0
    if val_n[: min(len(val_n), 240)] in cell_n:
        return 4.0
    wc, wv = _token_set(cell_n), _token_set(val_n)
    if not wc or not wv:
        return 0.0
    inter = len(wc & wv)
    uni = len(wc | wv) or 1
    j = inter / uni
    return j if j > 0.12 else 0.0


def scan_columns() -> List[str]:
    cols: List[str] = []
    for i in range(26):
        cols.append(chr(65 + i))
    for a in range(26):
        for b in range(26):
            cols.append(chr(65 + a) + chr(65 + b))
    return cols


def main() -> None:
    if not FORM_XLSX.exists():
        print(f"Missing intake form: {FORM_XLSX}", file=sys.stderr)
        sys.exit(1)

    _, data_rows = read_xlsx_first_sheet(FORM_XLSX)
    rows_by_fam: Dict[str, Dict[str, str]] = {}
    for row in data_rows:
        fam = resolve_vendor_family(row.get("A", ""))
        if fam:
            rows_by_fam[fam] = row

    cards_by_fam: Dict[str, Dict[str, Dict[str, str]]] = {}
    for fam, path in BUNDLED:
        if not path.exists():
            print(f"Skip missing card: {path}", file=sys.stderr)
            continue
        md = normalize_md_for_parsing(path.read_text(encoding="utf-8", errors="replace"))
        cards_by_fam[fam] = parse_model_card_md(md)

    all_cols = scan_columns()
    col_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for fam, survey_row in rows_by_fam.items():
        sections = cards_by_fam.get(fam)
        if not sections:
            continue
        for col in all_cols:
            cell = survey_row.get(col, "")
            if not isinstance(cell, str) or not cell.strip():
                continue
            for sec_name, fields in sections.items():
                if sec_name.strip().lower() == "references":
                    continue
                for fname, val in fields.items():
                    ck = composite_section_field_key(sec_name, fname)
                    s = overlap_score(cell, val)
                    if s > 0:
                        col_scores[col][ck] += s

    columns_out: Dict[str, List[str]] = {}
    for col, scores in col_scores.items():
        if not scores:
            continue
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        best_val = ranked[0][1]
        # Scores are sums of modest per-card overlaps; use relative cutoffs, not an absolute 1.2 floor.
        if best_val < 0.22:
            continue
        rel_floor = max(0.18, best_val * 0.42)
        picked = [k for k, v in ranked if v >= rel_floor][:10]
        if picked:
            columns_out[col] = picked

    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml  # type: ignore
    except ImportError:
        print("Install PyYAML: pip install PyYAML", file=sys.stderr)
        sys.exit(1)

    payload = {
        "columns": dict(sorted(columns_out.items(), key=lambda x: x[0])),
        "_meta": {
            "description": "Maps Excel column letters to CHAI field composite keys (section|||field). "
            "Edit manually when inference mis-assigns.",
        },
    }
    OUT_YAML.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=10000,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_YAML} ({len(columns_out)} columns mapped)")


if __name__ == "__main__":
    main()
