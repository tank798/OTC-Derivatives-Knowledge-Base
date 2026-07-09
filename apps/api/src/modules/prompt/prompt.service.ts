import { Injectable } from "@nestjs/common";
import { readFileSync } from "fs";
import { resolve } from "path";
import { promptManifest } from "@otc/prompts";

@Injectable()
export class PromptService {
  private readonly cache = new Map<string, string>();
  private readonly promptsDir: string;

  constructor() {
    // Resolve from repo root (dist/apps/api/src/modules/prompt → up 6 levels)
    const repoRoot = resolve(__dirname, "../../../../../../");
    this.promptsDir = resolve(repoRoot, "packages/prompts");
  }

  getComplianceAgentPrompt(): string {
    return this.loadPrompt(promptManifest.agent.compliance);
  }

  private loadPrompt(relativePath: string): string {
    const cached = this.cache.get(relativePath);
    if (cached) return cached;

    const fullPath = resolve(this.promptsDir, relativePath);
    try {
      const content = readFileSync(fullPath, "utf-8");
      this.cache.set(relativePath, content);
      return content;
    } catch {
      console.error(`[PromptService] Failed to load prompt: ${fullPath}`);
      return "";
    }
  }
}
