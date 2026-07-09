#!/usr/bin/env python3
"""Extract downloaded attachments and add them as searchable documents."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Dict, Iterable, List, Optional
import zipfile
import xml.etree.ElementTree as ET


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


def remove_attachment_extract_gap(gaps: List[Dict], att: Dict) -> List[Dict]:
    return [
        row
        for row in gaps
        if not (
            row.get("gap_type") == "attachment_extract_failed"
            and row.get("source_id") == att.get("source_id")
            and row.get("doc_id") == att.get("attachment_id")
            and row.get("url") == att.get("url")
        )
    ]


def extract_pdf(path: Path) -> str:
    pdftotext = shutil.which("pdftotext") or "/opt/homebrew/bin/pdftotext"
    if Path(pdftotext).exists():
        result = subprocess.run(
            [pdftotext, "-layout", str(path), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        text = result.stdout.decode("utf-8", errors="replace").strip()
        if len(text) >= 80:
            return text
        ocr_text = extract_pdf_ocr(path)
        return ocr_text or text

    from pypdf import PdfReader
    reader = PdfReader(str(path))
    chunks: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def extract_pdf_ocr(path: Path) -> str:
    pdftoppm = shutil.which("pdftoppm") or "/Users/castle/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pdftoppm"
    tesseract = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    if not Path(pdftoppm).exists() or not Path(tesseract).exists():
        return ""
    chunks: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        prefix = str(Path(tmp) / "page")
        subprocess.run(
            [pdftoppm, "-r", "200", "-png", str(path), prefix],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for image in sorted(Path(tmp).glob("page-*.png")):
            result = subprocess.run(
                [tesseract, str(image), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            text = result.stdout.decode("utf-8", errors="replace").strip()
            if text:
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


def extract_xlsx(path: Path) -> str:
    chunks: List[str] = []
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    }
    with zipfile.ZipFile(path) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("main:si", ns):
                texts = [node.text or "" for node in si.findall(".//main:t", ns)]
                shared.append("".join(texts))
        for name in sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
            root = ET.fromstring(zf.read(name))
            rows: List[str] = []
            for row in root.findall(".//main:row", ns):
                cells: List[str] = []
                for cell in row.findall("main:c", ns):
                    value = cell.find("main:v", ns)
                    if value is None or value.text is None:
                        continue
                    text = value.text
                    if cell.get("t") == "s":
                        try:
                            text = shared[int(text)]
                        except Exception:
                            pass
                    cells.append(text)
                if cells:
                    rows.append("\t".join(cells))
            if rows:
                chunks.append(Path(name).stem + "\n" + "\n".join(rows))
    return "\n\n".join(chunks).strip()


def extract_xls(path: Path) -> str:
    text = extract_with_textutil(path)
    if len(text.strip()) >= 80:
        return text
    soffice_candidates = [
        "/opt/homebrew/bin/soffice",
        shutil.which("soffice") or "",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        last_error: Optional[Exception] = None
        for soffice in soffice_candidates:
            if not soffice or not Path(soffice).exists():
                continue
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "csv", "--outdir", str(tmp_path), str(path)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as exc:
                last_error = exc
                continue
            csv_path = tmp_path / f"{path.stem}.csv"
            if csv_path.exists():
                return csv_path.read_text(encoding="utf-8", errors="replace").strip()
        if last_error:
            raise last_error
    return text


def extract_zip(path: Path) -> str:
    chunks: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(path) as zf:
            for member in zf.infolist():
                if member.is_dir() or member.file_size == 0:
                    continue
                suffix = Path(member.filename).suffix.lower()
                if suffix not in {".pdf", ".doc", ".docx", ".rtf", ".txt", ".xls", ".xlsx"}:
                    continue
                target = tmp_path / Path(member.filename).name
                target.write_bytes(zf.read(member))
                text = extract_text(target)
                if text:
                    chunks.append(f"{member.filename}\n{text}")
    return "\n\n".join(chunks).strip()


def extract_text(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".xlsx":
        return extract_xlsx(path)
    if suffix == ".xls":
        return extract_xls(path)
    if suffix == ".zip":
        return extract_zip(path)
    if suffix in {".doc", ".docx", ".rtf", ".txt"}:
        return extract_with_textutil(path)
    return None


def is_html_error_page(path: Path) -> bool:
    try:
        head = path.read_bytes()[:4096].decode("utf-8", errors="ignore").lower()
    except Exception:
        return False
    if "<html" not in head and "<!doctype html" not in head:
        return False
    return any(marker in head for marker in ["403", "访问错误", "forbidden", "request-id"])


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
    html_error_keys = {
        (att.get("source_id"), att.get("attachment_id"), att.get("url"))
        for att in attachments
        if att.get("download_error") == "Downloaded HTML error page instead of attachment"
    }
    if html_error_keys:
        gaps = [
            row
            for row in gaps
            if not (
                row.get("gap_type") == "attachment_extract_failed"
                and (row.get("source_id"), row.get("doc_id"), row.get("url")) in html_error_keys
            )
        ]
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
        doc_id = f"attachment_{att['attachment_id']}"
        att.pop("extract_error", None)
        if is_html_error_page(source_path):
            failed += 1
            att["text_extracted"] = False
            att["downloaded"] = False
            att["download_error"] = "Downloaded HTML error page instead of attachment"
            att.pop("local_path", None)
            att.pop("text_path", None)
            att.pop("text_char_count", None)
            documents.pop(doc_id, None)
            gaps = [
                row
                for row in gaps
                if not (
                    row.get("gap_type") == "attachment_extract_failed"
                    and row.get("source_id") == att.get("source_id")
                    and row.get("doc_id") == att.get("attachment_id")
                    and row.get("url") == att.get("url")
                )
            ]
            gap_keys = {gap_key(row) for row in gaps}
            gap = {
                "source_id": att.get("source_id"),
                "doc_id": att.get("attachment_id"),
                "url": att.get("url"),
                "gap_type": "attachment_download_html_error",
                "reason": "Downloaded HTML error page instead of attachment",
                "body_read": False,
            }
            if gap_key(gap) not in gap_keys:
                gaps.append(gap)
                gap_keys.add(gap_key(gap))
            continue
        try:
            text = extract_text(source_path)
        except Exception as exc:
            text = None
            att["extract_error"] = repr(exc)
        if not text or len(text.strip()) < args.min_chars:
            failed += 1
            att["text_extracted"] = False
            att.pop("text_path", None)
            att.pop("text_char_count", None)
            documents.pop(doc_id, None)
            gaps = remove_attachment_extract_gap(gaps, att)
            gap_keys = {gap_key(row) for row in gaps}
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
        gaps = remove_attachment_extract_gap(gaps, att)
        gap_keys = {gap_key(row) for row in gaps}

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
