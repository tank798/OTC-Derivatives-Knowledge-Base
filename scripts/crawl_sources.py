#!/usr/bin/env python3
"""Crawl official financial-regulation sources into local raw and index files.

The crawler is intentionally conservative:
- It starts from official registry seed URLs.
- It keeps raw HTML/PDF and extracted text.
- It records pages that fail or are not readable in gaps.jsonl.
- It does not treat search snippets or guessed URLs as evidence.
"""

import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW_HTML = ROOT / "data" / "raw" / "html"
RAW_PDF = ROOT / "data" / "raw" / "pdf"
RAW_TEXT = ROOT / "data" / "raw" / "text"
PROCESSED = ROOT / "data" / "processed"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
    "FinancialRegulationKnowledgeBase/0.1"
)

DATE_RE = re.compile(r"(20\d{2})[-年./](0?[1-9]|1[0-2])[-月./](0?[1-9]|[12]\d|3[01])")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
ARTICLE_URL_RE = re.compile(r"(content\.shtml|/content_\d+|/t\d{8}_\d+|\.html?$)", re.I)


class LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text_parts: List[str] = []
        self.text_parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "a":
            attr = dict(attrs)
            self._href = attr.get("href")
            self._text_parts = []
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._href:
            text = clean_space("".join(self._text_parts))
            self.links.append((self._href, text))
            self._href = None
            self._text_parts = []
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._href:
            self._text_parts.append(data)
        self.text_parts.append(data)


def clean_space(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ \u3000]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def url_id(source_id: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"{source_id}_{digest}"


def load_registry(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs() -> None:
    for path in (RAW_HTML, RAW_PDF, RAW_TEXT, PROCESSED):
        path.mkdir(parents=True, exist_ok=True)


def request_url(url: str, timeout: int = 30) -> Tuple[bytes, str]:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        return resp.read(), content_type


def decode_html(data: bytes, content_type: str = "") -> str:
    candidates = []
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        candidates.append(match.group(1))
    candidates.extend(["utf-8", "gb18030", "gbk"])
    for enc in candidates:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def parse_html(raw_html: str, base_url: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    parser = LinkTextParser()
    parser.feed(raw_html)
    text = clean_space("\n".join(parser.text_parts))
    links = []
    for href, anchor in parser.links:
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        links.append((urljoin(base_url, href), anchor))
    title_match = TITLE_RE.search(raw_html)
    title = clean_space(title_match.group(1)) if title_match else ""
    if not title:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        title = first_line[:120]
    return title, text, links


def extract_date(text: str) -> Optional[str]:
    match = DATE_RE.search(text)
    if not match:
        return None
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def domain_allowed(url: str, allowed_domains: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed_domains)


def keyword_match(text: str, keywords: Iterable[str]) -> bool:
    if not keywords:
        return True
    return any(k and k in text for k in keywords)


def looks_like_document_url(url: str, anchor: str, keywords: Iterable[str]) -> bool:
    if url.lower().endswith(".pdf"):
        return True
    combined = f"{anchor} {url}"
    if keyword_match(combined, keywords):
        return True
    if not keywords and ARTICLE_URL_RE.search(url):
        return True
    return False


def append_jsonl(path: Path, row: Dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_seen_docs(path: Path) -> set:
    seen = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                seen.add(json.loads(line)["url"])
            except Exception:
                continue
    return seen


def save_page(source: Dict, url: str, data: bytes, content_type: str, title_hint: str = "") -> Dict:
    source_id = source["source_id"]
    doc_id = url_id(source_id, url)
    checksum = sha256_bytes(data)
    retrieved_at = now_iso()
    is_pdf = url.lower().endswith(".pdf") or "pdf" in content_type.lower()

    if is_pdf:
        raw_dir = RAW_PDF / source_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{doc_id}.pdf"
        raw_path.write_bytes(data)
        title = title_hint or Path(urlparse(url).path).name
        text = ""
        body_read = False
        text_path = None
    else:
        raw_dir = RAW_HTML / source_id
        text_dir = RAW_TEXT / source_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{doc_id}.html"
        raw_path.write_bytes(data)
        raw_html = decode_html(data, content_type)
        title, text, _ = parse_html(raw_html, url)
        title = title_hint or title
        text_path_obj = text_dir / f"{doc_id}.txt"
        text_path_obj.write_text(text, encoding="utf-8")
        text_path = str(text_path_obj.relative_to(ROOT))
        body_read = bool(text and len(text) > 120)

    row = {
        "doc_id": doc_id,
        "source_id": source_id,
        "publisher": source.get("publisher"),
        "authority_level": source.get("authority_level", "unknown"),
        "title": title,
        "url": url,
        "retrieved_at": retrieved_at,
        "published_at": extract_date(text if not is_pdf else title),
        "effective_at": None,
        "status": "unknown",
        "asset_classes": source.get("asset_classes", []),
        "product_types": source.get("product_types", []),
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)),
        "text_path": text_path,
        "checksum": checksum,
        "content_type": content_type,
    }
    return row


def crawl_source(source: Dict, max_per_source: int, delay: float, fetch_details: bool) -> Tuple[int, int]:
    source_id = source["source_id"]
    allowed = source.get("allowed_domains", [])
    keywords = source.get("include_keywords", [])
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    seen = load_seen_docs(documents_path)

    candidate_urls: List[Tuple[str, str]] = [(u, "") for u in source.get("seed_urls", [])]
    discovered: List[Tuple[str, str]] = []
    saved_count = 0
    gap_count = 0

    for seed_url, _ in candidate_urls:
        try:
            data, content_type = request_url(seed_url)
            seed_doc = save_page(source, seed_url, data, content_type, "")
            if seed_url not in seen:
                append_jsonl(documents_path, seed_doc)
                seen.add(seed_url)
                saved_count += 1
            if "pdf" not in content_type.lower() and not seed_url.lower().endswith(".pdf"):
                raw_html = decode_html(data, content_type)
                _, _, links = parse_html(raw_html, seed_url)
                for link, anchor in links:
                    if not domain_allowed(link, allowed):
                        continue
                    combined = f"{anchor} {link}"
                    if looks_like_document_url(link, anchor, keywords) or keyword_match(combined, keywords):
                        discovered.append((link, anchor))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            gap_count += 1
            append_jsonl(gaps_path, {
                "source_id": source_id,
                "url": seed_url,
                "retrieved_at": now_iso(),
                "gap_type": "seed_fetch_failed",
                "reason": repr(exc),
                "body_read": False,
            })
        time.sleep(delay)

    if not fetch_details:
        return saved_count, gap_count

    seen_candidates = set()
    for url, anchor in discovered:
        if url in seen_candidates or url in seen:
            continue
        seen_candidates.add(url)
        if saved_count >= max_per_source:
            break
        try:
            data, content_type = request_url(url)
            row = save_page(source, url, data, content_type, anchor)
            append_jsonl(documents_path, row)
            seen.add(url)
            saved_count += 1
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            gap_count += 1
            append_jsonl(gaps_path, {
                "source_id": source_id,
                "url": url,
                "title_hint": anchor,
                "retrieved_at": now_iso(),
                "gap_type": "document_fetch_failed",
                "reason": repr(exc),
                "body_read": False,
            })
        time.sleep(delay)

    return saved_count, gap_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=str(ROOT / "data" / "registry" / "sources.json"))
    parser.add_argument("--source", action="append", help="Limit to one or more source_id values.")
    parser.add_argument("--max-per-source", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--no-fetch-details", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    registry = load_registry(Path(args.registry))
    selected = set(args.source or [])
    sources = registry.get("sources", [])
    if selected:
        sources = [s for s in sources if s.get("source_id") in selected]

    summary = []
    for source in sources:
        saved, gaps = crawl_source(
            source,
            max_per_source=args.max_per_source,
            delay=args.delay,
            fetch_details=not args.no_fetch_details,
        )
        summary.append({"source_id": source["source_id"], "saved": saved, "gaps": gaps})
        print(f"{source['source_id']}: saved={saved} gaps={gaps}", flush=True)

    (PROCESSED / "crawl_summary.json").write_text(
        json.dumps({"finished_at": now_iso(), "summary": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
