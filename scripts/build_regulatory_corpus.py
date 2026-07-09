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
    "中国共产党", "中共中央", "中央八项规定", "八项规定", "党纪",
    "党建", "习近平", "违规吃喝", "民主生活会", "考试成绩查询",
    "培训学时查询", "投资者之家", "WEB 应用防火墙", "人员招录",
    "培训班", "考试", "成绩查询", "信息查询", "信息公示",
    "公开征求意见",
]

NAV_TITLES = {
    "目录页", "部门规章", "术语表", "网站地图", "无障碍浏览", "English Version",
    "新闻发布", "法律法规", "政策法规_国家外汇管理局门户网站", "综合", "基本法规",
    "行政许可", "其他", "欢迎您访问中国证券业协会网站", "自律规则",
    "法律规则", "法律", "行政法规", "司法解释", "证监会令", "证监会公告",
    "业务规则", "中国债券信息网", "Document", "债券信息披露", "债券", "清算会员",
}

NEWS_PREFIXES = (
    "中国证监会发布《",
    "中国证监会就",
    "中国证监会等",
)


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


def text_length(doc: Dict) -> int:
    text_path = doc.get("text_path")
    if not text_path:
        return 0
    path = ROOT / text_path
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="ignore").strip())


def is_regulatory_document(doc: Dict, evidence_url_set: Set[str]) -> bool:
    url = doc.get("url", "")
    title = (doc.get("title") or "").strip()
    source_id = doc.get("source_id", "")
    doc_id = doc.get("doc_id", "")
    if url in evidence_url_set:
        return True
    if title in NAV_TITLES:
        return False
    if any(k in title for k in NOISE_KEYWORDS):
        return False
    if any(title.startswith(prefix) for prefix in NEWS_PREFIXES):
        return False
    if source_id == "npc_law_db":
        return True
    if source_id == "csrc" and doc_id.startswith("csrc_neris_"):
        return True
    if source_id == "sse" and doc_id.startswith("sse_rules_"):
        return True
    if source_id == "amac" and doc_id.startswith("amac_policy_"):
        return True
    if source_id in {"bse", "czce", "dce", "gfex"} and doc.get("body_read"):
        return True
    if source_id in {"shfe", "ine"}:
        return False
    if not doc.get("body_read") and text_length(doc) < 120:
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
