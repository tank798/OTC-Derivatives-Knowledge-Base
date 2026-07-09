import { Injectable } from "@nestjs/common";
import { LlmService } from "../llm/llm.service";
import { RetrievalService } from "../retrieval/retrieval.service";
import { PromptService } from "../prompt/prompt.service";
import type { ComplianceAnswer, ProductStructure, RetrievalHit } from "@otc/shared";

// ────────── SSE event types for streaming ──────────
export type SSEEvent =
  | { type: "thinking"; message: string }
  | { type: "retrieving"; count: number }
  | { type: "product_structure"; data: ProductStructure }
  | { type: "answer_chunk"; content: string }
  | { type: "answer"; data: ComplianceAnswer }
  | { type: "hits"; hits: RetrievalHit[] }
  | { type: "error"; message: string }
  | { type: "done" };

@Injectable()
export class ComplianceService {
  constructor(
    private readonly llm: LlmService,
    private readonly retrieval: RetrievalService,
    private readonly prompt: PromptService,
  ) {}

  // ────────── Non-streaming entry point ──────────

  async answer(query: string): Promise<{
    answer: ComplianceAnswer;
    hits: RetrievalHit[];
  }> {
    const productStructure = await this.parseProductStructure(query);
    const hits = this.retrieval.search(query);
    const answer = await this.generateAnswer(query, productStructure, hits);

    // Compute and attach confidence score
    const confidence = this.computeConfidenceScore(hits, answer);
    answer.confidenceScore = confidence.score;
    answer.confidenceReason = confidence.reason;

    return { answer, hits };
  }

  // ────────── Streaming entry point ──────────

  async *answerStream(query: string): AsyncGenerator<SSEEvent, void, unknown> {
    try {
      // Step 1: Product structure analysis
      yield { type: "thinking", message: "正在分析产品结构..." };
      let structure: ProductStructure;
      try {
        structure = await this.parseProductStructure(query);
      } catch (err) {
        yield { type: "error", message: "产品结构分析失败：" + (err instanceof Error ? err.message : "未知错误") };
        return;
      }
      yield { type: "product_structure", data: structure };

      // Step 2: Retrieval
      yield { type: "thinking", message: "正在检索相关法规条文..." };
      let hits: RetrievalHit[];
      try {
        hits = this.retrieval.search(query);
      } catch (err) {
        yield { type: "error", message: "法规检索失败：" + (err instanceof Error ? err.message : "未知错误") };
        return;
      }
      yield { type: "retrieving", count: hits.length };
      yield { type: "hits", hits };

      // Step 3: Stream-generated compliance answer
      yield { type: "thinking", message: "正在生成合规分析报告..." };

      const agentPrompt = this.prompt.getComplianceAgentPrompt();
      const userPrompt = this.buildUserPrompt(query, structure, hits);

      let fullText = "";
      try {
        for await (const chunk of this.llm.streamChat(agentPrompt, userPrompt, 180000)) {
          fullText += chunk;
          yield { type: "answer_chunk", content: chunk };
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "未知错误";
        yield { type: "error", message: "合规分析生成失败：" + message };
        return;
      }

      // Step 4: Parse the answer into structured format
      let answer: ComplianceAnswer;
      try {
        answer = this.parseComplianceAnswer(fullText, structure, hits);
      } catch (err) {
        yield { type: "error", message: "答案解析失败：" + (err instanceof Error ? err.message : "未知错误") };
        return;
      }

      // Step 5: Compute confidence score
      const confidence = this.computeConfidenceScore(hits, answer);
      answer.confidenceScore = confidence.score;
      answer.confidenceReason = confidence.reason;

      yield { type: "answer", data: answer };
    } catch (err) {
      const message = err instanceof Error ? err.message : "合规分析过程中发生未知错误";
      console.error("[Compliance/answerStream]", err);
      yield { type: "error", message };
    } finally {
      yield { type: "done" };
    }
  }

  // ────────── Product Structure Extraction ──────────

  private async parseProductStructure(query: string): Promise<ProductStructure> {
    try {
      const systemPrompt = `你是一个金融产品结构分析专家。分析用户描述中的金融产品，提取结构信息。
严格按照 JSON 格式输出，不要包含 markdown 代码块标记、不要加注释、不要加额外说明文字。`;

      const userPrompt = `分析以下金融产品描述，提取结构要素。仅输出一个 JSON 对象，不要添加任何其他文字：

{
  "underlyingAsset": "标的资产（如：沪深300指数、中证500指数、某个股、国债、商品期货等）",
  "productType": "产品类型（如：场外期权、收益互换、收益凭证、资管计划、私募基金、收益凭证等）",
  "transactionStructure": "交易结构细节（如：香草看涨、看跌价差、雪球结构、鲨鱼鳍、Airbag、DNT等）",
  "counterparty": "交易对手方（如：证券公司、银行、私募基金、一般企业、自然人等）",
  "investorType": "投资者类型（如：专业机构投资者、合格投资者、普通个人投资者、未说明等）",
  "isCrossBorder": false,
  "riskPoints": ["识别到的风险点1"],
  "missingInfo": ["识别到但用户未提供的关键信息1"]
}

规则：
- 如果某项信息在用户描述中未体现，填入空字符串或空数组，不要编造
- isCrossBorder 根据是否提到境外标的、境外对手方或跨境资金流动判断
- riskPoints 从标的波动、杠杆、对手方信用、流动性、跨境合规等维度识别
- missingInfo 列出做出合规判断所需但未提供的其他关键信息

用户问题：${query}`;

      const text = await this.llm.chat(systemPrompt, userPrompt, 30000);
      const cleaned = text
        .replace(/```(?:json)?\s*/gi, "")
        .replace(/```\s*/g, "")
        .trim();

      // Try to find a JSON object in the response if exact parsing fails
      const jsonStart = cleaned.indexOf("{");
      const jsonEnd = cleaned.lastIndexOf("}");
      const jsonStr = jsonStart !== -1 && jsonEnd !== -1 ? cleaned.slice(jsonStart, jsonEnd + 1) : cleaned;

      const parsed = JSON.parse(jsonStr);

      return {
        underlyingAsset: String(parsed.underlyingAsset ?? parsed.underlying_asset ?? ""),
        productType: String(parsed.productType ?? parsed.product_type ?? ""),
        transactionStructure: String(parsed.transactionStructure ?? parsed.transaction_structure ?? parsed.tradeStructure ?? ""),
        counterparty: String(parsed.counterparty ?? parsed.counterparty ?? ""),
        investorType: String(parsed.investorType ?? parsed.investor_type ?? ""),
        isCrossBorder: Boolean(parsed.isCrossBorder ?? parsed.is_cross_border ?? false),
        riskPoints: Array.isArray(parsed.riskPoints ?? parsed.risk_points ?? [])
          ? (parsed.riskPoints ?? parsed.risk_points ?? [])
          : [],
        missingInfo: Array.isArray(parsed.missingInfo ?? parsed.missing_info ?? [])
          ? (parsed.missingInfo ?? parsed.missing_info ?? [])
          : [],
      };
    } catch (err) {
      console.warn("[Compliance] Product structure parsing failed, using defaults:", err);
      return {
        underlyingAsset: "",
        productType: "",
        transactionStructure: "",
        counterparty: "",
        investorType: "",
        isCrossBorder: false,
        riskPoints: [],
        missingInfo: [],
      };
    }
  }

  // ────────── Prompt Assembly ──────────

  private buildUserPrompt(
    query: string,
    structure: ProductStructure,
    hits: RetrievalHit[],
  ): string {
    const structureText = [
      "- 标的资产: " + (structure.underlyingAsset || "未识别"),
      "- 产品类型: " + (structure.productType || "未识别"),
      "- 交易结构: " + (structure.transactionStructure || "未识别"),
      "- 交易对手方: " + (structure.counterparty || "未识别"),
      "- 投资者类型: " + (structure.investorType || "未识别"),
      "- 是否跨境: " + (structure.isCrossBorder ? "是" : "否"),
      "- 风险点: " + (structure.riskPoints.length > 0 ? structure.riskPoints.join("、") : "未识别"),
      "- 待补充信息: " + (structure.missingInfo.length > 0 ? structure.missingInfo.join("、") : "无"),
    ].join("\n");

    const hitsText = this.formatHitsForPrompt(hits);

    return `请严格按照合规agent的指令和格式回答以下问题。不可省略任何章节，不可用其他格式替代。

## 用户问题
${query}

## 识别到的产品结构
${structureText}

## 检索到的法规条文（共 ${hits.length} 条，请严格基于这些内容回答，不得编造）
${hitsText}

请立即按合规agent要求的模板输出（从"## 结论"开始）。`;
  }

  private formatHitsForPrompt(hits: RetrievalHit[]): string {
    if (hits.length === 0) {
      return "（未检索到相关法规条文。请如实告知用户，并建议人工合规复核。）";
    }

    const parts: string[] = [];

    // Group by source
    const evidenceHits = hits.filter((h) => h.source === "evidence");
    const clauseHits = hits.filter((h) => h.source === "clause");

    let idx = 0;

    if (evidenceHits.length > 0) {
      parts.push("━━━ 【证据账本命中】 ━━━（效力高于一般条款，优先参考）");
      for (const h of evidenceHits) {
        idx++;
        parts.push(this.formatSingleHit(idx, h));
      }
    }

    if (clauseHits.length > 0) {
      parts.push("━━━ 【法规条款命中】 ━━━");
      for (const h of clauseHits) {
        idx++;
        parts.push(this.formatSingleHit(idx, h));
      }
    }

    return parts.join("\n\n");
  }

  private formatSingleHit(index: number, h: RetrievalHit): string {
    const lines: string[] = [];
    lines.push(`[${index}] 法规名称: 《${h.title}》`);
    lines.push(`    发布机构: ${h.publisher || "未标注"}`);
    lines.push(`    效力层级: ${h.authorityLevel || "未标注"}`);
    lines.push(`    发布日期: ${h.publishedAt || "未标注"}`);

    if (h.articleNo) {
      lines.push(`    条号: 【第${h.articleNo}条】`);
    }

    if (h.url) {
      lines.push(`    原文链接: ${h.url}`);
    }

    // Flag verification issues
    if (h.verificationStatus) {
      if (h.verificationStatus.includes("未核验") || h.verificationStatus === "unknown") {
        lines.push(`    ⚠️ 核验状态: 内容未经验证（附件未核验），使用时需人工确认`);
      } else {
        lines.push(`    核验状态: ${h.verificationStatus}`);
      }
    }

    const textPreview = h.text.slice(0, 1500);
    lines.push(`    相关原文: ${textPreview}`);

    return lines.join("\n");
  }

  // ────────── Answer Generation (non-streaming) ──────────

  private async generateAnswer(
    query: string,
    structure: ProductStructure,
    hits: RetrievalHit[],
  ): Promise<ComplianceAnswer> {
    const agentPrompt = this.prompt.getComplianceAgentPrompt();
    const userPrompt = this.buildUserPrompt(query, structure, hits);

    const answerText = await this.llm.chat(agentPrompt, userPrompt, 180000);

    return this.parseComplianceAnswer(answerText, structure, hits);
  }

  // ────────── Answer Parsing ──────────

  private parseComplianceAnswer(
    text: string,
    structure: ProductStructure,
    hits: RetrievalHit[],
  ): ComplianceAnswer {
    // --- Extract conclusion ---
    const conclusionMatch = text.match(/##\s*结论\s*\n([^\n]+)/);
    const rawConclusion = conclusionMatch?.[1]?.trim() ?? "需人工合规复核";

    let conclusionLabel: ComplianceAnswer["conclusionLabel"] = "需人工合规复核";
    if (rawConclusion.includes("可做") && !rawConclusion.includes("不") && !rawConclusion.includes("条件") && !rawConclusion.includes("人工")) {
      conclusionLabel = "可做";
    } else if (rawConclusion.includes("不可做") || rawConclusion.includes("不能")) {
      conclusionLabel = "不可做";
    } else if (rawConclusion.includes("条件")) {
      conclusionLabel = "有条件可做";
    }

    // --- Extract regulatory basis items ---
    const regBasis: ComplianceAnswer["regulatoryBasis"] = [];
    const basisSection = text.match(/##\s*法规依据\s*\n([\s\S]*?)(?=##\s*限制条件|##\s*待补充|$)/);
    if (basisSection) {
      // Split by numbered items (e.g., "1. **《..." or "1.**《...")
      const items = basisSection[1].split(/\n\d+\.\s*\*{1,2}《/).filter(Boolean);
      for (const item of items) {
        // Reconstruct the title that was stripped by the split
        const hasOpeningBrackets = item.includes("**《") || item.includes("《");
        let title = "";
        let fullItem = item;

        if (!hasOpeningBrackets) {
          // The title was consumed by the split pattern; extract from the start
          const titleEnd = item.indexOf("》");
          if (titleEnd !== -1) {
            title = item.slice(0, titleEnd);
            fullItem = item.slice(titleEnd + 1);
          }
        } else {
          const titleMatch = item.match(/\*{0,2}《(.+?)》/);
          if (titleMatch) {
            title = titleMatch[1];
          }
        }

        // Extract publisher/date from parentheses after title
        const publisherMatch = fullItem.match(/（(.+?)）\s*\n/);

        // Extract article number and excerpt
        const articleNoMatch = fullItem.match(/第([^条]+)条[：:]/);
        const excerptMatch = fullItem.match(/第[^条]+条[：:]\s*(.+?)(?:\n|$)/);

        // Extract requirement
        const reqMatch = fullItem.match(/监管要求[：:]\s*(.+?)(?:\n|$)/);

        if (title) {
          regBasis.push({
            title,
            publisher: publisherMatch?.[1] ?? "",
            url: "",
            articleNo: articleNoMatch?.[1] ?? "",
            excerpt: excerptMatch?.[1]?.trim() ?? "",
            requirement: reqMatch?.[1]?.trim() ?? "",
          });
        }
      }
    }

    // --- Extract restrictions ---
    const restrictionsSection = text.match(/##\s*限制条件\s*\n([\s\S]*?)(?=##\s*待补充|$)/);
    const restrictions: string[] = [];
    if (restrictionsSection) {
      const lines = restrictionsSection[1].split("\n").filter((l) => l.trim().startsWith("-"));
      restrictions.push(...lines.map((l) => l.replace(/^-\s*/, "").trim()));
    }

    // --- Extract missing info ---
    const missingSection = text.match(/##\s*待补充信息\s*\n([\s\S]*?)(?=##\s*人工复核|$)/);
    const missingInfo: string[] = [];
    if (missingSection) {
      const lines = missingSection[1].split("\n").filter((l) => l.trim().startsWith("-"));
      missingInfo.push(...lines.map((l) => l.replace(/^-\s*/, "").trim()));
    }

    // --- Extract manual review note ---
    const reviewMatch = text.match(/##\s*人工复核提示\s*\n([\s\S]*?)$/);
    const manualReviewNote = reviewMatch?.[1]?.trim() ?? "";

    // --- Retrieval trace ---
    const evidenceCount = hits.filter((h) => h.source === "evidence").length;
    const clauseCount = hits.filter((h) => h.source === "clause").length;

    // Post-process: fill article_no from full clause library when empty
    const filledBasis = this.fillArticleNumbers(regBasis, this.retrieval);

    const answer: ComplianceAnswer = {
      conclusion: rawConclusion,
      conclusionLabel,
      productStructure: structure,
      regulatoryBasis: filledBasis.length > 0 ? filledBasis : hits.slice(0, 3).map((h) => ({
        title: h.title,
        publisher: h.publisher,
        url: h.url,
        articleNo: h.articleNo ?? "",
        excerpt: h.excerpt,
        requirement: "详见原文",
      })),
      restrictions: restrictions.length > 0 ? restrictions : structure.missingInfo.map(
        (m) => `需补充：${m}`
      ),
      missingInfo: missingInfo.length > 0 ? missingInfo : structure.missingInfo,
      manualReviewNote:
        manualReviewNote ||
        (hits.length === 0
          ? "未检索到相关法规，需人工合规复核。"
          : ""),
      confidenceScore: "medium",
      confidenceReason: "",
      retrievalTrace: {
        evidenceHits: evidenceCount,
        clauseHits: clauseCount,
        documentHits: 0,
        strategy:
          hits.length > 0
            ? "evidence_ledger + clauses.jsonl 关键词检索"
            : "未命中任何法规条文",
      },
    };

    return answer;
  }

  // ────────── Article No Backfill ──────────

  /** Fill empty article_no in regulatory basis by matching against full clause library. */
  private fillArticleNumbers(
    basis: ComplianceAnswer["regulatoryBasis"],
    retrieval: RetrievalService,
  ): ComplianceAnswer["regulatoryBasis"] {
    return basis.map((item) => {
      if (item.articleNo) return item;
      const fullTitle = item.title.replace(/[《》]/g, "");
      const titleKey = fullTitle.slice(0, 15);
      const match = retrieval.findClauseByTitle(titleKey);
      if (match) {
        return { ...item, articleNo: match.articleNo, excerpt: match.excerpt || item.excerpt };
      }
      return item;
    });
  }

  // ────────── Confidence Scoring ──────────

  private computeConfidenceScore(
    hits: RetrievalHit[],
    answer: ComplianceAnswer,
  ): { score: "high" | "medium" | "low"; reason: string } {
    let points = 0;
    const reasons: string[] = [];

    // --- Factor 1: Number of evidence hits ---
    const evidenceHits = hits.filter((h) => h.source === "evidence").length;
    if (evidenceHits >= 3) {
      points += 3;
      reasons.push(`证据命中数≥3 (${evidenceHits}条)`);
    } else if (evidenceHits >= 1) {
      points += 1;
      reasons.push(`证据命中数=${evidenceHits}`);
    } else {
      reasons.push("无证据账本命中");
    }

    // --- Factor 2: Authority level of top hits ---
    const topHits = hits.slice(0, 5);
    const hasHighAuthority = topHits.some(
      (h) =>
        h.authorityLevel === "law" ||
        h.authorityLevel === "administrative_regulation" ||
        h.authorityLevel === "department_rule",
    );
    if (hasHighAuthority) {
      points += 2;
      reasons.push("命中高效力层级法规");
    } else {
      const hasAnyAuthority = topHits.some((h) => h.authorityLevel);
      if (!hasAnyAuthority) {
        reasons.push("法规效力层级未标注");
      } else {
        reasons.push("命中法规层级偏低");
      }
    }

    // --- Factor 3: Article numbers present in regulatory basis ---
    const hasArticleNumbers = answer.regulatoryBasis.some((b) => b.articleNo);
    if (hasArticleNumbers) {
      points += 2;
      reasons.push("法规依据包含条号引用");
    } else if (answer.regulatoryBasis.length > 0) {
      reasons.push("法规依据无明确条号");
    }

    // --- Factor 4: Conclusion label ---
    if (answer.conclusionLabel === "需人工合规复核") {
      points -= 1;
      reasons.push("结论为需人工合规复核");
    } else if (answer.conclusionLabel === "可做") {
      points += 1;
      reasons.push("结论明确为可做");
    }

    // --- Factor 5: Uncertainty signals in LLM output ---
    const uncertaintyWords = ["不确定", "不明确", "可能", "请核实", "建议咨询", "未找到", "未检索"];
    const combinedText = [
      answer.conclusion,
      answer.manualReviewNote,
      ...answer.regulatoryBasis.map((b) => b.excerpt + b.requirement),
    ].join(" ");
    const hasUncertainty = uncertaintyWords.some((w) => combinedText.includes(w));
    if (hasUncertainty) {
      points -= 2;
      reasons.push("LLM输出包含不确定性表述");
    }

    // --- Factor 6: Regulatory basis count ---
    if (answer.regulatoryBasis.length >= 3) {
      points += 1;
      reasons.push(`引用法规≥3条`);
    } else if (answer.regulatoryBasis.length === 0) {
      points -= 2;
      reasons.push("无法规依据引用");
    }

    // --- Determine final score ---
    if (points >= 5) {
      return { score: "high", reason: reasons.join("；") };
    }
    if (points >= 2) {
      return { score: "medium", reason: reasons.join("；") };
    }
    return { score: "low", reason: reasons.join("；") };
  }
}
