#!/usr/bin/env bash
# Audit active runtime for legacy v0.3 symbols (excludes migration scripts and backups).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

fail=0
check_zero() {
  local label="$1"
  local pattern="$2"
  local path="$3"
  local matches
  matches=$(grep -R -n -E "$pattern" "$path" \
    --exclude-dir=v03_backup \
    --exclude-dir=clinical_migrated \
    --exclude-dir=__pycache__ \
    --exclude='*.md' \
    --exclude='*.pyc' \
    --exclude='*.json' \
    2>/dev/null | grep -v 'scripts/migrate_' | grep -v 'ragas_eval/' | grep -v 'scripts/forms_only.py' | grep -v 'clinical_card_mapper.py' || true)
  local count
  count=$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')
  if [ "$count" != "0" ]; then
    echo "FAIL: $label ($count matches)"
    printf '%s\n' "$matches" | head -20
    fail=1
  else
    echo "OK: $label"
  fi
}

check_zero "_AGENT_TO_CHAI in src/pipelines" "_AGENT_TO_CHAI" src/pipelines
check_zero "max_fields=74" "max_fields=74" src
check_zero "iter_chai_field_placements imports" "import iter_chai_field_placements|from core.chai_schema import.*iter_chai" src
check_zero "intended_use_and_workflow in terminal" "intended_use_and_workflow" terminal_app.py
check_zero "xml_path in terminal" "xml_path" terminal_app.py

if [ "$fail" -eq 0 ]; then
  echo "v0.3 runtime audit: PASS"
else
  echo "v0.3 runtime audit: FAIL"
  exit 1
fi
