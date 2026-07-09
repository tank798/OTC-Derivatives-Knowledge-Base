#!/usr/bin/env python3
"""Hydrate CSRC NERIS list metadata rows by local title keyword selection."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from typing import Dict, Iterable, List, Tuple
from urllib.parse import quote

from crawl_csrc_neris_api import (
    DETAIL_URL,
    PROCESSED,
    build_document,
    csrc_doc_id,
    fetch_lawlist,
    gap_key,
    now_iso,
    write_jsonl,
)


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def as_search_row(doc: Dict) -> Dict:
    return {
        "secFutrsLawId": doc.get("csrc_neris_id"),
        "secFutrsLawName": doc.get("title"),
        "lawPubOrgName": doc.get("publisher"),
        "fileno": doc.get("document_no"),
        "lawAthrtyStsCde": doc.get("csrc_neris_status_code"),
        "secFutrsLawNbr": doc.get("csrc_neris_nbr"),
        "secFutrsLawVersion": doc.get("csrc_neris_version"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", action="append", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--detail-timeout", type=int, default=20)
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--delay", type=float, default=0)
    args = parser.parse_args()

    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    keywords = [k for k in args.keyword if k]
    selected: List[Dict] = []
    for doc in documents.values():
        if not doc.get("doc_id", "").startswith("csrc_neris_"):
            continue
        title = doc.get("title") or ""
        if not any(k in title for k in keywords):
            continue
        if doc.get("body_read") and not args.refresh_existing:
            continue
        if not doc.get("csrc_neris_id"):
            continue
        selected.append(doc)

    selected.sort(key=lambda row: (row.get("published_at") or "", row.get("title") or ""), reverse=True)
    if args.limit:
        selected = selected[:args.limit]
    print(f"selected={len(selected)} keywords={','.join(keywords)}", flush=True)

    def hydrate(doc: Dict) -> Tuple[Dict, List[Dict]]:
        sec_id = doc.get("csrc_neris_id")
        doc_id = csrc_doc_id(sec_id)
        row_gaps: List[Dict] = []
        try:
            detail = fetch_lawlist(sec_id, args.detail_timeout)
        except Exception as exc:
            row_gaps.append({
                "source_id": "csrc",
                "doc_id": doc_id,
                "url": f"{DETAIL_URL}?navbarId=3&secFutrsLawId={quote(sec_id)}&body=",
                "retrieved_at": now_iso(),
                "gap_type": "csrc_neris_detail_failed",
                "reason": repr(exc),
                "body_read": False,
            })
            detail = None
        row, short_gaps = build_document(as_search_row(doc), detail, min_chars=120, add_short_gap=True)
        row_gaps.extend(short_gaps)
        return row, row_gaps

    saved = 0
    saved_gaps = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(hydrate, doc) for doc in selected]
        for future in as_completed(futures):
            row, row_gaps = future.result()
            documents[row["doc_id"]] = row
            saved += 1
            for gap in row_gaps:
                if gap_key(gap) not in gap_keys:
                    gaps.append(gap)
                    gap_keys.add(gap_key(gap))
                    saved_gaps += 1
            if args.delay:
                time.sleep(args.delay)
            if saved % 100 == 0:
                write_jsonl(documents_path, documents.values())
                write_jsonl(gaps_path, gaps)
                print(f"progress saved_docs={saved}/{len(selected)} saved_gaps={saved_gaps}", flush=True)

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"saved_docs={saved} saved_gaps={saved_gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
