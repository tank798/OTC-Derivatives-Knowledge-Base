#!/usr/bin/env python3
"""Crawl Beijing Stock Exchange rule pages through a Playwright browser session."""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW_JSON = ROOT / "data" / "raw" / "html" / "bse"
RAW_TEXT = ROOT / "data" / "raw" / "text" / "bse"
BASE = "https://www.bse.cn"
DEFAULT_PWCLI = Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_space(value: str) -> str:
    value = value or ""
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ \u3000]+", " ", value)
    value = re.sub(r"\n[ \u3000]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def bse_doc_id(info_id: str) -> str:
    return f"bse_{info_id}"


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


def parse_date(value: str) -> str | None:
    if not value:
        return None
    match = re.search(r"(20\d{2})[-/年.](0?[1-9]|1[0-2])[-/月.](3[01]|[12]\d|0?[1-9])", value)
    if not match:
        return value[:10] if len(value) >= 10 else value
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def extract_labeled_date(text: str, label: str) -> str | None:
    pattern = rf"【{re.escape(label)}】\s*(20\d{{2}}[-/年.]\d{{1,2}}[-/月.]\d{{1,2}})"
    match = re.search(pattern, text)
    return parse_date(match.group(1)) if match else None


def extract_status(text: str) -> str:
    match = re.search(r"【时效性】\s*([^\n]+)", text)
    if match:
        return clean_space(match.group(1))
    if "征求意见" in text[:500]:
        return "draft"
    return "unknown"


def infer_asset_classes(title: str, category: str) -> List[str]:
    classes = []
    combined = f"{title} {category}"
    if any(token in combined for token in ("股票", "交易", "上市", "融资融券", "股份")):
        classes.append("equity")
    if "债券" in combined:
        classes.append("fixed_income")
    if not classes:
        classes.extend(["equity", "fixed_income"])
    return classes


def infer_product_types(title: str, category: str) -> List[str]:
    combined = f"{title} {category}"
    tags = []
    if "融资融券" in combined:
        tags.append("margin_financing_securities_lending")
    if "做市" in combined:
        tags.append("market_making")
    if "债券" in combined:
        tags.append("bond")
    if "适当性" in combined:
        tags.append("investor_suitability")
    if "交易" in combined:
        tags.append("equity_trading")
    if not tags:
        tags.append("exchange_rule")
    return tags


def gap_key(row: Dict) -> Tuple:
    return (row.get("source_id"), row.get("doc_id"), row.get("url"), row.get("gap_type"))


def browser_js(max_docs: int) -> str:
    return f"""
async (page) => {{
  const categories = [
    {{category: '法律', url: '{BASE}/rule/law_list.html'}},
    {{category: '行政法规及国务院文件', url: '{BASE}/rule/council_list.html'}},
    {{category: '司法解释', url: '{BASE}/rule/justice_list.html'}},
    {{category: '部门规章及规范性文件-证监会令', url: '{BASE}/rule/regulation_list.html'}},
    {{category: '部门规章及规范性文件-证监会公告', url: '{BASE}/rule/secnotice_list.html'}},
    {{category: '监管规则适用指引', url: '{BASE}/rule/guide_list.html'}},
    {{category: '业务规则-最新规则', url: '{BASE}/node/latestRule.html'}},
    {{category: '业务规则-股票-发行融资', url: '{BASE}/business/fxrz_list.html'}},
    {{category: '业务规则-股票-持续监管', url: '{BASE}/business/cxjg_list.html'}},
    {{category: '业务规则-股票-交易管理', url: '{BASE}/business/jygl_list.html'}},
    {{category: '业务规则-债券-发行融资', url: '{BASE}/business/fxrzzq_list.html'}},
    {{category: '业务规则-债券-持续监管', url: '{BASE}/business/cxjgzq_list.html'}},
    {{category: '业务规则-债券-交易管理', url: '{BASE}/business/jyglzq_list.html'}},
    {{category: '业务规则-市场管理', url: '{BASE}/business/scgl_list.html'}},
    {{category: '公开征求意见', url: '{BASE}/rule/public_opinion.html'}}
  ];
  const listFields = ['infoId','title','linkUrl','htmlUrl','publishDate','fileUrl'];
  const subFields = ['infoId','title','htmlUrl','metaDescription','subTitle','fileUrl','fileName','linkUrl','mlinkUrl','picURL','nodeId','p1','potenctLevel','publishDate'];
  const toAbs = (value) => {{
    if (!value) return '';
    if (/^https?:\\/\\//i.test(value)) return value;
    return '{BASE}' + (value.startsWith('/') ? value : '/' + value);
  }};
  const parseJsonp = (text) => {{
    const start = text.indexOf('(');
    const end = text.lastIndexOf(')');
    return JSON.parse(text.slice(start + 1, end));
  }};
  async function postJsonp(endpoint, data) {{
    return await page.evaluate(async (args) => {{
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(args.data)) {{
        if (Array.isArray(value)) {{
          for (const item of value) params.append(key + '[]', item);
        }} else {{
          params.set(key, value ?? '');
        }}
      }}
      const response = await fetch(args.endpoint + '?t=' + Math.random() + '&callback=cb', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}},
        body: params.toString()
      }});
      const text = await response.text();
      const start = text.indexOf('(');
      const end = text.lastIndexOf(')');
      return JSON.parse(text.slice(start + 1, end))[0];
    }}, {{
      endpoint,
      data
    }});
  }}
  async function listForCategory(category) {{
    await page.goto(category.url, {{waitUntil: 'networkidle', timeout: 45000}});
    const meta = await page.evaluate(() => ({{
      title: document.title,
      nodeId: document.querySelector('#nodeId')?.value || '',
      siteId: document.querySelector('#siteId')?.value || '6',
      dataType: document.querySelector('.getData')?.getAttribute('data-type') || '',
      pageText: document.body.innerText.slice(0, 1000)
    }}));
    const nodeId = meta.nodeId || meta.dataType;
    if (!nodeId) {{
      const fallbackItems = await page.evaluate(() => Array.from(document.querySelectorAll('a[infoid]')).map((a) => ({{
        infoId: a.getAttribute('infoid'),
        title: a.innerText.trim(),
        htmlUrl: a.getAttribute('href') || '',
        linkUrl: '',
        fileUrl: '',
        publishDate: (a.closest('li, tr, .main-show')?.innerText || '').match(/20\\d{{2}}[-/]\\d{{2}}[-/]\\d{{2}}/)?.[0] || ''
      }})));
      for (const row of fallbackItems) {{
        row.category = category.category;
        row.categoryUrl = category.url;
        row.apiNodeId = '';
      }}
      return {{category, meta, items: fallbackItems, error: fallbackItems.length ? '' : 'missing_node_id'}};
    }}
    const endpoint = meta.nodeId ? '/info/listseSub.do' : '/info/listse.do';
    const fields = meta.nodeId ? subFields : listFields;
    let pageNo = 0;
    let totalPages = 1;
    const items = [];
    do {{
      const result = await postJsonp(endpoint, {{
        page: String(pageNo),
        pageSize: '100',
        keywords: '',
        startTime: '',
        endTime: '',
        nodeIds: [nodeId],
        needFields: fields,
        siteId: meta.siteId
      }});
      if (!result.result) throw new Error('BSE API failed for ' + category.url);
      const data = result.data || {{}};
      for (const row of (data.content || [])) {{
        items.push({{...row, category: category.category, categoryUrl: category.url, apiNodeId: nodeId}});
      }}
      totalPages = data.totalPages || Math.ceil((data.totalElements || items.length) / 100) || 1;
      pageNo += 1;
    }} while (pageNo < totalPages);
    return {{category, meta, items}};
  }}
  const byId = new Map();
  const categoryResults = [];
  for (const category of categories) {{
    try {{
      const result = await listForCategory(category);
      categoryResults.push({{category: category.category, url: category.url, count: result.items.length, meta: result.meta, error: result.error || ''}});
      for (const item of result.items) {{
        const key = String(item.infoId || item.htmlUrl || item.fileUrl || item.title);
        if (!byId.has(key)) byId.set(key, item);
      }}
    }} catch (error) {{
      categoryResults.push({{category: category.category, url: category.url, count: 0, error: String(error)}});
    }}
  }}
  const selected = Array.from(byId.values()).slice(0, {max_docs});
  const docs = [];
  for (const item of selected) {{
    const htmlUrl = toAbs(item.linkUrl || item.htmlUrl);
    const fileUrl = toAbs(item.fileUrl);
    let article = {{url: htmlUrl || fileUrl, title: item.title || '', text: item.metaDescription || '', links: []}};
    if (htmlUrl) {{
      try {{
        await page.goto(htmlUrl, {{waitUntil: 'networkidle', timeout: 45000}});
        article = await page.evaluate(() => {{
          const candidates = ['.detail_content', '.TRS_Editor', '.article', '.content', '.main_content_center', '#zoom', 'body'];
          let el = null;
          for (const selector of candidates) {{
            const node = document.querySelector(selector);
            if (node && node.innerText && node.innerText.length > 200) {{ el = node; break; }}
          }}
          return {{
            url: location.href,
            title: document.title,
            text: (el || document.body).innerText,
            links: Array.from(document.querySelectorAll('a')).map(a => ({{text: a.innerText.trim(), href: a.href}})).filter(x => x.text || x.href).slice(0, 80)
          }};
        }});
      }} catch (error) {{
        article.error = String(error);
      }}
    }}
    docs.push({{item, article, fileUrl}});
  }}
  return JSON.stringify({{retrievedAt: new Date().toISOString(), categoryResults, documents: docs}});
}}
"""


def run_browser_extract(pwcli: Path, max_docs: int, timeout: int) -> Dict:
    open_cmd = [str(pwcli), "open", f"{BASE}/index.html"]
    subprocess.run(open_cmd, cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    run_cmd = [str(pwcli), "run-code", browser_js(max_docs)]
    result = subprocess.run(run_cmd, cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    match = re.search(r"### Result\s*\n(?P<payload>.*?)\n### Ran Playwright code", result.stdout, re.S)
    if not match:
        raise RuntimeError(f"Could not parse Playwright output:\n{result.stdout[:2000]}")
    payload = json.loads(match.group("payload").strip())
    return json.loads(payload) if isinstance(payload, str) else payload


def build_document(row: Dict, min_chars: int) -> Tuple[Dict, List[Dict]]:
    item = row["item"]
    article = row["article"]
    info_id = str(item.get("infoId") or hashlib.sha1((article.get("url") or item.get("title") or "").encode()).hexdigest()[:12])
    doc_id = bse_doc_id(info_id)
    title = clean_space(article.get("title") or item.get("title") or "")
    text = clean_space(article.get("text") or item.get("metaDescription") or "")
    article_url = article.get("url") or ""
    file_url = row.get("fileUrl") or ""

    RAW_JSON.mkdir(parents=True, exist_ok=True)
    RAW_TEXT.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_JSON / f"{doc_id}.json"
    text_path = RAW_TEXT / f"{doc_id}.txt"
    raw_path.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    text_path.write_text(text, encoding="utf-8")

    published_at = parse_date(item.get("publishDate") or "")
    effective_at = extract_labeled_date(text, "实施日期")
    if not published_at:
        published_at = extract_labeled_date(text, "发布日期")

    category = item.get("category") or ""
    body_read = len(text) >= min_chars
    doc = {
        "doc_id": doc_id,
        "source_id": "bse",
        "publisher": "北京证券交易所",
        "authority_level": "exchange_rule",
        "title": title,
        "url": article_url,
        "retrieved_at": now_iso(),
        "published_at": published_at,
        "effective_at": effective_at,
        "status": extract_status(text),
        "asset_classes": infer_asset_classes(title, category),
        "product_types": infer_product_types(title, category),
        "body_read": body_read,
        "raw_path": str(raw_path.relative_to(ROOT)),
        "text_path": str(text_path.relative_to(ROOT)),
        "content_type": "browser_dom",
        "bse_info_id": info_id,
        "bse_node_id": str(item.get("apiNodeId") or item.get("nodeId") or ""),
        "bse_category": category,
        "attachment_url": file_url,
    }
    gaps: List[Dict] = []
    if not body_read:
        gaps.append({
            "source_id": "bse",
            "doc_id": doc_id,
            "url": article_url,
            "retrieved_at": now_iso(),
            "gap_type": "bse_text_too_short",
            "reason": f"Extracted text length {len(text)} below {min_chars}",
            "body_read": False,
        })
    if article.get("error"):
        gaps.append({
            "source_id": "bse",
            "doc_id": doc_id,
            "url": article_url,
            "retrieved_at": now_iso(),
            "gap_type": "bse_article_browser_failed",
            "reason": article["error"],
            "body_read": False,
        })
    return doc, gaps


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pwcli", type=Path, default=DEFAULT_PWCLI)
    parser.add_argument("--max-docs", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--min-chars", type=int, default=80)
    args = parser.parse_args()

    extracted = run_browser_extract(args.pwcli, args.max_docs, args.timeout)
    documents_path = PROCESSED / "documents.jsonl"
    gaps_path = PROCESSED / "gaps.jsonl"
    documents = {row["doc_id"]: row for row in iter_jsonl(documents_path)}
    gaps = [
        row for row in iter_jsonl(gaps_path)
        if not (row.get("source_id") == "bse" and row.get("gap_type") in {"seed_fetch_failed", "bse_text_too_short", "bse_article_browser_failed"})
    ]
    gap_keys = {gap_key(row) for row in gaps}

    saved = 0
    short = 0
    for row in extracted.get("documents") or []:
        doc, row_gaps = build_document(row, args.min_chars)
        documents[doc["doc_id"]] = doc
        saved += 1
        if not doc.get("body_read"):
            short += 1
        for gap in row_gaps:
            if gap_key(gap) not in gap_keys:
                gaps.append(gap)
                gap_keys.add(gap_key(gap))

    RAW_JSON.mkdir(parents=True, exist_ok=True)
    (RAW_JSON / "bse_browser_crawl_summary.json").write_text(
        json.dumps({
            "retrieved_at": now_iso(),
            "category_results": extracted.get("categoryResults") or [],
            "saved_documents": saved,
            "short_documents": short,
        }, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_jsonl(documents_path, documents.values())
    write_jsonl(gaps_path, gaps)
    print(f"bse_saved={saved} short={short} categories={len(extracted.get('categoryResults') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
