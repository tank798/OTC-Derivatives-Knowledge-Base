export const promptManifest = {
  agent: {
    compliance: "agent/compliance-agent.md",
  },
} as const;

export type PromptKey = keyof typeof promptManifest.agent;
