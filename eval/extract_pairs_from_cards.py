import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

CARDS = [
    {
        "name": "dermgpt",
        "md_file": "dermgpt-20260216-022503 (1).md",
        "out_csv": "dermgpt_pairs.csv",
    },
    {
        "name": "skin_analytics",
        "md_file": "derm-20260216-194019.md",
        "out_csv": "skin_analytics_pairs.csv",
    },
    {
        "name": "skinvision",
        "md_file": "skinvision_card.md",
        "out_csv": "skinvision_pairs.csv",
    },
]

INLINE_CITATION_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
URL_RE = re.compile(r"https?://[^\s\])>]+")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s;,\]]+\b", re.I)

def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def expand_citation_group(group: str) -> List[int]:
    nums = []
    for part in re.split(r"\s*,\s*", group.strip()):
        if "-" in part:
            a, b = [x.strip() for x in part.split("-", 1)]
            if a.isdigit() and b.isdigit():
                a, b = int(a), int(b)
                if a <= b:
                    nums.extend(range(a, b + 1))
        elif part.isdigit():
            nums.append(int(part))
    return nums

def strip_inline_citations(text: str) -> str:
    return clean_text(INLINE_CITATION_RE.sub("", text))

def is_reference_line(line: str) -> bool:
    return bool(re.match(r"^\[(\d+)\]\s+", line.strip()))

def extract_numbered_reference_map(md_text: str) -> Dict[int, str]:
    ref_map: Dict[int, str] = {}
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        m = re.match(r"^\[(\d+)\]\s+(.*)$", line)
        if not m:
            continue

        ref_num = int(m.group(1))
        rest = m.group(2).strip()

        # Angle-bracket URLs: <https://...>
        if rest.startswith("<http") and rest.endswith(">") and rest.count("<") == 1:
            rest = rest[1:-1].strip()

        # Critical: URL_RE stops at the first whitespace, which truncates legitimate URLs whose
        # path contains spaces (e.g. ".../PD1123_Digital Practice.pdf"). For standard
        # "[n] https://..." reference lines, use the full remainder of the line as the URL.
        if rest.startswith("http://") or rest.startswith("https://"):
            ref_map[ref_num] = rest
            continue

        url_match = URL_RE.search(rest)
        if url_match:
            ref_map[ref_num] = url_match.group(0)
            continue

        doi_match = DOI_RE.search(rest)
        if doi_match:
            ref_map[ref_num] = f"https://doi.org/{doi_match.group(0)}"

    return ref_map


def warn_unresolved_ref_numbers(md_text: str, ref_map: Dict[int, str], card_label: str) -> None:
    """
    Log citation indices used inline that never appear in the References map (typo / missing ref row).
    """
    unresolved: set[int] = set()
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line or is_reference_line(line):
            continue
        for m in INLINE_CITATION_RE.finditer(line):
            for n in expand_citation_group(m.group(1)):
                if n not in ref_map:
                    unresolved.add(n)
    if unresolved:
        nums = ", ".join(str(x) for x in sorted(unresolved))
        print(
            f"[WARN] {card_label}: inline citations reference [{nums}] but no matching "
            f"[n] URL line was parsed in References — those cites will not produce pairs."
        )


def split_sentences(text: str) -> List[str]:
    """
    Lightweight sentence splitter that preserves decimals reasonably well.
    """
    text = clean_text(text)
    if not text:
        return []

    # protect common abbreviations / decimals a bit
    protected = text
    protected = protected.replace("e.g.", "eg")
    protected = protected.replace("i.e.", "ie")
    protected = protected.replace("U.S.", "US")
    protected = re.sub(r"(\d)\.(\d)", r"\1<DECIMAL>\2", protected)

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"])|(?<=[.!?])\s+(?=-\s*\*\*)", protected)

    sentences = []
    for part in parts:
        part = part.replace("<DECIMAL>", ".")
        part = clean_text(part)
        if part:
            sentences.append(part)

    return sentences

def normalize_statement(line: str) -> str:
    line = line.strip()

    # remove bullet marker
    line = re.sub(r"^[-*•]\s*", "", line)

    # convert markdown bold labels into prose-ish text
    # "- **Model Name:** DermGPT" -> "Model Name: DermGPT"
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)

    # remove heading markers
    line = re.sub(r"^#+\s*", "", line)

    line = strip_inline_citations(line)
    line = clean_text(line)

    return line

def substantive_enough(text: str) -> bool:
    if not text:
        return False
    if len(text) < 25:
        return False
    if text.lower().startswith("resources"):
        return False
    if text.lower().startswith("references"):
        return False
    return True

def substantive_enough_cited_line(text: str) -> bool:
    """
    Short bullets (e.g. "Version: 3.0.2") are still valid if they carry explicit [n] cites.
    Keep a low floor and exclude section headers / reference spam.
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 3:
        return False
    tl = t.lower()
    if tl.startswith("resources"):
        return False
    if tl.startswith("references"):
        return False
    return True


def _field_label_prefix(line: str) -> str:
    """Return 'Label: ' prefix from a bold bullet, else empty."""
    m = re.match(r"^[-*•]\s*\*\*(.+?):\*\*\s*", line.strip())
    if m:
        return f"{m.group(1)}: "
    m = re.match(r"^[-*•]\s*([^:]{1,80}):\s*", line.strip())
    if m and not m.group(1).startswith("http"):
        return f"{m.group(1).strip()}: "
    return ""


def _cites_are_trailing_only(line: str, matches: List[re.Match]) -> bool:
    """True when every [n] on the line is in one contiguous cluster at EOL."""
    if not matches:
        return True
    rest = line[matches[0].start() :]
    return bool(re.fullmatch(r"(?:\s*\[\d+(?:\s*[-,]\s*\d+)*\])+\s*", rest))


def _body_start(line: str) -> int:
    label_m = re.match(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", line)
    if label_m:
        return label_m.end()
    label_m2 = re.match(r"^[-*•]\s*[^:]+:\s*", line)
    if label_m2:
        return label_m2.end()
    return 0


def _statement_for_citation_span(
    line: str, cite_match: re.Match, matches: List[re.Match]
) -> str:
    """
    Scope a citation to the claim text it supports.

    - Trailing-only cites (legacy field-level markup): full normalized line.
    - Mid-line cites: field label + text since the previous cite (or field body
      start) through this cite. Citations that follow a completed sentence stay
      attached to that sentence (period + cite), not an empty following span.
    """
    if _cites_are_trailing_only(line, matches):
        return normalize_statement(line)

    prefix = _field_label_prefix(line)
    body_start = _body_start(line)
    prev_end = body_start
    for m in matches:
        if m.end() <= cite_match.start():
            prev_end = m.end()
        else:
            break

    chunk = strip_inline_citations(line[prev_end : cite_match.end()]).lstrip(" ,;:")
    statement = clean_text(prefix + chunk)
    if not substantive_enough_cited_line(statement):
        return normalize_statement(line)
    return statement


def extract_inline_pairs(md_text: str, ref_map: Dict[int, str]) -> List[Tuple[str, str]]:
    """
    One row per (statement, url).

    - If all [n] cites on a line trail at the end: statement = full line (legacy).
    - If cites appear mid-line: statement = field label + text since prior cite.
    """
    pairs: List[Tuple[str, str]] = []

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line or is_reference_line(line):
            continue

        matches = list(INLINE_CITATION_RE.finditer(line))
        if not matches:
            continue

        for m in matches:
            for n in expand_citation_group(m.group(1)):
                url = ref_map.get(n)
                if not url:
                    continue
                statement = _statement_for_citation_span(line, m, matches)
                if not substantive_enough_cited_line(statement):
                    continue
                pairs.append((statement, url))

    return dedupe_pairs(pairs)

def extract_reference_section_text(md_text: str) -> str:
    patterns = [
        r"\n##\s*6\)\s*Resources\b",
        r"\n##\s*Resources\b",
        r"\n##\s*References\b",
        r"\n###\s*References\b",
        r"\n- \*\*Evaluation References, if available:\*\*",
    ]
    for pat in patterns:
        m = re.search(pat, md_text, flags=re.I)
        if m:
            return md_text[m.start():]
    return ""

def extract_urls_from_reference_section(md_text: str) -> List[str]:
    ref_section = extract_reference_section_text(md_text)
    if not ref_section:
        return []

    urls = URL_RE.findall(ref_section)
    doi_urls = [f"https://doi.org/{d}" for d in DOI_RE.findall(ref_section)]

    seen = set()
    out = []
    for u in urls + doi_urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def collect_candidate_content_lines(md_text: str) -> List[str]:
    """
    Collects many more claim-like lines from sections 1-5.
    """
    lines = md_text.splitlines()
    candidates = []
    in_content = False

    for raw_line in lines:
        line = raw_line.strip()

        if re.match(r"^##\s*[1-5]\)", line):
            in_content = True
            continue
        if re.match(r"^##\s*6\)", line) or re.match(r"^##\s*(Resources|References)\b", line, flags=re.I):
            in_content = False
            continue

        if not in_content:
            continue

        if not line or is_reference_line(line):
            continue

        # keep bullets and regular lines
        if line.startswith("-") or line.startswith("*") or re.match(r"^[A-Za-z(]", line):
            normalized = normalize_statement(line)
            if substantive_enough(normalized):
                candidates.append(normalized)

    return candidates

def fallback_pairs(md_text: str, urls: List[str]) -> List[Tuple[str, str]]:
    """
    When inline numeric citations are sparse/missing:
    - take many substantive lines from sections 1-5
    - split into sentences
    - pair each sentence with all reference URLs
    This is intentionally broad; you can trim later.
    """
    pairs: List[Tuple[str, str]] = []
    candidates = collect_candidate_content_lines(md_text)

    for block in candidates:
        sentences = split_sentences(block)
        if not sentences:
            sentences = [block]

        for sent in sentences:
            if not substantive_enough(sent):
                continue
            for url in urls:
                pairs.append((sent, url))

    return dedupe_pairs(pairs)

def dedupe_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    out = []
    for statement, url in pairs:
        key = (statement, url)
        if key not in seen:
            seen.add(key)
            out.append((statement, url))
    return out

def write_pairs_csv(pairs: List[Tuple[str, str]], out_csv: str) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["statement", "url"])
        for statement, url in pairs:
            writer.writerow([statement, url])

def process_one_card(name: str, md_file: str, out_csv: str, allow_fallback: bool = False) -> None:
    path = Path(md_file)
    if not path.exists():
        print(f"[SKIP] Missing markdown card: {md_file}")
        return

    md_text = path.read_text(encoding="utf-8")
    ref_map = extract_numbered_reference_map(md_text)
    warn_unresolved_ref_numbers(md_text, ref_map, name)
    inline_pairs = extract_inline_pairs(md_text, ref_map)

    if inline_pairs:
        write_pairs_csv(inline_pairs, out_csv)
        print(f"[OK] {name}: wrote {len(inline_pairs)} citation-line pairs (no sentence chunking) -> {out_csv}")
        return

    if allow_fallback:
        urls = extract_urls_from_reference_section(md_text)
        if urls:
            fb_pairs = fallback_pairs(md_text, urls)
            write_pairs_csv(fb_pairs, out_csv)
            print(f"[OK] {name}: no inline numeric citations; wrote {len(fb_pairs)} legacy fallback pairs -> {out_csv}")
            return

    write_pairs_csv([], out_csv)
    print(
        f"[WARN] {name}: no lines with inline [n] citations (or missing ref map). "
        f"Wrote empty pairs CSV (synthetic per-sentence × all-URLs fallback is disabled): {out_csv}"
    )


def safe_slug(filename: str) -> str:
    s = filename.strip()
    s = re.sub(r"\.md$", "", s, flags=re.I)
    s = re.sub(r"[^\w.-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "card"


def iter_top_level_md(md_dir: Path):
    """Only `*.md` directly under md_dir (avoids venv / nested junk)."""
    for p in sorted(md_dir.glob("*.md")):
        if p.is_file():
            yield p


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Extract (statement, url) pairs from CHAI cards: one statement per cited line, explicit [n] cites only unless --allow-fallback."
    )
    ap.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Legacy mode: if no inline [n] cites, pair sentences from sections 1–5 with every reference URL (not recommended).",
    )
    ap.add_argument(
        "--md-dir",
        type=str,
        default=None,
        help="Process every top-level *.md in this directory (recommended for “all cards”).",
    )
    ap.add_argument(
        "--md-files",
        nargs="+",
        default=None,
        help="Explicit markdown files to process (filenames or paths). Overrides --md-dir.",
    )
    ap.add_argument(
        "--md-list-file",
        type=str,
        default=None,
        help="Text file: one markdown path/filename per line (# comments allowed). Paths are relative to that file’s directory unless absolute.",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default=".",
        help="Directory for output *_pairs.csv files.",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.md_list_file:
        list_path = Path(args.md_list_file).expanduser().resolve()
        if not list_path.is_file():
            raise SystemExit(f"[ERROR] --md-list-file not found: {list_path}")
        root = list_path.parent
        md_files = []
        for line in list_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if not p.is_absolute():
                p = (root / line).resolve()
            md_files.append(p)
        if not md_files:
            raise SystemExit(f"[ERROR] No usable lines in {list_path}")
        for md_path in md_files:
            if not md_path.exists():
                print(f"[SKIP] Missing markdown card (not on disk): {md_path}")
                continue
            slug = safe_slug(md_path.name)
            out_csv = out_dir / f"{slug}_pairs.csv"
            print(f"[INFO] {md_path} -> {out_csv}")
            process_one_card(
                name=slug,
                md_file=str(md_path),
                out_csv=str(out_csv),
                allow_fallback=args.allow_fallback,
            )
    elif args.md_files:
        for raw in args.md_files:
            md_path = Path(raw).expanduser()
            if not md_path.is_absolute():
                md_path = (Path.cwd() / md_path).resolve()
            if not md_path.exists():
                print(f"[SKIP] Missing markdown card (not on disk): {md_path}")
                continue
            slug = safe_slug(md_path.name)
            out_csv = out_dir / f"{slug}_pairs.csv"
            print(f"[INFO] {md_path} -> {out_csv}")
            process_one_card(
                name=slug,
                md_file=str(md_path),
                out_csv=str(out_csv),
                allow_fallback=args.allow_fallback,
            )
    elif args.md_dir:
        md_dir = Path(args.md_dir).resolve()
        md_files = list(iter_top_level_md(md_dir))
        if not md_files:
            raise SystemExit(f"[ERROR] No top-level *.md files in {md_dir}")
        for md_path in md_files:
            slug = safe_slug(md_path.name)
            out_csv = out_dir / f"{slug}_pairs.csv"
            print(f"[INFO] {md_path.name} -> {out_csv}")
            process_one_card(
                name=slug,
                md_file=str(md_path),
                out_csv=str(out_csv),
                allow_fallback=args.allow_fallback,
            )
    else:
        for card in CARDS:
            out_csv = out_dir / card["out_csv"]
            process_one_card(
                name=card["name"],
                md_file=card["md_file"],
                out_csv=str(out_csv),
                allow_fallback=args.allow_fallback,
            )