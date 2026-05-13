"""
Inferential stats for RAGAS field-level scores (Auto / A cards only).

What this does
--------------
- 95% bootstrap CIs for the mean faithfulness and mean answer_relevancy per model
  (resamples the 6 field rows with replacement within each model).
- Paired tests between models on the same 6 fields: paired t-test p-value and
  bootstrap CI for the mean paired difference.

Important limitations
---------------------
- n = one row per (model, field) with 6 fields → very small effective sample;
  intervals are wide and p-values are easy to misinterpret.
- Fields are not independent (same card, shared retrieval/generation), so these
  are exploratory summaries, not a rigorous trial design.
- If a metric is constant (e.g. faithfulness all 1.0), variance is zero and
  p-values / CIs are not meaningful for discrimination.

Python 3.11+; requires pandas, numpy, scipy (see requirements.txt).
"""

from __future__ import annotations

from pathlib import Path
import zlib

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
DATASET_CSV = ROOT / "ragas_dataset.csv"
RESULTS_CSV = ROOT / "ragas_results.csv"
OUT_BY_MODEL = ROOT / "ragas_inference_by_model.csv"
OUT_PAIRWISE = ROOT / "ragas_inference_pairwise.csv"

RNG_SEED = 42
N_BOOT = 10_000
MODEL_ORDER = ["DermaSensor", "DermGPT", "Tandem"]


def _boot_seed(label: str) -> int:
    return RNG_SEED + (zlib.crc32(label.encode("utf-8")) & 0xFFFF)


def _merge_scores() -> pd.DataFrame:
    dataset = pd.read_csv(DATASET_CSV)
    results = pd.read_csv(RESULTS_CSV).rename(
        columns={"user_input": "question", "response": "answer", "retrieved_contexts": "contexts"}
    )
    merged = dataset.merge(
        results[["question", "answer", "faithfulness", "answer_relevancy"]],
        on=["question", "answer"],
        how="left",
        validate="one_to_one",
    )
    merged["provenance"] = merged["card_label"].str.split(" · ").str[0]
    merged["model"] = merged["card_label"].str.split(" · ").str[1]
    return merged[merged["provenance"].eq("A")].copy()


def bootstrap_mean_ci(values: np.ndarray, *, n_boot: int = N_BOOT, seed: int = RNG_SEED) -> tuple[float, float, float]:
    """Return mean and 95% percentile bootstrap CI for the mean."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[i] = float(x[idx].mean())
    return float(x.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def paired_stats(
    a: np.ndarray,
    b: np.ndarray,
    *,
    n_boot: int = N_BOOT,
    seed: int = RNG_SEED,
) -> tuple[float, float, float, float, float]:
    """
    Paired comparison a vs b (same length).
    Returns: mean_diff (a-b), ci_low, ci_high, p_ttest_rel, p_wilcoxon (or nan).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    mean_d = float(np.mean(d))

    rng = np.random.default_rng(seed + 31337)
    boots = np.empty(n_boot, dtype=float)
    n = len(d)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[i] = float(d[idx].mean())
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))

    t_res = stats.ttest_rel(a, b, nan_policy="omit")
    p_t = float(t_res.pvalue) if np.isfinite(t_res.pvalue) else float("nan")

    p_w = float("nan")
    if n >= 3 and np.std(d) > 1e-12:
        try:
            w_res = stats.wilcoxon(d, zero_method="wilcox", mode="auto")
            p_w = float(w_res.pvalue)
        except ValueError:
            p_w = float("nan")

    return mean_d, lo, hi, p_t, p_w


def main() -> None:
    merged = _merge_scores()
    rows_model: list[dict] = []
    for model in MODEL_ORDER:
        g = merged[merged["model"].eq(model)]
        for metric_col, name in [("faithfulness", "faithfulness"), ("answer_relevancy", "answer_relevancy")]:
            v = g[metric_col].to_numpy()
            m, lo, hi = bootstrap_mean_ci(v, seed=_boot_seed(f"mean:{model}:{name}"))
            rows_model.append(
                {
                    "model": model,
                    "metric": name,
                    "n_fields": int(len(v)),
                    "mean": m,
                    "ci95_low": lo,
                    "ci95_high": hi,
                }
            )
    pd.DataFrame(rows_model).to_csv(OUT_BY_MODEL, index=False)

    wide = merged.pivot_table(index="field", columns="model", values=["faithfulness", "answer_relevancy"], aggfunc="first")
    rows_pair: list[dict] = []
    for i, m1 in enumerate(MODEL_ORDER):
        for m2 in MODEL_ORDER[i + 1 :]:
            for metric_col, name in [("faithfulness", "faithfulness"), ("answer_relevancy", "answer_relevancy")]:
                try:
                    s1 = wide[(metric_col, m1)].to_numpy()
                    s2 = wide[(metric_col, m2)].to_numpy()
                except KeyError:
                    continue
                mask = np.isfinite(s1) & np.isfinite(s2)
                s1, s2 = s1[mask], s2[mask]
                mean_d, lo, hi, p_t, p_w = paired_stats(
                    s1, s2, seed=_boot_seed(f"paired:{m1}:{m2}:{name}")
                )
                rows_pair.append(
                    {
                        "model_higher_column": m1,
                        "model_lower_column": m2,
                        "metric": name,
                        "n_paired": int(len(s1)),
                        "mean_diff_m1_minus_m2": mean_d,
                        "ci95_diff_low": lo,
                        "ci95_diff_high": hi,
                        "p_paired_ttest": p_t,
                        "p_wilcoxon": p_w,
                    }
                )
    pd.DataFrame(rows_pair).to_csv(OUT_PAIRWISE, index=False)

    print(f"Wrote {OUT_BY_MODEL}")
    print(f"Wrote {OUT_PAIRWISE}")


if __name__ == "__main__":
    main()
