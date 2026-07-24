import json
import re
from pathlib import Path

def md_reference_to_jsonl(md_path, jsonl_path):
    text = Path(md_path).read_text(encoding="utf-8")

    # Split on markdown sections like: ## Source: <url>
    parts = re.split(r"^## Source:\s*(.+)$", text, flags=re.MULTILINE)

    # parts will look like:
    # [header_text, url1, body1, url2, body2, ...]
    entries = []

    for i in range(1, len(parts), 2):
        url = parts[i].strip()
        body = parts[i + 1].strip()

        # remove separator lines and obvious warnings if desired
        body = re.sub(r"^---\s*$", "", body, flags=re.MULTILINE).strip()

        if not body:
            continue

        entries.append({
            "title": url,
            "text": body
        })

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Saved {len(entries)} entries to {jsonl_path}")

if __name__ == "__main__":
    md_reference_to_jsonl("skinvision_reference.md", "skinvision_corpus.jsonl")
    md_reference_to_jsonl("skin_analytics_reference.md", "skin_analytics_corpus.jsonl")
    md_reference_to_jsonl("dermgpt_reference.md", "dermgpt_corpus.jsonl")