"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { ComplianceQueryResponseData } from "@otc/shared";
import { queryCompliance } from "../lib/api";
import { Sidebar } from "./sidebar";
import { ChatPanel } from "./chat-panel";
import { ProductStructurePanel } from "./product-structure-panel";
import { RegulationHitsPanel } from "./regulation-hits-panel";

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
];

export function Workspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [latestData, setLatestData] = useState<ComplianceQueryResponseData | null>(null);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(async (text: string) => {
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
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "查询失败";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, text: `❌ ${errMsg}`, status: "error" }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  const latestAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const showPanels = latestAssistant?.data != null;

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Left Sidebar */}
      <Sidebar
        questions={EXAMPLE_QUESTIONS}
        onSelect={(q) => {
          setInput(q);
          inputRef.current?.focus();
        }}
        messages={messages}
      />

      {/* Center Chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div
          ref={scrollRef}
          className="hidden-scrollbar flex-1 overflow-y-auto px-4 py-6 sm:px-8 lg:px-12"
        >
          <ChatPanel
            messages={messages}
            loading={loading}
            onSubmit={handleSubmit}
            input={input}
            setInput={setInput}
            onKeyDown={handleKeyDown}
            inputRef={inputRef}
          />
        </div>
      </div>

      {/* Right Panels */}
      {showPanels && latestAssistant?.data ? (
        <div className="hidden-scrollbar w-96 shrink-0 overflow-y-auto border-l border-slate-200 bg-slate-50 p-4 xl:block">
          <ProductStructurePanel
            structure={latestAssistant.data.answer.productStructure}
            conclusion={latestAssistant.data.answer.conclusion}
            conclusionLabel={latestAssistant.data.answer.conclusionLabel}
          />
          <RegulationHitsPanel hits={latestAssistant.data.hits} />
        </div>
      ) : (
        <div className="hidden w-96 shrink-0 border-l border-slate-200 bg-slate-50 p-6 xl:flex xl:flex-col xl:items-center xl:justify-center">
          <p className="text-sm text-slate-400">提交问题后<br />这里将展示产品结构<br />和命中法规</p>
        </div>
      )}
    </div>
  );
}
