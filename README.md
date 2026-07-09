# 金融监管法规知识库

目标：为证券公司金融创新/场外衍生品产品设计场景，建立一个可持续更新的中国金融监管法规知识库。

本项目按“官方源注册表 -> 原文归档 -> 文档级索引 -> 条款级切片 -> Wiki 层 -> RAG 检索”的方式组织，不把“全量”理解为一次性手工清单。

## 当前快照

- 文档级索引：9373 条
- 监管语料：9137 条
- 条款级切片：77494 条
- 已核验证据：41 条
- 附件元数据：124 条
- 待处理缺口：0 条
- 已解决缺口：9 条
- 手工补录官方 Word/PDF：29 个，已产出 2209 条条款切片

已专项补齐：国家法律法规数据库 8 部上位法、CSRC NERIS 7291 条元数据与重点正文、AMAC 490 条规则、SSE 728 条规则/历史规则、BSE 272 条规则/法律规则正文、中国货币网 124 个附件全文、NFRA 官方接口正文、CZCE 部分 WAF 页面浏览器正文抽取，以及 DCE/GFEX/CZCE/CSRC/BSE 的手工官方 Word/PDF 缺口。当前项目内 `data/processed/gaps.jsonl` 为空，已解决缺口记录见 `data/processed/resolved_gaps.jsonl`。

## 目录

- `data/registry/`: 官方源注册表、分类体系、检索种子。
- `data/raw/html/`: 抓取到的原始网页。
- `data/raw/pdf/`: 抓取到的 PDF 原文。
- `data/raw/text/`: 从网页/PDF 抽取的纯文本。
- `data/processed/`: 文档索引、条款切片、证据账本、缺口清单。
- `wiki/`: 给人看的 Obsidian/Wiki 层入口。
- `scripts/`: 抓取、索引、条款切分、Wiki 生成脚本。
- `docs/`: 项目规则、抓取策略和知识库设计说明。

`data/raw/` 默认作为本地缓存，不提交大体积原始网页和附件；但 `data/raw/files/manual_regulatory/` 与 `data/raw/text/manual_regulatory/` 保存手工补录的官方原件和抽取文本，随仓库保留。`data/processed/clauses.jsonl` 体积较大，使用 Git LFS 跟踪。

## 快速运行

```bash
python3 scripts/crawl_sources.py --registry data/registry/sources.json --max-per-source 30
python3 scripts/crawl_npc_law_api.py
python3 scripts/crawl_csrc_neris_api.py --workers 16 --detail-timeout 20
python3 scripts/hydrate_csrc_neris_local.py --keyword 衍生品 --keyword 场外 --keyword 期权 --keyword 证券公司 --keyword 私募 --keyword 基金 --keyword 资产管理 --keyword 适当性 --keyword 债券 --keyword 回购 --keyword 期货
python3 scripts/crawl_amac_policy_api.py --page-size 50 --max-pages 30
python3 scripts/crawl_sse_rules.py --no-download-attachments
python3 scripts/crawl_bse_rules_browser.py
python3 scripts/crawl_chinamoney_api.py
python3 scripts/crawl_nfra_api.py
python3 scripts/extract_pdfs.py
python3 scripts/retry_chinamoney_attachments.py --timeout 60
python3 scripts/extract_attachments.py
python3 scripts/ocr_pdf_gaps.py --min-chars 50
python3 scripts/retry_csrc_neris_gaps.py --workers 4 --detail-timeout 90 --min-chars 50
python3 scripts/import_manual_regulatory_files.py
python3 scripts/normalize_documents.py
python3 scripts/build_regulatory_corpus.py
python3 scripts/segment_clauses.py --documents data/processed/regulatory_documents.jsonl --out data/processed/clauses.jsonl
python3 scripts/build_wiki.py
```

第一次运行建议先小批量抓取，确认每个监管源的页面结构和反爬状态，再扩大 `--max-per-source`。

## 合规问答 Agent（P0 原型）

基于现有知识库数据的本地 RAG 合规问答系统，可自动识别产品结构、检索法规依据、生成带引用的合规判断。

### 快速开始

```bash
# 1. 安装依赖
corepack enable pnpm
corepack pnpm install

# 2. 配置 API key
cp apps/api/.env.example apps/api/.env
# 编辑 apps/api/.env，填入 DeepSeek API key：
#   LLM_API_KEY=sk-your-key-here
#   LLM_BASE_URL=https://api.deepseek.com
#   LLM_MODEL=deepseek-chat

# 3. 启动后端（端口 4000）
corepack pnpm dev:api

# 4. 启动前端（端口 3000，新终端窗口）
corepack pnpm dev:web
```

访问 http://localhost:3000，输入产品结构或合规问题即可。

### 技术栈

- Frontend: Next.js 15 + React 19 + Tailwind CSS
- Backend: NestJS + 内存检索索引（77,494 条条款 + 41 条证据）
- LLM: OpenAI-compatible API（默认 DeepSeek deepseek-chat）
- Monorepo: pnpm workspace

### 检索策略

1. `evidence_ledger.jsonl`（41 条已核验证据，权重最高）
2. `clauses.jsonl`（77,494 条条款切片，中文关键词扩展 + 效力层级加权）
3. 优先返回法律/行政法规/部门规章，再补充自律规则

### API 端点

- `GET /api/compliance/health` — 健康检查 + 索引统计
- `POST /api/compliance/query` — 合规问答

### 回答格式

所有回答遵循固定模板：结论 → 产品结构识别 → 法规依据（带链接）→ 限制条件 → 待补充信息 → 人工复核提示。

### 目录结构

```
apps/
  web/      Next.js 前端（工作台式 UI）
  api/      NestJS 后端
packages/
  shared/   共享类型、schema
  prompts/  Agent prompt 资产
```

## 当前原则

1. 只用官方源作为正式知识库依据；媒体、公众号、研报只能作为线索，不进入正式法规依据。
2. 每个法规文件必须保留原始 URL、发布主体、发布日期/生效日期、效力状态、正文读取状态。
3. 场外衍生品判断必须优先命中上位法、证监会规章、自律规则、交易场所/登记结算/银行间基础设施规则。
4. 条款级回答必须输出来源文件名、条号、原始链接和检索日期。
5. 无法抓取正文的源不伪装成已覆盖，进入 `data/processed/gaps.jsonl`。
