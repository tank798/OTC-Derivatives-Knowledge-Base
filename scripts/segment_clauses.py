#!/usr/bin/env python3
"""Build clause-level chunks from crawled policy documents."""

import argparse
import json
from pathlib import Path
import re
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_SPLIT_RE = re.compile(r"(?=(第[一二三四五六七八九十百千万零〇两\d]+条))")
HEADING_RE = re.compile(r"^(第[一二三四五六七八九十百千万零〇两\d]+[章节编]|附[件录]|[一二三四五六七八九十]+、).{0,80}$")


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_by_size(text: str, max_chars: int = 1200, overlap: int = 160) -> List[str]:
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paras:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
            continue
        if current:
            chunks.append(current)
        if len(para) <= max_chars:
            current = para
        else:
            start = 0
            while start < len(para):
                chunks.append(para[start:start + max_chars])
                start += max_chars - overlap
            current = ""
    if current:
        chunks.append(current)
    return chunks


def split_articles(text: str) -> List[str]:
    parts = [p.strip() for p in ARTICLE_SPLIT_RE.split(text) if p.strip()]
    if len(parts) < 4:
        return []
    articles = []
    i = 0
    while i < len(parts):
        if re.match(r"^第[一二三四五六七八九十百千万零〇两\d]+条$", parts[i]) and i + 1 < len(parts):
            articles.append(parts[i] + parts[i + 1])
            i += 2
        else:
            i += 1
    return [a.strip() for a in articles if len(a.strip()) > 20]


def article_no(text: str) -> str:
    match = re.match(r"^(第[一二三四五六七八九十百千万零〇两\d]+条)", text)
    return match.group(1) if match else ""


def infer_heading_path(text: str) -> List[str]:
    headings = []
    for line in text.splitlines()[:20]:
        line = line.strip()
        if HEADING_RE.match(line):
            headings.append(line)
    return headings[-3:]


def build_clauses(doc: Dict) -> List[Dict]:
    text_path = doc.get("text_path")
    if not text_path:
        return []
    full_path = ROOT / text_path
    if not full_path.exists():
        return []
    text = clean_text(full_path.read_text(encoding="utf-8", errors="replace"))
    if not text:
        return []

    article_chunks = split_articles(text)
    chunks = article_chunks or chunk_by_size(text)
    rows = []
    for idx, chunk in enumerate(chunks, start=1):
        cid = f"{doc['doc_id']}_c{idx:04d}"
        rows.append({
            "clause_id": cid,
            "doc_id": doc["doc_id"],
            "source_id": doc.get("source_id"),
            "publisher": doc.get("publisher"),
            "title": doc.get("title"),
            "url": doc.get("url"),
            "retrieved_at": doc.get("retrieved_at"),
            "published_at": doc.get("published_at"),
            "authority_level": doc.get("authority_level"),
            "article_no": article_no(chunk),
            "heading_path": infer_heading_path(chunk),
            "text": chunk,
            "asset_classes": doc.get("asset_classes", []),
            "product_types": doc.get("product_types", []),
            "citation": {
                "title": doc.get("title"),
                "publisher": doc.get("publisher"),
                "url": doc.get("url"),
                "published_at": doc.get("published_at"),
                "retrieved_at": doc.get("retrieved_at")
            }
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    default_documents = ROOT / "data" / "processed" / "regulatory_documents.jsonl"
    if not default_documents.exists():
        default_documents = ROOT / "data" / "processed" / "documents.jsonl"
    parser.add_argument("--documents", default=str(default_documents))
    parser.add_argument("--out", default=str(ROOT / "data" / "processed" / "clauses.jsonl"))
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as out:
        for doc in iter_jsonl(Path(args.documents)):
            for clause in build_clauses(doc):
                out.write(json.dumps(clause, ensure_ascii=False, sort_keys=True) + "\n")
                count += 1
    print(f"clauses={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
