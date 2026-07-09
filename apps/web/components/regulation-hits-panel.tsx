"use client";

import { useState, useMemo } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";
import clsx from "clsx";

type Hit = ComplianceQueryResponseData["hits"][number];

const AUTHORITY_LEVELS: Record<string, number> = {
  "法律": 5,
  "行政法规": 4,
  "部门规章": 3,
  "规范性文件": 2,
  "行业自律规则": 1,
  "": 0,
};

const SORT_OPTIONS = [
  { key: "score", label: "相关度" },
  { key: "authority", label: "效力层级" },
  { key: "date", label: "日期" },
] as const;

type SortKey = (typeof SORT_OPTIONS)[number]["key"];

export function RegulationHitsPanel({ hits }: { hits: Hit[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [showFilters, setShowFilters] = useState(false);

  // Filter and sort hits
  const processedHits = useMemo(() => {
    let filtered = hits;

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      filtered = hits.filter(
        (h) =>
          h.title.toLowerCase().includes(q) ||
          h.text.toLowerCase().includes(q) ||
          h.publisher.toLowerCase().includes(q)
      );
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      switch (sortKey) {
        case "score":
          return b.score - a.score;
        case "authority":
          return (
            (AUTHORITY_LEVELS[b.authorityLevel] ?? 0) -
            (AUTHORITY_LEVELS[a.authorityLevel] ?? 0)
          );
        case "date":
          return (b.publishedAt || "").localeCompare(a.publishedAt || "");
        default:
          return 0;
      }
    });

    return sorted;
  }, [hits, searchQuery, sortKey]);

  const evidenceCount = hits.filter((h) => h.source === "evidence").length;
  const clauseCount = hits.filter((h) => h.source === "clause").length;
  const docCount = hits.filter((h) => h.source === "document").length;

  if (hits.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-tertiary">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          命中法规
        </h3>
        <p className="mt-3 text-xs text-ink-tertiary">未检索到相关法规</p>
      </div>
    );
  }

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
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <h3 className="text-xs font-semibold text-ink-secondary">
            命中法规（{hits.length}）
          </h3>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="rounded p-1 text-ink-tertiary transition-base hover:bg-slate-100"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="8" y1="12" x2="20" y2="12" />
            <line x1="12" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      </div>

      {/* Search and sort (collapsible) */}
      {showFilters && (
        <div className="animate-slide-up border-b border-slate-100 px-4 py-3">
          {/* Search */}
          <div className="relative mb-2">
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-tertiary"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索法规..."
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-7 pr-3 text-xs text-ink outline-none transition-base placeholder:text-ink-tertiary focus:border-accent/30 focus:bg-white"
            />
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <span className="text-2xs text-ink-tertiary">排序:</span>
            <div className="flex gap-1">
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setSortKey(opt.key)}
                  className={clsx(
                    "rounded-md px-2 py-1 text-2xs font-medium transition-base",
                    sortKey === opt.key
                      ? "bg-accent/10 text-accent"
                      : "text-ink-tertiary hover:bg-slate-100"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Counts */}
          <div className="mt-2 flex gap-3 text-2xs text-ink-tertiary">
            <span>⭐ 证据 {evidenceCount}</span>
            <span>📄 条款 {clauseCount}</span>
            {docCount > 0 && <span>📋 文档 {docCount}</span>}
          </div>
        </div>
      )}

      {/* Counts (always visible when filters hidden) */}
      {!showFilters && (
        <div className="flex gap-3 px-4 py-2 text-2xs text-ink-tertiary">
          <span>⭐ {evidenceCount}</span>
          <span>📄 {clauseCount}</span>
          {docCount > 0 && <span>📋 {docCount}</span>}
        </div>
      )}

      {/* Hit list */}
      <div className="space-y-0.5 px-3 pb-3">
        {processedHits.slice(0, 20).map((hit) => {
          const isExpanded = expandedId === hit.id;
          return (
            <div
              key={hit.id}
              className={clsx(
                "rounded-lg border transition-base",
                isExpanded
                  ? "border-accent/20 bg-accent/5"
                  : "border-transparent bg-slate-50 hover:border-slate-200"
              )}
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : hit.id)}
                className="flex w-full items-start gap-2 px-3 py-2.5 text-left"
              >
                {/* Source icon */}
                <span className="mt-0.5 shrink-0 text-xs">
                  {hit.source === "evidence" ? "⭐" : hit.source === "clause" ? "📄" : "📋"}
                </span>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-ink">
                    {hit.title}
                  </p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="truncate text-2xs text-ink-tertiary">
                      {hit.publisher}
                    </span>
                    {hit.authorityLevel && (
                      <span className="shrink-0 rounded bg-ink-tertiary/10 px-1 py-px text-2xs text-ink-tertiary">
                        {hit.authorityLevel}
                      </span>
                    )}
                  </div>
                </div>

                {/* Score + expand */}
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <ScoreBadge score={hit.score} />
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={clsx(
                      "text-ink-tertiary transition-transform",
                      isExpanded && "rotate-180"
                    )}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </button>

              {/* Expanded content */}
              {isExpanded && (
                <div className="animate-fade-in border-t border-slate-100 px-3 pb-3 pt-2">
                  {/* Article info */}
                  {hit.articleNo && (
                    <p className="mb-1.5 text-2xs font-medium text-accent">
                      第{hit.articleNo}条
                    </p>
                  )}

                  {/* Full text */}
                  <p className="text-xs leading-6 text-ink-secondary">
                    {hit.text}
                  </p>

                  {/* Metadata */}
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-ink-tertiary">
                    {hit.publishedAt && (
                      <span>发布: {hit.publishedAt}</span>
                    )}
                    {hit.effectiveAt && (
                      <span>施行: {hit.effectiveAt}</span>
                    )}
                    {hit.matchReason && (
                      <span>匹配: {hit.matchReason}</span>
                    )}
                  </div>

                  {/* Verification */}
                  {hit.verificationStatus && (
                    <p className="mt-1 text-2xs text-warning">
                      核验: {hit.verificationStatus}
                    </p>
                  )}

                  {/* Link */}
                  {hit.url && (
                    <a
                      href={hit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1.5 inline-flex items-center gap-1 text-2xs text-accent transition-base hover:underline"
                    >
                      <svg
                        width="10"
                        height="10"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                      原文链接
                    </a>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* More indicator */}
      {processedHits.length > 20 && (
        <div className="border-t border-slate-100 px-4 py-2.5 text-center">
          <p className="text-2xs text-ink-tertiary">
            还有 {processedHits.length - 20} 条结果
          </p>
        </div>
      )}

      {/* No results after filter */}
      {processedHits.length === 0 && searchQuery && (
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-ink-tertiary">
            未找到匹配 &ldquo;{searchQuery}&rdquo; 的法规
          </p>
        </div>
      )}
    </div>
  );
}

// ── Score badge sub-component ──
function ScoreBadge({ score }: { score: number }) {
  const pct = Math.min(Math.max(score, 0), 1);
  let color: string;
  if (pct >= 0.7) color = "text-success";
  else if (pct >= 0.4) color = "text-warning";
  else color = "text-ink-tertiary";

  return (
    <span className={clsx("text-2xs font-medium", color)}>
      {Math.round(pct * 100)}%
    </span>
  );
}
