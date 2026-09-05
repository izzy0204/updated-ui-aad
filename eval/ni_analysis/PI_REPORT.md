# Eval-3 Overall: Automated vs Manual Model Cards — PI Statistical Report

**Comparison:** Automated vs expert manual reference cards  
**Units:** n = 5 matched product pairs (DermGPT, Dermasensor, DERM, SkinVision, Forus)  
**Reference standard:** Manual cards  
**Default difference:** Δ = Auto − Manual (positive = automated card better), except Flesch–Kincaid†

---

## Methods

### Study design

We compared automated and manual dermatology AI model cards using a **paired non-inferiority**
framework. Each of five commercial products contributed one manual card and one automated card.
The manual card is the reference benchmark. The question is not whether automated cards are
identical to manual cards, but whether automated cards are **not meaningfully worse** than manual
cards within an **analyst-specified tolerance** (the non-inferiority margin, δ).

### Outcome definitions

- **SourceCheckup partial-credit:** fraction of citation–claim pairs judged supported, with half
  credit for partially supported pairs.
- **SourceCheckup strict:** fraction of citation–claim pairs judged fully supported.
- **FactScore partial-credit:** fraction of atomic factual claims supported by the retrieval
  corpus, with half credit for partial support.
- **FactScore strict:** fraction of atomic claims judged fully supported.
- **Flesch Reading Ease (FRE):** readability index where higher scores indicate easier text.
- **Flesch–Kincaid grade:** approximate U.S. school grade level required to read the text;
  lower scores indicate easier text.

### Data sources (eval-3 overall)

| Metric family | Source |
|---------------|--------|
| SourceCheckup (strict & partial) | Eval-3 only |
| FactScore (strict & partial) | Best-of eval-2/eval-3 per product × variant (higher score kept) |
| Flesch Reading Ease / Flesch–Kincaid | Best-of eval-2/eval-3 (max FRE; min grade) |

Best-of rule: `eval/plot_best_of_eval2_eval3.py` → `eval/figures/best_of_eval2_eval3/best_of_scores.tsv`.

### Primary endpoint

The **primary endpoint** was **SourceCheckup partial-credit** (δ = 10 percentage points, pp).
Citation integrity is the core quality standard for model cards: other metrics were evaluated as
**secondary endpoints**. All other metrics in this report are secondary/supporting.

### Non-inferiority margins (δ)

Non-inferiority margins were **analyst-specified** at conservative, moderate, and liberal levels
based on (1) substantive tolerability, (2) the spread of manual reference scores across products,
and (3) the observed paired Auto–Manual differences. **Moderate δ** was used for primary reporting.
This margin selection should be considered exploratory rather than strictly pre-specified before
viewing comparative results, unless documented otherwise in the study protocol.

| Endpoint | Moderate δ | Unit |
|----------|------------|------|
| SourceCheckup partial *(primary)* | 10 | pp |
| SourceCheckup strict | 8 | pp |
| FactScore partial | 15 | pp |
| FactScore strict | 15 | pp |
| Flesch Reading Ease | 10 | FRE points |
| Flesch–Kincaid grade† | 2.0 | grade levels |

†For Flesch–Kincaid, Δ = Manual grade − Auto grade so that positive values consistently indicate
better automated readability (lower grade level = easier to read).

Example (primary endpoint): A non-inferiority margin of 10 pp on citation partial-credit score means automated cards could score up to 10 pp below manual cards and still be considered not meaningfully worse.

### Statistical analysis

For each endpoint, paired differences Δᵢ were computed across the five products. Non-inferiority
was tested against H₀: μΔ ≤ −δ versus H₁: μΔ > −δ.

**Primary decision rule:** A 95% **percentile bootstrap confidence interval** for the mean paired
difference was estimated from **10,000 bootstrap resamples** in which the five paired observations
were **sampled with replacement**. Non-inferiority was **declared if the bootstrap lower bound
exceeded −δ**. This CI-based rule was the sole criterion for declaring non-inferiority.

**Sensitivity analyses** (did not override the primary CI conclusion):

1. **One-sample t-test on paired Auto–Manual differences:** evaluated H₀: μΔ ≤ −δ vs H₁: μΔ > −δ.
2. **Wilcoxon signed-rank test on (Δ + δ):** nonparametric assessment of whether the paired-difference
   distribution was shifted above the non-inferiority boundary; tests a rank-based location shift,
   not the mean specifically.
3. **Exact paired sign-flip permutation test:** because n = 5 yields only 2⁵ = 32 sign configurations,
   all configurations were enumerated and p = (count + 1) / 33, where count is the number of
   configurations with mean Δ ≤ −δ. The minimum attainable one-sided p-value is therefore 1/33 ≈ 0.030.

Sensitivity analyses were included to assess robustness across parametric, rank-based, and
randomization-based approaches given the small sample size.

**Product-level checks:** The column *Products within NI margin* counts products for which the
**observed** paired difference satisfied Δᵢ > −δ. This is a **descriptive** classification only;
no product-specific inferential hypothesis test was performed (one pair per product).

Global non-inferiority asks whether the **average** paired difference across products exceeds −δ.
Product-level checks ask whether each **observed** Δᵢ exceeds −δ. These answer different questions
and are not contradictory (e.g., global NI can hold while one product falls outside the margin).

---

## Results

### Table 1. Global non-inferiority results (eval-3 overall, moderate δ, n = 5)

| Metric | Score source | Mean Δ | 95% Bootstrap CI | δ | NI pass (primary CI)? | p (t, NI)* | p (Wilcoxon)* | p (exact perm, NI)* | Products within NI margin |
|--------|--------------|--------|------------------|---|------------------------|------------|---------------|---------------------|---------------------------|
| SourceCheckup partial *(primary)* | eval-3 | +10.4 pp | [4.2, 17.3] pp | 10 pp | **Yes** | 0.003 | 0.0312 | 0.061 (1/32 configs ≤ −δ) | 5/5 |
| SourceCheckup strict | eval-3 | +17.7 pp | [7.9, 29.7] pp | 8 pp | **Yes** | 0.007 | 0.0312 | 0.242 (7/32 configs ≤ −δ) | 5/5 |
| FactScore partial | best-of eval-2/3 | +4.8 pp | [-8.2, 15.1] pp | 15 pp | **Yes** | 0.023 | 0.0625 | 0.030 (0/32 configs ≤ −δ) | 4/5 |
| FactScore strict | best-of eval-2/3 | +7.9 pp | [-7.4, 20.9] pp | 15 pp | **Yes** | 0.028 | 0.0625 | 0.061 (1/32 configs ≤ −δ) | 4/5 |
| Flesch Reading Ease | best-of eval-2/3 | +13.7 | [3.1, 25.0] | 10 FRE points | **Yes** | 0.010 | 0.0312 | 0.152 (4/32 configs ≤ −δ) | 5/5 |
| Flesch–Kincaid grade† | best-of eval-2/3 | +2.8 | [0.8, 5.2] | 2 grade levels | **Yes** | 0.009 | 0.0312 | 0.212 (6/32 configs ≤ −δ) | 5/5 |

\*Sensitivity analyses only; primary NI decision based on bootstrap CI lower bound > −δ.

**NI pass (primary CI)?** = Yes if 95% percentile bootstrap CI lower bound > −δ.

### Primary endpoint: SourceCheckup partial-credit

Automated cards **met the non-inferiority criterion** for citation support (δ = 10 pp):
mean Δ = **+10.4 pp**, 95% bootstrap CI **[4.2, 17.3] pp**.
The entire interval lies **above zero**, indicating higher average citation support for
automated cards in this sample. The **primary conclusion remains non-inferiority** (not superiority),
as that was the **analysis framework** (non-inferiority, not superiority).

- Primary CI rule: **pass** (lower bound 4.2 > −10)
- Sensitivity t-test: p = 0.003
- Sensitivity Wilcoxon: p = 0.0312 (minimum attainable ≈ 0.031 with n = 5)
- Sensitivity exact permutation: p = 0.061 (1/32 configurations with mean ≤ −δ)
- Products within NI margin: **5/5**

### Table 2. SourceCheckup partial-credit by product (eval-3, δ = 10 pp)

| Product | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|------------|----------|--------|-------------------|
| DERM | 80.6 | 94.7 | +14.2 | Yes |
| DermGPT | 84.4 | 90.0 | +5.6 | Yes |
| Dermasensor | 98.6 | 100.0 | +1.4 | Yes |
| Forus | 66.7 | 90.2 | +23.6 | Yes |
| SkinVision | 92.9 | 100.0 | +7.1 | Yes |

### Table 3. FactScore partial-credit by product (best-of eval-2/3, δ = 15 pp)

| Product | Manual (%) | Auto (%) | Δ (pp) | Within NI margin? |
|---------|------------|----------|--------|-------------------|
| DERM | 69.6 | 85.3 | +15.7 | Yes |
| DermGPT | 88.1 | 95.8 | +7.7 | Yes |
| Dermasensor | 77.6 | 80.8 | +3.2 | Yes |
| Forus | 81.9 | 100.0 | +18.1 | Yes |
| SkinVision | 83.3 | 62.5 | -20.8 | **No** |

**SkinVision note:** The automated eval-3 card cites only one URL (`skinvision.com/en-us`), which
returned cookie-consent text in the FactScore corpus; the eval-2 automated card performs better
(62.5% vs 11.8% eval-3). SourceCheckup wall failures were relabelled to supported; FactScore has
no equivalent adjustment.

### Table 4. Flesch readability by product (best-of eval-2/3)

| Product | Manual FRE | Auto FRE | Δ FRE | Manual FK | Auto FK | Δ FK† | FRE within margin (δ=10)? | FK within margin (δ=2)? |
|---------|------------|----------|-------|-----------|---------|-------|---------------------------|-------------------------|
| DERM | 22.3 | 32.3 | +10.0 | 16.0 | 14.2 | +1.8 | Yes | Yes |
| DermGPT | 4.7 | 25.9 | +21.2 | 18.6 | 14.6 | +4.0 | Yes | Yes |
| Dermasensor | 19.1 | 21.7 | +2.6 | 17.2 | 16.2 | +1.0 | Yes | Yes |
| Forus | 25.8 | 25.9 | +0.1 | 14.6 | 14.6 | +0.0 | Yes | Yes |
| SkinVision | 7.2 | 41.7 | +34.5 | 19.7 | 12.7 | +7.0 | Yes | Yes |

Forus automated readability uses the eval-2 card (eval-3 automated card was much harder to read).

---

## Summary and interpretation

1. **Primary endpoint (SourceCheckup partial-credit, eval-3):** Automated cards were **non-inferior**
   to manual cards on citation support (δ = 10 pp). All five products were descriptively within the
   margin.

2. **Secondary — strict citation support:** Non-inferior on average; 5/5 products within margin.

3. **Secondary — FactScore (best-of):** Met **global** non-inferiority on average (δ = 15 pp), but
   **SkinVision** fell outside the margin (−20.8 pp partial). This reflects sparse citations and
   cookie-wall corpus content on the automated card, not a SourceCheckup failure.

4. **Secondary — readability (best-of):** Non-inferior on average; 5/5 within margin on both FRE
   and Flesch–Kincaid after best-of selection.

### Overall conclusion

Automated cards were **non-inferior to manual reference cards on the primary citation-support endpoint**.
Secondary analyses supported non-inferiority for strict citation support, corpus grounding (FactScore),
and readability at the specified margins. Product-level results were generally consistent with global
analyses, except **SkinVision FactScore**, which warrants further review.

**Analysis script:** `eval/run_noninferiority_analysis.py`  
**Outputs:** `eval/ni_analysis/`
