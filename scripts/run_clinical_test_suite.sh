#!/usr/bin/env bash
# Run the offline clinical model card unit test suite and v0.3 removal gate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! PYTHONPATH="${ROOT}/src:${ROOT}/.pytest_deps" python3 -c "import pytest" 2>/dev/null; then
  echo "Installing dev test dependencies to .pytest_deps..."
  python3 -m pip install -q -r requirements-dev.txt --target "${ROOT}/.pytest_deps"
fi
if ! python3 -c "import dotenv" 2>/dev/null; then
  echo "Installing project dependencies..."
  python3 -m pip install -q -r requirements.txt
fi
export PYTHONPATH="${ROOT}/src:${ROOT}/.pytest_deps:${PYTHONPATH:-}"

echo "==> pytest (unit markers only)"
python3 -m pytest -m unit

echo "==> v0.3 removal gate"
python3 scripts/check_v03_removal_gate.py

echo "==> v0.3 runtime audit"
bash scripts/audit_v03_runtime.sh

echo "Clinical test suite: PASS"
