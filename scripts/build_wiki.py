#!/usr/bin/env python3
"""Generate Obsidian-friendly Wiki pages from registry and processed indexes."""

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
PROCESSED = ROOT / "data" / "processed"
REGISTRY = ROOT / "data" / "registry" / "sources.json"


def iter_jsonl(path: Path) -> Iterable[Dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_registry() -> Dict:
    with REGISTRY.open("r", encoding="utf-8") as f:
        return json.load(f)


def md_link(title: str, url: str) -> str:
    return f"[{title}]({url})" if url else title


def write_home(raw_docs_count: int, regulatory_docs_count: int, clauses_count: int, gaps_count: int) -> None:
    evidence_count = sum(1 for _ in iter_jsonl(PROCESSED / "evidence_ledger.jsonl"))
    today = dt.date.today().isoformat()
    text = f"""# 金融监管法规知识库

更新时间：{today}

## 当前状态

- 原始文档索引：{raw_docs_count} 条
- 监管语料索引：{regulatory_docs_count} 条
- 条款级切片：{clauses_count} 条
- 已核验证据：{evidence_count} 条
- 待处理缺口：{gaps_count} 条

## 入口

- [[监管源地图]]
- [[法规条目索引]]
- [[已核验证据账本]]
- [[条款级知识库说明]]
- [[场外衍生品合规检索框架]]
- [[抓取缺口清单]]

## 使用方式

做产品合规判断时，先从“场外衍生品合规检索框架”进入，再按产品资产类别和交易结构命中条款。任何结论都必须回链到原始法规 URL。
"""
    (WIKI / "Home.md").write_text(text, encoding="utf-8")


def write_sources(registry: Dict) -> None:
    lines = ["# 监管源地图", "", "| 来源 | 发布主体 | 等级 | 资产类别 | 产品类别 | 抓取备注 |", "|---|---|---|---|---|---|"]
    for source in registry.get("sources", []):
        lines.append(
            "| {source} | {publisher} | {level} | {assets} | {products} | {notes} |".format(
                source=md_link(source["source_id"], source.get("base_url", "")),
                publisher=source.get("publisher", ""),
                level=source.get("authority_level", ""),
                assets=", ".join(source.get("asset_classes", [])),
                products=", ".join(source.get("product_types", [])[:8]),
                notes=(source.get("crawl_notes", "") or "").replace("|", "/"),
            )
        )
    (WIKI / "监管源地图.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_docs_index(docs: list) -> None:
    by_source = collections.defaultdict(list)
    for doc in docs:
        by_source[doc.get("source_id", "unknown")].append(doc)

    lines = ["# 法规条目索引", ""]
    for source_id in sorted(by_source):
        lines.extend([f"## {source_id}", "", "| 标题 | 发布主体 | 发布日期 | 正文 | 原始链接 |", "|---|---|---:|---|---|"])
        for doc in sorted(by_source[source_id], key=lambda d: (d.get("published_at") or "", d.get("title") or ""), reverse=True):
            lines.append(
                "| {title} | {publisher} | {date} | {body} | {url} |".format(
                    title=(doc.get("title") or "").replace("|", "/")[:120],
                    publisher=doc.get("publisher") or "",
                    date=doc.get("published_at") or "",
                    body="已读" if doc.get("body_read") else "未读/目录/PDF",
                    url=md_link("原文", doc.get("url", "")),
                )
            )
        lines.append("")
    (WIKI / "法规条目索引.md").write_text("\n".join(lines), encoding="utf-8")


def write_evidence_ledger(evidence: list) -> None:
    by_source = collections.defaultdict(list)
    for row in evidence:
        by_source[row.get("source_id", "unknown")].append(row)

    lines = ["# 已核验证据账本", "", "这些条目来自官方源，并已区分正文、公告、附件是否核验。", ""]
    for source_id in sorted(by_source):
        lines.extend([f"## {source_id}", "", "| 文件 | 发布/生效 | 核验状态 | 关键标签 | 原文 |", "|---|---|---|---|---|"])
        for row in sorted(by_source[source_id], key=lambda r: (r.get("published_at") or "", r.get("title") or ""), reverse=True):
            date = row.get("published_at") or ""
            if row.get("effective_at"):
                date += f" / {row.get('effective_at')}"
            lines.append(
                "| {title} | {date} | {status} | {tags} | {url} |".format(
                    title=(row.get("title") or "").replace("|", "/")[:120],
                    date=date,
                    status=row.get("verification_status") or "",
                    tags=", ".join(row.get("tags", [])[:6]).replace("|", "/"),
                    url=md_link("原文", row.get("url", "")),
                )
            )
        lines.append("")
    (WIKI / "已核验证据账本.md").write_text("\n".join(lines), encoding="utf-8")


def write_clause_explainer(clauses_count: int) -> None:
    text = f"""# 条款级知识库说明

当前条款切片数量：{clauses_count}

## 条款来源

条款切片来自 `data/processed/clauses.jsonl`，每条都绑定：

- `clause_id`
- `doc_id`
- `title`
- `publisher`
- `article_no`
- `url`
- `retrieved_at`

## 检索规则

1. 先检索产品类型：场外期权、收益凭证、互换、远期、信用保护、回购、ABS、REITs、资管计划等。
2. 再检索监管动作：备案、准入、适当性、禁止、信息披露、净资本、风险控制、清算结算、跨境。
3. 命中条款后必须回到原文确认效力状态。

## 回答格式

```text
结论：
依据：
- 文件：
- 条款：
- 原文链接：
限制条件：
需人工复核：
```
"""
    (WIKI / "条款级知识库说明.md").write_text(text, encoding="utf-8")


def write_otc_framework() -> None:
    text = """# 场外衍生品合规检索框架

## 产品结构拆解

- 标的资产：股票、指数、债券、基金、商品、汇率、利率、信用。
- 交易结构：互换、远期、非标准化期权、组合结构、收益凭证、信用保护。
- 交易主体：证券公司、基金管理人、私募基金、银行、合格投资者、专业机构投资者。
- 交易场景：自营、代客、做市、风险管理、资管产品投资、跨境交易。

## 必查规则层级

1. 上位法：证券法、期货和衍生品法、证券投资基金法、公司法、信托法。
2. 部门规章：证监会、央行、金监总局、外汇局。
3. 自律规则：中证协、基金业协会、交易商协会。
4. 交易与结算规则：交易所、中证登、中债登、上清所、外汇交易中心。
5. 业务名单和备案：场外期权交易商名单、信用保护合约备案、私募/资管备案。

## 合规问题模板

- 这个产品的法律性质是什么，属于互换、远期、非标准化期权还是收益凭证？
- 发行/交易主体是否具备业务资格？
- 交易对手是否满足投资者适当性要求？
- 是否触发备案、报告、信息披露、集中清算或登记要求？
- 是否涉及跨境、外汇、银行间、基金投资范围或资管嵌套限制？
- 是否存在明确禁止性规定或监管窗口指导风险？
"""
    (WIKI / "场外衍生品合规检索框架.md").write_text(text, encoding="utf-8")


def write_gaps(gaps: list) -> None:
    lines = ["# 抓取缺口清单", "", "| 来源 | URL | 类型 | 原因 | 时间 |", "|---|---|---|---|---|"]
    for gap in gaps[-500:]:
        lines.append(
            "| {source} | {url} | {typ} | {reason} | {time} |".format(
                source=gap.get("source_id", ""),
                url=md_link("链接", gap.get("url", "")),
                typ=gap.get("gap_type", ""),
                reason=(gap.get("reason", "") or "").replace("|", "/")[:180],
                time=gap.get("retrieved_at", ""),
            )
        )
    (WIKI / "抓取缺口清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    WIKI.mkdir(parents=True, exist_ok=True)
    registry = load_registry()
    raw_docs = list(iter_jsonl(PROCESSED / "documents.jsonl"))
    docs = list(iter_jsonl(PROCESSED / "regulatory_documents.jsonl"))
    if not docs:
        docs = raw_docs
    clauses = list(iter_jsonl(PROCESSED / "clauses.jsonl"))
    gaps = list(iter_jsonl(PROCESSED / "gaps.jsonl"))
    evidence = list(iter_jsonl(PROCESSED / "evidence_ledger.jsonl"))

    write_home(len(raw_docs), len(docs), len(clauses), len(gaps))
    write_sources(registry)
    write_docs_index(docs)
    write_evidence_ledger(evidence)
    write_clause_explainer(len(clauses))
    write_otc_framework()
    write_gaps(gaps)
    print(f"wiki_pages=7 raw_docs={len(raw_docs)} regulatory_docs={len(docs)} clauses={len(clauses)} evidence={len(evidence)} gaps={len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
