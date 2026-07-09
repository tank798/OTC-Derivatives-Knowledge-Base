// ────────── API 通用响应 ──────────

export type ApiError = {
  message: string;
  code?: string;
};

export type ApiResponse<T> =
  | { success: true; data: T }
  | { success: false; error: ApiError };

// ────────── API 端点类型 ──────────
export type ComplianceQueryRequest = {
  query: string;
};

export type ComplianceQueryResponseData = {
  answer: {
    conclusion: string;
    conclusionLabel: "可做" | "不可做" | "有条件可做" | "需人工合规复核";
    productStructure: {
      underlyingAsset: string;
      productType: string;
      transactionStructure: string;
      counterparty: string;
      investorType: string;
      isCrossBorder: boolean;
      riskPoints: string[];
      missingInfo: string[];
    };
    regulatoryBasis: Array<{
      title: string;
      publisher: string;
      url: string;
      articleNo: string;
      excerpt: string;
      requirement: string;
    }>;
    restrictions: string[];
    missingInfo: string[];
    manualReviewNote: string;
    retrievalTrace?: {
      evidenceHits: number;
      clauseHits: number;
      documentHits: number;
      strategy: string;
    };
  };
  hits: Array<{
    source: "evidence" | "clause" | "document";
    id: string;
    title: string;
    publisher: string;
    url: string;
    publishedAt: string;
    effectiveAt: string;
    articleNo: string;
    text: string;
    excerpt: string;
    score: number;
    authorityLevel: string;
    verificationStatus: string;
    matchReason: string;
  }>;
};

// ────────── 流式事件（预留） ──────────
export type ComplianceStreamEvent =
  | { type: "thinking"; message: string }
  | { type: "retrieving"; count: number }
  | { type: "chunk"; content: string }
  | {
      type: "answer";
      answer: ComplianceQueryResponseData["answer"];
    }
  | { type: "hits"; hits: ComplianceQueryResponseData["hits"] }
  | { type: "error"; message: string }
  | { type: "done" };
