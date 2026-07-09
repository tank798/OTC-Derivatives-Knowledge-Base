"use client";

import { useState } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";

const CONCLUSION_COLORS: Record<string, string> = {
  "可做": "bg-green-50 border-green-200 text-green-800",
  "不可做": "bg-red-50 border-red-200 text-red-800",
  "有条件可做": "bg-yellow-50 border-yellow-200 text-yellow-800",
  "需人工合规复核": "bg-orange-50 border-orange-200 text-orange-800",
};

export function ComplianceAnswerCard({
  data,
}: {
  data: ComplianceQueryResponseData;
}) {
  const { answer } = data;
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const text = [
      `结论: ${answer.conclusion}`,
      "",
      "## 产品结构识别",
      `- 标的资产: ${answer.productStructure.underlyingAsset || "未识别"}`,
      `- 产品类型: ${answer.productStructure.productType || "未识别"}`,
      `- 交易结构: ${answer.productStructure.transactionStructure || "未识别"}`,
      `- 投资者类型: ${answer.productStructure.investorType || "未识别"}`,
      `- 是否跨境: ${answer.productStructure.isCrossBorder ? "是" : "否"}`,
      "",
      "## 法规依据",
      ...answer.regulatoryBasis.map(
        (b) => `- 《${b.title}》（${b.publisher}）: ${b.requirement}`
      ),
      "",
      "## 限制条件",
      ...answer.restrictions.map((r) => `- ${r}`),
      "",
      "## 待补充信息",
      ...answer.missingInfo.map((m) => `- ${m}`),
    ].join("\n");

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const colorClass = CONCLUSION_COLORS[answer.conclusionLabel] ?? CONCLUSION_COLORS["需人工合规复核"];

  return (
    <div className="w-full max-w-[85%] space-y-4">
      {/* Conclusion Banner */}
      <div className={`rounded-xl border px-5 py-3 ${colorClass}`}>
        <span className="text-sm font-bold">结论：{answer.conclusion}</span>
      </div>

      {/* Product Structure Summary */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">
          产品结构识别
        </h3>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <Pair label="标的资产" value={answer.productStructure.underlyingAsset} />
          <Pair label="交易结构" value={answer.productStructure.transactionStructure} />
          <Pair label="投资者" value={answer.productStructure.investorType} />
          <Pair
            label="跨境"
            value={answer.productStructure.isCrossBorder ? "是" : "否"}
          />
        </div>
        {answer.productStructure.missingInfo.length > 0 && (
          <div className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
            ⚠ 待补充：{answer.productStructure.missingInfo.join("、")}
          </div>
        )}
      </div>

      {/* Regulatory Basis */}
      {answer.regulatoryBasis.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase text-slate-400">
            法规依据（{answer.regulatoryBasis.length} 条）
          </h3>
          <div className="space-y-3">
            {answer.regulatoryBasis.slice(0, 5).map((basis, i) => (
              <div key={i} className="border-b border-slate-50 pb-3 last:border-0 last:pb-0">
                <p className="text-sm font-semibold text-slate-900">
                  《{basis.title}》
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {basis.publisher}
                  {basis.articleNo ? ` · 第${basis.articleNo}条` : ""}
                </p>
                {basis.excerpt && (
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    {basis.excerpt}
                  </p>
                )}
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {basis.requirement}
                </p>
                {basis.url && (
                  <a
                    href={basis.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-block text-xs text-blue-600 hover:underline"
                  >
                    查看原文 →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Restrictions */}
      {answer.restrictions.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase text-slate-400">
            限制条件
          </h3>
          <ul className="list-disc pl-5 text-sm leading-7 text-slate-700">
            {answer.restrictions.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing Info */}
      {answer.missingInfo.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase text-amber-600">
            待补充信息
          </h3>
          <ul className="list-disc pl-5 text-sm leading-7 text-amber-800">
            {answer.missingInfo.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Manual Review Note */}
      {answer.manualReviewNote && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase text-orange-600">
            人工复核提示
          </h3>
          <p className="text-sm leading-7 text-orange-800">
            {answer.manualReviewNote}
          </p>
        </div>
      )}

      {/* Trace */}
      {answer.retrievalTrace && (
        <p className="text-xs text-slate-400">
          检索策略：{answer.retrievalTrace.strategy} · 证据 {answer.retrievalTrace.evidenceHits} 条 · 条款 {answer.retrievalTrace.clauseHits} 条
        </p>
      )}

      {/* Copy Button */}
      <button
        onClick={handleCopy}
        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 transition hover:bg-slate-50"
      >
        {copied ? "✓ 已复制" : "复制回答"}
      </button>
    </div>
  );
}

function Pair({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <span className="text-slate-400">{label}：</span>
      <span className="text-slate-700">{value || "未识别"}</span>
    </div>
  );
}
