# Auto vs Manual non-inferiority analysis

Manual cards are the reference benchmark. **Non-inferiority** means the bootstrap 95% CI
lower bound of mean(Auto − Manual) is **greater than −δ** (Auto not unacceptably worse).

Tests per metric: bootstrap CI (primary), one-sample t-test on paired differences, Wilcoxon signed-rank,
exact paired sign-flip permutation NI (all 2^n configurations), and unpaired two-sided permutation (exploratory).

## eval3

### Card-level global tests (moderate δ)

| Metric | n | Mean Δ | 95% CI | δ | NI pass (CI) | p (t, NI) | p (Wilcoxon) | p (exact perm) | Products within NI margin |
|--------|---|--------|--------|---|--------------|-----------|--------------|----------------|---------------------------|
| factscore_partial | 5 | 7.64 | [-21.22, 27.49] | 15.0 | No | 0.0950 | 0.0938 | 0.1818 (5/32) | 4/5 |
| factscore_strict | 5 | 13.26 | [-12.87, 33.17] | 15.0 | **Yes** | 0.0521 | 0.0625 | 0.1515 (4/32) | 4/5 |
| flesch_kincaid_grade | 5 | 2.28 | [-0.60, 5.20] | 2.0 | **Yes** | 0.0284 | 0.0625 | 0.1818 (5/32) | 4/5 |
| flesch_reading_ease | 5 | 8.13 | [-9.00, 25.65] | 10.0 | **Yes** | 0.0675 | 0.0625 | 0.1515 (4/32) | 4/5 |
| sourcecheckup_partial | 5 | 10.39 | [4.25, 17.94] | 10.0 | **Yes** | 0.0032 | 0.0312 | 0.0606 (1/32) | 5/5 |
| sourcecheckup_strict | 5 | 17.67 | [7.93, 28.02] | 8.0 | **Yes** | 0.0068 | 0.0312 | 0.2424 (7/32) | 5/5 |

### Per-product failures (moderate δ)

- **factscore_partial** / SkinVision (card): Δ=-47.33 (threshold −15.0)
- **factscore_strict** / SkinVision (card): Δ=-36.72 (threshold −15.0)
- **flesch_kincaid_grade** / Forus (card): Δ=-2.80 (threshold −2.0)
- **flesch_reading_ease** / Forus (card): Δ=-23.25 (threshold −10.0)

## eval3_overall

### Card-level global tests (moderate δ)

| Metric | n | Mean Δ | 95% CI | δ | NI pass (CI) | p (t, NI) | p (Wilcoxon) | p (exact perm) | Products within NI margin |
|--------|---|--------|--------|---|--------------|-----------|--------------|----------------|---------------------------|
| factscore_partial | 5 | 4.78 | [-8.24, 15.06] | 15.0 | **Yes** | 0.0232 | 0.0625 | 0.0303 (0/32) | 4/5 |
| factscore_strict | 5 | 7.95 | [-7.37, 20.94] | 15.0 | **Yes** | 0.0277 | 0.0625 | 0.0606 (1/32) | 4/5 |
| flesch_kincaid_grade | 5 | 2.76 | [0.76, 5.20] | 2.0 | **Yes** | 0.0094 | 0.0312 | 0.2121 (6/32) | 5/5 |
| flesch_reading_ease | 5 | 13.69 | [3.09, 24.96] | 10.0 | **Yes** | 0.0102 | 0.0312 | 0.1515 (4/32) | 5/5 |
| sourcecheckup_partial | 5 | 10.39 | [4.25, 17.27] | 10.0 | **Yes** | 0.0032 | 0.0312 | 0.0606 (1/32) | 5/5 |
| sourcecheckup_strict | 5 | 17.67 | [7.93, 29.70] | 8.0 | **Yes** | 0.0068 | 0.0312 | 0.2424 (7/32) | 5/5 |

### Per-product failures (moderate δ)

- **factscore_partial** / SkinVision (card): Δ=-20.83 (threshold −15.0)
- **factscore_strict** / SkinVision (card): Δ=-22.54 (threshold −15.0)
