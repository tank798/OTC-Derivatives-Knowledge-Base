"use client";

import type { RefObject } from "react";
import type { ChatMessage } from "./workspace";
import { ComplianceAnswerCard } from "./compliance-answer-card";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  onSubmit: (text: string) => void;
  input: string;
  setInput: (v: string) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
};

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="thinking-bubble-dot text-xl leading-none">.</span>
      <span className="thinking-bubble-dot text-xl leading-none">.</span>
      <span className="thinking-bubble-dot text-xl leading-none">.</span>
    </span>
  );
}

export function ChatPanel({
  messages,
  loading,
  onSubmit,
  input,
  setInput,
  onKeyDown,
  inputRef,
}: Props) {
  const showWelcome = messages.length === 0;

  return (
    <div className="mx-auto flex h-full max-w-[800px] flex-col">
      {/* Messages */}
      <div className="flex-1 space-y-6">
        {showWelcome && (
          <div className="py-16 text-center">
            <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
              金融监管合规问答
            </h1>
            <p className="mt-3 text-slate-500">
              输入产品结构或合规问题，获取法规依据和合规判断
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["场外衍生品", "收益互换", "场外期权", "收益凭证", "适当性管理", "跨境"].map(
                (tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
                  >
                    {tag}
                  </span>
                )
              )}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "user" ? (
              <div className="max-w-[80%] rounded-2xl bg-slate-100 px-5 py-3 text-sm leading-7 text-slate-900">
                {msg.text}
              </div>
            ) : msg.status === "loading" ? (
              <div className="text-slate-500">
                <TypingDots />
              </div>
            ) : msg.status === "error" ? (
              <div className="max-w-[85%] rounded-2xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">
                {msg.text}
              </div>
            ) : msg.data ? (
              <ComplianceAnswerCard data={msg.data} />
            ) : (
              <div className="max-w-[85%] text-sm leading-7 text-slate-700">
                {msg.text}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="sticky bottom-0 mt-4 border-t border-slate-100 bg-white pt-4">
        <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm focus-within:border-slate-300 focus-within:shadow-md transition">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="输入产品结构或合规问题..."
            rows={2}
            className="flex-1 resize-none bg-transparent text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400"
            disabled={loading}
          />
          <button
            onClick={() => onSubmit(input)}
            disabled={loading || !input.trim()}
            className="shrink-0 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "..." : "发送"}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate-400">
          按 Enter 发送，Shift+Enter 换行 · 所有回答均标注法规来源
        </p>
      </div>
    </div>
  );
}
