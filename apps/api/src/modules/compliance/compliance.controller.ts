import { Controller, Post, Body, Get } from "@nestjs/common";
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
      const message = err instanceof Error ? err.message : "查询失败";
      console.error("[ComplianceController]", err);
      return fail(message);
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
