#!/usr/bin/env python3
"""Crawl the CSRC NERIS securities-futures regulation database."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_JSON = ROOT / "data" / "raw" / "html" / "csrc_neris"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "csrc_neris"

BASE = "https://neris.csrc.gov.cn/falvfagui"
SEARCH_URL = f"{BASE}/multipleFindController/solrSearch"
DETAIL_URL = f"{BASE}/rdqsHeader/mainbody"
LAWLIST_URL = f"{BASE}/rdqsHeader/lawlist"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
    "FinancialRegulationKnowledgeBase/0.1"
)

STATUS_LABELS = {
    "0": "not_yet_effective",
    "1": "current",
    "2": "amended",
    "3": "repealed",
    "4": "unknown",
}


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1
        if tag.lower() in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        if tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_space(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ \u3000]+", " ", value)
    value = re.sub(r"\n[ \u3000]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_tags(value: str) -> str:
    parser = TextParser()
    parser.feed(value or "")
    text = "\n".join(parser.parts)
    if not text.strip():
        text = re.sub(r"<[^>]+>", "", value or "")
    return clean_space(text)


def post_form(url: str, data: List[Tuple[str, str]], timeout: int = 30) -> Dict:
    encoded = urlencode(data)
    result = subprocess.run(
        [
            "curl",
            "-sL",
            "--compressed",
            "--fail",
            "--connect-timeout",
            "10",
            "--max-time",
            str(timeout),
            "-A",
            USER_AGENT,
            "-H",
            "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
            "-H",
            f"Origin: https://neris.csrc.gov.cn",
            "-H",
            f"Referer: {BASE}/multipleFindController/indexJsp",
            "--data",
            encoded,
            url,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 5,
    )
    return json.loads(result.stdout.decode("utf-8"))


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


def csrc_doc_id(sec_futrs_law_id: str) -> str:
    digest = hashlib.sha1(sec_futrs_law_id.encode("utf-8")).hexdigest()[:12]
    return f"csrc_neris_{digest}"


def ms_to_date(value) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        china_tz = dt.timezone(dt.timedelta(hours=8))
        return dt.datetime.fromtimestamp(int(value) / 1000, tz=china_tz).date().isoformat()
    except Exception:
        return str(value)


def search_page(page_no: int, page_size: int, title_query: str = "", body_query: str = "") -> Dict:
    sec_name = ""
    title_qry = ""
    if title_query:
        escaped = title_query.replace("(", "\\(").replace(")", "\\)")
        sec_name = f" AND (secFutrsLawName:*{escaped}*)"
        title_qry = title_query
    body = f'"{body_query}"' if body_query else ""
    data: List[Tuple[str, str]] = [
        ("pageNo", str(page_no)),
        ("pageSize", str(page_size)),
        ("secFutrsLawName", sec_name),
        ("body", body),
        ("titleQry", title_qry),
        ("keyQry", body_query),
        ("lawPubOrgName", ""),
        ("isLike", "on"),
        ("nbr", "1"),
    ]
    for status in ["0", "1", "2", "3", "4"]:
        data.append(("lawAthrtyStsCdeList", status))
    return post_form(SEARCH_URL, data)


def fetch_lawlist(sec_futrs_law_id: str, timeout: int) -> Dict:
    data = [
        ("body", ""),
        ("secFutrsLawId", sec_futrs_law_id),
        ("secFutrsLawEntryId", ""),
        ("navbarId", "3"),
        ("lawEntryClsfCde", ""),
        ("pageNo", "0"),
        ("relativeType", "law"),
    ]
    return post_form(LAWLIST_URL, data, timeout=timeout)


def infer_authority_level(publisher: str, title: str, fileno: str) -> str:
    text = f"{publisher} {title} {fileno}"
    if any(k in text for k in ["全国人民代表大会", "全国人大", "主席令"]):
        return "law"
    if "国务院" in text and "证监会" not in text:
        return "administrative_regulation"
    if any(k in text for k in ["证券交易所", "期货交易所", "北京证券交易所"]):
        return "exchange_rule"
    if any(k in text for k in ["证券登记结算", "证券业协会", "期货业协会", "基金业协会"]):
        return "self_regulatory_rule"
    if "证监会" in text or "中国证券监督管理委员会" in text:
        return "department_rule"
    return "securities_futures_rule"


def infer_asset_classes(title: str, publisher: str) -> List[str]:
    text = f"{title} {publisher}"
    assets = set()
    if any(k in text for k in ["股票", "上市公司", "证券公司", "证券交易", "权益"]):
        assets.add("equity")
    if any(k in text for k in ["债券", "公司债", "资产支持证券", "ABS", "回购", "信用"]):
        assets.add("fixed_income")
    if any(k in text for k in ["基金", "资管", "资产管理", "REIT"]):
        assets.add("fund")
    if any(k in text for k in ["期货", "期权", "商品", "能源", "交割"]):
        assets.add("commodity")
    if any(k in text for k in ["跨境", "境外", "QFII", "RQFII", "外汇"]):
        assets.add("fx")
    if not assets:
        assets.update(["equity", "fixed_income", "fund", "cross_asset"])
    assets.add("cross_asset")
    return sorted(assets)


def infer_product_types(title: str, text: str) -> List[str]:
    blob = f"{title} {text[:2000]}"
    products = set()
    if any(k in blob for k in ["衍生品", "互换", "远期", "非标准化期权", "场外期权"]):
        products.update(["otc_derivative", "swap", "forward", "non_standard_option"])
    if "期权" in blob:
        products.add("listed_option")
    if "收益凭证" in blob:
        products.add("income_certificate")
    if any(k in blob for k in ["基金", "公募"]):
        products.add("public_fund")
    if "私募" in blob:
        products.add("private_fund")
    if any(k in blob for k in ["资管", "资产管理"]):
        products.add("asset_management_plan")
    if any(k in blob for k in ["期货", "期货公司"]):
        products.add("futures")
    if any(k in blob for k in ["债券", "公司债", "ABS", "资产支持证券"]):
        products.update(["bond", "abs"])
    if "回购" in blob:
        products.add("repo")
    if any(k in blob for k in ["信用保护", "信用风险缓释", "CDS", "CRM"]):
        products.update(["crm", "cds", "credit_derivative"])
    if any(k in blob for k in ["融资融券", "转融通"]):
        products.add("margin_financing_securities_lending")
    if "REIT" in blob or "不动产投资信托基金" in blob:
        products.add("reit")
    if not products:
        products.update(["securities_futures_rule"])
    return sorted(products)


def flatten_law_text(payload: Dict) -> str:
    lawlist = payload.get("lawlist") or {}
    law = lawlist.get("law") or {}
    lines: List[str] = []
    for field in ["wtAnttnSecFutrsLawName", "bodyAgoCntnt"]:
        value = strip_tags(law.get(field) or "")
        if value:
            lines.append(value)

    for entry in lawlist.get("lawEntryVOs") or []:
        title = strip_tags(entry.get("title") or "")
        cntnt = strip_tags(entry.get("cntnt") or "")
        item_texts = [
            strip_tags(item.get("cntnt") or "")
            for item in (entry.get("itemList") or [])
            if strip_tags(item.get("cntnt") or "")
        ]
        if item_texts:
            if title or cntnt:
                lines.append(clean_space(f"{title} {cntnt}"))
            lines.extend(item_texts)
        elif title or cntnt:
            lines.append(clean_space(f"{title} {cntnt}"))

    for field in ["bodyAftCntnt", "draftDscr"]:
        value = strip_tags(law.get(field) or "")
        if value:
            lines.append(value)
    return clean_space("\n\n".join(line for line in lines if line))


def build_document(search_row: Dict, detail_payload: Optional[Dict], min_chars: int, add_short_gap: bool = True) -> Tuple[Dict, List[Dict]]:
    sec_id = search_row.get("secFutrsLawId") or ""
    doc_id = csrc_doc_id(sec_id)
    gaps: List[Dict] = []

    RAW_JSON.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_JSON / f"{doc_id}.json"
    text_path_obj = RAW_TEXT / f"{doc_id}.txt"

    if detail_payload is not None:
        raw_path.write_text(json.dumps(detail_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    lawlist = (detail_payload or {}).get("lawlist") or {}
    law = lawlist.get("law") or {}
    title = clean_space(
        law.get("wtAnttnSecFutrsLawName")
        or law.get("secFutrsLawName")
        or search_row.get("secFutrsLawName")
        or ""
    )
    publisher = clean_space(law.get("lawPubOrgName") or search_row.get("lawPubOrgName") or "中国证券监督管理委员会")
    fileno = clean_space(law.get("fileno") or search_row.get("fileno") or "")
    text = flatten_law_text(detail_payload or {})
    if text:
        text_path_obj.write_text(text, encoding="utf-8")
    body_read = len(text) >= min_chars
    if add_short_gap and not body_read:
        gaps.append({
            "source_id": "csrc",
            "doc_id": doc_id,
            "url": f"{DETAIL_URL}?navbarId=3&secFutrsLawId={quote(sec_id)}&body=",
            "retrieved_at": now_iso(),
            "gap_type": "csrc_neris_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })

    status_code = str(law.get("lawAthrtyStsCde") or search_row.get("lawAthrtyStsCde") or "")
    row = {
        "doc_id": doc_id,
        "source_id": "csrc",
        "publisher": publisher,
        "authority_level": infer_authority_level(publisher, title, fileno),
        "title": title,
        "url": f"{DETAIL_URL}?navbarId=3&secFutrsLawId={quote(sec_id)}&body=",
        "api_url": LAWLIST_URL,
        "retrieved_at": now_iso(),
        "published_at": ms_to_date(law.get("pubDate") or search_row.get("pubDate")),
        "effective_at": ms_to_date(law.get("efctvDate") or search_row.get("efctvDate")),
        "status": STATUS_LABELS.get(status_code, "unknown"),
        "asset_classes": infer_asset_classes(title, publisher),
        "product_types": infer_product_types(title, text),
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)) if raw_path.exists() else None,
        "text_path": str(text_path_obj.relative_to(ROOT)) if text_path_obj.exists() else None,
        "checksum": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.exists() else None,
        "content_type": "json_detail",
        "document_no": fileno,
        "csrc_neris_id": sec_id,
        "csrc_neris_nbr": law.get("secFutrsLawNbr") or search_row.get("secFutrsLawNbr"),
        "csrc_neris_version": law.get("secFutrsLawVersion") or search_row.get("secFutrsLawVersion"),
        "csrc_neris_status_code": status_code,
        "attachment_links": [],
    }
    return row, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title-query", default="", help="Optional NERIS title keyword filter.")
    parser.add_argument("--body-query", default="", help="Optional NERIS body keyword filter.")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=0, help="0 means all pages reported by rowCount.")
    parser.add_argument("--max-details", type=int, default=0, help="0 means no detail cap.")
    parser.add_argument("--list-only", action="store_true", help="Only store list metadata, do not fetch lawlist detail.")
    parser.add_argument("--refresh-existing", action="store_true", help="Refetch existing csrc_neris documents with body text.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent detail fetch workers.")
    parser.add_argument("--detail-timeout", type=int, default=20)
    parser.add_argument("--min-chars", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.08)
    args = parser.parse_args()

    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    page_no = max(1, args.start_page)
    total_pages: Optional[int] = None
    saved_docs = 0
    saved_gaps = 0
    skipped_docs = 0
    seen_ids = set()
    consecutive_empty = 0

    while True:
        if args.max_pages and page_no > args.max_pages:
            break
        if total_pages is not None and page_no > total_pages:
            break

        try:
            payload = search_page(page_no, args.page_size, args.title_query, args.body_query)
        except Exception as exc:
            row = {
                "source_id": "csrc",
                "url": SEARCH_URL,
                "retrieved_at": now_iso(),
                "gap_type": "csrc_neris_search_failed",
                "reason": f"page={page_no} {exc!r}",
                "body_read": False,
            }
            if gap_key(row) not in gap_keys:
                gaps.append(row)
                gap_keys.add(gap_key(row))
                saved_gaps += 1
            break

        page_util = payload.get("pageUtil") or {}
        rows = page_util.get("pageList") or []
        row_count = int(page_util.get("rowCount") or len(rows) or 0)
        if total_pages is None and row_count:
            total_pages = max(1, math.ceil(row_count / max(1, args.page_size)))
        print(f"page={page_no} records={len(rows)} row_count={row_count} total_pages={total_pages}", flush=True)

        if not rows:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            page_no += 1
            time.sleep(args.delay)
            continue
        consecutive_empty = 0

        pending_rows: List[Dict] = []
        for search_row in rows:
            sec_id = search_row.get("secFutrsLawId") or ""
            if not sec_id:
                continue
            if sec_id in seen_ids:
                continue
            seen_ids.add(sec_id)
            pending_rows.append(search_row)
            if args.max_details and len(pending_rows) + saved_docs >= args.max_details:
                break

        def process_one(search_row: Dict) -> Tuple[str, Dict, List[Dict]]:
            sec_id = search_row.get("secFutrsLawId") or ""
            doc_id = csrc_doc_id(sec_id)
            existing = documents.get(doc_id)
            if (
                existing
                and not args.refresh_existing
                and not args.list_only
                and existing.get("body_read")
                and existing.get("text_path")
            ):
                return "skipped", existing, []

            detail_payload: Optional[Dict] = None
            local_gaps: List[Dict] = []
            if not args.list_only:
                try:
                    detail_payload = fetch_lawlist(sec_id, args.detail_timeout)
                except Exception as exc:
                    gap = {
                        "source_id": "csrc",
                        "doc_id": doc_id,
                        "url": f"{DETAIL_URL}?navbarId=3&secFutrsLawId={quote(sec_id)}&body=",
                        "retrieved_at": now_iso(),
                        "gap_type": "csrc_neris_detail_failed",
                        "reason": repr(exc),
                        "body_read": False,
                    }
                    local_gaps.append(gap)

            row, row_gaps = build_document(search_row, detail_payload, args.min_chars, add_short_gap=not args.list_only)
            if args.list_only:
                row["body_read"] = False
                row["content_type"] = "list_metadata"
            local_gaps.extend(row_gaps)
            return "saved", row, local_gaps

        if args.workers > 1 and len(pending_rows) > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [executor.submit(process_one, row) for row in pending_rows]
                for future in as_completed(futures):
                    status, row, row_gaps = future.result()
                    if status == "skipped":
                        skipped_docs += 1
                    else:
                        documents[row["doc_id"]] = row
                        saved_docs += 1
                    for gap in row_gaps:
                        if gap_key(gap) not in gap_keys:
                            gaps.append(gap)
                            gap_keys.add(gap_key(gap))
                            saved_gaps += 1
        else:
            for search_row in pending_rows:
                status, row, row_gaps = process_one(search_row)
                if status == "skipped":
                    skipped_docs += 1
                else:
                    documents[row["doc_id"]] = row
                    saved_docs += 1
                for gap in row_gaps:
                    if gap_key(gap) not in gap_keys:
                        gaps.append(gap)
                        gap_keys.add(gap_key(gap))
                        saved_gaps += 1
                time.sleep(args.delay)

                if args.max_details and saved_docs >= args.max_details:
                    write_jsonl(documents_path, documents.values())
                    write_jsonl(gaps_path, gaps)
                    print(f"saved_docs={saved_docs} skipped_docs={skipped_docs} saved_gaps={saved_gaps}")
                    return 0

        if args.workers > 1:
            for _ in pending_rows:
                if args.delay:
                    time.sleep(args.delay)

        if args.max_details and saved_docs >= args.max_details:
            write_jsonl(documents_path, documents.values())
            write_jsonl(gaps_path, gaps)
            print(f"saved_docs={saved_docs} skipped_docs={skipped_docs} saved_gaps={saved_gaps}")
            return 0

        if args.max_details and saved_docs + skipped_docs >= args.max_details:
            write_jsonl(documents_path, documents.values())
            write_jsonl(gaps_path, gaps)
            print(f"saved_docs={saved_docs} skipped_docs={skipped_docs} saved_gaps={saved_gaps}")
            return 0

        if not pending_rows and page_no > 1:
            break

        write_jsonl(documents_path, documents.values())
        write_jsonl(gaps_path, gaps)

        if len(pending_rows) == 0 and page_no > 1:
            break
        page_no += 1
        time.sleep(args.delay)

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"saved_docs={saved_docs} skipped_docs={skipped_docs} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
