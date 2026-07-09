"use client";

import { useEffect, useState } from "react";

const THINKING_STAGES = [
  { key: "analyzing", label: "正在分析产品结构", icon: "🔍" },
  { key: "retrieving", label: "正在检索相关法规", icon: "📖" },
  { key: "generating", label: "正在生成合规意见", icon: "✍️" },
] as const;

function PulsingDot({ index }: { index: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 rounded-full bg-accent"
      style={{
        animation: "pulse-dot 1.4s ease-in-out infinite",
        animationDelay: `${index * 0.2}s`,
      }}
    />
  );
}

export function ThinkingBubble() {
  const [stageIndex, setStageIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  // Progress through stages over time
  useEffect(() => {
    const stageTimer = setInterval(() => {
      setStageIndex((prev) => Math.min(prev + 1, THINKING_STAGES.length - 1));
    }, 4000);
    return () => clearInterval(stageTimer);
  }, []);

  // Elapsed time counter
  useEffect(() => {
    const elapsedTimer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(elapsedTimer);
  }, []);

  const currentStages = THINKING_STAGES.slice(0, Math.max(stageIndex + 1, 1));

  return (
    <div className="w-full max-w-[85%] animate-fade-in">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {/* Progress indicator */}
        <div className="mb-3 flex items-center gap-2">
          <div className="flex items-center gap-0.5">
            <PulsingDot index={0} />
            <PulsingDot index={1} />
            <PulsingDot index={2} />
          </div>
          <span className="text-xs text-ink-tertiary">
            正在处理... {elapsed > 5 ? `(${elapsed}s)` : ""}
          </span>
        </div>

        {/* Stage progression */}
        <div className="space-y-1.5">
          {currentStages.map((stage, i) => {
            const isActive = i === stageIndex && i < THINKING_STAGES.length - 1;
            const isDone = i < stageIndex || (i === stageIndex && stageIndex >= THINKING_STAGES.length - 1);

            return (
              <div
                key={stage.key}
                className={`flex items-center gap-2 text-sm transition-all duration-300 ${
                  isActive
                    ? "text-accent"
                    : isDone
                    ? "text-success"
                    : "text-ink-secondary"
                }`}
              >
                <span className="w-5 text-center text-xs">
                  {isDone ? "✓" : isActive ? stage.icon : "○"}
                </span>
                <span
                  className={`${
                    isActive ? "font-medium" : isDone ? "" : "opacity-50"
                  }`}
                >
                  {stage.label}
                </span>
                {isActive && (
                  <span className="inline-flex gap-0.5">
                    <span
                      className="inline-block h-1 w-1 rounded-full bg-current animate-pulse-dot"
                      style={{ animationDelay: "0s" }}
                    />
                    <span
                      className="inline-block h-1 w-1 rounded-full bg-current animate-pulse-dot"
                      style={{ animationDelay: "0.2s" }}
                    />
                    <span
                      className="inline-block h-1 w-1 rounded-full bg-current animate-pulse-dot"
                      style={{ animationDelay: "0.4s" }}
                    />
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Subtle processing bar */}
        <div className="mt-3 h-0.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent to-accent/60 transition-all duration-700 ease-out"
            style={{
              width: `${Math.min(((stageIndex + 1) / THINKING_STAGES.length) * 100, 100)}%`,
            }}
          />
        </div>
      </div>
    </div>
  );
}
