"""
Automatically make `src/` importable when running from the repo root.

Python imports `sitecustomize` automatically (if present on sys.path) during
startup. This prevents `ModuleNotFoundError: No module named 'utils'` when
invoking scripts from the repository root without setting PYTHONPATH=src.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    if src_dir.is_dir():
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


_ensure_src_on_path()

