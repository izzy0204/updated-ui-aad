import os
import google.generativeai as genai

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
DEFAULT_TEMP  = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

def make_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing in environment")
    genai.configure(api_key=key)
    return genai.GenerativeModel(DEFAULT_MODEL)