"""Load SWG industry intake (Monday xlsx) and field-map config for survey-reported keys."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_forms_xlsx() -> Path:
    return repo_root() / "forms" / "SWG_Intake_Form_-_AI_Industry_Partnerships_1758725525 (1).xlsx"


def default_field_map_path() -> Path:
    return repo_root() / "config" / "swg_intake_field_map.yml"


def _parse_cell_ref(ref: str) -> str:
    return "".join(c for c in ref if c.isalpha())


def read_xlsx_first_sheet(path: Path) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """
    Return (header_by_column_letter, data_rows) for the first worksheet.
    Each data row is a dict column_letter -> string value.
    """
    with zipfile.ZipFile(path) as z:
        sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings: List[str] = []
        for si in sst.findall("m:si", _NS):
            parts: List[str] = []
            for t in si.findall(".//m:t", _NS):
                parts.append(t.text or "")
            strings.append("".join(parts))

        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        sheet_data = sheet.find("m:sheetData", _NS)
        if sheet_data is None:
            return {}, []

        rows_el = sheet_data.findall("m:row", _NS)
        if not rows_el:
            return {}, []

        def row_to_dict(r: Any) -> Dict[str, str]:
            out: Dict[str, str] = {}
            for c in r.findall("m:c", _NS):
                ref = c.get("r")
                if not ref:
                    continue
                col = _parse_cell_ref(ref)
                t = c.get("t")
                v = c.find("m:v", _NS)
                if v is None or v.text is None:
                    continue
                if t == "s":
                    out[col] = strings[int(v.text)]
                else:
                    out[col] = v.text
            return out

        header: Dict[str, str] = {}
        data_rows: List[Dict[str, str]] = []
        seen_header = False
        for r in rows_el:
            d = row_to_dict(r)
            if not d:
                continue
            v_a = d.get("A", "").strip().lower()
            if v_a == "name" and "B" in d and str(d.get("B", "")).strip().lower() == "email":
                header = d
                seen_header = True
                continue
            if not seen_header:
                continue
            if not d.get("A", "").strip():
                continue
            data_rows.append(d)

        return header, data_rows


_NAME_NORMALIZE = re.compile(r"[^a-z0-9]+")


def normalize_vendor_token(s: str) -> str:
    s = s.lower().strip()
    s = _NAME_NORMALIZE.sub("", s)
    return s


def resolve_vendor_family(name_cell: str) -> Optional[str]:
    """Map intake Name column to a family token for matching."""
    t = normalize_vendor_token(name_cell)
    if "tandem" in t:
        return "tandem"
    if "dermgpt" in t:
        return "dermgpt"
    if "dermasensor" in t:
        return "dermasensor"
    return None


def family_from_doc_title(doc_title: Optional[str]) -> Optional[str]:
    if not doc_title:
        return None
    dt = normalize_vendor_token(doc_title)
    if "tandem" in dt:
        return "tandem"
    if "dermgpt" in dt:
        return "dermgpt"
    if "dermasensor" in dt:
        return "dermasensor"
    return None


def match_survey_row_for_title(
    data_rows: List[Dict[str, str]], doc_title: Optional[str]
) -> Optional[Dict[str, str]]:
    """Pick the intake row whose vendor family matches the model name in doc_title."""
    want = family_from_doc_title(doc_title)
    if not want:
        return None
    for row in data_rows:
        name_cell = row.get("A", "").strip()
        fam = resolve_vendor_family(name_cell)
        if fam == want:
            return row
    return None


def load_column_field_map_yaml(path: Path) -> Dict[str, List[str]]:
    """Load YAML mapping Excel column letter -> list of composite keys section|||field."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        return {}
    cols = raw.get("columns") if isinstance(raw, dict) else raw
    if not isinstance(cols, dict):
        return {}
    out: Dict[str, List[str]] = {}
    for k, v in cols.items():
        col = str(k).strip().upper()
        if isinstance(v, list):
            out[col] = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(v, str) and v.strip():
            out[col] = [v.strip()]
    return out


def survey_reported_composite_keys(
    *,
    survey_row: Optional[Dict[str, str]],
    column_to_fields: Dict[str, List[str]],
) -> Set[str]:
    """Composite keys that have a non-empty mapped survey cell for this row."""
    reported: Set[str] = set()
    if not survey_row:
        return reported
    for col, keys in column_to_fields.items():
        cell = survey_row.get(col, "")
        if isinstance(cell, str) and cell.strip():
            for ck in keys:
                reported.add(ck)
    return reported
