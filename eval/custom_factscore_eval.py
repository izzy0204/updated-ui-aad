import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any

import nltk
from rank_bm25 import BM25Okapi
from openai import OpenAI

# ----------------------------
# Config
# ----------------------------

OPENAI_MODEL = "gpt-4o-mini"
TOP_K_EVIDENCE = 5
MAX_EVIDENCE_CHARS_PER_DOC = 3000

RUNS = [
    {
        "name": "dermgpt",
        "corpus": "dermgpt_corpus.jsonl",
        "outputs": "dermgpt_outputs.jsonl",
    },
    {
        "name": "skin_analytics",
        "corpus": "skin_analytics_corpus.jsonl",
        "outputs": "skin_analytics_outputs.jsonl",
    },
    {
        "name": "skinvision",
        "corpus": "skinvision_corpus.jsonl",
        "outputs": "skinvision_outputs.jsonl",
    },
]

# ----------------------------
# Helpers
# ----------------------------

def ensure_nltk():
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt")

def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def sent_tokenize_safe(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    sents = nltk.sent_tokenize(text)
    return [s.strip() for s in sents if s.strip()]

def simple_tokenize(text: str) -> List[str]:
    text = text.lower()
    return re.findall(r"[a-z0-9]+", text)

# ----------------------------
# Loading data
# ----------------------------

def load_corpus(jsonl_path: str) -> List[Dict[str, str]]:
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            title = row.get("title", "")
            text = row.get("text", "")
            if isinstance(text, list):
                text = "\n".join(str(x) for x in text)
            text = normalize_whitespace(str(text))
            if text:
                docs.append({"title": str(title), "text": text})
    return docs

def load_output_text(outputs_jsonl_path: str) -> str:
    rows = []
    with open(outputs_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    if not rows:
        return ""
    return normalize_whitespace(rows[0]["output"])

# ----------------------------
# Atomic fact extraction
# ----------------------------

def extract_atomic_facts(client: OpenAI, text: str) -> List[str]:
    prompt = f"""
You are extracting atomic factual claims from a model card.

Rules:
- Break the text into short atomic factual claims.
- Each claim must contain exactly one fact whenever possible.
- Keep the wording faithful to the source text.
- Exclude vague marketing language unless it makes a concrete factual claim.
- Exclude pure opinions, recommendations, or empty headings.
- Include quantitative claims, performance claims, dates, approvals, training-data claims, and deployment claims.
- Return ONLY valid JSON in this format:
{{"facts": ["fact 1", "fact 2", "..."]}}

Text:
{text}
""".strip()

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You extract atomic factual claims."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    data = json.loads(content)
    facts = data.get("facts", [])
    cleaned = []
    for fact in facts:
        fact = normalize_whitespace(str(fact))
        if fact:
            cleaned.append(fact)
    return cleaned

# ----------------------------
# Retrieval
# ----------------------------

class CorpusRetriever:
    def __init__(self, docs: List[Dict[str, str]]):
        self.docs = docs
        self.tokenized = [simple_tokenize(doc["title"] + " " + doc["text"]) for doc in docs]
        self.bm25 = BM25Okapi(self.tokenized)

    def search(self, query: str, top_k: int = TOP_K_EVIDENCE) -> List[Dict[str, str]]:
        q_tokens = simple_tokenize(query)
        scores = self.bm25.get_scores(q_tokens)
        ranked = sorted(
            zip(self.docs, scores),
            key=lambda x: x[1],
            reverse=True
        )
        results = []
        for doc, score in ranked[:top_k]:
            results.append({
                "title": doc["title"],
                "text": doc["text"][:MAX_EVIDENCE_CHARS_PER_DOC],
                "score": float(score),
            })
        return results

# ----------------------------
# Verification
# ----------------------------

def judge_support(client: OpenAI, claim: str, evidence_docs: List[Dict[str, str]]) -> Dict[str, Any]:
    evidence_text = []
    for i, doc in enumerate(evidence_docs, start=1):
        evidence_text.append(
            f"[Document {i}]\nTitle: {doc['title']}\nText: {doc['text']}\n"
        )
    joined_evidence = "\n".join(evidence_text)

    prompt = f"""
You are verifying whether a claim is supported by the provided evidence.

Label definitions:
- SUPPORTED: The claim is directly supported by the evidence.
- UNSUPPORTED: The evidence does not support the claim, or contradicts it.
- PARTIAL: The evidence supports only part of the claim, but not all of it.

Be conservative.
Do not use outside knowledge.
Use only the provided evidence.

Return ONLY valid JSON in this exact format:
{{
  "label": "SUPPORTED or UNSUPPORTED or PARTIAL",
  "reason": "brief explanation"
}}

Claim:
{claim}

Evidence:
{joined_evidence}
""".strip()

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You verify factual support using only provided evidence."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    data = json.loads(content)
    label = str(data.get("label", "")).strip().upper()
    reason = normalize_whitespace(str(data.get("reason", "")))

    if label not in {"SUPPORTED", "UNSUPPORTED", "PARTIAL"}:
        label = "UNSUPPORTED"

    return {
        "label": label,
        "reason": reason,
    }

# ----------------------------
# Main scoring
# ----------------------------

def evaluate_one(client: OpenAI, name: str, corpus_path: str, outputs_path: str) -> Dict[str, Any]:
    if not Path(corpus_path).exists():
        print(f"[SKIP] Missing corpus: {corpus_path}")
        return {}

    if not Path(outputs_path).exists():
        print(f"[SKIP] Missing outputs: {outputs_path}")
        return {}

    print(f"\n=== Evaluating {name} ===")
    print(f"[INFO] Loading corpus: {corpus_path}")
    docs = load_corpus(corpus_path)
    print(f"[INFO] Loaded {len(docs)} corpus docs")

    print(f"[INFO] Loading model card text: {outputs_path}")
    output_text = load_output_text(outputs_path)
    if not output_text:
        print("[SKIP] Output text is empty")
        return {}

    print("[INFO] Extracting atomic facts...")
    facts = extract_atomic_facts(client, output_text)
    print(f"[INFO] Extracted {len(facts)} atomic facts")

    retriever = CorpusRetriever(docs)

    detailed = []
    supported = 0
    partial = 0
    unsupported = 0

    for idx, fact in enumerate(facts, start=1):
        print(f"[INFO] Verifying fact {idx}/{len(facts)}")
        evidence = retriever.search(fact, top_k=TOP_K_EVIDENCE)
        judgment = judge_support(client, fact, evidence)

        label = judgment["label"]
        if label == "SUPPORTED":
            supported += 1
        elif label == "PARTIAL":
            partial += 1
        else:
            unsupported += 1

        detailed.append({
            "fact": fact,
            "label": label,
            "reason": judgment["reason"],
            "evidence": evidence,
        })

    total = len(facts)
    score_strict = supported / total if total else 0.0
    score_partial_credit = (supported + 0.5 * partial) / total if total else 0.0

    result = {
        "name": name,
        "total_facts": total,
        "supported": supported,
        "partial": partial,
        "unsupported": unsupported,
        "score_strict": score_strict,
        "score_partial_credit": score_partial_credit,
        "details": detailed,
    }

    out_path = f"{name}_factscore_like_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[OK] Saved detailed results to {out_path}")
    print(f"[RESULT] {name}: strict={score_strict:.3f}, partial-credit={score_partial_credit:.3f}")

    return result

def save_summary(all_results: List[Dict[str, Any]], out_path: str = "factscore_like_summary.json"):
    summary_rows = []
    for r in all_results:
        if not r:
            continue
        summary_rows.append({
            "name": r["name"],
            "total_facts": r["total_facts"],
            "supported": r["supported"],
            "partial": r["partial"],
            "unsupported": r["unsupported"],
            "score_strict": r["score_strict"],
            "score_partial_credit": r["score_partial_credit"],
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Saved summary to {out_path}")

if __name__ == "__main__":
    ensure_nltk()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY first.")

    client = OpenAI(api_key=api_key)

    all_results = []
    for run in RUNS:
        result = evaluate_one(
            client=client,
            name=run["name"],
            corpus_path=run["corpus"],
            outputs_path=run["outputs"],
        )
        if result:
            all_results.append(result)

    save_summary(all_results)