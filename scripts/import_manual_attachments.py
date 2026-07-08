#!/usr/bin/env python3
"""Import manually downloaded attachment files into the processed index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_FILES = ROOT / "data" / "raw" / "files" / "china_money"


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def attachment_suffix(att: Dict) -> str:
    for field in ("attachment_path", "attachment_name"):
        suffix = Path(str(att.get(field) or "")).suffix
        if suffix:
            return suffix
    return ".bin"


def expected_path(att: Dict) -> Path:
    return RAW_FILES / f"{att['attachment_id']}{attachment_suffix(att)}"


def looks_like_html_error(path: Path) -> bool:
    try:
        head = path.read_bytes()[:4096].decode("utf-8", errors="ignore").lower()
    except Exception:
        return False
    if "<html" not in head and "<!doctype html" not in head:
        return False
    return any(marker in head for marker in ["403", "访问错误", "forbidden", "request-id"])


def write_manifest(rows: List[Dict], manifest_path: Path) -> None:
    missing = [row for row in rows if not row.get("downloaded")]
    headers = [
        "attachment_id",
        "expected_local_path",
        "attachment_name",
        "parent_title",
        "download_url",
    ]
    lines = [",".join(headers)]
    for att in missing:
        values = [
            att.get("attachment_id", ""),
            str(expected_path(att).relative_to(ROOT)),
            att.get("attachment_name", ""),
            att.get("parent_title", ""),
            att.get("url") or att.get("download_url") or "",
        ]
        lines.append(",".join('"' + value.replace('"', '""') + '"' for value in values))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"manifest_missing={len(missing)} path={manifest_path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="data/processed/manual_downloads.csv",
        help="CSV path for the manual download manifest.",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Do not rewrite the manual download manifest.",
    )
    args = parser.parse_args()

    attachments_path = PROCESSED / "attachments.jsonl"
    attachments = list(iter_jsonl(attachments_path))
    RAW_FILES.mkdir(parents=True, exist_ok=True)

    imported = 0
    skipped_html = 0
    still_missing = 0
    for att in attachments:
        if att.get("source_id") != "china_money" or att.get("downloaded"):
            continue
        path = expected_path(att)
        if not path.exists() or path.stat().st_size == 0:
            still_missing += 1
            continue
        if looks_like_html_error(path):
            skipped_html += 1
            still_missing += 1
            continue
        att["downloaded"] = True
        att["local_path"] = str(path.relative_to(ROOT))
        att["text_extracted"] = False
        att.pop("download_error", None)
        att.pop("extract_error", None)
        att.pop("text_path", None)
        att.pop("text_char_count", None)
        imported += 1

    if imported:
        write_jsonl(attachments_path, attachments)
    if not args.no_manifest:
        write_manifest(attachments, ROOT / args.manifest)
    print(f"imported={imported} skipped_html={skipped_html} still_missing={still_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
