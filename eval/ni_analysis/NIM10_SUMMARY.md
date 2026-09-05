# Global NI summary (NIM = 10 for all metrics except Flesch–Kincaid = 2)

Eval-3 overall: SourceCheckup = eval-3; FactScore & Flesch = best-of eval-2/eval-3.
**Δ = Auto − Manual** for all metrics.
Positive Δ = automated better for SourceCheckup, FactScore, and Flesch Reading Ease.
For Flesch–Kincaid (lower grade = easier), negative Δ = automated easier; NI pass if 95% CI **upper** bound < +NIM.

| Metric | NIM | Mean Δ | 95% CI | NI pass (CI)? | p (t) | p (Wilcoxon) | p (exact perm) | Products within margin |
|--------|-----|--------|--------|---------------|-------|--------------|----------------|------------------------|
| SourceCheckup partial | 10 pp | +10.4 pp | [4.2, 17.9] | **Yes** | 0.003 | 0.0312 | 0.061 | 5/5 |
| SourceCheckup strict | 10 pp | +17.7 pp | [7.9, 29.7] | **Yes** | 0.005 | 0.0312 | 0.212 | 5/5 |
| FactScore partial | 10 pp | +4.8 pp | [-8.2, 15.1] | **Yes** | 0.050 | 0.0625 | 0.121 | 4/5 |
| FactScore strict | 10 pp | +7.9 pp | [-7.4, 20.9] | **Yes** | 0.052 | 0.0625 | 0.152 | 4/5 |
| Flesch Reading Ease | 10 FRE pts | +13.7 | [3.1, 25.5] | **Yes** | 0.010 | 0.0312 | 0.152 | 5/5 |
| Flesch–Kincaid grade | 2 grades | -2.8 | [-5.0, -0.8] | **Yes** | 0.009 | 0.0312 | 0.212 | 5/5 |

## Product-level tables (Δ = Auto − Manual)

### SourceCheckup partial (NIM = 10)

| AI model | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 84.4 | 90.0 | +5.6 | Yes |
| Dermasensor | 98.6 | 100.0 | +1.4 | Yes |
| DERM | 80.6 | 94.7 | +14.2 | Yes |
| SkinVision | 92.9 | 100.0 | +7.1 | Yes |
| Forus | 66.7 | 90.2 | +23.6 | Yes |

### SourceCheckup strict (NIM = 10)

| AI model | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 68.8 | 80.0 | +11.2 | Yes |
| Dermasensor | 97.1 | 100.0 | +2.9 | Yes |
| DERM | 63.9 | 89.5 | +25.6 | Yes |
| SkinVision | 88.6 | 100.0 | +11.4 | Yes |
| Forus | 48.1 | 85.4 | +37.2 | Yes |

### FactScore partial (NIM = 10)

| AI model | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 88.1 | 95.8 | +7.7 | Yes |
| Dermasensor | 77.6 | 80.8 | +3.2 | Yes |
| DERM | 69.6 | 85.3 | +15.7 | Yes |
| SkinVision | 83.3 | 62.5 | -20.8 | **No** |
| Forus | 81.9 | 100.0 | +18.1 | Yes |

### FactScore strict (NIM = 10)

| AI model | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 86.4 | 93.8 | +7.4 | Yes |
| Dermasensor | 70.7 | 76.9 | +6.2 | Yes |
| DERM | 60.8 | 85.3 | +24.5 | Yes |
| SkinVision | 78.8 | 56.2 | -22.5 | **No** |
| Forus | 75.9 | 100.0 | +24.1 | Yes |

### Flesch Reading Ease (NIM = 10)

| AI model | Manual FRE | Auto FRE | Δ FRE | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 4.7 | 25.9 | +21.2 | Yes |
| Dermasensor | 19.1 | 21.7 | +2.6 | Yes |
| DERM | 22.3 | 32.3 | +10.0 | Yes |
| SkinVision | 7.2 | 41.7 | +34.5 | Yes |
| Forus | 25.8 | 25.9 | +0.1 | Yes |

### Flesch–Kincaid grade (NIM = 2)

| AI model | Manual FK | Auto FK | Δ FK | Within NI margin? |
|---------|----------|---------|-------|-------------------|
| DermGPT | 18.6 | 14.6 | -4.0 | Yes |
| Dermasensor | 17.2 | 16.2 | -1.0 | Yes |
| DERM | 16.0 | 14.2 | -1.8 | Yes |
| SkinVision | 19.7 | 12.7 | -7.0 | Yes |
| Forus | 14.6 | 14.6 | +0.0 | Yes |
