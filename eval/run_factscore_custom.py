import json
import os
from pathlib import Path
from factscore.factscorer import FactScorer

print("script started")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("OPENAI_API_KEY present:", bool(OPENAI_API_KEY))

def load_generations(jsonl_path: str):
    topics = []
    generations = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            topics.append(row["topic"])
            generations.append(row["output"])

    return topics, generations

def run_one(fs, knowledge_name: str, corpus_jsonl: str, db_path: str, outputs_jsonl: str):
    print(f"[CHECK] knowledge_name={knowledge_name}")
    print(f"[CHECK] corpus exists? {Path(corpus_jsonl).exists()} -> {corpus_jsonl}")
    print(f"[CHECK] outputs exists? {Path(outputs_jsonl).exists()} -> {outputs_jsonl}")

    if not Path(corpus_jsonl).exists():
        print(f"[SKIP] Missing corpus: {corpus_jsonl}")
        return None

    if not Path(outputs_jsonl).exists():
        print(f"[SKIP] Missing outputs: {outputs_jsonl}")
        return None

    print(f"[INFO] Registering knowledge source: {knowledge_name}")
    fs.register_knowledge_source(
        knowledge_name,
        data_path=corpus_jsonl,
        db_path=db_path
    )

    topics, generations = load_generations(outputs_jsonl)

    print(f"[INFO] Loaded {len(topics)} topic(s) from {outputs_jsonl}")
    print(f"[INFO] Scoring {knowledge_name}...")

    result = fs.get_score(
        topics,
        generations,
        knowledge_source=knowledge_name,
        gamma=10
    )

    print(f"\n=== {knowledge_name} ===")
    print(json.dumps(result, indent=2))

    return result

def save_summary(results: dict, out_path: str = "factscore_summary.json"):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Saved summary to {out_path}")

if __name__ == "__main__":
    print("main block running")

    if not OPENAI_API_KEY:
        raise ValueError("Set your OPENAI_API_KEY environment variable first.")

    fs = FactScorer(openai_key=OPENAI_API_KEY)
    all_results = {}

    dermgpt_result = run_one(
        fs=fs,
        knowledge_name="dermgpt_custom",
        corpus_jsonl="dermgpt_corpus.jsonl",
        db_path="dermgpt_corpus.db",
        outputs_jsonl="dermgpt_outputs.jsonl"
    )
    if dermgpt_result is not None:
        all_results["dermgpt_custom"] = dermgpt_result

    derm_result = run_one(
        fs=fs,
        knowledge_name="skin_analytics_custom",
        corpus_jsonl="skin_analytics_corpus.jsonl",
        db_path="skin_analytics_corpus.db",
        outputs_jsonl="skin_analytics_outputs.jsonl"
    )
    if derm_result is not None:
        all_results["skin_analytics_custom"] = derm_result

    skinvision_result = run_one(
        fs=fs,
        knowledge_name="skinvision_custom",
        corpus_jsonl="skinvision_corpus.jsonl",
        db_path="skinvision_corpus.db",
        outputs_jsonl="skinvision_outputs.jsonl"
    )
    if skinvision_result is not None:
        all_results["skinvision_custom"] = skinvision_result

    save_summary(all_results)