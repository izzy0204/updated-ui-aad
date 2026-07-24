import requests
from bs4 import BeautifulSoup
from readability import Document
from pdfminer.high_level import extract_text
from pathlib import Path
from tqdm import tqdm
import re

OUTPUT_MD = "skinvision_reference.md"

URLS = [
    "https://www.skinvision.com/articles/how-does-skinvisions-algorithm-detect-skin-cancer",
    "https://www.skinvision.com/about",
    "https://www.skinvision.com/contact-us",
    "https://www.skinvision.com/instructions-for-use",
    "https://www.skinvision.com/scientific-evidence",
    "https://skinvision-static-content.s3-eu-west-1.amazonaws.com/website/eifu/2.10/Instructions_for_Use_SkinVision_Service_6.0_-_EN_-_v2.10.pdf",
    "https://www.skinvision.com/getting-started",
    "https://skinvision-static-content.s3-eu-west-1.amazonaws.com/website/en/Terms_and_Conditions.pdf",
    "https://www.skinvision.com/press-release/skinvision-earns-europes-top-medical-certification-for-ai-powered-skin-cancer-detection",
    "https://www.skinvision.com/aad",
    "https://www.skinvision.com/articles/how-machine-learning-detects-skin-cancer",
    "https://www.skinvision.com/articles/what-to-expect-from-your-skin-check-appointment",
    "https://www.skinvision.com/questions/is-my-personal-information-safe",
    "https://www.skinvision.com/press-release/skinvision-achieves-three-iso-certifications",
    "https://skinvision-static-content.s3-eu-west-1.amazonaws.com/website/en/Privacy_Policy_SkinVision.pdf",
    "https://www.sciencedirect.com/org/science/article/pii/S2562095919000023",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC9367531/",
    "https://repub.eur.nl/pub/119322/Repub_119322_O-A.pdf",
    "https://pubmed.ncbi.nlm.nih.gov/35124665/",
    "https://pubmed.ncbi.nlm.nih.gov/37261324/",
    "https://pubmed.ncbi.nlm.nih.gov/28562195/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC7027514/",
    "https://pubmed.ncbi.nlm.nih.gov/31494983/",
    "https://academic.oup.com/bjd/article/191/Supplement_1/i196/7698886"
]

def clean_text(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def scrape_html(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    doc = Document(r.text)
    html = doc.summary()

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    return clean_text(text)

def scrape_pdf(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    tmp = Path("_tmp.pdf")
    tmp.write_bytes(r.content)

    text = extract_text(tmp)
    tmp.unlink()

    return clean_text(text)

def scrape_all(urls, output_md):
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# SkinVision — Aggregated Reference Evidence\n\n")
        f.write("> Automatically scraped source corpus for model card grounding\n\n")

        for url in tqdm(urls):
            f.write("\n---\n\n")
            f.write(f"## Source: {url}\n\n")

            try:
                if url.lower().endswith(".pdf"):
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
