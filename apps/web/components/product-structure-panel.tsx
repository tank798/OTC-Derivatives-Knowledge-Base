"use client";

import type { ComplianceQueryResponseData } from "@otc/shared";
import clsx from "clsx";

type Props = {
  structure: ComplianceQueryResponseData["answer"]["productStructure"];
  conclusion: string;
  conclusionLabel: string;
};

const LABEL_CLASSES: Record<string, string> = {
  "可做": "bg-success/10 text-success border-success/20",
  "不可做": "bg-danger/10 text-danger border-danger/20",
  "有条件可做": "bg-warning/10 text-warning border-warning/20",
  "需人工合规复核": "bg-warning/10 text-warning border-warning/20",
};

export function ProductStructurePanel({
  structure,
  conclusion,
  conclusionLabel,
}: Props) {
  const labelClass = LABEL_CLASSES[conclusionLabel] ?? LABEL_CLASSES["需人工合规复核"];

  const fields: Array<{ label: string; value?: string; highlight?: boolean }> = [
    { label: "标的资产", value: structure.underlyingAsset },
    { label: "产品类型", value: structure.productType },
    { label: "交易结构", value: structure.transactionStructure },
    { label: "交易对手方", value: structure.counterparty },
    { label: "投资者类型", value: structure.investorType },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-ink-tertiary"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
          </svg>
          <h3 className="text-xs font-semibold text-ink-secondary">产品画像</h3>
        </div>
        <span
          className={clsx(
            "rounded-md border px-2 py-0.5 text-2xs font-medium",
            labelClass
          )}
        >
          {conclusionLabel}
        </span>
      </div>

      {/* Fields */}
      <div className="space-y-0 p-4">
        {fields.map((f) => (
          <FieldRow key={f.label} label={f.label} value={f.value} />
        ))}

        {/* Cross border */}
        <div className="flex items-center justify-between border-t border-slate-50 pt-2.5">
          <span className="text-xs text-ink-tertiary">是否跨境</span>
          <span
            className={clsx(
              "text-xs font-medium",
              structure.isCrossBorder ? "text-warning" : "text-ink-secondary"
            )}
          >
            <span
              className={clsx(
                "mr-1 inline-block h-1.5 w-1.5 rounded-full",
                structure.isCrossBorder ? "bg-warning" : "bg-ink-tertiary"
              )}
            />
            {structure.isCrossBorder ? "是" : "否"}
          </span>
        </div>
      </div>

      {/* Risk points */}
      {structure.riskPoints.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="mb-2 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
            风险识别
          </p>
          <div className="flex flex-wrap gap-1">
            {structure.riskPoints.map((r) => (
              <span
                key={r}
                className="rounded-md bg-danger/8 px-2 py-0.5 text-2xs font-medium text-danger"
              >
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Missing info */}
      {structure.missingInfo.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="mb-2 text-2xs font-semibold uppercase tracking-wider text-warning">
            待补充
          </p>
          <ul className="space-y-1">
            {structure.missingInfo.map((m) => (
              <li
                key={m}
                className="flex items-start gap-2 text-xs leading-5 text-warning/80"
              >
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warning/40" />
                {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Conclusion summary */}
      <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3">
        <p className="mb-1 text-2xs text-ink-tertiary">合规结论</p>
        <p className="line-clamp-2 text-xs font-medium leading-6 text-ink">
          {conclusion}
        </p>
      </div>
    </div>
  );
}

function FieldRow({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  const missing = !value || value === "";
  return (
    <div className="flex items-center justify-between border-b border-slate-50 py-2 last:border-0">
      <span className="text-xs text-ink-tertiary">{label}</span>
      <span
        className={clsx(
          "ml-2 truncate text-right text-xs font-medium",
          missing ? "text-warning" : "text-ink-secondary"
        )}
      >
        {missing ? (
          <span className="inline-flex items-center gap-1">
            <svg
              width="8"
              height="8"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            待识别
          </span>
        ) : (
          value
        )}
      </span>
    </div>
  );
}
