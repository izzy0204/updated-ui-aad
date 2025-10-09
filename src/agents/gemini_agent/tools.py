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
    for s in sources:
        manifest_lines.append(f"[SOURCE {s.id}] {s.type} {s.url}")
        body_lines.append(f"[SOURCE {s.id}] {s.url}\\n{s.text}\\n---")
    manifest = "\\n".join(manifest_lines)
    body = "\\n".join(body_lines)
    # truncate giant payloads (~45k chars safety)
    return manifest[:8000], body[:45000]

# ---------- JSON helpers ----------
def extract_json_block(s: str) -> Dict[str, Any]:
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(s[start:end+1])
    except Exception:
        return {}

# ---------- Utility ----------
def set_by_path(root: Dict[str, Any], path: str, value):
    keys = path.split(".")
    cur = root
    for k in keys[:-1]:
        cur = cur[k]
    cur[keys[-1]] = value

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
