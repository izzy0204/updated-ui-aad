import requests
from bs4 import BeautifulSoup
from readability import Document
from pdfminer.high_level import extract_text
from pathlib import Path
from tqdm import tqdm
import re

OUTPUT_MD = "dermgpt_reference.md"

URLS = [
    "https://www.dermgpt.com/",
    "https://www.dermgpt.com/sla",
    "https://www.jaad.org/article/S0190-9622(25)01529-4/abstract",
    "https://pubmed.ncbi.nlm.nih.gov/38754096/",
    "https://www.sciencedirect.com/science/article/pii/S2667102625000919",
]

def clean_text(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def is_pdf_url(url):
    return ".pdf" in url.lower()

def scrape_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    doc = Document(r.text)
    html = doc.summary()

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    return clean_text(text)

def scrape_pdf(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()

    tmp = Path("_tmp.pdf")
    tmp.write_bytes(r.content)

    text = extract_text(tmp)
    tmp.unlink()

    return clean_text(text)

def scrape_all(urls, output_md):
    seen = set()

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# DermGPT — Aggregated Reference Evidence\n\n")
        f.write("> Automatically scraped source corpus for model card grounding\n\n")

        for url in tqdm(urls):
            if url in seen:
                continue
            seen.add(url)

            f.write("\n---\n\n")
            f.write(f"## Source: {url}\n\n")

            try:
                if is_pdf_url(url):
                    text = scrape_pdf(url)
                else:
                    text = scrape_html(url)

                if not text or len(text) < 200:
                    f.write("_[Warning: very little text extracted]_\n\n")

                f.write(text + "\n")

            except Exception as e:
                f.write(f"_ERROR scraping this source: {e}_\n")

if __name__ == "__main__":
    scrape_all(URLS, OUTPUT_MD)
    print(f"Saved reference file to {OUTPUT_MD}")