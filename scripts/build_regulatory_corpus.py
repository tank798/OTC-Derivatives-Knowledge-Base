#!/usr/bin/env python3
"""Build a cleaner regulatory corpus from crawled documents and evidence ledger."""

import json
from pathlib import Path
from typing import Dict, Iterable, Set


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

RULE_KEYWORDS = [
    "办法", "规定", "规则", "细则", "指引", "指南", "通知", "公告", "目录",
    "适当性", "衍生品", "场外", "期权", "互换", "远期", "收益凭证",
    "资管", "基金", "私募", "债券", "回购", "结算", "清算", "登记",
    "风险", "净资本", "信息披露", "备案", "跨境", "外汇", "反洗钱",
]

NOISE_KEYWORDS = [
    "主题演讲", "表彰大会", "专题党课", "圆桌会", "工作推进会",
    "新闻发布会", "立案调查", "虚假信息", "学习教育",
]


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def evidence_urls() -> Set[str]:
    urls = set()
    for row in iter_jsonl(PROCESSED / "evidence_ledger.jsonl"):
        if row.get("url"):
            urls.add(row["url"])
        if row.get("release_url"):
            urls.add(row["release_url"])
        if row.get("alt_url"):
            urls.add(row["alt_url"])
    return urls


def is_regulatory_document(doc: Dict, evidence_url_set: Set[str]) -> bool:
    url = doc.get("url", "")
    title = doc.get("title") or ""
    if url in evidence_url_set:
        return True
    if title == "目录页":
        return False
    if any(k in title for k in NOISE_KEYWORDS):
        return False
    return any(k in title or k in url for k in RULE_KEYWORDS)


def main() -> int:
    ev_urls = evidence_urls()
    rows = []
    for doc in iter_jsonl(PROCESSED / "documents.jsonl"):
        if is_regulatory_document(doc, ev_urls):
            rows.append(doc)

    out = PROCESSED / "regulatory_documents.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"regulatory_documents={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

