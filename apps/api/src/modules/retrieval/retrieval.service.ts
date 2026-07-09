import { Injectable, OnModuleInit } from "@nestjs/common";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import type { EvidenceEntry, ClauseEntry, RetrievalHit } from "@otc/shared";

// ────────── 中文关键词扩展词典 ──────────
const KEYWORD_EXPANSION: Record<string, string[]> = {
  "场外期权": ["非标准化期权", "OTC option", "场外衍生品", "期权交易商"],
  "收益互换": ["互换", "收益互换", "TRS", "总收益互换", "equity swap"],
  "收益凭证": ["证券公司收益凭证", "发行", "销售", "收益凭证业务"],
  "适当性": ["专业投资者", "合格投资者", "风险承受能力", "投资者适当性", "客户分类"],
  "备案": ["报告", "登记", "交易报告库", "备案管理", "信息报送"],
  "净资本": ["风险资本", "资本约束", "风险控制指标", "净资本监管"],
  "衍生品": ["场外衍生品", "金融衍生品", "derivatives", "衍生工具"],
  "证券公司": ["券商", "证券经营机构", "securities company"],
  "跨境": ["跨境交易", "跨境投资", "QDII", "QFII", "RQFII", "互联互通", "外汇管理"],
  "私募": ["私募基金", "私募投资基金", "私募产品", "private fund"],
  "资管": ["资产管理", "资管计划", "资管产品", "集合资管", "定向资管"],
  "期货": ["期货公司", "期货交易", "商品期货", "金融期货", "futures"],
  "风险揭示": ["风险披露", "风险告知", "风险提示", "风险说明书"],
  "保证金": ["履约保障", "保证金交易", "杠杆", "margin"],
  "对冲": ["套期保值", "风险对冲", "hedge"],
  "交易商": ["衍生品交易商", "期权经营机构", "做市商", "dealer"],
  "投资者": ["客户", "委托人", "合格投资者", "专业投资者", "investor"],
};

function expandKeywords(query: string): string[] {
  const terms = [query];
  for (const [key, expansions] of Object.entries(KEYWORD_EXPANSION)) {
    if (query.includes(key) || query.includes(key.slice(0, 2))) {
      terms.push(...expansions);
    }
  }
  return [...new Set(terms)];
}

// ────────── 评分 ──────────
function scoreText(text: string, terms: string[]): number {
  const lower = text.toLowerCase();
  let score = 0;
  for (const term of terms) {
    const lowerTerm = term.toLowerCase();
    let idx = 0;
    while ((idx = lower.indexOf(lowerTerm, idx)) !== -1) {
      score += Math.max(1, term.length);
      idx += lowerTerm.length;
    }
  }
  return score;
}

@Injectable()
export class RetrievalService implements OnModuleInit {
  private evidences: EvidenceEntry[] = [];
  private clauses: ClauseEntry[] = [];
  private clauseIndex: Map<string, ClauseEntry[]> = new Map(); // keyword → clauses
  private ready = false;

  async onModuleInit() {
    await this.loadData();
  }

  get isReady(): boolean {
    return this.ready;
  }

  get stats(): { evidences: number; clauses: number } {
    return { evidences: this.evidences.length, clauses: this.clauses.length };
  }

  private findRepoRoot(): string {
    // Walk up from cwd until we find data/processed directory
    let dir = process.cwd();
    for (let i = 0; i < 10; i++) {
      if (existsSync(resolve(dir, "data/processed"))) return dir;
      const parent = resolve(dir, "..");
      if (parent === dir) break;
      dir = parent;
    }
    // Fallback: try resolving from __dirname
    dir = __dirname;
    for (let i = 0; i < 10; i++) {
      if (existsSync(resolve(dir, "data/processed"))) return dir;
      const parent = resolve(dir, "..");
      if (parent === dir) break;
      dir = parent;
    }
    throw new Error("Cannot find repo root (data/processed not found)");
  }

  private loadData() {
    const repoRoot = this.findRepoRoot();
    const dataDir = resolve(repoRoot, "data/processed");
    console.log(`[Retrieval] dataDir=${dataDir}`);

    // Load evidence ledger
    const evidencePath = resolve(dataDir, "evidence_ledger.jsonl");
    if (existsSync(evidencePath)) {
      const text = readFileSync(evidencePath, "utf-8");
      this.evidences = text
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => {
          try { return JSON.parse(l) as EvidenceEntry; }
          catch { return null; }
        })
        .filter(Boolean) as EvidenceEntry[];
      console.log(`[Retrieval] Loaded ${this.evidences.length} evidence entries`);
    }

    // Load clauses & build simple keyword index
    const clausesPath = resolve(dataDir, "clauses.jsonl");
    if (existsSync(clausesPath)) {
      const text = readFileSync(clausesPath, "utf-8");
      const raw = text
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => {
          try { return JSON.parse(l) as ClauseEntry; }
          catch { return null; }
        })
        .filter(Boolean) as ClauseEntry[];

      this.clauses = raw;
      console.log(`[Retrieval] Loaded ${this.clauses.length} clause entries`);

      // Build a lightweight keyword index from title words
      for (const c of this.clauses) {
        const titleWords = c.title?.split(/[，,、\s]+/).filter((w: string) => w.length >= 2) ?? [];
        for (const w of titleWords) {
          const existing = this.clauseIndex.get(w) ?? [];
          if (existing.length < 200) { // cap per keyword
            existing.push(c);
            this.clauseIndex.set(w, existing);
          }
        }
      }
      console.log(`[Retrieval] Indexed ${this.clauseIndex.size} title keywords`);
    }

    this.ready = true;
  }

  /** Main search: returns ranked hits from evidence + clauses. */
  search(
    query: string,
    options: { maxEvidence?: number; maxClauses?: number; maxTotal?: number } = {}
  ): RetrievalHit[] {
    const maxEvidence = options.maxEvidence ?? 10;
    const maxClauses = options.maxClauses ?? 20;
    const maxTotal = options.maxTotal ?? 25;
    const terms = expandKeywords(query);

    const results: RetrievalHit[] = [];

    // 1. Search evidence (highest weight)
    for (const ev of this.evidences) {
      const searchText = [ev.title, ev.support_scope, ...(ev.tags ?? []), ev.publisher]
        .filter(Boolean)
        .join(" ");
      const baseScore = scoreText(searchText, terms);
      if (baseScore === 0) continue;
      // Evidence gets a moderate boost over clauses
      const score = baseScore * 1.5;
      results.push(this.evidenceToHit(ev, score, query));
    }

    // 2. Search clauses
    // First, try keyword-indexed lookup
    const indexedClauses = new Set<ClauseEntry>();
    for (const term of terms) {
      const entries = this.clauseIndex.get(term);
      if (entries) {
        for (const c of entries.slice(0, 100)) {
          indexedClauses.add(c);
        }
      }
    }

    // If indexed search found enough, use those; otherwise do a broader scan
    const clausePool = indexedClauses.size >= 50
      ? [...indexedClauses]
      : this.clauses.slice(0, 20000); // scan first 20k clauses as fallback

    for (const cl of clausePool) {
      const searchText = `${cl.title} ${cl.text}`.slice(0, 3000); // limit per clause
      const baseScore = scoreText(searchText, terms);
      if (baseScore <= 0) continue;

      // Weight by authority level
      const authorityWeight = this.authorityWeight(cl.authority_level);
      const score = baseScore * authorityWeight;
      results.push(this.clauseToHit(cl, score, query));
    }

    // Sort by score descending
    results.sort((a, b) => b.score - a.score);

    // Deduplicate by title + excerpt
    const seen = new Set<string>();
    const deduped: RetrievalHit[] = [];
    const evidenceHits: RetrievalHit[] = [];
    const clauseHits: RetrievalHit[] = [];

    for (const r of results) {
      const key = `${r.title}|${r.excerpt.slice(0, 80)}`;
      if (seen.has(key)) continue;
      seen.add(key);

      if (r.source === "evidence" && evidenceHits.length < maxEvidence) {
        evidenceHits.push(r);
      } else if (r.source === "clause" && clauseHits.length < maxClauses) {
        clauseHits.push(r);
      }
    }

    // Combine: evidence first, then clauses
    deduped.push(...evidenceHits, ...clauseHits);
    return deduped.slice(0, maxTotal);
  }

  /** Find a clause by partial title match (for article_no backfill). */
  findClauseByTitle(titleKey: string): { articleNo: string; excerpt: string } | null {
    const key = titleKey.toLowerCase();
    for (const c of this.clauses) {
      if (c.article_no && c.title?.toLowerCase().includes(key)) {
        // Normalize: strip 第/条 prefix/suffix for consistent display
        const normalized = c.article_no.replace(/^第/, "").replace(/条$/, "");
        return { articleNo: normalized, excerpt: c.text.slice(0, 300) };
      }
    }
    return null;
  }

  private authorityWeight(level?: string): number {
    switch (level) {
      case "law": return 5.0;
      case "administrative_regulation": return 4.5;
      case "department_rule": return 4.0;
      case "normative_doc": return 3.0;
      case "self_regulatory_rule": return 2.5;
      case "exchange_rule": return 2.0;
      case "business_guideline": return 1.5;
      default: return 1.0;
    }
  }

  private evidenceToHit(ev: EvidenceEntry, score: number, _query: string): RetrievalHit {
    return {
      source: "evidence",
      id: ev.evidence_id,
      title: ev.title,
      publisher: ev.publisher,
      url: ev.url,
      publishedAt: ev.published_at,
      effectiveAt: ev.effective_at,
      articleNo: "",
      text: ev.support_scope,
      excerpt: ev.support_scope.slice(0, 300),
      score: Math.round(score * 100) / 100,
      authorityLevel: ev.authority_level,
      verificationStatus: ev.verification_status,
      matchReason: `证据账本命中: ${ev.support_scope.slice(0, 80)}...`,
    };
  }

  private clauseToHit(cl: ClauseEntry, score: number, _query: string): RetrievalHit {
    return {
      source: "clause",
      id: cl.clause_id,
      title: cl.title,
      publisher: cl.publisher ?? "",
      url: cl.url ?? "",
      publishedAt: cl.published_at ?? "",
      effectiveAt: "",
      articleNo: cl.article_no ?? "",
      text: cl.text,
      excerpt: cl.text.slice(0, 300),
      score: Math.round(score * 100) / 100,
      authorityLevel: cl.authority_level ?? "",
      verificationStatus: "",
      matchReason: "",
    };
  }
}
