#!/usr/bin/env python3
"""Simple local keyword search over evidence and clause-level corpus."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def score_text(text: str, terms: List[str]) -> int:
    score = 0
    lower = text.lower()
    for term in terms:
        t = term.lower()
        score += lower.count(t) * max(1, len(t))
    return score


def preview(text: str, terms: List[str], width: int = 240) -> str:
    if not text:
        return ""
    lower = text.lower()
    positions = [lower.find(t.lower()) for t in terms if lower.find(t.lower()) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    return text[start:start + width].replace("\n", " ")


def search_evidence(terms: List[str], limit: int) -> List[Tuple[int, Dict]]:
    hits = []
    for row in iter_jsonl(PROCESSED / "evidence_ledger.jsonl"):
        text = " ".join([
            row.get("title", ""),
            row.get("support_scope", ""),
            " ".join(row.get("tags", [])),
            row.get("publisher", ""),
        ])
        score = score_text(text, terms)
        if score:
            hits.append((score, row))
    return sorted(hits, key=lambda x: x[0], reverse=True)[:limit]


def search_clauses(terms: List[str], limit: int) -> List[Tuple[int, Dict]]:
    hits = []
    for row in iter_jsonl(PROCESSED / "clauses.jsonl"):
        text = " ".join([row.get("title", ""), row.get("text", "")])
        score = score_text(text, terms)
        if score:
            hits.append((score, row))
    return sorted(hits, key=lambda x: x[0], reverse=True)[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Space-separated keyword query.")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    terms = [t for t in args.query.split() if t]

    print("# Evidence")
    for score, row in search_evidence(terms, args.limit):
        print(f"- [{score}] {row.get('title')} | {row.get('publisher')} | {row.get('verification_status')}")
        print(f"  {row.get('url')}")
        print(f"  {row.get('support_scope')}")

    print("\n# Clauses")
    for score, row in search_clauses(terms, args.limit):
        print(f"- [{score}] {row.get('title')} {row.get('article_no') or ''} | {row.get('publisher')}")
        print(f"  {row.get('url')}")
        print(f"  {preview(row.get('text', ''), terms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

