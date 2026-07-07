# 金融监管法规知识库

目标：为证券公司金融创新/场外衍生品产品设计场景，建立一个可持续更新的中国金融监管法规知识库。

本项目按“官方源注册表 -> 原文归档 -> 文档级索引 -> 条款级切片 -> Wiki 层 -> RAG 检索”的方式组织，不把“全量”理解为一次性手工清单。

## 目录

- `data/registry/`: 官方源注册表、分类体系、检索种子。
- `data/raw/html/`: 抓取到的原始网页。
- `data/raw/pdf/`: 抓取到的 PDF 原文。
- `data/raw/text/`: 从网页/PDF 抽取的纯文本。
- `data/processed/`: 文档索引、条款切片、证据账本、缺口清单。
- `wiki/`: 给人看的 Obsidian/Wiki 层入口。
- `scripts/`: 抓取、索引、条款切分、Wiki 生成脚本。
- `docs/`: 项目规则、抓取策略和知识库设计说明。

## 快速运行

```bash
python3 scripts/crawl_sources.py --registry data/registry/sources.json --max-per-source 30
python3 scripts/segment_clauses.py --documents data/processed/documents.jsonl --out data/processed/clauses.jsonl
python3 scripts/build_wiki.py
```

第一次运行建议先小批量抓取，确认每个监管源的页面结构和反爬状态，再扩大 `--max-per-source`。

## 当前原则

1. 只用官方源作为正式知识库依据；媒体、公众号、研报只能作为线索，不进入正式法规依据。
2. 每个法规文件必须保留原始 URL、发布主体、发布日期/生效日期、效力状态、正文读取状态。
3. 场外衍生品判断必须优先命中上位法、证监会规章、自律规则、交易场所/登记结算/银行间基础设施规则。
4. 条款级回答必须输出来源文件名、条号、原始链接和检索日期。
5. 无法抓取正文的源不伪装成已覆盖，进入 `data/processed/gaps.jsonl`。

