"""
Run RAGAS metrics on ragas_dataset.csv (question, answer, contexts, optional ground_truth).

Requires API access for default Ragas LLM-based metrics (set OPENAI_API_KEY in .env or env).

`context_precision` and `context_recall` are only included when every row has a non-empty
`ground_truth` (mapped to Ragas `reference`). Otherwise we still run `faithfulness` and
`answer_relevancy`.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv
from ragas import evaluate
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.embeddings.base import embedding_factory
from ragas.metrics import answer_relevancy, faithfulness
try:
    from ragas.metrics import context_precision, context_recall
except Exception:
    context_precision = None
    context_recall = None

# Note: ragas 0.4.x metric objects live under ragas.metrics (deprecated import path),
# but these are the Metric objects expected by ragas.evaluate() in 0.4.x.

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input",
        type=Path,
        default=_EVAL_DIR / "ragas_dataset.csv",
        help="CSV built by build_ragas_dataset.py",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=_EVAL_DIR / "ragas_results.csv",
        help="Where to write metric scores",
    )
    p.add_argument(
        "--dotenv",
        type=Path,
        default=_REPO_ROOT / ".env",
        help="Optional dotenv path",
    )
    return p.parse_args()


def parse_contexts(x) -> list:
    if isinstance(x, list):
        return x
    if pd.isna(x) or x == "":
        return []
    if isinstance(x, str):
        x = x.strip()
        try:
            return json.loads(x)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(x)
        except Exception:
            return [x]
    return []


def main() -> None:
    args = parse_args()
    load_dotenv(args.dotenv)

    if not args.input.is_file():
        raise SystemExit(f"Missing input CSV: {args.input}")

    df = pd.read_csv(args.input)
    required = {"question", "answer", "contexts"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"CSV missing columns: {missing}")

    df["contexts"] = df["contexts"].apply(parse_contexts)

    if "ground_truth" not in df.columns:
        df["ground_truth"] = ""

    df["ground_truth"] = df["ground_truth"].fillna("")

    # Recent Ragas versions require `reference` for context_precision and context_recall.
    # Fill every row with human/reference answers (not the generated answer alone) before running those metrics.
    gt = df["ground_truth"].astype(str).str.strip()
    has_full_reference = bool(gt.ne("").all() and gt.notna().all())

    payload = df[["question", "answer", "contexts"]].copy()
    if not has_full_reference:
        print(
            "Note: Skipping context_precision and context_recall (fill `ground_truth` for every row to enable).",
            file=sys.stderr,
        )

    # Ragas 0.4.x requires explicit llm/embeddings objects for metrics.
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Add it to .env or export it before running RAGAS."
        )

    # Configure OpenAI clients for ragas 0.4.x factories.
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    llm = llm_factory(
        "gpt-4o-mini",
        provider="openai",
        client=openai_client,
        temperature=0.0,
        max_tokens=4096,
    )
    embeddings = embedding_factory(
        provider="openai",
        model="text-embedding-3-small",
        client=openai_client,
        interface="legacy",
    )

    # Ragas 0.4.x expects these canonical column names.
    eval_df = pd.DataFrame(
        {
            "user_input": payload["question"].astype(str),
            "response": payload["answer"].astype(str),
            "retrieved_contexts": payload["contexts"],
        }
    )
    if has_full_reference:
        eval_df["reference"] = gt.astype(str)

    dataset = Dataset.from_pandas(eval_df, preserve_index=False)

    metrics = [faithfulness, answer_relevancy]
    if has_full_reference and context_precision is not None and context_recall is not None:
        metrics.extend([context_precision, context_recall])

    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=True,
        batch_size=1,
    )

    result_df = result.to_pandas()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output, index=False)
    print(result_df)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
