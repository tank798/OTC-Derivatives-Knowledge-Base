#!/usr/bin/env python3
"""Normalize document metadata after crawl/extraction passes."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

GENERIC_TITLES = {"", "目录页", "首页"}
BAD_PREFIXES = ("|", "English", "移动端", "微博", "微信", "无障碍")


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def infer_title_from_text(path: Path) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(BAD_PREFIXES):
            continue
        if len(line) > 160:
            line = line[:160]
        return line
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", default=str(PROCESSED / "documents.jsonl"))
    args = parser.parse_args()

    path = Path(args.documents)
    rows = list(iter_jsonl(path))
    updated = 0
    for row in rows:
        title = (row.get("title") or "").strip()
        if title not in GENERIC_TITLES:
            continue
        text_path = row.get("text_path")
        if not text_path:
            continue
        inferred = infer_title_from_text(ROOT / text_path)
        if inferred and inferred not in GENERIC_TITLES:
            row["title"] = inferred
            row["title_inferred"] = True
            updated += 1

    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)
    print(f"titles_updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

