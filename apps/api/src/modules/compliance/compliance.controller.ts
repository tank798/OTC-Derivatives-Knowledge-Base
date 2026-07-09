import { Controller, Post, Body, Get, Res } from "@nestjs/common";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ExpressResponse = any;
import { ComplianceService } from "./compliance.service";
import { RetrievalService } from "../retrieval/retrieval.service";
import { ok, fail } from "../../common/api-response";

@Controller("compliance")
export class ComplianceController {
  constructor(
    private readonly compliance: ComplianceService,
    private readonly retrieval: RetrievalService,
  ) {}

  @Post("query")
  async query(@Body() body: { query: string }) {
    if (!body.query?.trim()) {
      return fail("请输入问题");
    }

    if (!this.retrieval.isReady) {
      return fail("知识库索引尚未加载完成，请稍后重试", "INDEX_NOT_READY");
    }

    try {
      const result = await this.compliance.answer(body.query.trim());
      return ok(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "合规查询失败";
      console.error("[ComplianceController] POST /compliance/query error:", err);
      return fail(message);
    }
  }

  @Post("query/stream")
  async queryStream(
    @Body() body: { query: string },
    @Res() res: ExpressResponse,
  ) {
    // Validate input before setting up SSE
    if (!body.query?.trim()) {
      res.status(400).json({ success: false, error: { message: "请输入问题" } });
      return;
    }

    if (!this.retrieval.isReady) {
      res.status(503).json({
        success: false,
        error: { message: "知识库索引尚未加载完成，请稍后重试", code: "INDEX_NOT_READY" },
      });
      return;
    }

    // Set SSE headers
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("X-Accel-Buffering", "no"); // Disable nginx buffering if proxied
    res.flushHeaders();

    // Handle client disconnect
    let aborted = false;
    res.on("close", () => {
      aborted = true;
    });

    try {
      const stream = this.compliance.answerStream(body.query.trim());

      for await (const event of stream) {
        if (aborted) break;

        res.write(`data: ${JSON.stringify(event)}\n\n`);

        // If using compression, flush after each event
        if (typeof (res as any).flush === "function") {
          (res as any).flush();
        }

        if (event.type === "done" || event.type === "error") break;
      }
    } catch (err) {
      if (!aborted) {
        const message = err instanceof Error ? err.message : "合规查询流异常";
        console.error("[ComplianceController] POST /compliance/query/stream error:", err);
        try {
          res.write(`data: ${JSON.stringify({ type: "error", message })}\n\n`);
        } catch {
          // Response may already be closed
        }
      }
    } finally {
      if (!aborted) {
        res.end();
      }
    }
  }

  @Get("health")
  health() {
    return ok({
      status: "ok",
      indexReady: this.retrieval.isReady,
      stats: this.retrieval.stats,
    });
  }
}
