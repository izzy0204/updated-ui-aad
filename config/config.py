import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
DEFAULT_TEMP  = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

# Web Search Configuration (simplified - only DuckDuckGo available)
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "10"))

def make_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing in environment")
    genai.configure(api_key=key)
    return genai.GenerativeModel(DEFAULT_MODEL)

def get_web_search_config():
    """Get web search configuration"""
    return {
        'enabled': WEB_SEARCH_ENABLED,
        'max_results': WEB_SEARCH_MAX_RESULTS
    }