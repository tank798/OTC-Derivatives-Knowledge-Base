"use client";

import type { ChatMessage } from "./workspace";

type Props = {
  questions: string[];
  onSelect: (q: string) => void;
  messages: ChatMessage[];
};

export function Sidebar({ questions, onSelect, messages }: Props) {
  const history = messages
    .filter((m) => m.role === "user")
    .slice(-10)
    .reverse();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-slate-50 md:flex">
      {/* Brand */}
      <div className="border-b border-slate-200 px-5 py-4">
        <h1 className="text-base font-bold text-slate-900">合规问答</h1>
        <p className="mt-0.5 text-xs text-slate-500">
          金融监管法规知识库
        </p>
      </div>

      {/* Example Questions */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          示例问题
        </p>
        <div className="space-y-1">
          {questions.map((q) => (
            <button
              key={q.slice(0, 20)}
              onClick={() => onSelect(q)}
              className="block w-full rounded-lg px-3 py-2 text-left text-sm leading-5 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              {q}
            </button>
          ))}
        </div>

        {/* History */}
        {history.length > 0 && (
          <>
            <p className="mb-2 mt-6 px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              历史提问
            </p>
            <div className="space-y-1">
              {history.map((m) => (
                <div
                  key={m.id}
                  className="truncate rounded-lg px-3 py-2 text-sm text-slate-500"
                >
                  {m.text.slice(0, 40)}...
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-slate-200 px-5 py-3">
        <p className="text-xs text-slate-400">
          仅供合规参考，不构成法律意见
        </p>
      </div>
    </aside>
  );
}
