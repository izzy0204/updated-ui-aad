# config/config.py
import os
from dotenv import load_dotenv
from dataclasses import dataclass

#  Load .env one time only
load_dotenv()

@dataclass
class Settings:
    # --- Gemini Model & API ---
    google_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "30"))

    # --- Thinking Configuration (Gemini 2.5 Flash) ---
    gemini_thinking_budget: int = int(os.getenv("GEMINI_THINKING_BUDGET", "2048"))
    gemini_include_thoughts: bool = bool(int(os.getenv("GEMINI_INCLUDE_THOUGHTS", "0")))
    gemini_max_concurrent: int = int(os.getenv("GEMINI_MAX_CONCURRENT", "10"))

    # --- Pricing / Limits ---
    input_cost_per_1k: float = float(os.getenv("INPUT_COST_PER_1K", "0.00015"))
    output_cost_per_1k: float = float(os.getenv("OUTPUT_COST_PER_1K", "0.0006"))
    max_input_chars: int = int(os.getenv("MAX_INPUT_CHARS", "12000"))
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2000"))

    # --- Debug / Verbosity ---
    extractor_verbose: bool = bool(int(os.getenv("EXTRACTOR_VERBOSE", "1")))

    # --- Integration Tokens ---
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    batch_size: int = int(os.getenv("BATCH_SIZE", "3"))

def get_settings() -> Settings:
    return Settings()

def warn_if_missing(name: str, value: str):
    if not value:
        print(f"Warning: {name} is not set. Continuing without it.")
    return value
