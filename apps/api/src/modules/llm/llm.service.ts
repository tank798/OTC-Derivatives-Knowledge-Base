import { Injectable } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";

export type LlmChatMessage =
  | { role: "system" | "user"; content: string }
  | { role: "assistant"; content: string | null; tool_calls?: Array<{
      id: string; type: "function";
      function: { name: string; arguments: string };
    }> }
  | { role: "tool"; tool_call_id: string; content: string };

@Injectable()
export class LlmService {
  private readonly apiKey: string | null;
  private readonly baseURL: string;
  private readonly model: string;

  constructor(private readonly configService: ConfigService) {
    this.apiKey = this.configService.get<string>("LLM_API_KEY") ?? null;
    this.baseURL = (this.configService.get<string>("LLM_BASE_URL") ?? "https://api.deepseek.com").replace(/\/$/, "");
    this.model = this.configService.get<string>("LLM_MODEL") ?? "deepseek-v4-pro";
  }

  get isConfigured(): boolean {
    return Boolean(this.apiKey);
  }

  get modelName(): string {
    return this.model;
  }

  /** Simple chat completion (non-streaming), returns text content. */
  async chat(
    systemPrompt: string,
    userPrompt: string,
    timeoutMs = 120000
  ): Promise<string> {
    if (!this.apiKey) throw new Error("LLM_API_KEY is not configured");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const body = {
        model: this.model,
        temperature: 0.2,
        stream: false,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      };

      const resp = await fetch(`${this.baseURL}/chat/completions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      const text = await resp.text();
      const payload = text ? JSON.parse(text) : {};

      if (!resp.ok) {
        const msg = payload?.error?.message ?? payload?.message ?? `HTTP ${resp.status}`;
        throw new Error(msg);
      }

      const content = payload?.choices?.[0]?.message?.content;
      if (typeof content !== "string") {
        throw new Error("Empty response from LLM");
      }
      return content;
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`LLM request timed out after ${timeoutMs}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Streaming chat completion. Yields content chunks as they arrive.
   * Collect all chunks to reconstruct the full response.
   */
  async *streamChat(
    systemPrompt: string,
    userPrompt: string,
    timeoutMs = 120000
  ): AsyncGenerator<string, void, unknown> {
    if (!this.apiKey) throw new Error("LLM_API_KEY is not configured");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const body = {
        model: this.model,
        temperature: 0.2,
        stream: true,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      };

      const resp = await fetch(`${this.baseURL}/chat/completions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        const payload = text ? JSON.parse(text) : {};
        const msg = payload?.error?.message ?? payload?.message ?? `HTTP ${resp.status}`;
        throw new Error(msg);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("LLM stream response has no readable body");

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
          if (!trimmed.startsWith("data: ")) continue;
          const data = trimmed.slice(6);
          if (data === "[DONE]") return;

          try {
            const parsed = JSON.parse(data);
            const content: string | null = parsed?.choices?.[0]?.delta?.content;
            if (typeof content === "string" && content.length > 0) {
              yield content;
            }
          } catch {
            // Skip malformed JSON lines from streaming
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`LLM stream request timed out after ${timeoutMs}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /** Chat with tool calling support. */
  async chatWithTools(
    systemPrompt: string,
    messages: LlmChatMessage[],
    tools: Array<{
      type: "function";
      function: { name: string; description: string; parameters: Record<string, unknown> };
    }>,
    timeoutMs = 120000
  ): Promise<{
    content: string | null;
    toolCalls: Array<{ id: string; name: string; arguments: Record<string, unknown> }>;
  }> {
    if (!this.apiKey) throw new Error("LLM_API_KEY is not configured");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const body: Record<string, unknown> = {
        model: this.model,
        temperature: 0.2,
        stream: false,
        messages: [{ role: "system", content: systemPrompt }, ...messages],
        tools,
        tool_choice: "auto",
      };

      const resp = await fetch(`${this.baseURL}/chat/completions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      const text = await resp.text();
      const payload = text ? JSON.parse(text) : {};

      if (!resp.ok) {
        const msg = payload?.error?.message ?? payload?.message ?? `HTTP ${resp.status}`;
        throw new Error(msg);
      }

      const msg = payload?.choices?.[0]?.message ?? {};
      const content = typeof msg.content === "string" ? msg.content : null;
      const rawCalls = Array.isArray(msg.tool_calls) ? msg.tool_calls : [];

      const toolCalls = rawCalls.map((tc: Record<string, unknown>, i: number) => {
        const fn = tc.function as Record<string, unknown> | undefined;
        const name = typeof fn?.name === "string" ? fn.name : "";
        const rawArgs = typeof fn?.arguments === "string" ? fn.arguments : "{}";
        let args: Record<string, unknown> = {};
        try { args = JSON.parse(rawArgs); } catch { /* keep empty */ }
        return { id: (tc.id as string) ?? `call_${i}`, name, arguments: args };
      });

      return { content, toolCalls };
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`LLM request timed out after ${timeoutMs}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
