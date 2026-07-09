#!/usr/bin/env python3
"""Crawl AMAC policy-rule channels through the official policy search API."""

import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_HTML = ROOT / "data" / "raw" / "html" / "amac_policy"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "amac_policy"
BASE = "https://fg.amac.org.cn"

CHANNELS = {
    "3856": "法律法规/法律",
    "3857": "法律法规/行政法规",
    "3858": "法律法规/司法解释",
    "3860": "部门规章/综合",
    "3861": "部门规章/公募基金",
    "3870": "部门规章/私募基金",
    "3871": "部门规章/资产管理",
    "3872": "部门规章/信息科技",
    "3873": "部门规章/QDII",
    "3874": "部门规章/QFII/RQFII",
    "3875": "部门规章/其他",
    "3877": "规范性文件/综合",
    "3878": "规范性文件/公募基金",
    "3888": "规范性文件/私募基金",
    "3889": "规范性文件/资产管理",
    "3890": "规范性文件/信息科技",
    "3892": "自律规则/自律管理",
    "3893": "自律规则/会员管理",
    "3894": "自律规则/公募基金",
    "3901": "自律规则/私募基金",
    "3906": "自律规则/资产管理",
    "3914": "自律规则/基金托管及服务",
    "3921": "自律规则/从业人员",
    "3926": "自律规则/信息科技",
    "3927": "自律规则/其他",
    "3929": "行业标准/国标",
    "3930": "行业标准/行标",
    "3931": "行业标准/团标",
}

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
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "td"}:
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
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "td"}:
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


def get_bytes(url: str, timeout: int = 60) -> Tuple[bytes, str]:
    req = Request(
        normalize_url(url),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Referer": f"{BASE}/governmentrules_3854/flfg/fl/",
        },
    )
    context = ssl._create_unverified_context()
    try:
        with urlopen(req, timeout=timeout, context=context) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except URLError as exc:
        result = subprocess.run(
            ["curl", "-sL", "--insecure", "-A", USER_AGENT, "-H", f"Referer: {BASE}/governmentrules_3854/flfg/fl/", normalize_url(url)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if result.stdout:
            return result.stdout, ""
        raise exc


def get_json(path: str, params: Dict, timeout: int = 60) -> Dict:
    url = urljoin(BASE, path) + "?" + urlencode(params)
    data, _ = get_bytes(url, timeout=timeout)
    return json.loads(data.decode("utf-8"))


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


def html_to_text(raw_html: str) -> Tuple[str, List[Tuple[str, str]]]:
    start = raw_html.find('<div class="job-infos">')
    end = raw_html.find('<div class="com-line">', start)
    if start >= 0 and end > start:
        raw_html = raw_html[start:end]
    parser = TextParser()
    parser.feed(raw_html)
    return clean_space("\n".join(parser.parts)), parser.links


def extract_date(value: str) -> Optional[str]:
    match = DATE_RE.search(value or "")
    if not match:
        return None
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


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


def authority_level(channel_name: str) -> str:
    if channel_name.startswith("法律法规/法律"):
        return "law"
    if channel_name.startswith("法律法规/行政法规"):
        return "administrative_regulation"
    if channel_name.startswith("部门规章"):
        return "department_rule"
    if channel_name.startswith("规范性文件"):
        return "regulator_normative_document"
    if channel_name.startswith("自律规则"):
        return "self_regulatory_rule"
    if channel_name.startswith("行业标准"):
        return "industry_standard"
    return "self_regulatory_rule"


def fetch_channel(channel_id: str, page_no: int, page_size: int) -> Dict:
    return get_json(
        "/portal/ESSearch/wcmPolicy/getPolicyDataByProgram_v2",
        {"chnlId": channel_id, "pageNo": page_no, "pageSize": page_size},
    )


def fetch_all_records(channel_id: str, page_size: int, max_pages: int, delay: float) -> List[Dict]:
    records: List[Dict] = []
    for page_no in range(1, max_pages + 1):
        payload = fetch_channel(channel_id, page_no, page_size)
        data = ((payload.get("data") or {}).get("data") or {})
        page_records = data.get("policyRulesVos") or []
        records.extend(page_records)
        total = int(data.get("total") or len(records))
        if len(records) >= total or not page_records:
            break
        time.sleep(delay)
    return records


def build_document(record: Dict, channel_id: str, channel_name: str, min_chars: int) -> Tuple[Dict, List[Dict]]:
    url = urljoin(BASE, record.get("docPubUrl") or "")
    doc_id = f"amac_policy_{record.get('docId') or sha1(url)}"
    gaps: List[Dict] = []
    RAW_HTML.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_HTML / f"{doc_id}.html"
    text_path_obj = RAW_TEXT / f"{doc_id}.txt"

    body_read = False
    text = ""
    content_type = ""
    links: List[Tuple[str, str]] = []
    try:
        data, content_type = get_bytes(url)
        raw_path.write_bytes(data)
        raw_html = decode_html(data, content_type)
        text, links = html_to_text(raw_html)
        if text:
            text_path_obj.write_text(text, encoding="utf-8")
        body_read = len(text) >= min_chars
    except Exception as exc:
        gaps.append({
            "source_id": "amac",
            "doc_id": doc_id,
            "url": url,
            "retrieved_at": now_iso(),
            "gap_type": "amac_detail_fetch_failed",
            "reason": repr(exc),
            "body_read": False,
        })

    if text and not body_read:
        gaps.append({
            "source_id": "amac",
            "doc_id": doc_id,
            "url": url,
            "retrieved_at": now_iso(),
            "gap_type": "amac_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })

    row = {
        "doc_id": doc_id,
        "source_id": "amac",
        "publisher": "中国证券投资基金业协会",
        "authority_level": authority_level(channel_name),
        "title": clean_space(record.get("docTitle") or ""),
        "url": url,
        "api_url": f"{BASE}/portal/ESSearch/wcmPolicy/getPolicyDataByProgram_v2?chnlId={channel_id}",
        "retrieved_at": now_iso(),
        "published_at": record.get("lawPromTime") or extract_date(text),
        "effective_at": None,
        "status": "unknown",
        "asset_classes": ["fund", "equity", "fixed_income", "cross_asset"],
        "product_types": ["private_fund", "public_fund", "asset_management_plan", "etf", "reit"],
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)) if raw_path.exists() else None,
        "text_path": str(text_path_obj.relative_to(ROOT)) if text_path_obj.exists() else None,
        "checksum": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.exists() else None,
        "content_type": content_type or "text/html",
        "amac_doc_id": record.get("docId"),
        "amac_channel_id": channel_id,
        "amac_channel_name": channel_name,
        "document_no": record.get("legalIsNum"),
        "attachment_links": [
            {"url": urljoin(url, href), "title": title}
            for href, title in links
            if href and not href.startswith("#") and ("附件" in title or href.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")))
        ],
    }
    return row, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", action="append", help="Limit to AMAC channel id.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    selected = {cid: CHANNELS[cid] for cid in (args.channel or CHANNELS.keys()) if cid in CHANNELS}
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    saved_docs = 0
    saved_gaps = 0
    for channel_id, channel_name in selected.items():
        try:
            records = fetch_all_records(channel_id, args.page_size, args.max_pages, args.delay)
        except Exception as exc:
            row = {
                "source_id": "amac",
                "url": f"{BASE}/portal/ESSearch/wcmPolicy/getPolicyDataByProgram_v2?chnlId={channel_id}",
                "retrieved_at": now_iso(),
                "gap_type": "amac_channel_fetch_failed",
                "reason": repr(exc),
                "body_read": False,
            }
            if gap_key(row) not in gap_keys:
                gaps.append(row)
                gap_keys.add(gap_key(row))
                saved_gaps += 1
            continue

        print(f"channel={channel_id} name={channel_name} records={len(records)}", flush=True)
        for record in records:
            row, row_gaps = build_document(record, channel_id, channel_name, args.min_chars)
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
    print(f"saved_docs={saved_docs} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
