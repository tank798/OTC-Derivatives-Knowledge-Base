"use client";

import { useEffect, type RefObject } from "react";
import type { ChatMessage } from "./workspace";
import { ComplianceAnswerCard } from "./compliance-answer-card";
import { ThinkingBubble } from "./thinking-bubble";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  onSubmit: (text: string) => void;
  onRetry: (text: string) => void;
  input: string;
  setInput: (v: string) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  scrollRef: RefObject<HTMLDivElement | null>;
};

const EXAMPLE_TAGS = [
  "收益互换监管要求",
  "场外期权适当性管理",
  "收益凭证合格投资者",
  "跨境衍生品外汇管理",
  "期货公司风险揭示",
  "私募基金收益凭证",
  "结构化产品挂钩规则",
  "SAC协议签署要求",
];

export function ChatPanel({
  messages,
  loading,
  onSubmit,
  onRetry,
  input,
  setInput,
  onKeyDown,
  inputRef,
  scrollRef,
}: Props) {
  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, scrollRef]);

  const showWelcome = messages.length === 0;

  return (
    <div className="mx-auto flex h-full max-w-[820px] flex-col">
      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto scrollbar-thin px-1 pb-4"
      >
        {showWelcome ? (
          <div className="flex min-h-full flex-col items-center justify-center py-16">
            {/* Logo / Icon */}
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10">
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-accent"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>

            <h1 className="text-2xl font-bold text-ink sm:text-3xl">
              金融监管合规问答
            </h1>
            <p className="mt-2 max-w-md text-center text-sm text-ink-secondary">
              输入产品结构或合规问题，系统将自动识别产品要素、
              <br />
              检索相关法规并给出合规判断
            </p>

            {/* Quick tags */}
            <div className="mt-8 w-full max-w-xl">
              <p className="mb-3 text-center text-xs text-ink-tertiary">
                快速尝试以下问题
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_TAGS.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => onSubmit(tag)}
                    className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs text-ink-secondary transition-base hover:border-accent/30 hover:bg-accent/5 hover:text-accent"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>

            {/* Features hint */}
            <div className="mt-10 grid grid-cols-3 gap-6">
              <div className="text-center">
                <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-success"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <p className="text-xs font-medium text-ink">合规判断</p>
                <p className="mt-0.5 text-2xs text-ink-tertiary">
                  即时合规结论
                </p>
              </div>
              <div className="text-center">
                <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-accent"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                  </svg>
                </div>
                <p className="text-xs font-medium text-ink">法规溯源</p>
                <p className="mt-0.5 text-2xs text-ink-tertiary">
                  逐条标注依据
                </p>
              </div>
              <div className="text-center">
                <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-warning/10">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-warning"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </div>
                <p className="text-xs font-medium text-ink">风险识别</p>
                <p className="mt-0.5 text-2xs text-ink-tertiary">
                  标记待补信息
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {messages.map((msg, idx) => {
              // Find the preceding user message for retry
              const userQueryForRetry =
                msg.role === "assistant" && msg.status === "error"
                  ? (() => {
                      for (let i = idx - 1; i >= 0; i--) {
                        if (messages[i].role === "user") return messages[i].text;
                      }
                      return "";
                    })()
                  : "";

              return (
              <div
                key={msg.id}
                className={`flex animate-fade-in ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "user" ? (
                  <div className="max-w-[75%] rounded-2xl bg-accent/8 px-5 py-3 text-sm leading-7 text-ink shadow-sm">
                    {msg.text}
                  </div>
                ) : msg.status === "loading" ? (
                  <ThinkingBubble />
                ) : msg.status === "error" ? (
                  <div className="w-full max-w-[85%] animate-fade-in rounded-xl border border-danger/20 bg-danger/5 p-4">
                    <div className="flex items-start gap-3">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        className="mt-0.5 shrink-0 text-danger"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <line x1="15" y1="9" x2="9" y2="15" />
                        <line x1="9" y1="9" x2="15" y2="15" />
                      </svg>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-danger">
                          查询失败
                        </p>
                        <p className="mt-0.5 text-xs text-danger/70">
                          {msg.text}
                        </p>
                        {userQueryForRetry && (
                          <button
                            onClick={() => onRetry(userQueryForRetry)}
                            className="mt-2 rounded-lg border border-danger/20 bg-white px-3 py-1 text-xs font-medium text-danger transition-base hover:bg-danger/5"
                          >
                            重新发送
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ) : msg.data ? (
                  <ComplianceAnswerCard data={msg.data} />
                ) : (
                  <div className="max-w-[85%] animate-fade-in rounded-xl border border-slate-200 bg-white p-4 text-sm leading-7 text-ink shadow-sm">
                    {msg.text}
                  </div>
                )}
              </div>
            );
            })}
          </div>
        )}
      </div>

      {/* Input area - sticky bottom */}
      <div className="sticky bottom-0 border-t border-slate-200/70 bg-surface px-4 pb-4 pt-3">
        <div className="mx-auto max-w-[820px]">
          <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 shadow-sm transition-base focus-within:border-accent/30 focus-within:shadow-elevated">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="输入产品结构或合规问题..."
              rows={1}
              className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-sm leading-6 text-ink outline-none placeholder:text-ink-tertiary"
              disabled={loading}
            />
            <button
              onClick={() => onSubmit(input)}
              disabled={loading || !input.trim()}
              className="flex shrink-0 items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-base hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <span className="flex items-center gap-1">
                  <span className="inline-block h-1.5 w-1.5 animate-pulse-dot rounded-full bg-white/70" />
                  <span className="inline-block h-1.5 w-1.5 animate-pulse-dot rounded-full bg-white/70" />
                  <span className="inline-block h-1.5 w-1.5 animate-pulse-dot rounded-full bg-white/70" />
                </span>
              ) : (
                <>
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
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                  发送
                </>
              )}
            </button>
          </div>
          <div className="mt-1.5 flex items-center justify-between px-1">
            <p className="text-2xs text-ink-tertiary">
              Enter 发送 · Shift+Enter 换行
            </p>
            <p className="text-2xs text-ink-tertiary">
              所有回答均标注法规来源
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
