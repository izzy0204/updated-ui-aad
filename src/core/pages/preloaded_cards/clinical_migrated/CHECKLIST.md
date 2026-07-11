# Clinical migration manual sign-off

Use this checklist before removing legacy v0.3 runtime support (plan step S10).
All six bundled cards must pass visual review in DermAUTO-CARD with regulatory coloring enabled.

## Preload hygiene

- Legacy v0.3 `.md` files removed from `preloaded_cards/` root (archived in `v03_backup/`)
- Canonical `.clinical.json` + `.citations.json` bundles present for all six models
- `v03_backup/MANIFEST.json` checksums verified before archival

## Per-card DermAUTO review

For each card, open the sidebar entry and confirm:


| Card                        | JSON loads | Citations clickable | Regulatory row colored only | Summary ≤3 sentences | Reviewer | Date |
| --------------------------- | ---------- | ------------------- | --------------------------- | -------------------- | -------- | ---- |
| dermasensor-20260501-192348 | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |
| Dermasensor                 | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |
| dermgpt-20260429-173126     | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |
| DermGPT updated             | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |
| tandem-20260501-043225      | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |
| Tandem updated              | [ ]        | [ ]                 | [ ]                         | [ ]                  |          |      |


## Automated gates (run before sign-off)

```bash
bash scripts/run_clinical_test_suite.sh
```

Expected: pytest unit suite PASS, v0.3 removal gate PASS, v0.3 runtime audit PASS.

## Approval

- All six cards reviewed in DermAUTO with "Color-code regulatory status row" enabled
- No blocking validation errors on bundled `.clinical.json` files
- Approved for v0.3 runtime removal (S10)

**Approver name:** ____________________

**Date:** ____________________