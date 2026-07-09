import { z } from "zod";

// ────────── 产品结构 ──────────
export const productStructureSchema = z.object({
  underlyingAsset: z.string().optional().default(""),
  productType: z.string().optional().default(""),
  transactionStructure: z.string().optional().default(""),
  counterparty: z.string().optional().default(""),
  investorType: z.string().optional().default(""),
  isCrossBorder: z.boolean().optional().default(false),
  riskPoints: z.array(z.string()).optional().default([]),
  missingInfo: z.array(z.string()).optional().default([]),
});

export type ProductStructure = z.infer<typeof productStructureSchema>;

// ────────── 检索命中 ──────────
export const retrievalHitSchema = z.object({
  source: z.enum(["evidence", "clause", "document"]),
  id: z.string(),
  title: z.string(),
  publisher: z.string().optional().default(""),
  url: z.string().optional().default(""),
  publishedAt: z.string().optional().default(""),
  effectiveAt: z.string().optional().default(""),
  articleNo: z.string().optional().default(""),
  text: z.string(),
  excerpt: z.string().optional().default(""),
  score: z.number(),
  authorityLevel: z.string().optional().default(""),
  verificationStatus: z.string().optional().default(""),
  matchReason: z.string().optional().default(""),
});

export type RetrievalHit = z.infer<typeof retrievalHitSchema>;

// ────────── 合规回答 ──────────
export const complianceAnswerSchema = z.object({
  conclusion: z.string(),
  conclusionLabel: z.enum(["可做", "不可做", "有条件可做", "需人工合规复核"]),
  productStructure: productStructureSchema,
  regulatoryBasis: z.array(
    z.object({
      title: z.string(),
      publisher: z.string(),
      url: z.string().optional().default(""),
      articleNo: z.string().optional().default(""),
      excerpt: z.string(),
      requirement: z.string(),
    })
  ),
  restrictions: z.array(z.string()),
  missingInfo: z.array(z.string()),
  manualReviewNote: z.string().optional().default(""),
  retrievalTrace: z
    .object({
      evidenceHits: z.number(),
      clauseHits: z.number(),
      documentHits: z.number(),
      strategy: z.string(),
    })
    .optional(),
});

export type ComplianceAnswer = z.infer<typeof complianceAnswerSchema>;

// ────────── API 请求/响应 ──────────
export const complianceQueryInputSchema = z.object({
  query: z.string().min(1, "请输入问题"),
});

export type ComplianceQueryInput = z.infer<typeof complianceQueryInputSchema>;

export const complianceQueryResponseSchema = z.object({
  answer: complianceAnswerSchema,
  hits: z.array(retrievalHitSchema),
});

export type ComplianceQueryResponse = z.infer<
  typeof complianceQueryResponseSchema
>;

// ────────── 证据账本条目的 schema（仅用于类型） ──────────
export const evidenceEntrySchema = z.object({
  evidence_id: z.string(),
  source_id: z.string(),
  publisher: z.string(),
  title: z.string(),
  url: z.string().optional().default(""),
  published_at: z.string().optional().default(""),
  effective_at: z.string().optional().default(""),
  body_read: z.boolean().optional().default(false),
  attachment_read: z.boolean().optional().default(false),
  authority_level: z.string().optional().default(""),
  support_scope: z.string().optional().default(""),
  tags: z.array(z.string()).optional().default([]),
  verification_status: z.string().optional().default(""),
  verified_by: z.string().optional().default(""),
});

export type EvidenceEntry = z.infer<typeof evidenceEntrySchema>;

// ────────── 条款条目的 schema ──────────
export const clauseEntrySchema = z.object({
  clause_id: z.string(),
  doc_id: z.string(),
  title: z.string(),
  text: z.string(),
  article_no: z.string().optional().default(""),
  heading_path: z.array(z.string()).optional().default([]),
  publisher: z.string().optional().default(""),
  source_id: z.string().optional().default(""),
  published_at: z.string().optional().default(""),
  retrieved_at: z.string().optional().default(""),
  url: z.string().optional().default(""),
  asset_classes: z.array(z.string()).optional().default([]),
  product_types: z.array(z.string()).optional().default([]),
  authority_level: z.string().optional().default(""),
});

export type ClauseEntry = z.infer<typeof clauseEntrySchema>;
