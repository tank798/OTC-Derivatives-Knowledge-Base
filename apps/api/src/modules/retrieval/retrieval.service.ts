import { Injectable, OnModuleInit } from "@nestjs/common";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import type { EvidenceEntry, ClauseEntry, RetrievalHit } from "@otc/shared";

// ────────── BM25 参数 ──────────
const BM25_K1 = 1.5;
const BM25_B = 0.75;
const CACHE_MAX_SIZE = 20;

// ────────── 中文分词的界定符 ──────────
const CJK_DELIMITERS = /[，。、；：！？（）【】《》""''「」『』\[\]\s\n\r\t]+/;

// ────────── 中文关键词扩展词典（增强版，含分类法映射） ──────────
const KEYWORD_EXPANSION: Record<string, string[]> = {
  "场外期权": ["非标准化期权", "OTC option", "场外衍生品", "期权交易商", "non_standard_option", "otc_derivative", "场外"],
  "收益互换": ["互换", "TRS", "总收益互换", "equity swap", "swap", "收益互换业务"],
  "互换": ["收益互换", "swap", "利率互换", "货币互换"],
  "收益凭证": ["证券公司收益凭证", "发行", "销售", "收益凭证业务", "income_certificate", "凭证"],
  "适当性": ["专业投资者", "合格投资者", "风险承受能力", "投资者适当性", "客户分类", "investor_suitability", "适配性"],
  "备案": ["报告", "登记", "交易报告库", "备案管理", "信息报送", "filing_registration", "reporting"],
  "净资本": ["风险资本", "资本约束", "风险控制指标", "净资本监管", "net_capital"],
  "衍生品": ["场外衍生品", "金融衍生品", "derivatives", "衍生工具", "otc_derivative"],
  "证券公司": ["券商", "证券经营机构", "securities company", "证券"],
  "跨境": ["跨境交易", "跨境投资", "QDII", "QFII", "RQFII", "互联互通", "外汇管理", "cross_border", "外汇"],
  "私募": ["私募基金", "私募投资基金", "私募产品", "private fund", "private_fund", "私募管理人"],
  "资管": ["资产管理", "资管计划", "资管产品", "集合资管", "定向资管", "asset_management_plan", "券商资管"],
  "期货": ["期货公司", "期货交易", "商品期货", "金融期货", "futures", "期货和衍生品法"],
  "风险揭示": ["风险披露", "风险告知", "风险提示", "风险说明书", "风险"],
  "保证金": ["履约保障", "保证金交易", "杠杆", "margin", "leverage_margin", "担保品"],
  "对冲": ["套期保值", "风险对冲", "hedge", "保值"],
  "交易商": ["衍生品交易商", "期权经营机构", "做市商", "dealer", "交易对手"],
  "投资者": ["客户", "委托人", "合格投资者", "专业投资者", "investor", "投资"],
  "结构化": ["结构化票据", "结构化产品", "structured_note", "结构"],
  "信用": ["信用保护", "信用风险缓释", "CRM", "CDS", "credit", "信用衍生品"],
  "回购": ["repo", "债券回购", "质押式回购", "逆回购"],
  "信息披露": ["披露", "报告", "信息披雳", "information_disclosure", "公示"],
  "杠杆": ["保证金", "杠杆交易", "margin", "杠杆率"],
  "场外": ["OTC", "场外交易", "柜台市场", "场外衍生品"],
  "远期": ["forward", "远期合约", "远期交易"],
  "债券": ["bond", "信用债", "利率债", "债券交易"],
  "商品": ["commodity", "大宗商品", "商品期货"],
  "外汇": ["fx", "fx_derivative", "外汇衍生品", "结售汇"],
  "做市": ["做市商", "market making", "流动性"],
  "禁止": ["prohibited_activity", "不得从事", "禁止行为", "违法违规"],
  "反洗钱": ["aml", "洗钱", "反洗钱规定"],
  "数据安全": ["data_security", "个人信息", "数据保护", "信息安全"],
  "销售": ["sales_marketing", "推介", "营销", "销售行为"],
  "结算": ["clearing_settlement", "清算", "交割", "结算规则"],
  "托管": ["custody", "托管人", "资产托管"],
  "估值": ["valuation", "定价", "公允价值"],
  "内控": ["internal_control", "内部控制", "风控制度"],
  "主权": ["地方政府", "政府债券", "sovereign", "国债"],
  "ETF": ["etf", "交易型开放式指数基金", "指数基金"],
  "REITs": ["reit", "不动产投资信托基金", "基础设施基金"],
  "ABS": ["abs", "资产支持证券", "资产证券化"],
  "利率": ["fixed_income", "利率风险", "基准利率"],
  "权益": ["equity", "股票", "股权"],
  "现金管理": ["cash_management", "流动性管理", "货币基金"],
  "跨资产": ["cross_asset", "多资产", "混合资产"],
  "合规": ["compliance", "合规管理", "合规要求"],
  "管理办法": ["管理", "监管", "规则", "规范"],
  "通知": ["通知", "规则", "文件", "要求"],
  "暂行": ["试行", "临时", "过渡", "暂行规定"],
  "投资者保护": ["投资者权益", "保护", "赔偿", "救济"],
  "杠杆融资": ["融资融券", "margin_financing_securities_lending", "证券借贷", "两融"],
  "股票质押": ["stock_pledge_repo", "质押回购", "股权质押"],
  "存托凭证": ["depositary", "CDR", "存托"],
  "利率互换": ["IRS", "interest rate swap", "利率掉期"],
  "信用违约": ["CDS", "信用违约互换", "credit default swap"],
  "财富管理": ["wealth_management", "理财", "财富"],
  "信托": ["trust_plan", "信托计划", "信托产品"],
  "资管新规": ["资产管理新规", "指导意见", "资管"],
};

// ────────── 中文 → 分类法术语映射 ──────────
const CHINESE_TO_TAXONOMY: Record<string, string[]> = {
  "场外期权": ["non_standard_option", "otc_derivative"],
  "互换": ["swap"],
  "收益互换": ["swap"],
  "远期": ["forward"],
  "结构化": ["structured_note"],
  "凭证": ["income_certificate"],
  "收益凭证": ["income_certificate"],
  "资管": ["asset_management_plan"],
  "私募": ["private_fund"],
  "公募": ["public_fund"],
  "期货": ["futures"],
  "期权": ["non_standard_option", "listed_option"],
  "信用风险缓释": ["crm"],
  "信用": ["credit", "cds"],
  "外汇": ["fx", "fx_derivative"],
  "债券": ["bond", "fixed_income"],
  "股票": ["equity"],
  "商品": ["commodity"],
  "跨境": ["cross_border"],
  "适当性": ["investor_suitability"],
  "备案": ["filing_registration", "reporting"],
  "信息披露": ["information_disclosure"],
  "风控": ["risk_control"],
  "净资本": ["net_capital"],
  "杠杆": ["leverage_margin", "margin"],
  "回购": ["repo"],
  "ABS": ["abs"],
  "REITs": ["reit"],
  "ETF": ["etf"],
  "利率": ["fixed_income"],
  "权益": ["equity"],
  "信用债": ["bond", "fixed_income", "credit"],
  "国债": ["bond", "fixed_income"],
  "融资融券": ["margin_financing_securities_lending"],
  "质押": ["stock_pledge_repo"],
  "存单": ["cash_management"],
  "现金管理": ["cash_management"],
  "跨资产": ["cross_asset"],
  "反洗钱": ["aml"],
  "数据": ["data_security"],
  "个人信息": ["personal_information"],
  "销售": ["sales_marketing"],
  "合同": ["contract_documentation"],
  "结算": ["clearing_settlement"],
  "托管": ["custody"],
  "估值": ["valuation"],
  "内控": ["internal_control"],
  "违约": ["default_disposal"],
  "利益冲突": ["conflict_of_interest"],
  "做市": ["trading_restriction"],
};

/**
 * 增强关键词扩展：结合 KEYWORD_EXPANSION 和分类法映射
 */
function expandKeywords(query: string, taxonomyTerms: string[] = []): string[] {
  const terms = new Set<string>([query]);

  // 从 KEYWORD_EXPANSION 扩展
  for (const [key, expansions] of Object.entries(KEYWORD_EXPANSION)) {
    if (query.includes(key) || query.includes(key.slice(0, 2))) {
      for (const ex of expansions) {
        terms.add(ex);
      }
    }
  }

  // 从分类法扩展
  for (const [chinese, taxonomyIds] of Object.entries(CHINESE_TO_TAXONOMY)) {
    if (query.includes(chinese) || query.includes(chinese.slice(0, 2))) {
      for (const t of taxonomyIds) {
        terms.add(t);
        taxonomyTerms.push(t);
      }
      // 同时加入该产品类型的英文描述作为搜索词
      for (const t of taxonomyIds) {
        terms.add(t.replace(/_/g, " "));
      }
    }
  }

  return [...terms];
}

/**
 * 中文分词：按界定符拆分 + 字符 bigram 提取
 */
function tokenizeText(text: string, includeBigrams: boolean): string[] {
  const terms: string[] = [];
  const words = text.split(CJK_DELIMITERS).filter((w) => w.length >= 2);

  for (const word of words) {
    terms.push(word);
    if (includeBigrams && word.length >= 2) {
      for (let i = 0; i < word.length - 1; i++) {
        terms.push(word.substring(i, i + 2));
      }
    }
  }

  return terms;
}

/**
 * 按 indexOf 循环统计子串出现次数
 */
function countSubstring(text: string, target: string): number {
  let count = 0;
  let idx = 0;
  while ((idx = text.indexOf(target, idx)) !== -1) {
    count++;
    idx += target.length;
  }
  return count;
}

/**
 * 计算 BM25 单项得分
 */
function computeBM25(
  freq: number,
  docLen: number,
  avgdl: number,
  totalDocs: number,
  docFreq: number,
): number {
  if (freq <= 0 || docFreq <= 0 || totalDocs <= 0) return 0;

  // 平均文档长度为 0 时的保护
  const effectiveAvgdl = avgdl > 0 ? avgdl : docLen;

  // IDF: log((N - n + 0.5) / (n + 0.5) + 1)
  const idf = Math.log((totalDocs - docFreq + 0.5) / (docFreq + 0.5) + 1);

  // TF with saturation: (k1+1)*freq / (freq + k1*(1-b + b*dl/avgdl))
  const tf =
    ((BM25_K1 + 1) * freq) /
    (freq + BM25_K1 * (1 - BM25_B + BM25_B * (docLen / effectiveAvgdl)));

  return idf * tf;
}

// ────────── 私有类型 ──────────
interface Posting {
  idx: number;
  freq: number;
}

interface CachedResult {
  results: RetrievalHit[];
  ts: number;
}

interface TaxonomyData {
  asset_classes: string[];
  product_types: string[];
  compliance_tags: string[];
  authority_levels: string[];
}

// ────────── Service ──────────
@Injectable()
export class RetrievalService implements OnModuleInit {
  // 原始数据
  private evidences: EvidenceEntry[] = [];
  private clauses: ClauseEntry[] = [];

  // ── 证据账本倒排索引 ──
  private evidenceIndex = new Map<string, Posting[]>(); // term → (idx, freq)
  private evidenceDocLengths: number[] = [];
  private evidenceAvgdl = 0;
  private evidenceN = 0;

  // ── 条款标题倒排索引 (word tokens + bigrams) ──
  private titleIndex = new Map<string, Posting[]>();
  private titleDocLengths: number[] = [];
  private titleAvgdl = 0;
  private titleN = 0;

  // ── 条款全文倒排索引 (word tokens only) ──
  private textIndex = new Map<string, Posting[]>();
  private textDocLengths: number[] = [];
  private textAvgdl = 0;
  private textN = 0;

  // ── 元数据索引 ──
  private authorityIndex = new Map<string, number[]>();
  private productTypeIndex = new Map<string, number[]>();
  private assetClassIndex = new Map<string, number[]>();
  private sourceIdIndex = new Map<string, number[]>();

  // ── 分类法数据 ──
  private taxonomy: TaxonomyData | null = null;

  // ── 标题搜索用的 keyword → clause index ──
  private clauseTitleKeywords = new Map<string, number[]>();

  // ── 缓存 ──
  private resultCache = new Map<string, CachedResult>();

  // ── 就绪标志 ──
  private ready = false;

  // ████ 生命周期 ████

  async onModuleInit() {
    await this.loadData();
  }

  get isReady(): boolean {
    return this.ready;
  }

  get stats(): { evidences: number; clauses: number } {
    return {
      evidences: this.evidences.length,
      clauses: this.clauses.length,
    };
  }

  // ████ 数据加载和索引构建 ████

  private findRepoRoot(): string {
    let dir = process.cwd();
    for (let i = 0; i < 10; i++) {
      if (existsSync(resolve(dir, "data/processed"))) return dir;
      const parent = resolve(dir, "..");
      if (parent === dir) break;
      dir = parent;
    }
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
    const startTime = Date.now();
    const repoRoot = this.findRepoRoot();
    const dataDir = resolve(repoRoot, "data/processed");
    const registryDir = resolve(repoRoot, "data/registry");
    console.log(`[Retrieval] dataDir=${dataDir}`);

    // ── 加载分类法 ──
    const taxonomyPath = resolve(registryDir, "taxonomy.json");
    if (existsSync(taxonomyPath)) {
      try {
        this.taxonomy = JSON.parse(readFileSync(taxonomyPath, "utf-8"));
        console.log(`[Retrieval] Loaded taxonomy: ${this.taxonomy?.product_types?.length ?? 0} product types`);
      } catch (e) {
        console.warn(`[Retrieval] Failed to load taxonomy: ${e}`);
      }
    }

    // ── 加载证据账本 ──
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

    // ── 加载条款 ──
    const clausesPath = resolve(dataDir, "clauses.jsonl");
    if (existsSync(clausesPath)) {
      const text = readFileSync(clausesPath, "utf-8");
      this.clauses = text
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => {
          try { return JSON.parse(l) as ClauseEntry; }
          catch { return null; }
        })
        .filter(Boolean) as ClauseEntry[];
      console.log(`[Retrieval] Loaded ${this.clauses.length} clause entries`);
    }

    // ── 构建倒排索引 ──
    this.buildIndices();

    const elapsed = Date.now() - startTime;
    console.log(`[Retrieval] Index build complete in ${elapsed}ms`);
    this.ready = true;
  }

  private buildIndices() {
    // ── 证据索引 ──
    const evStart = Date.now();
    for (let i = 0; i < this.evidences.length; i++) {
      const ev = this.evidences[i];
      const text = [
        ev.title ?? "",
        ev.support_scope ?? "",
        ...(ev.tags ?? []),
        ev.publisher ?? "",
      ]
        .filter(Boolean)
        .join(" ");

      const terms = tokenizeText(text, true); // evidence 使用 bigrams
      this.evidenceDocLengths[i] = text.length;
      const freqMap = new Map<string, number>();
      for (const term of terms) {
        freqMap.set(term, (freqMap.get(term) ?? 0) + 1);
      }
      for (const [term, freq] of freqMap) {
        const list = this.evidenceIndex.get(term);
        if (list) {
          list.push({ idx: i, freq });
        } else {
          this.evidenceIndex.set(term, [{ idx: i, freq }]);
        }
      }
    }
    this.evidenceN = this.evidences.length;
    this.evidenceAvgdl =
      this.evidenceN > 0
        ? this.evidenceDocLengths.reduce((a, b) => a + b, 0) / this.evidenceN
        : 0;
    console.log(
      `[Retrieval] Evidence index: ${this.evidenceIndex.size} unique terms, ${this.evidenceN} docs, avgdl=${this.evidenceAvgdl.toFixed(1)} (${Date.now() - evStart}ms)`,
    );

    // ── 条款标题索引 (含 heading_path) ──
    const titleStart = Date.now();
    for (let i = 0; i < this.clauses.length; i++) {
      const cl = this.clauses[i];

      // 标题 + heading_path 联合构建索引文本
      const headingText =
        cl.heading_path && cl.heading_path.length > 0
          ? cl.heading_path.join(" ")
          : "";
      const titleText = [cl.title ?? "", headingText].filter(Boolean).join(" ");

      const terms = tokenizeText(titleText, true); // 标题使用 bigrams
      this.titleDocLengths[i] = titleText.length;
      const freqMap = new Map<string, number>();
      for (const term of terms) {
        freqMap.set(term, (freqMap.get(term) ?? 0) + 1);
      }
      for (const [term, freq] of freqMap) {
        const list = this.titleIndex.get(term);
        if (list) {
          list.push({ idx: i, freq });
        } else {
          this.titleIndex.set(term, [{ idx: i, freq }]);
        }
      }

      // 同时构建 keyword → clause index 用于快速查找
      const titleWords = (cl.title ?? "")
        .split(CJK_DELIMITERS)
        .filter((w: string) => w.length >= 2);
      for (const w of titleWords) {
        const existing = this.clauseTitleKeywords.get(w) ?? [];
        if (existing.length < 200) {
          existing.push(i);
          this.clauseTitleKeywords.set(w, existing);
        }
      }
    }
    this.titleN = this.clauses.length;
    this.titleAvgdl =
      this.titleN > 0
        ? this.titleDocLengths.reduce((a, b) => a + b, 0) / this.titleN
        : 0;
    console.log(
      `[Retrieval] Title index: ${this.titleIndex.size} unique terms, ${this.titleN} docs, avgdl=${this.titleAvgdl.toFixed(1)} (${Date.now() - titleStart}ms)`,
    );

    // ── 条款全文索引 (仅 word tokens) ──
    const textStart = Date.now();
    for (let i = 0; i < this.clauses.length; i++) {
      const cl = this.clauses[i];
      const text = `${cl.title ?? ""} ${cl.text ?? ""}`;

      const terms = tokenizeText(text, false); // 全文不使用 bigrams（为了索引大小）
      this.textDocLengths[i] = text.length;
      const freqMap = new Map<string, number>();
      for (const term of terms) {
        freqMap.set(term, (freqMap.get(term) ?? 0) + 1);
      }
      // 去重后写入倒排索引
      for (const [term, freq] of freqMap) {
        const list = this.textIndex.get(term);
        if (list) {
          list.push({ idx: i, freq });
        } else {
          this.textIndex.set(term, [{ idx: i, freq }]);
        }
      }
    }
    this.textN = this.clauses.length;
    this.textAvgdl =
      this.textN > 0
        ? this.textDocLengths.reduce((a, b) => a + b, 0) / this.textN
        : 0;
    console.log(
      `[Retrieval] Text index: ${this.textIndex.size} unique terms, ${this.textN} docs, avgdl=${this.textAvgdl.toFixed(1)} (${Date.now() - textStart}ms)`,
    );

    // ── 元数据索引 ──
    const metaStart = Date.now();
    for (let i = 0; i < this.clauses.length; i++) {
      const cl = this.clauses[i];

      // authority index
      const auth = cl.authority_level ?? "unknown";
      const authList = this.authorityIndex.get(auth) ?? [];
      authList.push(i);
      this.authorityIndex.set(auth, authList);

      // product types index
      if (cl.product_types) {
        for (const pt of cl.product_types) {
          const ptList = this.productTypeIndex.get(pt) ?? [];
          ptList.push(i);
          this.productTypeIndex.set(pt, ptList);
        }
      }

      // asset classes index
      if (cl.asset_classes) {
        for (const ac of cl.asset_classes) {
          const acList = this.assetClassIndex.get(ac) ?? [];
          acList.push(i);
          this.assetClassIndex.set(ac, acList);
        }
      }

      // source_id index
      const sid = cl.source_id ?? "unknown";
      const sidList = this.sourceIdIndex.get(sid) ?? [];
      sidList.push(i);
      this.sourceIdIndex.set(sid, sidList);
    }
    console.log(
      `[Retrieval] Metadata indices built in ${Date.now() - metaStart}ms`,
    );
  }

  // ████ 公开搜索 API ████

  /**
   * 主搜索入口：多阶段 BM25 检索。
   *
   * 阶段 1：证据账本 BM25（2x 权重）
   * 阶段 2：条款标题 + heading_path BM25
   * 阶段 3：条款全文 BM25
   */
  search(
    query: string,
    options: {
      maxEvidence?: number;
      maxClauses?: number;
      maxTotal?: number;
    } = {},
  ): RetrievalHit[] {
    const maxEvidence = options.maxEvidence ?? 10;
    const maxClauses = options.maxClauses ?? 20;
    const maxTotal = options.maxTotal ?? 25;

    // 空查询保护
    if (!query || !query.trim()) return [];

    // ── 缓存命中 ──
    const cached = this.getCached(query);
    if (cached) return cached;

    // ── 查询扩展 ──
    const taxonomyTerms: string[] = [];
    const expanded = expandKeywords(query, taxonomyTerms);
    const expandedSet = new Set(expanded);

    // ── 生成查询词（word tokens + bigrams） ──
    const queryTerms = tokenizeText(query, true); // 查询时使用 bigrams 以提高召回率
    for (const ex of expandedSet) {
      const exTerms = tokenizeText(ex, true);
      for (const t of exTerms) {
        queryTerms.push(t);
      }
      // 同时保留原始扩展词
      if (ex.length >= 2) queryTerms.push(ex);
    }

    // 对查询词去重
    const uniqueQueryTerms = [...new Set(queryTerms)];
    if (uniqueQueryTerms.length === 0) return [];

    // ── 结果收集 ──
    const results: RetrievalHit[] = [];
    const seenClauseIds = new Set<string>(); // 避免相同 clause 在多阶段重复

    // ── 阶段 1：证据账本 BM25（2x 权重） ──
    const evCandidates = new Map<number, number>(); // idx → score
    for (const term of uniqueQueryTerms) {
      const postings = this.evidenceIndex.get(term);
      if (!postings) continue;
      const docFreqN = postings.length;
      for (const p of postings) {
        const bm25 = computeBM25(
          p.freq,
          this.evidenceDocLengths[p.idx] ?? 0,
          this.evidenceAvgdl,
          this.evidenceN,
          docFreqN,
        );
        if (bm25 > 0) {
          evCandidates.set(
            p.idx,
            (evCandidates.get(p.idx) ?? 0) + bm25,
          );
        }
      }
    }

    for (const [evIdx, score] of evCandidates) {
      if (evIdx >= this.evidences.length) continue;
      // 证据 2x boost
      const boostedScore = score * 2;
      if (boostedScore > 0) {
        const hit = this.evidenceToHit(
          this.evidences[evIdx],
          boostedScore,
          query,
        );
        results.push(hit);
      }
    }

    // ── 阶段 2：条款标题 + heading_path BM25 ──
    const titleCandidates = new Map<number, number>(); // clauseIdx → score
    for (const term of uniqueQueryTerms) {
      const postings = this.titleIndex.get(term);
      if (!postings) continue;
      const docFreqN = postings.length;
      for (const p of postings) {
        const bm25 = computeBM25(
          p.freq,
          this.titleDocLengths[p.idx] ?? 0,
          this.titleAvgdl,
          this.titleN,
          docFreqN,
        );
        if (bm25 > 0) {
          titleCandidates.set(
            p.idx,
            (titleCandidates.get(p.idx) ?? 0) + bm25,
          );
        }
      }
    }

    for (const [clIdx, score] of titleCandidates) {
      if (clIdx >= this.clauses.length) continue;
      const cl = this.clauses[clIdx];
      if (seenClauseIds.has(cl.clause_id)) continue;
      seenClauseIds.add(cl.clause_id);

      // 标题匹配加分（粗评分额外奖励）
      const authorityWeight = this.authorityWeight(cl.authority_level);
      const taxonomyBoost = this.computeTaxonomyBoost(cl, taxonomyTerms);
      const finalScore = score * authorityWeight * taxonomyBoost;

      const hit = this.clauseToHit(cl, finalScore, query);
      hit.matchReason = `标题+标题词命中 (BM25=${finalScore.toFixed(2)})`;
      results.push(hit);
    }

    // ── 阶段 3：条款全文 BM25 ──
    const textCandidates = new Map<number, number>();
    for (const term of uniqueQueryTerms) {
      const postings = this.textIndex.get(term);
      if (!postings) continue;
      const docFreqN = postings.length;
      for (const p of postings) {
        const bm25 = computeBM25(
          p.freq,
          this.textDocLengths[p.idx] ?? 0,
          this.textAvgdl,
          this.textN,
          docFreqN,
        );
        if (bm25 > 0) {
          textCandidates.set(
            p.idx,
            (textCandidates.get(p.idx) ?? 0) + bm25,
          );
        }
      }
    }

    for (const [clIdx, score] of textCandidates) {
      if (clIdx >= this.clauses.length) continue;
      const cl = this.clauses[clIdx];
      if (seenClauseIds.has(cl.clause_id)) continue;
      seenClauseIds.add(cl.clause_id);

      const authorityWeight = this.authorityWeight(cl.authority_level);
      const taxonomyBoost = this.computeTaxonomyBoost(cl, taxonomyTerms);
      const finalScore = score * authorityWeight * taxonomyBoost;

      if (finalScore > 0) {
        const hit = this.clauseToHit(cl, finalScore, query);
        hit.matchReason = `全文 BM25 (BM25=${finalScore.toFixed(2)})`;
        results.push(hit);
      }
    }

    // ── 排序（分数降序） ──
    results.sort((a, b) => b.score - a.score);

    // ── 按 title + excerpt 去重 ──
    const seen = new Set<string>();
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

    // ── 组合：证据优先，条款其次 ──
    const deduped = [...evidenceHits, ...clauseHits].slice(0, maxTotal);

    // ── 写入缓存 ──
    this.setCache(query, deduped);

    return deduped;
  }

  /**
   * 按标题部分匹配查找条款（用于 article_no 回填）
   */
  findClauseByTitle(
    titleKey: string,
  ): { articleNo: string; excerpt: string } | null {
    const key = titleKey.toLowerCase();

    // 先从 keyword 索引快速查找
    for (const [, indices] of this.clauseTitleKeywords) {
      for (const idx of indices) {
        const c = this.clauses[idx];
        if (
          c.article_no &&
          c.title?.toLowerCase().includes(key)
        ) {
          const normalized = c.article_no
            .replace(/^第/, "")
            .replace(/条$/, "");
          return {
            articleNo: normalized,
            excerpt: c.text.slice(0, 300),
          };
        }
      }
    }

    // 回退到线性扫描
    for (const c of this.clauses) {
      if (c.article_no && c.title?.toLowerCase().includes(key)) {
        const normalized = c.article_no
          .replace(/^第/, "")
          .replace(/条$/, "");
        return { articleNo: normalized, excerpt: c.text.slice(0, 300) };
      }
    }
    return null;
  }

  // ████ 私有辅助方法 ████

  /**
   * 计算分类法加权：如果查询涉及特定产品类型/资产类别，
   * 对该类条款给予额外加分
   */
  private computeTaxonomyBoost(
    cl: ClauseEntry,
    taxonomyTerms: string[],
  ): number {
    if (taxonomyTerms.length === 0) return 1.0;

    let boost = 1.0;

    // 产品类型匹配
    if (cl.product_types && cl.product_types.length > 0) {
      const matched = cl.product_types.filter((pt) =>
        taxonomyTerms.includes(pt),
      );
      if (matched.length > 0) {
        boost *= 1.3;
      }
    }

    // 资产类别匹配
    if (cl.asset_classes && cl.asset_classes.length > 0) {
      const matched = cl.asset_classes.filter((ac) =>
        taxonomyTerms.includes(ac),
      );
      if (matched.length > 0) {
        boost *= 1.15;
      }
    }

    return boost;
  }

  private authorityWeight(level?: string): number {
    switch (level) {
      case "law":
        return 5.0;
      case "administrative_regulation":
        return 4.5;
      case "department_rule":
        return 4.0;
      case "normative_doc":
        return 3.0;
      case "self_regulatory_rule":
        return 2.5;
      case "exchange_rule":
        return 2.0;
      case "business_guideline":
        return 1.5;
      default:
        return 1.0;
    }
  }

  private evidenceToHit(
    ev: EvidenceEntry,
    score: number,
    _query: string,
  ): RetrievalHit {
    return {
      source: "evidence",
      id: ev.evidence_id,
      title: ev.title,
      publisher: ev.publisher,
      url: ev.url,
      publishedAt: ev.published_at,
      effectiveAt: ev.effective_at,
      articleNo: "",
      text: ev.support_scope ?? "",
      excerpt: (ev.support_scope ?? "").slice(0, 300),
      score: Math.round(score * 100) / 100,
      authorityLevel: ev.authority_level ?? "",
      verificationStatus: ev.verification_status ?? "",
      matchReason: `证据账本命中 (2x 权重)`,
    };
  }

  private clauseToHit(
    cl: ClauseEntry,
    score: number,
    _query: string,
  ): RetrievalHit {
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

  // ████ 缓存 ████

  private getCached(query: string): RetrievalHit[] | null {
    const key = query.trim().toLowerCase();
    const entry = this.resultCache.get(key);
    if (entry) {
      // LRU: 删除后重新插入使其处于 Map 尾部
      this.resultCache.delete(key);
      this.resultCache.set(key, entry);
      return entry.results;
    }
    return null;
  }

  private setCache(query: string, results: RetrievalHit[]) {
    const key = query.trim().toLowerCase();

    // LRU 逐出：如果已存在则先删除后重新插入
    if (this.resultCache.has(key)) {
      this.resultCache.delete(key);
    } else if (this.resultCache.size >= CACHE_MAX_SIZE) {
      // 删除最旧的条目
      const oldest = this.resultCache.keys().next().value;
      if (oldest !== undefined) {
        this.resultCache.delete(oldest);
      }
    }

    this.resultCache.set(key, { results, ts: Date.now() });
  }
}
