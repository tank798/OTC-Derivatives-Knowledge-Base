#!/usr/bin/env python3
"""Crawl Shanghai Stock Exchange 2025 business-rule pages."""

import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_HTML = ROOT / "data" / "raw" / "html" / "sse_rules"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "sse_rules"
RAW_FILES = ROOT / "data" / "raw" / "files" / "sse_rules"
BASE = "https://www.sse.com.cn"
TABLEMAP = f"{BASE}/xhtml/js/sselawsrules_tablemap.js"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
    "FinancialRegulationKnowledgeBase/0.1"
)
DATE_RE = re.compile(r"(20\d{2})[-年./](0?[1-9]|1[0-2])[-月./](3[01]|[12]\d|0?[1-9])")


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.links: List[Tuple[str, str]] = []
        self.skip = 0
        self._href: Optional[str] = None
        self._anchor: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
            return
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor = []
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "span"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
            return
        if tag == "a" and self._href:
            self.links.append((self._href, clean_space("".join(self._anchor))))
            self._href = None
            self._anchor = []
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "span"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self._href:
            self._anchor.append(data)
        self.parts.append(data)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_space(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ \u3000]+", " ", value)
    value = re.sub(r"\n[ \u3000]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe="/%:@"),
        quote(parts.query, safe="=&%:/?+@,;"),
        quote(parts.fragment, safe="=&%:/?+@,;"),
    ))


def get_bytes(url: str, timeout: int = 20) -> Tuple[bytes, str]:
    normalized = normalize_url(url)
    result = subprocess.run(
        [
            "curl",
            "-sL",
            "--fail",
            "--connect-timeout",
            "10",
            "--max-time",
            str(timeout),
            "-A",
            USER_AGENT,
            "-H",
            f"Referer: {BASE}/lawandrules/sselawsrules2025/overview/",
            normalized,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 5,
    )
    return result.stdout, ""


def decode_html(data: bytes, content_type: str = "") -> str:
    candidates = []
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        candidates.append(match.group(1))
    candidates.extend(["utf-8", "gb18030", "gbk"])
    for enc in candidates:
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def gap_key(row: Dict) -> Tuple:
    return (row.get("source_id"), row.get("doc_id"), row.get("url"), row.get("gap_type"))


def extract_categories(js: str) -> List[Dict]:
    rows: List[Dict] = []
    seen = set()
    for match in re.finditer(r"name:\s*'([^']+)'\s*,\s*\n\s*link:\s*'([^']+)'", js):
        name, link = match.groups()
        if link in seen:
            continue
        seen.add(link)
        rows.append({"name": clean_space(name), "url": urljoin(BASE, link)})
    return rows


def parse_source_html(raw_html: str) -> List[Dict]:
    match = re.search(r'<div id="sourceHtml"[^>]*>(.*?)</div>', raw_html, re.S | re.I)
    if not match:
        return []
    source = html.unescape(match.group(1))
    records = []
    for block in source.split("@doc@"):
        fields = [clean_space(field) for field in block.split("@memo@")]
        fields = [field for field in fields if field]
        if len(fields) >= 4:
            records.append({
                "rule_type": fields[0],
                "published_at": normalize_date(fields[1]),
                "url": urljoin(BASE, fields[2].removeprefix("/sse")),
                "title": fields[3],
            })
    return records


def normalize_date(value: str) -> Optional[str]:
    match = DATE_RE.search(value or "")
    if not match:
        return value or None
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def extract_article(raw_html: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    meta: Dict[str, str] = {}
    intro = re.search(r'<div class="article_intro">(.*?)</div>', raw_html, re.S | re.I)
    if intro:
        for label, value in re.findall(r"<em>(.*?)</em>\s*([^<]+)", intro.group(1), re.S):
            meta[clean_space(label)] = clean_space(value)

    start = raw_html.find('<div class="article-infor')
    end = raw_html.find('<div class="js_prenext_navigation', start)
    if start >= 0 and end > start:
        article_html = raw_html[start:end]
    else:
        article_html = raw_html
    parser = TextParser()
    parser.feed(article_html)
    return clean_space("\n".join(parser.parts)), parser.links, meta


def download_attachments(doc_url: str, links: List[Tuple[str, str]], doc_id: str) -> List[Dict]:
    RAW_FILES.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, (href, title) in enumerate(links, start=1):
        if not href or href.startswith("#"):
            continue
        if not href.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            continue
        url = urljoin(doc_url, href)
        suffix = Path(urlsplit(url).path).suffix or ".bin"
        local_path = RAW_FILES / f"{doc_id}_att{idx:02d}{suffix}"
        downloaded = False
        error = ""
        try:
            data, _ = get_bytes(url)
            if data and b"<html" not in data[:200].lower():
                local_path.write_bytes(data)
                downloaded = True
        except Exception as exc:
            error = repr(exc)
        rows.append({
            "url": url,
            "title": title or Path(urlsplit(url).path).name,
            "local_path": str(local_path.relative_to(ROOT)) if downloaded else None,
            "downloaded": downloaded,
            "download_error": error,
        })
    return rows


def infer_product_types(category: str, title: str) -> List[str]:
    text = f"{category} {title}"
    products = set()
    if any(k in text for k in ["债券", "回购", "信用保护", "CDX"]):
        products.update(["bond", "repo", "cds", "credit_derivative"])
    if any(k in text for k in ["基金", "ETF", "REIT"]):
        products.update(["public_fund", "etf", "reit"])
    if "期权" in text:
        products.add("listed_option")
    if any(k in text for k in ["融资融券", "转融通", "质押式"]):
        products.update(["margin_financing_securities_lending", "stock_pledge_repo"])
    if not products:
        products.update(["equity_trading", "exchange_rule"])
    return sorted(products)


def build_document(record: Dict, category: Dict, min_chars: int, download_files: bool) -> Tuple[Dict, List[Dict]]:
    url = record["url"]
    doc_id = f"sse_rules_{sha1(url)}"
    RAW_HTML.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_HTML / f"{doc_id}.html"
    text_path_obj = RAW_TEXT / f"{doc_id}.txt"
    gaps: List[Dict] = []
    text = ""
    links: List[Tuple[str, str]] = []
    meta: Dict[str, str] = {}
    content_type = ""

    try:
        data, content_type = get_bytes(url)
        raw_path.write_bytes(data)
        raw_html = decode_html(data, content_type)
        text, links, meta = extract_article(raw_html)
        if text:
            text_path_obj.write_text(text, encoding="utf-8")
    except Exception as exc:
        gaps.append({
            "source_id": "sse",
            "doc_id": doc_id,
            "url": url,
            "retrieved_at": now_iso(),
            "gap_type": "sse_rule_detail_fetch_failed",
            "reason": repr(exc),
            "body_read": False,
        })

    attachment_rows = download_attachments(url, links, doc_id) if download_files else []
    body_read = len(text) >= min_chars
    if text and not body_read:
        gaps.append({
            "source_id": "sse",
            "doc_id": doc_id,
            "url": url,
            "retrieved_at": now_iso(),
            "gap_type": "sse_rule_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })

    published_at = normalize_date(meta.get("发布日期") or record.get("published_at") or "")
    effective_at = normalize_date(meta.get("生效日期") or "")
    title = clean_space(record.get("title") or meta.get("标题") or "")
    category_name = category.get("name") or ""
    row = {
        "doc_id": doc_id,
        "source_id": "sse",
        "publisher": "上海证券交易所",
        "authority_level": "exchange_rule",
        "title": title,
        "url": url,
        "retrieved_at": now_iso(),
        "published_at": published_at,
        "effective_at": effective_at,
        "status": meta.get("时效性") or "unknown",
        "asset_classes": ["equity", "fixed_income", "fund", "cross_asset"],
        "product_types": infer_product_types(category_name, title),
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)) if raw_path.exists() else None,
        "text_path": str(text_path_obj.relative_to(ROOT)) if text_path_obj.exists() else None,
        "checksum": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.exists() else None,
        "content_type": content_type or "text/html",
        "sse_category": category_name,
        "sse_category_url": category.get("url"),
        "rule_type": record.get("rule_type") or meta.get("规则层级"),
        "document_no": meta.get("发文文号"),
        "rule_category": meta.get("规则类别"),
        "attachment_links": attachment_rows,
    }
    return row, gaps


def build_list_only_document(record: Dict, category: Dict) -> Dict:
    url = record["url"]
    title = clean_space(record.get("title") or "")
    category_name = category.get("name") or ""
    return {
        "doc_id": f"sse_rules_{sha1(url)}",
        "source_id": "sse",
        "publisher": "上海证券交易所",
        "authority_level": "exchange_rule",
        "title": title,
        "url": url,
        "retrieved_at": now_iso(),
        "published_at": normalize_date(record.get("published_at") or ""),
        "effective_at": None,
        "status": "repealed_or_historical" if "废止" in category_name else "unknown",
        "asset_classes": ["equity", "fixed_income", "fund", "cross_asset"],
        "product_types": infer_product_types(category_name, title),
        "body_read": False,
        "raw_path": None,
        "text_path": None,
        "checksum": None,
        "content_type": "list_metadata",
        "sse_category": category_name,
        "sse_category_url": category.get("url"),
        "rule_type": record.get("rule_type"),
        "document_no": None,
        "rule_category": None,
        "attachment_links": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category-url", action="append", help="Limit to specific SSE category URL.")
    parser.add_argument("--max-categories", type=int, default=0)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--no-download-attachments", action="store_true")
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    js_bytes, _ = get_bytes(TABLEMAP)
    categories = extract_categories(decode_html(js_bytes))
    if args.category_url:
        wanted = {urljoin(BASE, u) for u in args.category_url}
        categories = [row for row in categories if row["url"] in wanted]
    if args.max_categories and args.max_categories > 0:
        categories = categories[:args.max_categories]

    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    saved_docs = 0
    saved_gaps = 0
    for category in categories:
        try:
            data, content_type = get_bytes(category["url"])
            raw_html = decode_html(data, content_type)
            records = parse_source_html(raw_html)
            print(f"category={category['name']} records={len(records)}", flush=True)
        except Exception as exc:
            row = {
                "source_id": "sse",
                "url": category["url"],
                "retrieved_at": now_iso(),
                "gap_type": "sse_rule_category_fetch_failed",
                "reason": repr(exc),
                "body_read": False,
            }
            if gap_key(row) not in gap_keys:
                gaps.append(row)
                gap_keys.add(gap_key(row))
                saved_gaps += 1
            continue

        for record in records:
            if category.get("name") == "已废止规则文本":
                row = build_list_only_document(record, category)
                documents[row["doc_id"]] = row
                saved_docs += 1
                continue
            download_attachments_for_row = not args.no_download_attachments and "废止" not in (category.get("name") or "")
            row, row_gaps = build_document(record, category, args.min_chars, download_attachments_for_row)
            documents[row["doc_id"]] = row
            saved_docs += 1
            for gap in row_gaps:
                if gap_key(gap) not in gap_keys:
                    gaps.append(gap)
                    gap_keys.add(gap_key(gap))
                    saved_gaps += 1
            time.sleep(args.delay)
        write_jsonl(documents_path, documents.values())
        write_jsonl(gaps_path, gaps)
        time.sleep(args.delay)

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"saved_docs={saved_docs} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
