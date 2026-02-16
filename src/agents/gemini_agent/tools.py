from __future__ import annotations
import html, json, re, urllib.parse
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import requests

# ---------- Search (DuckDuckGo HTML endpoint) ----------
def ddg_search(query: str, timeout: float, n: int = 5) -> List[str]:
    """
    Returns up to n result URLs from DuckDuckGo HTML results page.
    Avoids JS; parses 'uddg' redirect param when present.
    """
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.get(url, params={"q": query, "kl": "us-en"}, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0"
        })
        if not r.ok:
            return []
        # Each result link often appears as <a class="result__a" href="/l/?kh=1&uddg=<enc>">
        urls: List[str] = []
        for m in re.finditer(r'href="([^"]+)"[^>]*class="result__a"', r.text):
            raw = html.unescape(m.group(1))
            if "uddg=" in raw:
                enc = raw.split("uddg=", 1)[1]
                enc = enc.split("&", 1)[0]
                u = urllib.parse.unquote(enc)
            else:
                u = raw
                if u.startswith("/"):  # relative → absolute
                    u = urllib.parse.urljoin("https://duckduckgo.com", u)
            if u.startswith("http"):
                urls.append(u)
            if len(urls) >= n:
                break
        return urls
    except Exception:
        return []

# ---------- Fetchers ----------
def fetch_text_url(url: str, timeout: float) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok:
            return ""
        txt = r.text
        # strip scripts/styles/tags → plain-ish text
        txt = re.sub(r"<script[\\s\\S]*?</script>", " ", txt, flags=re.I)
        txt = re.sub(r"<style[\\s\\S]*?</style>", " ", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        return re.sub(r"\\s+", " ", txt).strip()
    except Exception:
        return ""

def fetch_hf_readme(model_id: str, timeout: float) -> Tuple[str, str]:
    url = f"https://huggingface.co/{model_id}/raw/main/README.md"
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        return url, r.text if r.ok else ""
    except Exception:
        return url, ""

def fetch_github_readme(owner_repo: str, timeout: float) -> Tuple[str, str]:
    url = f"https://raw.githubusercontent.com/{owner_repo}/main/README.md"
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        return url, r.text if r.ok else ""
    except Exception:
        return url, ""

# ---------- Normalization / joining ----------
@dataclass
class Source:
    id: int
    url: str
    type: str
    text: str

def normalize_sources(blobs: List[Tuple[str, str]], types: List[str]) -> Tuple[str, str]:
    """
    blobs: list of (url, text)
    types: parallel list of source types: 'huggingface' | 'github' | 'web'
    Returns (manifest_text, combined_sources_text)
    """
    sources: List[Source] = []
    seen = set()
    sid = 1
    for (url, text), t in zip(blobs, types):
        if not text or (url, t) in seen:
            continue
        seen.add((url, t))
        clean = re.sub(r"\\s+", " ", text).strip()
        sources.append(Source(id=sid, url=url, type=t, text=clean))
        sid += 1

    manifest_lines = []
    body_lines = []
    
    # Truncate per-source instead of globally to ensure fair distribution
    # Allow more characters per source, with higher overall limit
    max_chars_per_source = 20000  # Increased per-source limit
    max_total_body_chars = 80000  # Increased overall limit (was 45000)
    
    total_chars = 0
    for s in sources:
        manifest_lines.append(f"[SOURCE {s.id}] {s.type} {s.url}")
        
        # Truncate individual source if needed
        source_text = s.text
        if len(source_text) > max_chars_per_source:
            source_text = source_text[:max_chars_per_source] + "... [truncated]"
        
        source_block = f"[SOURCE {s.id}] {s.url}\\n{source_text}\\n---"
        
        # Only add if we haven't exceeded total limit
        if total_chars + len(source_block) <= max_total_body_chars:
            body_lines.append(source_block)
            total_chars += len(source_block)
        else:
            # If adding this would exceed limit, truncate it to fit remaining space
            remaining = max_total_body_chars - total_chars
            if remaining > 100:  # Only add if there's meaningful space left
                truncated_block = source_block[:remaining] + "... [truncated due to total limit]"
                body_lines.append(truncated_block)
            break
    
    manifest = "\\n".join(manifest_lines)
    body = "\\n".join(body_lines)
    return manifest[:8000], body

# ---------- JSON helpers ----------
def extract_json_block(s: str) -> Dict[str, Any]:
    """Extract JSON block from text, with improved error handling for malformed responses."""
    if not s or not isinstance(s, str):
        return {}
    
    # Clean the input - remove common artifacts
    s = s.strip()
    
    # Remove markdown code blocks if present
    if s.startswith("```json"):
        s = s[7:]
    if s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    
    # Remove any remaining prompt text that might have leaked through
    prompt_indicators = [
        "CRITICAL REQUIREMENTS:",
        "You MUST return ONLY valid JSON",
        "The JSON MUST start with",
        " and end with ",
        "MANDATORY JSON FORMAT",
        "STRICT NAMING:",
        "OUTPUT POLICY:",
        "RESPOND AS JSON:",
        "Return ONLY a compact JSON",
        "The JSON MUST start with { and end with }"
    ]
    
    for indicator in prompt_indicators:
        if indicator in s:
            # Find the start of JSON
            json_start = s.find("{")
            if json_start > 0:
                s = s[json_start:]
                break
    
    # Look for JSON object boundaries
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        print(f"DEBUG: No JSON object found in: {repr(s[:100])}...")
        return {}
    
    json_str = s[start:end+1]
    
    # Additional cleaning for common malformed responses
    json_str = json_str.replace('" and end with "', '')
    json_str = json_str.replace('"CRITICAL REQUIREMENTS"', '')
    json_str = json_str.replace('"You MUST return ONLY valid JSON"', '')
    
    try:
        result = json.loads(json_str)
        # Ensure we got a dictionary, not just a string
        if isinstance(result, dict):
            return result
        else:
            # If we got a string like "values", wrap it in a dict
            print(f"DEBUG: Got non-dict result: {type(result)} = {repr(result)}")
            return {"raw_response": result}
    except json.JSONDecodeError as e:
        # Log the error for debugging
        print(f"JSON parsing error: {e}")
        print(f"Attempted to parse: {repr(json_str[:200])}...")
        
        # Try to fix common issues
        if '"values"' in json_str and not json_str.endswith('}'):
            # Try to complete the JSON
            try:
                fixed_json = json_str + '}'
                result = json.loads(fixed_json)
                if isinstance(result, dict):
                    print("DEBUG: Fixed incomplete JSON")
                    return result
            except:
                pass
        
        # Try to extract just the values part if the structure is malformed
        if '"values"' in json_str:
            try:
                # Find the values section
                values_start = json_str.find('"values"')
                if values_start >= 0:
                    # Look for the next colon and opening brace
                    colon_pos = json_str.find(':', values_start)
                    if colon_pos >= 0:
                        brace_pos = json_str.find('{', colon_pos)
                        if brace_pos >= 0:
                            # Find the matching closing brace
                            brace_count = 0
                            end_pos = brace_pos
                            for i, char in enumerate(json_str[brace_pos:], brace_pos):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_pos = i
                                        break
                            
                            values_json = json_str[brace_pos:end_pos+1]
                            values_obj = json.loads(values_json)
                            if isinstance(values_obj, dict):
                                print("DEBUG: Extracted values section")
                                return {"values": values_obj, "evidence": {}}
            except:
                pass
        
        return {}
    except Exception as e:
        print(f"Unexpected error in JSON parsing: {e}")
        return {}

# ---------- Utility ----------
def set_by_path(root: Dict[str, Any], path: str, value):
    print(f"DEBUG: set_by_path called with path={repr(path)}, value={repr(value)[:100]}...")
    
    # Safety check: reject paths that look like prompt text or are malformed
    if not path or not isinstance(path, str):
        print(f"ERROR: Invalid path type: {type(path)}")
        return
        
    if any(indicator in path for indicator in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST", " and end with"]):
        print(f"ERROR: Rejecting path that looks like prompt text: {repr(path)}")
        return
    
    # Additional safety checks for malformed paths
    if path.strip() == "" or len(path.strip()) < 2:
        print(f"ERROR: Path too short or empty: {repr(path)}")
        return
        
    # Check for invalid characters that shouldn't be in field paths
    invalid_chars = ['\n', '\r', '\t', '"', "'", '`', '(', ')', '[', ']', '{', '}']
    if any(char in path for char in invalid_chars):
        print(f"ERROR: Path contains invalid characters: {repr(path)}")
        return
    
    try:
        keys = path.split(".")
        cur = root
        for k in keys[:-1]:
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value
    except Exception as e:
        print(f"ERROR: Failed to set path {repr(path)}: {e}")
        return

def flatten_nonempty(d: Dict[str, Any]) -> int:
    """Counts non-empty leaf values in a nested dict."""
    def nonempty(v):
        return v not in (None, "", [], {})
    cnt = 0
    stack = [d]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            for v in x.values():
                if isinstance(v, dict):
                    stack.append(v)
                elif isinstance(v, list):
                    if v: cnt += 1
                else:
                    if nonempty(v): cnt += 1
    return cnt
