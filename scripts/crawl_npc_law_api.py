#!/usr/bin/env python3
"""Crawl core upper-level laws from the National Laws and Regulations Database."""

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
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import URLError
from zipfile import ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_JSON = ROOT / "data" / "raw" / "html" / "npc_law_db"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "npc_law_db"
RAW_FILES = ROOT / "data" / "raw" / "files" / "npc_law_db"
BASE = "https://flk.npc.gov.cn"

DEFAULT_LAWS = [
    "期货和衍生品法",
    "证券法",
    "证券投资基金法",
    "信托法",
    "反洗钱法",
    "数据安全法",
    "个人信息保护法",
    "网络安全法",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
    "FinancialRegulationKnowledgeBase/0.1"
)


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
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


def strip_tags(value: str) -> str:
    parser = TextParser()
    parser.feed(value or "")
    return clean_space("\n".join(parser.parts) or re.sub(r"<[^>]+>", "", value or ""))


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe="/%:@"),
        quote(parts.query, safe="=&%:/?+@,;"),
        quote(parts.fragment, safe="=&%:/?+@,;"),
    ))


def get_bytes(url: str, timeout: int = 60) -> Tuple[bytes, str]:
    req = Request(
        normalize_url(url),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Referer": f"{BASE}/",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except URLError as exc:
        result = subprocess.run(
            ["curl", "-sL", "-A", USER_AGENT, "-H", f"Referer: {BASE}/", normalize_url(url)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if result.stdout:
            return result.stdout, ""
        raise exc


def post_json(path: str, payload: Dict, timeout: int = 60) -> Dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        urljoin(BASE, path),
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE,
            "Referer": f"{BASE}/",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError:
        result = subprocess.run(
            [
                "curl",
                "-sL",
                "-H",
                "Content-Type: application/json;charset=UTF-8",
                "-H",
                f"Origin: {BASE}",
                "-H",
                f"Referer: {BASE}/",
                "-d",
                json.dumps(payload, ensure_ascii=False),
                urljoin(BASE, path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return json.loads(result.stdout.decode("utf-8"))


def get_json(path: str, params: Dict[str, str], timeout: int = 60) -> Dict:
    url = urljoin(BASE, path) + "?" + urlencode(params)
    data, _ = get_bytes(url, timeout=timeout)
    return json.loads(data.decode("utf-8"))


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


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def doc_id_for(bbbs: str) -> str:
    digest = hashlib.sha1(bbbs.encode("utf-8")).hexdigest()[:12]
    return f"npc_law_db_{digest}"


def search_law(query: str, page_size: int) -> Dict:
    payload = {
        "searchRange": 1,
        "sxrq": [],
        "gbrq": [],
        "searchType": 2,
        "sxx": [],
        "gbrqYear": [],
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "searchContent": query,
        "orderByParam": {"order": "-1", "sort": ""},
        "pageNum": 1,
        "pageSize": page_size,
    }
    return post_json("/law-search/search/list", payload)


def choose_best(rows: List[Dict], query: str) -> Optional[Dict]:
    expected = f"中华人民共和国{query}"
    compact_query = re.sub(r"\s+", "", query)
    compact_expected = re.sub(r"\s+", "", expected)
    cleaned = []
    for row in rows:
        item = dict(row)
        item["clean_title"] = strip_tags(row.get("title", ""))
        item["compact_title"] = re.sub(r"\s+", "", item["clean_title"])
        cleaned.append(item)

    def score(row: Dict) -> Tuple[int, str]:
        title = row.get("compact_title") or ""
        active = 2 if str(row.get("sxx")) == "3" else 0
        exact = 5 if title == compact_expected else 0
        contains = 2 if compact_query in title else 0
        law_level = 2 if row.get("flxz") == "法律" else 0
        return (exact + contains + active + law_level, row.get("gbrq") or "")

    candidates = [row for row in cleaned if compact_query in (row.get("compact_title") or "")]
    if not candidates:
        candidates = cleaned
    return max(candidates, key=score) if candidates else None


def fetch_detail(bbbs: str) -> Dict:
    return get_json("/law-search/search/flfgDetails", {"bbbs": bbbs})


def download_file_url(bbbs: str, fmt: str, file_id: str = "") -> Optional[str]:
    payload = get_json("/law-search/download/pc", {"bbbs": bbbs, "format": fmt, "fileId": file_id})
    data = payload.get("data") or {}
    return data.get("url") or data.get("urlIn")


def extract_docx_text(path: Path) -> str:
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        if len(clean_space(text)) > 100:
            return clean_space(text)
    except Exception:
        pass

    try:
        with ZipFile(path) as zf:
            xml_data = zf.read("word/document.xml")
        root = ET.fromstring(xml_data)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paras = []
        for para in root.findall(".//w:p", ns):
            parts = [node.text or "" for node in para.findall(".//w:t", ns)]
            if parts:
                paras.append("".join(parts))
        return clean_space("\n".join(paras))
    except Exception:
        return ""


def title_tree_text(node: Optional[Dict], depth: int = 0) -> List[str]:
    if not node:
        return []
    title = node.get("title") or ""
    lines = [("  " * depth) + title] if title else []
    for child in node.get("children") or []:
        lines.extend(title_tree_text(child, depth + 1))
    return lines


def authority_level(flfg: str) -> str:
    if flfg == "法律":
        return "law"
    if flfg == "行政法规":
        return "administrative_regulation"
    if flfg:
        return "upper_level_rule"
    return "law"


def build_document(query: str, search_row: Dict, detail_payload: Dict, min_chars: int, download: bool) -> Tuple[Dict, List[Dict]]:
    data = detail_payload.get("data") or {}
    bbbs = data.get("bbbs") or search_row.get("bbbs")
    doc_id = doc_id_for(bbbs)
    gaps: List[Dict] = []

    RAW_JSON.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    RAW_FILES.mkdir(parents=True, exist_ok=True)
    detail_path = RAW_JSON / f"{doc_id}.json"
    detail_path.write_text(json.dumps(detail_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    file_path = None
    checksum = None
    text = ""
    if download:
        try:
            signed_url = download_file_url(bbbs, "docx")
            if signed_url:
                data_bytes, _ = get_bytes(signed_url, timeout=90)
                file_path_obj = RAW_FILES / f"{doc_id}.docx"
                file_path_obj.write_bytes(data_bytes)
                file_path = str(file_path_obj.relative_to(ROOT))
                checksum = sha256_file(file_path_obj)
                text = extract_docx_text(file_path_obj)
        except Exception as exc:
            gaps.append({
                "source_id": "npc_law_db",
                "doc_id": doc_id,
                "url": f"{BASE}/detail?id={bbbs}",
                "retrieved_at": now_iso(),
                "gap_type": "npc_law_download_failed",
                "reason": repr(exc),
                "body_read": False,
            })

    if len(text) < min_chars:
        text = clean_space("\n".join(title_tree_text(data.get("content"))))

    text_path = None
    body_read = len(text) >= min_chars
    if text:
        text_path_obj = RAW_TEXT / f"{doc_id}.txt"
        text_path_obj.write_text(text, encoding="utf-8")
        text_path = str(text_path_obj.relative_to(ROOT))

    if not body_read:
        gaps.append({
            "source_id": "npc_law_db",
            "doc_id": doc_id,
            "url": f"{BASE}/detail?id={bbbs}",
            "retrieved_at": now_iso(),
            "gap_type": "npc_law_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })

    title = clean_space(data.get("title") or search_row.get("clean_title") or strip_tags(search_row.get("title", "")) or query)
    row = {
        "doc_id": doc_id,
        "source_id": "npc_law_db",
        "publisher": data.get("zdjgName") or search_row.get("zdjgName") or "国家法律法规数据库",
        "authority_level": authority_level(data.get("flxz") or search_row.get("flxz") or "法律"),
        "title": title,
        "url": f"{BASE}/detail?id={bbbs}",
        "api_url": f"{BASE}/law-search/search/flfgDetails?bbbs={bbbs}",
        "retrieved_at": now_iso(),
        "published_at": data.get("gbrq") or search_row.get("gbrq"),
        "effective_at": data.get("sxrq") or search_row.get("sxrq"),
        "status": "current" if str(data.get("sxx") or search_row.get("sxx")) == "3" else "unknown",
        "asset_classes": ["equity", "fixed_income", "fund", "fx", "commodity", "cross_asset"],
        "product_types": ["otc_derivative", "futures", "asset_management_plan", "private_fund", "public_fund", "trust_plan"],
        "body_read": body_read,
        "raw_path": str(detail_path.relative_to(ROOT)),
        "text_path": text_path,
        "checksum": checksum,
        "content_type": "json_detail_docx",
        "npc_bbbs": bbbs,
        "npc_flxz": data.get("flxz") or search_row.get("flxz"),
        "npc_oss_file": data.get("ossFile"),
        "docx_file_path": file_path,
    }
    return row, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--law", action="append", help="Law keyword to crawl. Defaults to core financial upper-level laws.")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    laws = args.law or DEFAULT_LAWS
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    saved_docs = 0
    saved_gaps = 0
    for query in laws:
        try:
            search_payload = search_law(query, args.page_size)
            rows = search_payload.get("rows") or []
            best = choose_best(rows, query)
            if not best or not best.get("bbbs"):
                raise RuntimeError(f"No matching FLK row for {query}")
            detail_payload = fetch_detail(best["bbbs"])
            row, row_gaps = build_document(best["clean_title"], best, detail_payload, args.min_chars, not args.no_download)
            documents[row["doc_id"]] = row
            saved_docs += 1
            print(f"law={query} title={row['title']} body_read={row['body_read']}", flush=True)
            for gap in row_gaps:
                if gap_key(gap) not in gap_keys:
                    gaps.append(gap)
                    gap_keys.add(gap_key(gap))
                    saved_gaps += 1
        except Exception as exc:
            row = {
                "source_id": "npc_law_db",
                "url": f"{BASE}/?searchContent={quote(query)}",
                "retrieved_at": now_iso(),
                "gap_type": "npc_law_crawl_failed",
                "reason": repr(exc),
                "body_read": False,
            }
            if gap_key(row) not in gap_keys:
                gaps.append(row)
                gap_keys.add(gap_key(row))
                saved_gaps += 1
            print(f"law={query} failed={exc!r}", flush=True)
        time.sleep(args.delay)

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"saved_docs={saved_docs} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
