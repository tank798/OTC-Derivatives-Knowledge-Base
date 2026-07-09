#!/usr/bin/env python3
"""OCR local PDF documents that were previously too short for text extraction."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

from extract_attachments import extract_pdf


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-chars", type=int, default=50)
    args = parser.parse_args()

    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    target_doc_ids = [
        gap.get("doc_id")
        for gap in gaps
        if gap.get("gap_type") == "pdf_text_too_short" and gap.get("doc_id") in documents
    ]

    fixed = 0
    still_short = 0
    for doc_id in target_doc_ids:
        doc = documents[doc_id]
        raw_path = doc.get("raw_path")
        if not raw_path:
            still_short += 1
            continue
        pdf_path = ROOT / raw_path
        if not pdf_path.exists():
            still_short += 1
            continue
        text = extract_pdf(pdf_path)
        if len(text.strip()) < args.min_chars:
            still_short += 1
            continue
        text_dir = ROOT / "data" / "raw" / "text" / doc.get("source_id", "pdf")
        text_dir.mkdir(parents=True, exist_ok=True)
        text_path = text_dir / f"{doc_id}.txt"
        text_path.write_text(text, encoding="utf-8")
        doc["body_read"] = True
        doc["text_path"] = str(text_path.relative_to(ROOT))
        doc["content_type"] = doc.get("content_type") or "application/pdf"
        documents[doc_id] = doc
        fixed += 1

    fixed_ids = {doc_id for doc_id in target_doc_ids if documents.get(doc_id, {}).get("body_read")}
    gaps = [
        gap
        for gap in gaps
        if not (gap.get("gap_type") == "pdf_text_too_short" and gap.get("doc_id") in fixed_ids)
    ]

    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"fixed={fixed} still_short={still_short}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
