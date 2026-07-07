#!/usr/bin/env python3
"""Extract text from downloaded regulatory PDF attachments."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_TEXT = ROOT / "data" / "raw" / "text"


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def extract_with_pypdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_with_pdfplumber(path: Path) -> str:
    import pdfplumber

    chunks: List[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_pdf(path: Path) -> str:
    try:
        text = extract_with_pypdf(path)
        if len(text) > 100:
            return text
    except Exception:
        pass
    return extract_with_pdfplumber(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", default=str(PROCESSED / "documents.jsonl"))
    parser.add_argument("--min-chars", type=int, default=80)
    args = parser.parse_args()

    documents_path = Path(args.documents)
    rows = list(iter_jsonl(documents_path))
    updated = 0
    failed = 0
    gap_rows = []

    for row in rows:
        raw_path = row.get("raw_path")
        if not raw_path or not raw_path.lower().endswith(".pdf"):
            continue
        pdf_path = ROOT / raw_path
        if not pdf_path.exists():
            failed += 1
            gap_rows.append({
                "source_id": row.get("source_id"),
                "doc_id": row.get("doc_id"),
                "url": row.get("url"),
                "gap_type": "pdf_missing",
                "reason": f"PDF file not found: {raw_path}",
                "body_read": False,
            })
            continue
        try:
            text = extract_pdf(pdf_path)
        except Exception as exc:
            failed += 1
            gap_rows.append({
                "source_id": row.get("source_id"),
                "doc_id": row.get("doc_id"),
                "url": row.get("url"),
                "gap_type": "pdf_extract_failed",
                "reason": repr(exc),
                "body_read": False,
            })
            continue

        if len(text.strip()) < args.min_chars:
            failed += 1
            gap_rows.append({
                "source_id": row.get("source_id"),
                "doc_id": row.get("doc_id"),
                "url": row.get("url"),
                "gap_type": "pdf_text_too_short",
                "reason": f"Extracted {len(text.strip())} chars",
                "body_read": False,
            })
            continue

        text_dir = RAW_TEXT / row.get("source_id", "unknown")
        text_dir.mkdir(parents=True, exist_ok=True)
        text_path = text_dir / f"{row['doc_id']}.txt"
        text_path.write_text(text, encoding="utf-8")
        row["text_path"] = str(text_path.relative_to(ROOT))
        row["body_read"] = True
        row["pdf_text_extracted"] = True
        updated += 1

    tmp_path = documents_path.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp_path.replace(documents_path)

    gaps_path = PROCESSED / "gaps.jsonl"
    if gap_rows:
        with gaps_path.open("a", encoding="utf-8") as f:
            for row in gap_rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"pdf_updated={updated} pdf_failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

