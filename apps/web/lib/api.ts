import type {
  ApiResponse,
  ComplianceQueryResponseData,
  ComplianceStreamEvent,
} from "@otc/shared";

const API_BASE = "/api/proxy";
const DEFAULT_TIMEOUT = 30_000;

// ── Error class with Chinese messages ──
export class ApiError extends Error {
  code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

function getChineseErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return "请求参数有误，请检查输入";
    case 404:
      return "服务接口未找到，请联系管理员";
    case 413:
      return "请求内容过长，请精简问题";
    case 429:
      return "请求过于频繁，请稍后再试";
    case 500:
      return "服务内部错误，请稍后重试";
    case 502:
    case 503:
      return "服务暂时不可用，请稍后重试";
    case 504:
      return "请求超时，请简化问题或稍后重试";
    default:
      return `请求失败（${status}），请稍后重试`;
  }
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeout?: number } = {}
): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return resp;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("请求超时，请简化问题或检查网络");
    }
    if (err instanceof TypeError) {
      throw new ApiError("网络连接失败，请检查网络");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ── Non-streaming query ──
export async function queryCompliance(
  query: string
): Promise<ComplianceQueryResponseData> {
  const resp = await fetchWithTimeout(`${API_BASE}/compliance/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    cache: "no-store",
  });

  if (!resp.ok) {
    throw new ApiError(getChineseErrorMessage(resp.status));
  }

  const json = (await resp.json()) as ApiResponse<ComplianceQueryResponseData>;
  if (!json.success) {
    throw new ApiError(
      json.error?.message ?? "查询失败，请稍后重试",
      json.error?.code
    );
  }
  return json.data;
}

// ── Health check ──
export async function checkHealth(): Promise<{
  status: string;
  indexReady: boolean;
  stats: { evidences: number; clauses: number };
}> {
  const resp = await fetchWithTimeout(`${API_BASE}/compliance/health`, {
    cache: "no-store",
    timeout: 10_000,
  });

  if (!resp.ok) {
    throw new ApiError(getChineseErrorMessage(resp.status));
  }

  const json = (await resp.json()) as ApiResponse<{
    status: string;
    indexReady: boolean;
    stats: { evidences: number; clauses: number };
  }>;

  if (!json.success) {
    throw new ApiError(
      json.error?.message ?? "获取服务状态失败",
      json.error?.code
    );
  }
  return json.data;
}

// ── Streaming query (SSE-based) ──
export async function queryComplianceStream(
  query: string,
  onEvent: (event: ComplianceStreamEvent) => void,
  options?: { signal?: AbortSignal; timeout?: number }
): Promise<void> {
  const controller = new AbortController();
  const signal = options?.signal
    ? anySignal([options.signal, controller.signal])
    : controller.signal;

  const timeout = options?.timeout ?? DEFAULT_TIMEOUT;
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(`${API_BASE}/compliance/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ query }),
      signal,
      cache: "no-store",
    });

    if (!resp.ok) {
      onEvent({ type: "error", message: getChineseErrorMessage(resp.status) });
      return;
    }

    const reader = resp.body?.getReader();
    if (!reader) {
      onEvent({ type: "error", message: "无法读取响应流" });
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;

        try {
          const data = JSON.parse(trimmed.slice(6)) as ComplianceStreamEvent;
          onEvent(data);
          if (data.type === "error" || data.type === "done") return;
        } catch {
          // Skip malformed SSE lines
        }
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      onEvent({ type: "error", message: "查询已取消或超时" });
    } else {
      onEvent({
        type: "error",
        message:
          err instanceof Error ? err.message : "连接失败，请稍后重试",
      });
    }
  } finally {
    clearTimeout(timer);
  }
}

// ── Utility: combine multiple AbortSignals ──
function anySignal(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), {
      once: true,
    });
  }
  return controller.signal;
}
