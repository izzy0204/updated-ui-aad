import json
import re
from pathlib import Path

def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def json_card_to_text(json_path: str) -> str:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                if value.strip():
                    chunks.append(f"{key.replace('_', ' ').title()}: {value.strip()}")
            elif isinstance(value, list):
                list_items = []
                for item in value:
                    if isinstance(item, str) and item.strip():
                        list_items.append(item.strip())
                if list_items:
                    chunks.append(f"{key.replace('_', ' ').title()}: {'; '.join(list_items)}")
    else:
        raise ValueError(f"{json_path} does not contain a JSON object at the top level.")

    return clean_text("\n".join(chunks))

def md_card_to_text(md_path: str) -> str:
    text = Path(md_path).read_text(encoding="utf-8")
    return clean_text(text)

def make_output_jsonl(topic: str, text: str, out_path: str) -> None:
    row = {
        "topic": topic,
        "output": text
    }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[OK] Wrote FActScore input to {out_path}")

if __name__ == "__main__":
    # Prefer JSON cards when available
    if Path("dermgpt-20260216-022503 (1).json").exists():
        dermgpt_text = json_card_to_text("dermgpt-20260216-022503 (1).json")
    else:
        dermgpt_text = md_card_to_text("dermgpt-20260216-022503 (1).md")
    make_output_jsonl("DermGPT model card", dermgpt_text, "dermgpt_outputs.jsonl")

    if Path("derm-20260216-194019.json").exists():
        derm_text = json_card_to_text("derm-20260216-194019.json")
    else:
        derm_text = md_card_to_text("derm-20260216-194019.md")
    make_output_jsonl("DERM model card", derm_text, "skin_analytics_outputs.jsonl")

    # Add SkinVision once you have its card file.
    # Example:
    # if Path("skinvision_card.json").exists():
    #     skinvision_text = json_card_to_text("skinvision_card.json")
    # else:
    #     skinvision_text = md_card_to_text("skinvision_card.md")
    # make_output_jsonl("SkinVision model card", skinvision_text, "skinvision_outputs.jsonl")