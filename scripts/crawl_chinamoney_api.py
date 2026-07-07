#!/usr/bin/env python3
"""Crawl ChinaMoney rule channels through the official JSON API."""

import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_HTML = ROOT / "data" / "raw" / "html" / "china_money"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "china_money"
RAW_FILES = ROOT / "data" / "raw" / "files" / "china_money"
BASE = "https://www.chinamoney.com.cn"

CHANNELS = {
    "2862": "政策法规/人民银行",
    "2863": "政策法规/外汇局",
    "2864": "政策法规/外汇交易中心",
    "2865": "政策法规/交易商协会",
    "7496": "外汇规则/产品指引",
    "7497": "外汇规则/人民币外汇",
    "7498": "外汇规则/外币对",
    "7499": "外汇规则/外币利率",
    "7502": "外汇规则/做市",
    "7503": "外汇规则/应急",
    "7513": "本币规则/债券交易基本规则",
    "7508": "本币规则/债券回购",
    "7516": "本币规则/债券借贷",
    "7519": "本币规则/跨境互联互通",
    "7523": "本币规则/利率互换",
    "7524": "本币规则/利率期权",
    "7525": "本币规则/远期利率协议",
    "7526": "本币规则/债券远期",
    "7527": "本币规则/CRMW",
    "7528": "本币规则/CDS",
    "7529": "本币规则/衍生品对外开放",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
DATE_RE = re.compile(r"(20\d{2})[-年./](0?[1-9]|1[0-2])[-月./](3[01]|[12]\d|0?[1-9])")


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1
        if tag.lower() in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        if tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
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


def post_json(path: str, data: Dict, timeout: int = 30) -> Dict:
    body = urlencode(data).encode("utf-8")
    req = Request(
        urljoin(BASE, path),
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE,
            "Referer": f"{BASE}/chinese/",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_bytes(url: str, timeout: int = 30) -> Tuple[bytes, str]:
    req = Request(normalize_url(url), headers={"User-Agent": USER_AGENT, "Referer": f"{BASE}/chinese/"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def decode_html(data: bytes, content_type: str) -> str:
    encodings = ["utf-8", "gb18030", "gbk"]
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if match:
        encodings.insert(0, match.group(1))
    for enc in encodings:
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def html_to_text(raw_html: str) -> str:
    parser = TextParser()
    parser.feed(raw_html)
    return clean_space("\n".join(parser.parts))


def sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def append_jsonl(path: Path, row: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def seen_values(path: Path, key: str) -> set:
    seen = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    value = json.loads(line).get(key)
                    if value:
                        seen.add(value)
                except Exception:
                    pass
    return seen


def rows_by_key(path: Path, key: str) -> Dict[str, Dict]:
    rows: Dict[str, Dict] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    row = json.loads(line)
                    value = row.get(key)
                    if value:
                        rows[value] = row
                except Exception:
                    pass
    return rows


def extract_date(text: str) -> Optional[str]:
    match = DATE_RE.search(text or "")
    if not match:
        return None
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def fetch_records(channel_id: str, page_size: int, max_pages: int) -> List[Dict]:
    rows: List[Dict] = []
    for page_no in range(1, max_pages + 1):
        payload = {"channelId": channel_id, "pageNo": page_no, "pageSize": page_size}
        data = post_json("/ags/ms/cm-s-notice-query/contents", payload)
        records = data.get("records") or []
        rows.extend(records)
        total_pages = int((data.get("data") or {}).get("pageTotalSize") or 1)
        if page_no >= total_pages:
            break
        time.sleep(0.2)
    return rows


def fetch_attachments(content_id: str) -> List[Dict]:
    try:
        data = post_json("/ags/ms/cm-s-notice-query/txtAttachmentInfo", {"contentId": content_id})
        return data.get("records") or []
    except Exception:
        return []


def save_detail(record: Dict, channel_name: str, seen_urls: set) -> Optional[Dict]:
    draft_path = record.get("draftPath")
    if not draft_path:
        return None
    url = urljoin(BASE, draft_path)
    if url in seen_urls:
        return None

    doc_id = f"china_money_api_{record['contentId']}"
    RAW_HTML.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_HTML / f"{doc_id}.html"
    text_path = RAW_TEXT / f"{doc_id}.txt"

    body_read = False
    text = ""
    content_type = ""
    try:
        data, content_type = get_bytes(url)
        raw_path.write_bytes(data)
        raw_html = decode_html(data, content_type)
        text = html_to_text(raw_html)
        if text:
            text_path.write_text(text, encoding="utf-8")
        body_read = len(text) > 100
    except Exception:
        pass

    row = {
        "doc_id": doc_id,
        "source_id": "china_money",
        "publisher": "中国外汇交易中心暨全国银行间同业拆借中心/中国货币网",
        "authority_level": "business_guideline",
        "title": record.get("title"),
        "url": url,
        "retrieved_at": now_iso(),
        "published_at": record.get("releaseDate") or extract_date(text),
        "effective_at": None,
        "status": "unknown",
        "asset_classes": ["fixed_income", "fx", "credit"],
        "product_types": ["bond", "repo", "fx_derivative", "swap", "forward", "cds"],
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)) if raw_path.exists() else None,
        "text_path": str(text_path.relative_to(ROOT)) if text_path.exists() else None,
        "checksum": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.exists() else None,
        "content_type": content_type,
        "content_id": record.get("contentId"),
        "channel_id": record.get("channelId"),
        "channel_name": channel_name,
        "channel_path": record.get("channelPath"),
        "has_attachment": bool(record.get("attSize")),
    }
    return row


def save_attachment(att: Dict, record: Dict, existing: Optional[Dict], download: bool) -> Optional[Dict]:
    att_path = att.get("attachmentPath")
    if not att_path:
        return None
    if existing and (existing.get("downloaded") or not download):
        return None

    priority = att.get("priority", "0")
    url = f"{BASE}/dqs/cm-s-notice-query/fileDownLoad.do?contentId={record.get('contentId')}&priority={priority}"
    suffix = Path(att_path).suffix or ("." + (record.get("suffix") or "bin"))
    file_id = f"china_money_{record['contentId']}_{priority}_{sha1(att_path)}"
    RAW_FILES.mkdir(parents=True, exist_ok=True)
    local_path = RAW_FILES / f"{file_id}{suffix}"

    downloaded = bool(existing and existing.get("downloaded"))
    reason = ""
    if download and not downloaded:
        try:
            data, _ = get_bytes(url)
            if data:
                local_path.write_bytes(data)
                downloaded = True
        except Exception as exc:
            reason = repr(exc)

    row = dict(existing or {})
    row.update({
        "attachment_id": file_id,
        "source_id": "china_money",
        "content_id": record.get("contentId"),
        "parent_title": record.get("title"),
        "attachment_name": att.get("attachmentName"),
        "attachment_path": att_path,
        "download_url": url,
        "url": url,
        "local_path": str(local_path.relative_to(ROOT)) if downloaded else None,
        "downloaded": downloaded,
        "download_error": reason,
        "retrieved_at": now_iso(),
    })
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", action="append", help="Limit to specific channelId.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--no-download-attachments", action="store_true")
    args = parser.parse_args()

    documents_path = PROCESSED / "documents.jsonl"
    attachments_path = PROCESSED / "attachments.jsonl"
    seen_urls = seen_values(documents_path, "url")
    attachment_rows = rows_by_key(attachments_path, "attachment_path")

    channels = {cid: CHANNELS[cid] for cid in (args.channel or CHANNELS.keys()) if cid in CHANNELS}
    saved_docs = 0
    saved_attachments = 0
    for channel_id, channel_name in channels.items():
        records = fetch_records(channel_id, args.page_size, args.max_pages)
        for record in records:
            row = save_detail(record, channel_name, seen_urls)
            if row:
                append_jsonl(documents_path, row)
                seen_urls.add(row["url"])
                saved_docs += 1
            for att in fetch_attachments(record.get("contentId")):
                existing = attachment_rows.get(att.get("attachmentPath"))
                att_row = save_attachment(att, record, existing, not args.no_download_attachments)
                if att_row:
                    attachment_rows[att_row["attachment_path"]] = att_row
                    saved_attachments += 1
            time.sleep(0.1)
        print(f"channel={channel_id} records={len(records)}", flush=True)

    with attachments_path.open("w", encoding="utf-8") as f:
        for row in attachment_rows.values():
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"saved_docs={saved_docs} saved_attachments={saved_attachments}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
