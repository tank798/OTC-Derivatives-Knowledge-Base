"use client";

import { useState } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";

type Hit = ComplianceQueryResponseData["hits"][number];

export function RegulationHitsPanel({ hits }: { hits: Hit[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (hits.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-xs font-semibold uppercase text-slate-400">命中法规</h3>
        <p className="mt-2 text-sm text-slate-400">未检索到相关法规</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-slate-400">
          命中法规（{hits.length}）
        </h3>
        <span className="text-xs text-slate-400">
          {hits.filter((h) => h.source === "evidence").length} 证据 +{" "}
          {hits.filter((h) => h.source === "clause").length} 条款
        </span>
      </div>

      <div className="space-y-2">
        {hits.slice(0, 15).map((hit) => {
          const isExpanded = expandedId === hit.id;
          return (
            <div
              key={hit.id}
              className="rounded-lg border border-slate-100 bg-slate-50 transition hover:border-slate-200"
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : hit.id)}
                className="flex w-full items-start justify-between gap-2 px-3 py-2 text-left"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-700">
                    {hit.source === "evidence" && "⭐ "}
                    {hit.title}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {hit.publisher}
                    {hit.authorityLevel ? ` · ${hit.authorityLevel}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-slate-400">
                  {isExpanded ? "收起" : "展开"}
                </span>
              </button>

              {isExpanded && (
                <div className="border-t border-slate-100 px-3 py-2">
                  <p className="text-xs leading-6 text-slate-600">
                    {hit.text.slice(0, 500)}
                    {hit.text.length > 500 ? "..." : ""}
                  </p>
                  {hit.url && (
                    <a
                      href={hit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-block text-xs text-blue-600 hover:underline"
                    >
                      原文链接 →
                    </a>
                  )}
                  {hit.verificationStatus && (
                    <p className="mt-1 text-xs text-amber-600">
                      核验状态：{hit.verificationStatus}
                    </p>
                  )}
                  <p className="mt-0.5 text-xs text-slate-400">
                    分数: {hit.score}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {hits.length > 15 && (
        <p className="mt-2 text-center text-xs text-slate-400">
          还有 {hits.length - 15} 条未显示
        </p>
      )}
    </div>
  );
}
