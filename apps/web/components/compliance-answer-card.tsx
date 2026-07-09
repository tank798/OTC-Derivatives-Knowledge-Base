"use client";

import { useState } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";
import clsx from "clsx";

// ── Conclusion color mapping ──
const CONCLUSION_CLASSES: Record<string, { banner: string; badge: string; label: string }> = {
  "可做": {
    banner: "border-success/30 bg-success/5",
    badge: "bg-success text-white",
    label: "合规结论",
  },
  "不可做": {
    banner: "border-danger/30 bg-danger/5",
    badge: "bg-danger text-white",
    label: "合规结论",
  },
  "有条件可做": {
    banner: "border-warning/30 bg-warning/5",
    badge: "bg-warning text-white",
    label: "合规结论",
  },
  "需人工合规复核": {
    banner: "border-warning/30 bg-warning/5",
    badge: "bg-warning/15 text-warning-700 border border-warning/30",
    label: "需复核",
  },
};

const CONFIDENCE_MAP: Record<string, { label: string; class: string }> = {
  "可做": { label: "高置信度", class: "text-success" },
  "不可做": { label: "高置信度", class: "text-success" },
  "有条件可做": { label: "中置信度", class: "text-warning" },
  "需人工合规复核": { label: "低置信度 — 建议人工复核", class: "text-warning" },
};

// ── Props ──
type Props = {
  data: ComplianceQueryResponseData;
};

export function ComplianceAnswerCard({ data }: Props) {
  const { answer } = data;
  const [copied, setCopied] = useState(false);

  const colors = CONCLUSION_CLASSES[answer.conclusionLabel] ?? CONCLUSION_CLASSES["需人工合规复核"];
  const confidence = CONFIDENCE_MAP[answer.conclusionLabel] ?? CONFIDENCE_MAP["需人工合规复核"];

  // ── Copy handler ──
  const handleCopy = async () => {
    const text = [
      `结论: ${answer.conclusion}（${answer.conclusionLabel}）`,
      "",
      "── 产品结构识别 ──",
      `标的资产: ${answer.productStructure.underlyingAsset || "未识别"}`,
      `产品类型: ${answer.productStructure.productType || "未识别"}`,
      `交易结构: ${answer.productStructure.transactionStructure || "未识别"}`,
      `交易对手方: ${answer.productStructure.counterparty || "未识别"}`,
      `投资者类型: ${answer.productStructure.investorType || "未识别"}`,
      `是否跨境: ${answer.productStructure.isCrossBorder ? "是" : "否"}`,
      ...answer.productStructure.riskPoints.map((r) => `风险点: ${r}`),
      ...answer.productStructure.missingInfo.map((m) => `待补充: ${m}`),
      "",
      "── 法规依据 ──",
      ...answer.regulatoryBasis.map(
        (b, i) =>
          `${i + 1}. 《${b.title}》` +
          (b.articleNo ? ` 第${b.articleNo}条` : "") +
          `\n   ${b.excerpt}` +
          (b.url ? `\n   ${b.url}` : "")
      ),
      "",
      "── 限制条件 ──",
      ...answer.restrictions.map((r, i) => `${i + 1}. ${r}`),
      "",
      ...(answer.missingInfo.length > 0
        ? [
            "── 待补充信息 ──",
            ...answer.missingInfo.map((m) => `- ${m}`),
            "",
          ]
        : []),
      ...(answer.manualReviewNote
        ? [`── 人工复核提示 ──`, answer.manualReviewNote, ""]
        : []),
      ...(answer.retrievalTrace
        ? [
            `检索信息: 策略 ${answer.retrievalTrace.strategy} · ` +
              `证据 ${answer.retrievalTrace.evidenceHits} 条 · ` +
              `条款 ${answer.retrievalTrace.clauseHits} 条`,
          ]
        : []),
    ].join("\n");

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  return (
    <div className="w-full max-w-[85%] animate-slide-up space-y-4">
      {/* ── Conclusion Banner ── */}
      <div
        className={clsx(
          "rounded-xl border p-4",
          colors.banner
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={clsx("rounded-md px-2 py-0.5 text-xs font-bold", colors.badge)}>
                {answer.conclusionLabel}
              </span>
              <span className={clsx("text-2xs font-medium", confidence.class)}>
                {confidence.label}
              </span>
            </div>
            <p className="mt-2 text-base font-semibold leading-7 text-ink">
              {answer.conclusion}
            </p>
          </div>
          <button
            onClick={handleCopy}
            className="no-print shrink-0 rounded-lg border border-white/50 bg-white/60 px-3 py-1.5 text-2xs text-ink-secondary transition-base hover:bg-white"
          >
            {copied ? (
              <span className="flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-success"><polyline points="20 6 9 17 4 12" /></svg>
                已复制
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                复制
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ── Product Structure ── */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-tertiary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
          </svg>
          产品结构识别
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
          <Field label="标的资产" value={answer.productStructure.underlyingAsset} />
          <Field label="产品类型" value={answer.productStructure.productType} />
          <Field label="交易结构" value={answer.productStructure.transactionStructure} />
          <Field label="交易对手方" value={answer.productStructure.counterparty} />
          <Field label="投资者类型" value={answer.productStructure.investorType} />
          <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-1.5">
            <span className="text-xs text-ink-tertiary">是否跨境</span>
            <span
              className={clsx(
                "text-xs font-medium",
                answer.productStructure.isCrossBorder
                  ? "text-warning"
                  : "text-ink-secondary"
              )}
            >
              {answer.productStructure.isCrossBorder ? "是 — 需关注外汇管理要求" : "否"}
            </span>
          </div>
        </div>

        {/* Risk points */}
        {answer.productStructure.riskPoints.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <div className="flex flex-wrap gap-1.5">
              {answer.productStructure.riskPoints.map((r) => (
                <span
                  key={r}
                  className="rounded-md bg-danger/8 px-2 py-0.5 text-xs font-medium text-danger"
                >
                  ⚠ {r}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Missing info */}
        {answer.productStructure.missingInfo.length > 0 && (
          <div className="mt-3 rounded-lg border border-warning/20 bg-warning/5 px-3 py-2">
            <p className="text-xs font-medium text-warning">待补充信息</p>
            <ul className="mt-1 list-disc pl-4 text-xs text-warning/80">
              {answer.productStructure.missingInfo.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── Regulatory Basis ── */}
      {answer.regulatoryBasis.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-tertiary">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            法规依据（{answer.regulatoryBasis.length} 条）
          </h3>
          <div className="space-y-3">
            {answer.regulatoryBasis.map((basis, i) => (
              <RegulatoryBasisCard key={i} basis={basis} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* ── Restrictions ── */}
      {answer.restrictions.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-tertiary">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
            限制条件
          </h3>
          <ol className="space-y-2">
            {answer.restrictions.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-secondary">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-100 text-2xs font-medium text-ink-tertiary">
                  {i + 1}
                </span>
                <span className="leading-6">{r}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* ── Missing Info ── */}
      {answer.missingInfo.length > 0 && (
        <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-warning">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            待补充信息
          </h3>
          <ul className="space-y-1">
            {answer.missingInfo.map((m, i) => (
              <li key={i} className="flex items-start gap-2 text-sm leading-6 text-warning/80">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warning/40" />
                {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Manual Review Note ── */}
      {answer.manualReviewNote && (
        <div className="rounded-xl border border-warning/30 bg-warning/5 p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-warning">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            人工复核提示
          </h3>
          <p className="text-sm leading-6 text-warning/80">{answer.manualReviewNote}</p>
        </div>
      )}

      {/* ── Retrieval Trace ── */}
      {answer.retrievalTrace && (
        <div className="flex items-center gap-3 text-2xs text-ink-tertiary">
          <span className="flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            检索策略: {answer.retrievalTrace.strategy}
          </span>
          <span>证据 {answer.retrievalTrace.evidenceHits} 条</span>
          <span>条款 {answer.retrievalTrace.clauseHits} 条</span>
          {answer.retrievalTrace.documentHits > 0 && (
            <span>文档 {answer.retrievalTrace.documentHits} 条</span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Field sub-component ──
function Field({ label, value }: { label: string; value?: string }) {
  const missing = !value || value === "";
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-1.5">
      <span className="text-xs text-ink-tertiary">{label}</span>
      <span
        className={clsx(
          "text-xs font-medium",
          missing ? "text-warning" : "text-ink-secondary"
        )}
      >
        {missing ? "待识别" : value}
      </span>
    </div>
  );
}

// ── Regulatory Basis Card ──
function RegulatoryBasisCard({
  basis,
  index,
}: {
  basis: ComplianceQueryResponseData["answer"]["regulatoryBasis"][number];
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const isLong = basis.excerpt.length > 200;
  const displayText = expanded || !isLong ? basis.excerpt : basis.excerpt.slice(0, 200) + "…";

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3 transition-base hover:border-slate-200">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink">
            《{basis.title}》
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-tertiary">{basis.publisher}</span>
            {basis.articleNo && (
              <span className="rounded bg-accent/10 px-1.5 py-0.5 text-2xs font-medium text-accent">
                第{basis.articleNo}条
              </span>
            )}
          </div>
        </div>
        <span className="shrink-0 text-2xs text-ink-tertiary">#{index + 1}</span>
      </div>

      {/* Excerpt / full text */}
      <div className="mt-2">
        <p className="text-xs leading-6 text-ink-secondary">{displayText}</p>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-0.5 text-xs text-accent hover:underline"
          >
            {expanded ? "收起" : "展开全文"}
          </button>
        )}
      </div>

      {/* Requirement */}
      {basis.requirement && (
        <p className="mt-2 rounded-md bg-white px-2.5 py-1.5 text-xs font-medium leading-6 text-ink shadow-sm">
          {basis.requirement}
        </p>
      )}

      {/* Link */}
      {basis.url && (
        <a
          href={basis.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1.5 inline-flex items-center gap-1 text-xs text-accent transition-base hover:text-accent/80"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          查看原文
        </a>
      )}
    </div>
  );
}
