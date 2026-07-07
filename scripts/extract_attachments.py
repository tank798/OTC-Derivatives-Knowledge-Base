#!/usr/bin/env python3
"""Extract downloaded attachments and add them as searchable documents."""

import argparse
import json
from pathlib import Path
import subprocess
from typing import Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ATT_TEXT = ROOT / "data" / "raw" / "text" / "attachments"


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


def gap_key(row: Dict) -> tuple:
    return (row.get("source_id"), row.get("doc_id"), row.get("url"), row.get("gap_type"))


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_with_textutil(path: Path) -> str:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8", errors="replace").strip()


def extract_text(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".doc", ".docx", ".rtf", ".txt", ".xls", ".xlsx"}:
        return extract_with_textutil(path)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-chars", type=int, default=80)
    args = parser.parse_args()

    attachments_path = PROCESSED / "attachments.jsonl"
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    attachments = list(iter_jsonl(attachments_path))
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = list(iter_jsonl(gaps_path))
    gap_keys = {gap_key(row) for row in gaps}

    ATT_TEXT.mkdir(parents=True, exist_ok=True)
    extracted = 0
    failed = 0
    for att in attachments:
        local_path = att.get("local_path")
        if not local_path:
            continue
        source_path = ROOT / local_path
        if not source_path.exists():
            continue
        try:
            text = extract_text(source_path)
        except Exception as exc:
            text = None
            att["extract_error"] = repr(exc)
        if not text or len(text.strip()) < args.min_chars:
            failed += 1
            att["text_extracted"] = False
            gap = {
                "source_id": att.get("source_id"),
                "doc_id": att.get("attachment_id"),
                "url": att.get("url"),
                "gap_type": "attachment_extract_failed",
                "reason": att.get("extract_error") or f"Extracted text too short: {len(text or '')}",
                "body_read": False,
            }
            if gap_key(gap) not in gap_keys:
                gaps.append(gap)
                gap_keys.add(gap_key(gap))
            continue

        text_path = ATT_TEXT / f"{att['attachment_id']}.txt"
        text_path.write_text(text, encoding="utf-8")
        att["text_extracted"] = True
        att["text_path"] = str(text_path.relative_to(ROOT))
        att["text_char_count"] = len(text)
        extracted += 1

        doc_id = f"attachment_{att['attachment_id']}"
        documents[doc_id] = {
            "doc_id": doc_id,
            "source_id": att.get("source_id"),
            "publisher": "中国外汇交易中心暨全国银行间同业拆借中心/中国货币网",
            "authority_level": "business_guideline",
            "title": att.get("attachment_name") or att.get("parent_title"),
            "parent_title": att.get("parent_title"),
            "url": att.get("url"),
            "retrieved_at": att.get("retrieved_at"),
            "published_at": None,
            "effective_at": None,
            "status": "unknown",
            "asset_classes": ["fixed_income", "fx", "credit"],
            "product_types": ["bond", "repo", "fx_derivative", "swap", "forward", "cds", "crm"],
            "body_read": True,
            "raw_path": local_path,
            "text_path": str(text_path.relative_to(ROOT)),
            "checksum": None,
            "content_type": source_path.suffix.lower().lstrip("."),
            "source_attachment_id": att.get("attachment_id"),
        }

    write_jsonl(attachments_path, attachments)
    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"attachments_extracted={extracted} attachments_failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
