import type { ApiResponse, ComplianceQueryResponseData } from "@otc/shared";

const API_BASE = "/api/proxy";

export async function queryCompliance(query: string): Promise<{
  answer: ComplianceQueryResponseData["answer"];
  hits: ComplianceQueryResponseData["hits"];
}> {
  const resp = await fetch(`${API_BASE}/compliance/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    cache: "no-store",
  });
  const json = (await resp.json()) as ApiResponse<ComplianceQueryResponseData>;
  if (!json.success) {
    throw new Error(json.error?.message ?? "Unknown error");
  }
  return json.data;
}

export async function checkHealth(): Promise<{
  status: string;
  indexReady: boolean;
  stats: { evidences: number; clauses: number };
}> {
  const resp = await fetch(`${API_BASE}/compliance/health`, { cache: "no-store" });
  const json = (await resp.json()) as ApiResponse<{
    status: string;
    indexReady: boolean;
    stats: { evidences: number; clauses: number };
  }>;
  if (!json.success) {
    throw new Error(json.error?.message ?? "Unknown error");
  }
  return json.data;
}
