#!/usr/bin/env python3
"""Import manually supplied regulatory Word/PDF files into the corpus."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pdfplumber
from docx import Document


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_FILES = ROOT / "data" / "raw" / "files" / "manual_regulatory"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "manual_regulatory"
DEFAULT_INPUT_DIR = Path("/Users/castle/C盘/常用/以往实习梳理/华泰金创产品/监管文件")

SOURCE_HINTS = {
    "DCE": "dce",
    "GFEX": "gfex",
    "CZCE": "czce",
    "CSRC_NERIS": "csrc",
    "BSE": "bse",
}

KNOWN_MANUAL_DOC_IDS = {
    "衍生品交易业务风险揭示书（参考范本）": "csrc_neris_ebb03143c7f7",
    "期货公司财务处理实施细则": "csrc_neris_298ffeb175d3",
    "中国企业境外可持续基础设施项目实施指引": "csrc_neris_6f04500ce4fa",
    "中国企业境外可持续基础设施项目评价规范": "csrc_neris_22b2113a597b",
    "中华人民共和国公司法": "bse_200024254",
    "中华人民共和国证券法": "bse_200024260",
}

PDF_TITLE_SOURCE = {
    "期货公司财务处理实施细则.pdf": ("期货公司财务处理实施细则", "csrc"),
    "中国企业境外可持续基础设施项目实施指引.pdf": ("中国企业境外可持续基础设施项目实施指引", "csrc"),
    "中国企业境外可持续基础设施项目评价规范.pdf": ("中国企业境外可持续基础设施项目评价规范", "csrc"),
    "中华人民共和国证券法.pdf": ("中华人民共和国证券法", "bse"),
}

ARTICLE_OR_RULE_RE = re.compile(r"(法|办法|规则|细则|指引|指南|规范|风险揭示书)")
DATE_RE = re.compile(
    r"(20\d{2})\s*(?:年|-|/)\s*(\d{1,2})\s*(?:月|-|/)\s*(\d{1,2})\s*(?:日)?"
)
EFFECTIVE_RE = re.compile(
    r"自\s*(20\d{2}\s*(?:年|-|/)\s*\d{1,2}\s*(?:月|-|/)\s*\d{1,2}\s*(?:日)?)\s*(?:起|实施|施行)"
)


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_source_registry() -> Dict[str, Dict]:
    registry_path = ROOT / "data" / "registry" / "sources.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    return {row["source_id"]: row for row in registry.get("sources", [])}


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_docx_text(path: Path) -> str:
    document = Document(path)
    lines = [para.text.strip() for para in document.paragraphs if para.text.strip()]
    return normalize_text("\n".join(lines))


def extract_pdf_text(path: Path) -> str:
    parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return normalize_text("\n\n".join(parts))


def first_content_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def title_from_numbered_docx(path: Path, text: str) -> Tuple[str, str]:
    name = path.stem
    parts = name.split("_")
    if len(parts) >= 4 and parts[0].isdigit():
        source_key = parts[1]
        title_start = 3
        if len(parts) >= 5 and parts[1] == "CSRC" and parts[2] == "NERIS":
            source_key = "CSRC_NERIS"
            title_start = 4
        source_id = SOURCE_HINTS.get(source_key, "manual")
        filename_title = "_".join(parts[title_start:]).strip()
    else:
        source_id = "manual"
        filename_title = name

    line = first_content_line(text)
    if (
        line
        and len(line) <= 80
        and not line.startswith(("（", "(", "【"))
        and ARTICLE_OR_RULE_RE.search(line)
        and "发布" not in line
    ):
        return line, source_id
    return filename_title, source_id


def normalize_date(raw: str) -> Optional[str]:
    match = DATE_RE.search(raw or "")
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return dt.date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def infer_dates(text: str) -> Tuple[Optional[str], Optional[str]]:
    head = text[:1500]
    published_at = normalize_date(head)
    effective_match = EFFECTIVE_RE.search(head)
    effective_at = normalize_date(effective_match.group(1)) if effective_match else None
    if not effective_at and "自发布之日起" in head:
        effective_at = published_at
    return published_at, effective_at


def stable_manual_doc_id(source_id: str, title: str) -> str:
    digest = hashlib.sha1(f"{source_id}:{title}".encode("utf-8")).hexdigest()[:12]
    return f"manual_{source_id}_{digest}"


def should_skip(path: Path) -> bool:
    if path.name.startswith("~$"):
        return True
    if path.name.startswith("00_"):
        return True
    return path.suffix.lower() not in {".docx", ".pdf"}


def read_manual_file(path: Path) -> Optional[Dict]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = extract_docx_text(path)
        title, source_id = title_from_numbered_docx(path, text)
    elif suffix == ".pdf":
        if path.name not in PDF_TITLE_SOURCE:
            return None
        text = extract_pdf_text(path)
        title, source_id = PDF_TITLE_SOURCE[path.name]
    else:
        return None

    text = normalize_text(text)
    if len(text) < 300 or "请从这里开始粘贴官方正文" in text:
        return None

    doc_id = KNOWN_MANUAL_DOC_IDS.get(title) or stable_manual_doc_id(source_id, title)
    published_at, effective_at = infer_dates(text)
    return {
        "doc_id": doc_id,
        "source_id": source_id,
        "title": title,
        "text": text,
        "published_at": published_at,
        "effective_at": effective_at,
        "source_file": path,
        "content_type": {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
        }[suffix],
    }


def merge_doc(existing: Optional[Dict], manual: Dict, registry: Dict[str, Dict], retrieved_at: str) -> Dict:
    source = registry.get(manual["source_id"], {})
    row = dict(existing or {})
    row.update(
        {
            "doc_id": manual["doc_id"],
            "source_id": manual["source_id"],
            "title": manual["title"],
            "publisher": row.get("publisher") or source.get("publisher") or "",
            "authority_level": row.get("authority_level") or source.get("authority_level") or "manual_regulatory",
            "asset_classes": row.get("asset_classes") or source.get("asset_classes", []),
            "product_types": row.get("product_types") or source.get("product_types", []),
            "published_at": row.get("published_at") or manual.get("published_at"),
            "effective_at": row.get("effective_at") or manual.get("effective_at"),
            "retrieved_at": row.get("retrieved_at") or retrieved_at,
            "manual_imported": True,
            "manual_imported_at": retrieved_at,
            "manual_source_filename": manual["source_file"].name,
            "content_type": manual["content_type"],
            "body_read": True,
            "status": row.get("status") or "current",
        }
    )

    if not row.get("url"):
        row["url"] = source.get("base_url", "")

    raw_target = RAW_FILES / f"{manual['doc_id']}{manual['source_file'].suffix.lower()}"
    text_target = RAW_TEXT / f"{manual['doc_id']}.txt"
    shutil.copy2(manual["source_file"], raw_target)
    text_target.write_text(manual["text"] + "\n", encoding="utf-8")

    row["raw_path"] = str(raw_target.relative_to(ROOT))
    row["text_path"] = str(text_target.relative_to(ROOT))
    row["checksum"] = hashlib.sha256(manual["text"].encode("utf-8")).hexdigest()
    row["text_char_count"] = len(manual["text"])
    return row


def resolve_gaps(gaps: List[Dict], imported_sources: set, imported_doc_ids: set, retrieved_at: str) -> Tuple[List[Dict], List[Dict]]:
    remaining: List[Dict] = []
    resolved: List[Dict] = []
    for gap in gaps:
        doc_id = gap.get("doc_id")
        source_id = gap.get("source_id")
        resolved_by_doc = doc_id and doc_id in imported_doc_ids
        resolved_by_source = source_id in {"dce", "gfex", "czce"} and source_id in imported_sources
        if resolved_by_doc or resolved_by_source:
            row = dict(gap)
            row["resolved_at"] = retrieved_at
            row["resolved_by"] = "manual_regulatory_file_import"
            row["resolution_note"] = "User supplied official Word/PDF text; corpus and clause index rebuilt from local manual file."
            resolved.append(row)
        else:
            remaining.append(gap)
    return remaining, resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--no-resolve-gaps", action="store_true")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    registry = load_source_registry()
    RAW_FILES.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)

    manual_rows: List[Dict] = []
    skipped: List[Dict] = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or should_skip(path):
            continue
        try:
            row = read_manual_file(path)
            if row:
                manual_rows.append(row)
            else:
                skipped.append({"file": path.name, "reason": "empty_placeholder_or_unmapped"})
        except Exception as exc:
            skipped.append({"file": path.name, "reason": repr(exc)})

    retrieved_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")
    existing_docs = list(iter_jsonl(PROCESSED / "documents.jsonl"))
    by_id = {row["doc_id"]: row for row in existing_docs}

    imported_docs: List[Dict] = []
    for manual in manual_rows:
        merged = merge_doc(by_id.get(manual["doc_id"]), manual, registry, retrieved_at)
        by_id[merged["doc_id"]] = merged
        imported_docs.append(merged)

    existing_order = [row["doc_id"] for row in existing_docs if row["doc_id"] in by_id]
    appended_ids = [row["doc_id"] for row in imported_docs if row["doc_id"] not in existing_order]
    ordered_ids = existing_order + appended_ids
    write_jsonl(PROCESSED / "documents.jsonl", (by_id[doc_id] for doc_id in ordered_ids))

    gaps_path = PROCESSED / "gaps.jsonl"
    resolved_path = PROCESSED / "resolved_gaps.jsonl"
    original_gaps = list(iter_jsonl(gaps_path))
    resolved_now: List[Dict] = []
    resolved_total = len(list(iter_jsonl(resolved_path)))
    if not args.no_resolve_gaps:
        imported_sources = {row["source_id"] for row in imported_docs}
        imported_doc_ids = {row["doc_id"] for row in imported_docs}
        remaining, resolved_now = resolve_gaps(original_gaps, imported_sources, imported_doc_ids, retrieved_at)
        write_jsonl(gaps_path, remaining)
        all_resolved = list(iter_jsonl(resolved_path)) + resolved_now
        write_jsonl(resolved_path, all_resolved)
        resolved_total = len(all_resolved)

    report = {
        "imported_at": retrieved_at,
        "input_dir": str(input_dir),
        "imported_count": len(imported_docs),
        "resolved_gaps_count": resolved_total,
        "resolved_gaps_this_run": len(resolved_now),
        "skipped": skipped,
        "documents": [
            {
                "doc_id": row["doc_id"],
                "source_id": row["source_id"],
                "title": row["title"],
                "text_char_count": row.get("text_char_count"),
                "raw_path": row.get("raw_path"),
                "text_path": row.get("text_path"),
            }
            for row in imported_docs
        ],
    }
    report_path = PROCESSED / "manual_regulatory_import_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"imported={len(imported_docs)} resolved_gaps={len(resolved_now)} skipped={len(skipped)}")
    print(f"report={report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
