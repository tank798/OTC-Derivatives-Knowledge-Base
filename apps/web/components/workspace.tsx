"use client";

import { useState, useRef, useEffect, useCallback, Component } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";
import { queryCompliance } from "../lib/api";
import { Sidebar } from "./sidebar";
import { ChatPanel } from "./chat-panel";
import { ProductStructurePanel } from "./product-structure-panel";
import { RegulationHitsPanel } from "./regulation-hits-panel";
import clsx from "clsx";

// ── Chat Message Type ──
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  status?: "loading" | "done" | "error";
  data?: ComplianceQueryResponseData;
};

const EXAMPLE_QUESTIONS = [
  "证券公司做收益互换需要关注哪些监管要求？",
  "场外期权能否面向普通个人投资者销售？",
  "期货公司开展衍生品交易需要给客户做风险揭示吗？",
  "一个挂钩股票指数的收益凭证产品需要看哪些规则？",
  "私募基金能否投资证券公司收益凭证？",
  "跨境收益互换涉及哪些外汇管理要求？",
  "结构化票据的销售适用性要求有哪些？",
  "信用保护工具的合格对手方有哪些要求？",
];

// ── Skeleton Loading ──
function LoadingSkeleton() {
  return (
    <div className="mx-auto flex h-full max-w-[820px] flex-col items-center justify-center py-16 animate-fade-in">
      <div className="flex flex-col items-center gap-4">
        <div className="h-12 w-12 animate-pulse rounded-full bg-slate-200" />
        <div className="h-6 w-64 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-80 animate-pulse rounded bg-slate-100" />
      </div>
    </div>
  );
}

// ── Error Boundary ──
type ErrorBoundaryProps = { children: React.ReactNode };
type ErrorBoundaryState = { hasError: boolean; error?: Error };

export class WorkspaceErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-surface">
          <div className="mx-auto max-w-md text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-danger"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-ink">应用出现异常</h2>
            <p className="mt-1 text-sm text-ink-secondary">
              请尝试刷新页面或联系管理员
            </p>
            <p className="mt-3 text-xs text-ink-tertiary">
              {this.state.error?.message}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: undefined });
                window.location.reload();
              }}
              className="mt-6 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition-base hover:bg-accent/90"
            >
              刷新页面
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Main Workspace ──
export function Workspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [latestData, setLatestData] = useState<ComplianceQueryResponseData | null>(null);
  const [input, setInput] = useState("");
  const [showDetailPanel, setShowDetailPanel] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Simulate initial loading
  useEffect(() => {
    const timer = setTimeout(() => setIsInitializing(false), 600);
    return () => clearTimeout(timer);
  }, []);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Handle submit
  const handleSubmit = useCallback(
    async (text: string) => {
      const query = text.trim();
      if (!query || loading) return;

      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        text: query,
        status: "done",
      };
      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: "",
        status: "loading",
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInput("");
      setLoading(true);

      try {
        const data = await queryCompliance(query);
        setLatestData(data);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, text: data.answer.conclusion, status: "done", data }
              : m
          )
        );
        setShowDetailPanel(true);
      } catch (err) {
        const errMsg =
          err instanceof Error ? err.message : "查询失败，请稍后重试";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, text: errMsg, status: "error" }
              : m
          )
        );
      } finally {
        setLoading(false);
      }
    },
    [loading]
  );

  // Retry handler
  const handleRetry = useCallback(
    (text: string) => {
      // Remove the last error message, then re-submit
      setMessages((prev) => {
        const lastTwo = prev.slice(-2);
        if (
          lastTwo.length === 2 &&
          lastTwo[0].role === "user" &&
          lastTwo[1].role === "assistant" &&
          lastTwo[1].status === "error"
        ) {
          return prev.slice(0, -2);
        }
        return prev;
      });
      // Small delay to let state settle
      setTimeout(() => handleSubmit(text), 50);
    },
    [handleSubmit]
  );

  // Keyboard handler
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSubmit(input);
      }
    },
    [handleSubmit, input]
  );

  // New query
  const handleNewQuery = useCallback(() => {
    setInput("");
    inputRef.current?.focus();
  }, []);

  // Find latest assistant message with data
  const latestAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const showPanels = latestAssistant?.data != null;

  // Responsive detail drawer
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState(false);

  const toggleMobilePanel = () => setIsMobilePanelOpen(!isMobilePanelOpen);

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Sidebar */}
      <Sidebar
        questions={EXAMPLE_QUESTIONS}
        onSelect={(q) => {
          setInput(q);
          handleSubmit(q);
        }}
        messages={messages}
        onNewQuery={handleNewQuery}
      />

      {/* Center Chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        {isInitializing ? (
          <LoadingSkeleton />
        ) : (
          <>
            {/* Detail panel toggle (mobile) */}
            {showPanels && (
              <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2 md:hidden">
                <button
                  onClick={toggleMobilePanel}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-ink-secondary transition-base hover:bg-slate-50"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <rect x="3" y="3" width="7" height="7" />
                    <rect x="14" y="3" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" />
                    <rect x="3" y="14" width="7" height="7" />
                  </svg>
                  查看产品画像
                </button>
                <span className="text-2xs text-ink-tertiary">
                  {latestAssistant?.data?.hits.length ?? 0} 条命中法规
                </span>
              </div>
            )}

            <div className="flex-1 overflow-hidden">
              <ChatPanel
                messages={messages}
                loading={loading}
                onSubmit={handleSubmit}
                onRetry={handleRetry}
                input={input}
                setInput={setInput}
                onKeyDown={handleKeyDown}
                inputRef={inputRef}
                scrollRef={scrollRef}
              />
            </div>
          </>
        )}
      </div>

      {/* Right Detail Panel (Desktop) */}
      {showPanels && latestAssistant?.data ? (
        <aside className="hidden w-96 shrink-0 overflow-y-auto border-l border-slate-200 bg-surface scrollbar-thin xl:block">
          <div className="space-y-4 p-4">
            <ProductStructurePanel
              structure={latestAssistant.data.answer.productStructure}
              conclusion={latestAssistant.data.answer.conclusion}
              conclusionLabel={latestAssistant.data.answer.conclusionLabel}
            />
            <RegulationHitsPanel hits={latestAssistant.data.hits} />
          </div>
        </aside>
      ) : (
        <aside className="hidden w-96 shrink-0 border-l border-slate-200 bg-surface xl:flex xl:flex-col xl:items-center xl:justify-center">
          <div className="px-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-ink-tertiary"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
              </svg>
            </div>
            <p className="text-sm text-ink-tertiary">
              提交合规问题后
              <br />
              这里将展示产品画像
              <br />
              和命中法规详情
            </p>
          </div>
        </aside>
      )}

      {/* Mobile Detail Panel (slide-over overlay) */}
      {showPanels && latestAssistant?.data && (
        <>
          {/* Overlay */}
          {isMobilePanelOpen && (
            <div
              className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm xl:hidden"
              onClick={() => setIsMobilePanelOpen(false)}
            />
          )}

          {/* Drawer */}
          <div
            className={clsx(
              "fixed bottom-0 left-0 right-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-2xl bg-surface shadow-floating transition-transform duration-300 ease-out xl:hidden scrollbar-thin",
              isMobilePanelOpen ? "translate-y-0" : "translate-y-full"
            )}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-surface px-5 py-3">
              <h3 className="text-sm font-semibold text-ink">产品画像与法规</h3>
              <button
                onClick={() => setIsMobilePanelOpen(false)}
                className="rounded-lg p-1.5 text-ink-tertiary transition-base hover:bg-slate-100"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="space-y-4 p-4 pb-8">
              <ProductStructurePanel
                structure={latestAssistant.data.answer.productStructure}
                conclusion={latestAssistant.data.answer.conclusion}
                conclusionLabel={latestAssistant.data.answer.conclusionLabel}
              />
              <RegulationHitsPanel hits={latestAssistant.data.hits} />
            </div>
          </div>
        </>
      )}

    </div>
  );
}
