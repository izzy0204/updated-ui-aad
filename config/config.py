import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
DEFAULT_TEMP  = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

# Web Search Configuration
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "auto")  # auto, google, bing, duckduckgo, serpapi
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "10"))
WEB_SEARCH_DELAY_SECONDS = float(os.getenv("WEB_SEARCH_DELAY_SECONDS", "0.5"))

# Search API Keys (optional - will use available providers)
# All API-based providers removed - no API keys available
# Only DuckDuckGo (no API key required) is available

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
        'provider': WEB_SEARCH_PROVIDER,
        'max_results': WEB_SEARCH_MAX_RESULTS,
        'delay_seconds': WEB_SEARCH_DELAY_SECONDS
    }