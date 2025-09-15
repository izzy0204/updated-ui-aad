import requests, io
from typing import Tuple
from bs4 import BeautifulSoup

def fetch_text(url: str) -> Tuple[str, str]:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200:
            return "", ""
        ctype = r.headers.get("Content-Type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            try:
                import pdfminer.high_level as pdfminer
                text = pdfminer.extract_text(io.BytesIO(r.content))
                return "application/pdf", (text or "").strip()
            except Exception:
                return "application/pdf", ""
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script","style","nav","header","footer","noscript"]):
                tag.extract()
            text = " ".join(soup.get_text(separator=" ").split())
            return "text/html", text
    except Exception:
        return "", ""