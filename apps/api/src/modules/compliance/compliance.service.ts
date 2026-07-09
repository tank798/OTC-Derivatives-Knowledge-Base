import { Injectable } from "@nestjs/common";
import { LlmService } from "../llm/llm.service";
import { RetrievalService } from "../retrieval/retrieval.service";
import { PromptService } from "../prompt/prompt.service";
import type { ComplianceAnswer, ProductStructure, RetrievalHit } from "@otc/shared";

@Injectable()
export class ComplianceService {
  constructor(
    private readonly llm: LlmService,
    private readonly retrieval: RetrievalService,
    private readonly prompt: PromptService,
  ) {}

  async answer(query: string): Promise<{
    answer: ComplianceAnswer;
    hits: RetrievalHit[];
  }> {
    // 1. Parse product structure from query
    const productStructure = await this.parseProductStructure(query);

    // 2. Retrieve relevant regulations
    const hits = this.retrieval.search(query);

    // 3. Generate compliance answer with LLM
    const answer = await this.generateAnswer(query, productStructure, hits);

    return { answer, hits };
  }

  private async parseProductStructure(query: string): Promise<ProductStructure> {
    try {
      const systemPrompt = `你是一个金融产品结构分析专家。从用户描述中提取产品结构信息，只返回合法 JSON，不要加 markdown 代码块标记。`;
      const userPrompt = `分析以下产品描述，返回 JSON（字段可为空字符串或空数组）：
{
  "underlyingAsset": "标的资产",
  "productType": "产品类型",
  "transactionStructure": "交易结构",
  "counterparty": "交易对手方",
  "investorType": "投资者类型",
  "isCrossBorder": false,
  "riskPoints": ["风险点1"],
  "missingInfo": ["待补充信息1"]
}

用户问题：${query}`;

      const text = await this.llm.chat(systemPrompt, userPrompt, 30000);
      const cleaned = text.replace(/```json\s*/gi, "").replace(/```\s*/g, "").trim();
      const parsed = JSON.parse(cleaned);
      return {
        underlyingAsset: String(parsed.underlyingAsset ?? ""),
        productType: String(parsed.productType ?? ""),
        transactionStructure: String(parsed.transactionStructure ?? ""),
        counterparty: String(parsed.counterparty ?? ""),
        investorType: String(parsed.investorType ?? ""),
        isCrossBorder: Boolean(parsed.isCrossBorder),
        riskPoints: Array.isArray(parsed.riskPoints) ? parsed.riskPoints : [],
        missingInfo: Array.isArray(parsed.missingInfo) ? parsed.missingInfo : [],
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

  private async generateAnswer(
    query: string,
    structure: ProductStructure,
    hits: RetrievalHit[],
  ): Promise<ComplianceAnswer> {
    const agentPrompt = this.prompt.getComplianceAgentPrompt();

    // Format hits for prompt
    const hitsText = hits.length === 0
      ? "（未检索到相关法规条文。请如实告知用户，并建议人工合规复核。）"
      : hits.map((h, i) => {
          const art = h.articleNo ? ` **条号: ${h.articleNo}** |` : "";
          return `[${i + 1}] 来源: ${h.source} |${art} 标题: ${h.title}
发布机构: ${h.publisher} | 发布日期: ${h.publishedAt}
效力层级: ${h.authorityLevel} | 核验状态: ${h.verificationStatus || "未核验"}
链接: ${h.url}
条文内容: ${h.text.slice(0, 1500)}
---`;
        }).join("\n\n");

    const structureText = `
- 标的资产: ${structure.underlyingAsset || "未识别"}
- 产品类型: ${structure.productType || "未识别"}
- 交易结构: ${structure.transactionStructure || "未识别"}
- 交易对手方: ${structure.counterparty || "未识别"}
- 投资者类型: ${structure.investorType || "未识别"}
- 是否跨境: ${structure.isCrossBorder ? "是" : "否"}
- 风险点: ${structure.riskPoints.join("、") || "未识别"}
- 待补充: ${structure.missingInfo.join("、") || "无"}
`;

    const userPrompt = `请严格按照以下格式回答合规问题。不可省略任何章节，不可用其他格式替代。

## 用户问题
${query}

## 识别到的产品结构
${structureText}

## 检索到的法规条文（共 ${hits.length} 条，请基于这些内容回答，不得编造）
${hitsText}

请立即按以下模板输出（从"## 结论"开始）：
## 结论
[一句话判断]

## 产品结构识别
[列出已识别的产品要素]

## 法规依据
[逐条列出，每条格式：**《法规名》**（发布机构，日期）第X条：原文摘录 → 监管要求]

## 限制条件
[具体条件列表]

## 待补充信息
[缺少什么信息]

## 人工复核提示
[需要人工关注的风险点]`;

    const answerText = await this.llm.chat(agentPrompt, userPrompt, 120000);

    // Parse the answer into structured format
    return this.parseComplianceAnswer(answerText, structure, hits);
  }

  /** Fill empty article_no in regulatory basis by matching against all loaded clauses. */
  private fillArticleNumbers(
    basis: ComplianceAnswer["regulatoryBasis"],
    _hits: RetrievalHit[],
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

  private parseComplianceAnswer(
    text: string,
    structure: ProductStructure,
    hits: RetrievalHit[],
  ): ComplianceAnswer {
    // Extract conclusion
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

    // Extract regulatory basis items
    const regBasis: ComplianceAnswer["regulatoryBasis"] = [];
    const basisSection = text.match(/##\s*法规依据\s*\n([\s\S]*?)(?=##\s*限制条件|##\s*待补充|$)/);
    if (basisSection) {
      const items = basisSection[1].split(/\n\d+\.\s*\*\*/).filter(Boolean);
      for (const item of items) {
        const titleMatch = item.match(/\*\*《(.+?)》\*\*/);
        const publisherMatch = item.match(/（(.+?)）/);
        const excerptMatch = item.match(/第[一二三四五六七八九十\d]+条[：:]\s*(.+?)(?:\n|$)/);
        const reqMatch = item.match(/监管要求[：:]\s*(.+?)(?:\n|$)/);
        if (titleMatch) {
          regBasis.push({
            title: titleMatch[1],
            publisher: publisherMatch?.[1] ?? "",
            url: "",
            articleNo: excerptMatch ? item.match(/第([^条]+)条/)?.[1] ?? "" : "",
            excerpt: excerptMatch?.[1]?.trim() ?? "",
            requirement: reqMatch?.[1]?.trim() ?? "",
          });
        }
      }
    }

    // Extract restrictions
    const restrictionsSection = text.match(/##\s*限制条件\s*\n([\s\S]*?)(?=##\s*待补充|$)/);
    const restrictions: string[] = [];
    if (restrictionsSection) {
      const lines = restrictionsSection[1].split("\n").filter((l) => l.trim().startsWith("-"));
      restrictions.push(...lines.map((l) => l.replace(/^-\s*/, "").trim()));
    }

    // Extract missing info
    const missingSection = text.match(/##\s*待补充信息\s*\n([\s\S]*?)(?=##\s*人工复核|$)/);
    const missingInfo: string[] = [];
    if (missingSection) {
      const lines = missingSection[1].split("\n").filter((l) => l.trim().startsWith("-"));
      missingInfo.push(...lines.map((l) => l.replace(/^-\s*/, "").trim()));
    }

    // Extract manual review note
    const reviewMatch = text.match(/##\s*人工复核提示\s*\n([\s\S]*?)$/);
    const manualReviewNote = reviewMatch?.[1]?.trim() ?? "";

    const evidenceCount = hits.filter((h) => h.source === "evidence").length;
    const clauseCount = hits.filter((h) => h.source === "clause").length;

    // Post-process: fill article_no from full clause library when empty
    const filledBasis = this.fillArticleNumbers(regBasis, hits, this.retrieval);

    return {
      conclusion: rawConclusion,
      conclusionLabel,
      productStructure: structure,
      regulatoryBasis: filledBasis.length > 0 ? filledBasis : hits.slice(0, 3).map((h) => ({
        title: h.title,
        publisher: h.publisher,
        url: h.url,
        articleNo: h.articleNo,
        excerpt: h.excerpt,
        requirement: "详见原文",
      })),
      restrictions,
      missingInfo: missingInfo.length > 0 ? missingInfo : structure.missingInfo,
      manualReviewNote,
      retrievalTrace: {
        evidenceHits: evidenceCount,
        clauseHits: clauseCount,
        documentHits: 0,
        strategy: hits.length > 0 ? "evidence_ledger + clauses.jsonl 关键词检索" : "未命中任何法规条文",
      },
    };
  }
}
