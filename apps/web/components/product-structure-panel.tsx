"use client";

import type { ComplianceQueryResponseData } from "@otc/shared";

type Props = {
  structure: ComplianceQueryResponseData["answer"]["productStructure"];
  conclusion: string;
  conclusionLabel: string;
};

const LABEL_COLORS: Record<string, string> = {
  "可做": "bg-green-100 text-green-700",
  "不可做": "bg-red-100 text-red-700",
  "有条件可做": "bg-yellow-100 text-yellow-700",
  "需人工合规复核": "bg-orange-100 text-orange-700",
};

export function ProductStructurePanel({ structure, conclusionLabel }: Props) {
  const labelColor = LABEL_COLORS[conclusionLabel] ?? LABEL_COLORS["需人工合规复核"];

  return (
    <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-slate-400">产品画像</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${labelColor}`}>
          {conclusionLabel}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <Field label="标的资产" value={structure.underlyingAsset} />
        <Field label="产品类型" value={structure.productType} />
        <Field label="交易结构" value={structure.transactionStructure} />
        <Field label="交易对手方" value={structure.counterparty} />
        <Field label="投资者类型" value={structure.investorType} />
        <div className="flex items-center justify-between">
          <span className="text-slate-400">是否跨境</span>
          <span className={structure.isCrossBorder ? "font-semibold text-amber-600" : "text-slate-500"}>
            {structure.isCrossBorder ? "是" : "否"}
          </span>
        </div>
      </div>

      {structure.riskPoints.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <p className="mb-1 text-xs text-slate-400">风险点</p>
          <div className="flex flex-wrap gap-1">
            {structure.riskPoints.map((r) => (
              <span key={r} className="rounded bg-red-50 px-2 py-0.5 text-xs text-red-600">
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {structure.missingInfo.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-3">
          <p className="mb-1 text-xs text-amber-600">待补充</p>
          <ul className="list-disc pl-4 text-xs text-amber-700">
            {structure.missingInfo.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-700">{value || "—"}</span>
    </div>
  );
}
