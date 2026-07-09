"use client";

import { useState, useEffect, useCallback } from "react";
import type { ChatMessage } from "./workspace";
import { checkHealth } from "../lib/api";

type Props = {
  questions: string[];
  onSelect: (q: string) => void;
  messages: ChatMessage[];
  onNewQuery: () => void;
};

type HealthStats = {
  evidences: number;
  clauses: number;
  loading: boolean;
  error: boolean;
};

export function Sidebar({ questions, onSelect, messages, onNewQuery }: Props) {
  // Load history from localStorage
  const [history, setHistory] = useState<{ id: string; text: string }[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("compliance-qa-history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Health stats
  const [healthStats, setHealthStats] = useState<HealthStats>({
    evidences: 0,
    clauses: 0,
    loading: true,
    error: false,
  });

  // Persist latest user messages to history
  useEffect(() => {
    const userMessages = messages
      .filter((m) => m.role === "user")
      .slice(-20)
      .reverse()
      .map((m) => ({ id: m.id, text: m.text }));
    if (userMessages.length > 0) {
      setHistory(userMessages);
      try {
        localStorage.setItem(
          "compliance-qa-history",
          JSON.stringify(userMessages)
        );
      } catch {
        // localStorage quota exceeded, silently fail
      }
    }
  }, [messages]);

  // Fetch health stats
  const fetchHealth = useCallback(async () => {
    try {
      const data = await checkHealth();
      setHealthStats({
        evidences: data.stats.evidences,
        clauses: data.stats.clauses,
        loading: false,
        error: false,
      });
    } catch {
      setHealthStats((prev) => ({ ...prev, loading: false, error: true }));
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleClearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem("compliance-qa-history");
    } catch {
      // ignore
    }
  };

  return (
    <aside className="hidden w-72 shrink-0 flex-col bg-primary md:flex">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent shadow-sm">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <div className="min-w-0">
          <h1 className="text-base font-bold text-white/95">合规问答</h1>
          <p className="truncate text-2xs text-white/40">
            OTC Derivatives Compliance
          </p>
        </div>
      </div>

      {/* New query button */}
      <div className="px-4 pt-4">
        <button
          onClick={onNewQuery}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/15 px-4 py-2.5 text-sm font-medium text-white/80 transition-base hover:bg-white/10 hover:text-white"
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
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新建查询
        </button>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin-dark px-3 py-4">
        {/* Example Questions */}
        <p className="mb-2 px-2 text-2xs font-semibold uppercase tracking-wider text-white/30">
          示例问题
        </p>
        <div className="flex flex-wrap gap-1.5 px-1">
          {questions.map((q) => (
            <button
              key={q.slice(0, 20)}
              onClick={() => onSelect(q)}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/60 transition-base hover:border-white/20 hover:bg-white/10 hover:text-white/85"
            >
              {q.length > 18 ? q.slice(0, 17) + "..." : q}
            </button>
          ))}
        </div>

        {/* History */}
        {history.length > 0 && (
          <>
            <div className="mb-2 mt-6 flex items-center justify-between px-2">
              <p className="text-2xs font-semibold uppercase tracking-wider text-white/30">
                历史查询
              </p>
              <button
                onClick={handleClearHistory}
                className="text-2xs text-white/25 transition-base hover:text-white/50"
              >
                清空
              </button>
            </div>
            <div className="space-y-0.5">
              {history.slice(0, 30).map((item) => (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.text)}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-white/50 transition-base hover:bg-white/8 hover:text-white/75"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="shrink-0 opacity-40"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  <span className="truncate">{item.text}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Footer with health stats */}
      <div className="border-t border-white/10 px-5 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                healthStats.loading
                  ? "bg-white/20"
                  : healthStats.error
                  ? "bg-danger"
                  : "bg-success"
              }`}
            />
            <span className="text-2xs text-white/35">
              {healthStats.loading
                ? "连接中..."
                : healthStats.error
                ? "服务异常"
                : "服务正常"}
            </span>
          </div>
          {!healthStats.loading && !healthStats.error && (
            <div className="flex gap-3 text-2xs text-white/30">
              <span>{healthStats.evidences} 证据</span>
              <span>{healthStats.clauses} 条款</span>
            </div>
          )}
        </div>
        <p className="mt-1.5 text-2xs text-white/20">
          仅供合规参考，不构成法律意见
        </p>
      </div>
    </aside>
  );
}
