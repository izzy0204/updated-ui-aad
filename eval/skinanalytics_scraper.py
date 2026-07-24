import requests
from bs4 import BeautifulSoup
from readability import Document
from pdfminer.high_level import extract_text
from pathlib import Path
from tqdm import tqdm
import re

OUTPUT_MD = "skin_analytics_reference.md"

URLS = [
    "https://skin-analytics.com/",
    "https://skin-analytics.com/faq/",
    "https://skin-analytics.com/news/skin-cancer/prospective-study-shows-ai-as-accurate-as-clinical-specialist/",
    "https://skin-analytics.com/ai-pathways/derm-performance/",
    "https://skin-analytics.com/news/regulatory-certification/derm-class-iii-ce-mark/",
    "https://skin-analytics.com/ai-pathways/equality-of-access/",
    "https://skin-analytics.com/ai-pathways/certifications/",
    "https://skin-analytics.com/wp-content/uploads/2024/06/SA-001165-LB-v11-DERM-Instructions-for-Use.pdf",
    "https://skin-analytics.com/wp-content/uploads/2025/01/SA-001165-LB-v12-DERM-Instructions-for-Use_20Jan2025.pdf",
    "https://skin-analytics.com/wp-content/uploads/2025/02/Everything-you-need-to-know-about-DERM-02.25.pdf",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10645139/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10996444/",
    "https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1288521/full",
    "https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2023.1264846/full",
    "https://peerj.com/articles/cs-1387/",
    "https://www.sciencedirect.com/science/article/pii/S0933365724002100",
    "https://www.medicaldevice-network.com/news/nhs-report-touts-effectiveness-of-skin-analytics-derm-ai-melanoma-tool/",
    "https://unityinsights.co.uk/our-insights/ai-in-health-and-care-award-skin-analytics-evaluation/",
    "https://pubmed.ncbi.nlm.nih.gov/37869160/",
    "https://openresearch.surrey.ac.uk/esploro/outputs/report/99873466002346",
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
        f.write("# Skin Analytics — Aggregated Reference Evidence\n\n")
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