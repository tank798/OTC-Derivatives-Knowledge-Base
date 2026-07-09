#!/usr/bin/env python3
"""Crawl NFRA policy-rule documents through the official JSON API."""

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
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_JSON = ROOT / "data" / "raw" / "html" / "nfra_api"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "nfra_api"
RAW_FILES = ROOT / "data" / "raw" / "files" / "nfra"
BASE = "https://www.nfra.gov.cn"
API = f"{BASE}/cbircweb"

DEFAULT_PARENT_ITEMS = {
    "926": "政策法规",
    "950": "征集调查/征求意见",
}

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
        if tag in {"script", "style", "noscript", "xml"}:
            self.skip += 1
            return
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "xml"} and self.skip:
            self.skip -= 1
            return
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


def html_to_text(raw_html: str) -> str:
    parser = TextParser()
    parser.feed(raw_html or "")
    return clean_space("\n".join(parser.parts))


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe="/%:@"),
        quote(parts.query, safe="=&%:/?+@,;"),
        quote(parts.fragment, safe="=&%:/?+@,;"),
    ))


def get_bytes(url: str, timeout: int = 45) -> Tuple[bytes, str]:
    normalized = normalize_url(url)
    req = Request(
        normalized,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,application/pdf,application/msword,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Referer": f"{BASE}/cn/view/pages/index/index.html",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except URLError as exc:
        if "nfra.gov.cn" not in normalized:
            raise
        result = subprocess.run(
            [
                "curl",
                "-sL",
                "--fail",
                "-A",
                USER_AGENT,
                "-H",
                "Accept-Language: zh-CN,zh;q=0.9,en;q=0.5",
                "-H",
                f"Referer: {BASE}/cn/view/pages/index/index.html",
                normalized,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if result.stdout:
            return result.stdout, ""
        raise exc


def get_json(url: str) -> Dict:
    data, _ = get_bytes(url)
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


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"(20\d{2})[-/年.](0?[1-9]|1[0-2])[-/月.](3[01]|[12]\d|0?[1-9])", value)
    if not match:
        return value[:10] if len(value) >= 10 else value
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def detail_url(doc_id: str, item_id: str) -> str:
    return f"{BASE}/cn/view/pages/ItemDetail.html?docId={doc_id}&itemId={item_id}"


def infer_authority(item_name: str, title: str) -> str:
    if "征求意见" in item_name or "征求意见" in title:
        return "draft_rule"
    if "法律法规" in item_name:
        return "law_or_administrative_regulation"
    if "规章" in item_name or "规范性文件" in item_name or "办法" in title or "规定" in title:
        return "regulator_rule"
    return "regulator_notice"


def infer_status(item_name: str, title: str) -> str:
    if "征求意见" in item_name or "征求意见" in title:
        return "draft"
    if "废止" in title:
        return "repealed_or_cleanup"
    return "unknown"


def download_file(url: Optional[str], doc_id: str, suffix: str) -> Tuple[Optional[str], Optional[str], str]:
    if not url:
        return None, None, ""
    RAW_FILES.mkdir(parents=True, exist_ok=True)
    final_url = urljoin(BASE, url)
    path = RAW_FILES / f"{doc_id}{suffix}"
    try:
        data, _ = get_bytes(final_url)
        if data:
            path.write_bytes(data)
            return str(path.relative_to(ROOT)), sha256_file(path), ""
    except Exception as exc:
        return None, None, repr(exc)
    return None, None, "empty_response"


def extract_with_textutil(path: Path) -> str:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8", errors="replace")


def extract_from_downloaded_doc(path: Optional[str]) -> str:
    if not path:
        return ""
    full_path = ROOT / path
    if not full_path.exists():
        return ""
    if full_path.suffix.lower() not in {".doc", ".docx", ".rtf"}:
        return ""
    try:
        return clean_space(extract_with_textutil(full_path))
    except Exception:
        return ""


def fetch_parent_item(parent_id: str, page_size: int, page_index: int) -> List[Dict]:
    local_path = RAW_JSON / f"parent_{parent_id}.json"
    if local_path.exists():
        payload = json.loads(local_path.read_text(encoding="utf-8"))
        if payload.get("rptCode") == 200:
            return payload.get("data") or []
    url = (
        f"{API}/DocInfo/SelectItemAndDocByItemPId?"
        f"itemId={parent_id}&pageSize={page_size}&pageIndex={page_index}"
    )
    payload = get_json(url)
    if payload.get("rptCode") != 200:
        raise RuntimeError(f"NFRA parent item request failed: {payload}")
    return payload.get("data") or []


def fetch_detail(doc_id: str) -> Dict:
    local_path = RAW_JSON / f"nfra_{doc_id}.json"
    if local_path.exists():
        payload = json.loads(local_path.read_text(encoding="utf-8"))
        if payload.get("rptCode") == 200:
            return payload.get("data") or {}
        if payload.get("docId"):
            return payload
    payload = get_json(f"{API}/DocInfo/SelectByDocId?docId={doc_id}")
    if payload.get("rptCode") != 200:
        raise RuntimeError(f"NFRA detail request failed for {doc_id}: {payload}")
    return payload.get("data") or {}


def item_path(detail: Dict) -> List[str]:
    paths: List[str] = []
    for item in detail.get("listTwoItem") or []:
        names = [node.get("itemName") for node in item.get("ItemLvs") or [] if node.get("itemName")]
        if names:
            paths.append(" / ".join(names))
    return paths


def build_document(
    list_doc: Dict,
    item: Dict,
    parent_id: str,
    min_chars: int,
    download_assets: bool,
) -> Tuple[Dict, List[Dict]]:
    doc_id_raw = str(list_doc.get("docId"))
    item_id = str(item.get("itemId") or parent_id)
    doc_id = f"nfra_{doc_id_raw}"
    item_name = item.get("itemName") or DEFAULT_PARENT_ITEMS.get(parent_id, parent_id)
    gaps: List[Dict] = []

    detail = {}
    raw_detail_path = RAW_JSON / f"{doc_id}.json"
    try:
        detail = fetch_detail(doc_id_raw)
        RAW_JSON.mkdir(parents=True, exist_ok=True)
        raw_detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        gaps.append({
            "source_id": "nfra",
            "doc_id": doc_id,
            "url": detail_url(doc_id_raw, item_id),
            "retrieved_at": now_iso(),
            "gap_type": "nfra_detail_fetch_failed",
            "reason": repr(exc),
            "body_read": False,
        })

    title = clean_space(detail.get("docSubtitle") or detail.get("docTitle") or list_doc.get("docSubtitle") or list_doc.get("docTitle") or "")
    doc_html = detail.get("docClob") or ""
    text = html_to_text(doc_html)

    doc_path = None
    pdf_path = None
    doc_checksum = None
    pdf_checksum = None
    doc_error = ""
    pdf_error = ""
    if download_assets:
        doc_file_url = list_doc.get("docFileUrl") or detail.get("docFileUrl")
        pdf_file_url = list_doc.get("pdfFileUrl") or detail.get("pdfFileUrl")
        doc_path, doc_checksum, doc_error = download_file(doc_file_url, doc_id, ".doc")
        pdf_path, pdf_checksum, pdf_error = download_file(pdf_file_url, doc_id, ".pdf")
        if len(text) < min_chars:
            downloaded_text = extract_from_downloaded_doc(doc_path)
            if len(downloaded_text) > len(text):
                text = downloaded_text
        for kind, error, file_url in (("doc", doc_error, doc_file_url), ("pdf", pdf_error, pdf_file_url)):
            if error and file_url:
                gaps.append({
                    "source_id": "nfra",
                    "doc_id": doc_id,
                    "url": urljoin(BASE, file_url),
                    "retrieved_at": now_iso(),
                    "gap_type": f"nfra_{kind}_download_failed",
                    "reason": error,
                    "body_read": False,
                })

    text_path = None
    body_read = len(text) >= min_chars
    if text:
        RAW_TEXT.mkdir(parents=True, exist_ok=True)
        text_path_obj = RAW_TEXT / f"{doc_id}.txt"
        text_path_obj.write_text(text, encoding="utf-8")
        text_path = str(text_path_obj.relative_to(ROOT))
    if not body_read:
        gaps.append({
            "source_id": "nfra",
            "doc_id": doc_id,
            "url": detail_url(doc_id_raw, item_id),
            "retrieved_at": now_iso(),
            "gap_type": "nfra_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })

    row = {
        "doc_id": doc_id,
        "source_id": "nfra",
        "publisher": "国家金融监督管理总局",
        "authority_level": infer_authority(item_name, title),
        "title": title,
        "url": detail_url(doc_id_raw, item_id),
        "api_url": f"{API}/DocInfo/SelectByDocId?docId={doc_id_raw}",
        "retrieved_at": now_iso(),
        "published_at": parse_date(detail.get("publishDate") or list_doc.get("publishDate")),
        "effective_at": parse_date(detail.get("builddate") or list_doc.get("builddate")),
        "status": infer_status(item_name, title),
        "asset_classes": ["banking", "insurance", "credit", "fixed_income", "cross_asset"],
        "product_types": ["banking", "insurance", "loan", "wealth_management", "trust_plan", "asset_management"],
        "body_read": body_read,
        "raw_path": str(raw_detail_path.relative_to(ROOT)) if raw_detail_path.exists() else None,
        "text_path": text_path,
        "checksum": doc_checksum or pdf_checksum,
        "content_type": "json_detail",
        "nfra_doc_id": doc_id_raw,
        "nfra_item_id": item_id,
        "nfra_item_name": item_name,
        "nfra_item_path": item_path(detail),
        "document_no": detail.get("documentNo"),
        "index_no": detail.get("indexNo"),
        "doc_file_url": urljoin(BASE, list_doc.get("docFileUrl") or detail.get("docFileUrl") or ""),
        "pdf_file_url": urljoin(BASE, list_doc.get("pdfFileUrl") or detail.get("pdfFileUrl") or ""),
        "doc_file_path": doc_path,
        "pdf_file_path": pdf_path,
    }
    return row, gaps


def gap_key(row: Dict) -> Tuple:
    return (row.get("source_id"), row.get("doc_id"), row.get("url"), row.get("gap_type"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-item", action="append", help="NFRA parent itemId, default: 926 and 950.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--page-index", type=int, default=1)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--no-download-assets", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    parent_items = args.parent_item or list(DEFAULT_PARENT_ITEMS)
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    saved_docs = 0
    saved_gaps = 0
    for parent_id in parent_items:
        parent_saved_docs = 0
        try:
            items = fetch_parent_item(parent_id, args.page_size, args.page_index)
        except Exception as exc:
            row = {
                "source_id": "nfra",
                "url": f"{API}/DocInfo/SelectItemAndDocByItemPId?itemId={parent_id}",
                "retrieved_at": now_iso(),
                "gap_type": "nfra_parent_fetch_failed",
                "reason": repr(exc),
                "body_read": False,
            }
            if gap_key(row) not in gap_keys:
                gaps.append(row)
                gap_keys.add(gap_key(row))
                saved_gaps += 1
            continue

        for item in items:
            docs = item.get("docInfoVOList") or []
            print(f"parent={parent_id} item={item.get('itemId')} docs={len(docs)}", flush=True)
            for list_doc in docs:
                try:
                    row, row_gaps = build_document(
                        list_doc,
                        item,
                        parent_id,
                        min_chars=args.min_chars,
                        download_assets=not args.no_download_assets,
                    )
                    if row.get("doc_id"):
                        documents[row["doc_id"]] = row
                        saved_docs += 1
                        parent_saved_docs += 1
                    for gap in row_gaps:
                        if gap_key(gap) not in gap_keys:
                            gaps.append(gap)
                            gap_keys.add(gap_key(gap))
                            saved_gaps += 1
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                    doc_id_raw = str(list_doc.get("docId"))
                    row = {
                        "source_id": "nfra",
                        "doc_id": f"nfra_{doc_id_raw}",
                        "url": detail_url(doc_id_raw, str(item.get("itemId") or parent_id)),
                        "retrieved_at": now_iso(),
                        "gap_type": "nfra_document_failed",
                        "reason": repr(exc),
                        "body_read": False,
                    }
                    if gap_key(row) not in gap_keys:
                        gaps.append(row)
                        gap_keys.add(gap_key(row))
                        saved_gaps += 1
                time.sleep(args.delay)

        if not parent_saved_docs:
            coverage_gap = {
                "source_id": "nfra",
                "url": f"{API}/DocInfo/SelectItemAndDocByItemPId?itemId={parent_id}",
                "retrieved_at": now_iso(),
                "gap_type": "nfra_no_documents_from_parent",
                "reason": "Official parent-item endpoint returned no documents for this parent item.",
                "body_read": False,
            }
            if gap_key(coverage_gap) not in gap_keys:
                gaps.append(coverage_gap)
                gap_keys.add(gap_key(coverage_gap))
                saved_gaps += 1

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"saved_docs={saved_docs} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
