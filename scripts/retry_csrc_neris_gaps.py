#!/usr/bin/env python3
"""Retry failed or short CSRC NERIS detail hydrations."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
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
        "pubDate": doc.get("published_at"),
        "efctvDate": doc.get("effective_at"),
    }


def is_csrc_doc_gap(gap: Dict, doc_id: str) -> bool:
    return gap.get("source_id") == "csrc" and gap.get("doc_id") == doc_id


def hydrate(doc: Dict, timeout: int, min_chars: int) -> Tuple[str, Dict, List[Dict]]:
    sec_id = doc.get("csrc_neris_id")
    doc_id = doc.get("doc_id") or csrc_doc_id(sec_id or "")
    try:
        detail = fetch_lawlist(sec_id, timeout)
    except Exception as exc:
        return "failed", doc, [{
            "source_id": "csrc",
            "doc_id": doc_id,
            "url": f"{DETAIL_URL}?navbarId=3&secFutrsLawId={quote(sec_id or '')}&body=",
            "retrieved_at": now_iso(),
            "gap_type": "csrc_neris_detail_failed",
            "reason": repr(exc),
            "body_read": False,
        }]
    row, row_gaps = build_document(as_search_row(doc), detail, min_chars=min_chars, add_short_gap=True)
    return "saved", row, row_gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--detail-timeout", type=int, default=60)
    parser.add_argument("--min-chars", type=int, default=50)
    parser.add_argument("--save-every", type=int, default=10)
    args = parser.parse_args()

    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))

    gap_doc_ids = []
    seen = set()
    for gap in gaps:
        if gap.get("source_id") != "csrc":
            continue
        doc_id = gap.get("doc_id")
        if doc_id and doc_id in documents and doc_id not in seen:
            gap_doc_ids.append(doc_id)
            seen.add(doc_id)

    selected = [
        documents[doc_id]
        for doc_id in gap_doc_ids
        if documents[doc_id].get("csrc_neris_id")
    ]
    selected.sort(key=lambda row: (row.get("published_at") or "", row.get("title") or ""), reverse=True)
    if args.limit:
        selected = selected[:args.limit]

    print(f"selected={len(selected)} workers={args.workers} timeout={args.detail_timeout} min_chars={args.min_chars}", flush=True)

    saved = 0
    failed = 0
    short = 0

    def commit() -> None:
        write_jsonl(documents_path, documents.values())
        write_jsonl(gaps_path, gaps)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(hydrate, doc, args.detail_timeout, args.min_chars): doc for doc in selected}
        for future in as_completed(futures):
            doc = futures[future]
            doc_id = doc["doc_id"]
            status, row, row_gaps = future.result()
            gaps = [gap for gap in gaps if not is_csrc_doc_gap(gap, doc_id)]
            if status == "saved":
                documents[row["doc_id"]] = row
                if row.get("body_read"):
                    saved += 1
                else:
                    short += 1
            else:
                failed += 1
            existing_keys = {gap_key(gap) for gap in gaps}
            for gap in row_gaps:
                if gap_key(gap) not in existing_keys:
                    gaps.append(gap)
                    existing_keys.add(gap_key(gap))

            done = saved + failed + short
            if done % args.save_every == 0 or done == len(selected):
                commit()
                print(f"progress done={done}/{len(selected)} saved={saved} short={short} failed={failed}", flush=True)

    commit()
    print(f"saved={saved} short={short} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
