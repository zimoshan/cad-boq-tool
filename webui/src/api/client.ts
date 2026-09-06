// webapi 客户端（fetch wrapper）
// 2026-09-06 Web 化 Phase 0

const API_BASE = "/api";  // dev 由 vite proxy 转 :8521；prod 同源

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: { message: res.statusText } }));
    const detail = body.detail || body;
    throw new ApiError(res.status, detail.code || "unknown", detail.message || res.statusText);
  }
  return res.json();
}

export const api = {
  // health
  health: () => request<{ status: string; version: string }>("/health").catch(() => ({ status: "down" as string, version: "?" })),

  // CAD
  cad: {
    parse: (projectId: number, filePath: string) =>
      request("/cad/parse", { method: "POST", body: JSON.stringify({ project_id: projectId, file_path: filePath }) }),
    viewport: (sheetId: number, minX: number, minY: number, maxX: number, maxY: number, limit = 10000) =>
      request("/cad/viewport", {
        method: "POST",
        body: JSON.stringify({ sheet_id: sheetId, min_x: minX, min_y: minY, max_x: maxX, max_y: maxY, limit }),
      }),
  },

  // Binding
  binding: {
    generate: (projectId: number, sheetId?: number, useLlm = true, topN = 5) =>
      request("/binding/generate", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, sheet_id: sheetId, use_llm: useLlm, top_n: topN }),
      }),
    confirm: (candidateId: number) =>
      request("/binding/confirm", { method: "POST", body: JSON.stringify({ candidate_id: candidateId }) }),
    reject: (candidateId: number, reason = "") =>
      request("/binding/reject", { method: "POST", body: JSON.stringify({ candidate_id: candidateId, reason }) }),
  },

  // BOQ
  boq: {
    parse: (projectId: number, filePath: string) =>
      request("/boq/parse", { method: "POST", body: JSON.stringify({ project_id: projectId, file_path: filePath }) }),
    writeback: (projectId: number, projectScale = 1.0) =>
      request("/boq/writeback", { method: "POST", body: JSON.stringify({ project_id: projectId, project_scale: projectScale }) }),
  },
};
