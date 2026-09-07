// webapi TypeScript 客户端（用 openapi-typescript 生成的类型）
// 类型自动从 webapi/main.py 的 OpenAPI spec 生成（src/api/types.ts）
// 重新生成：npx openapi-typescript openapi.json -o src/api/types.ts
//          （或 npm run typegen:full 一键导出 + 生成）
import type { components } from "./types";

/**
 * Phase 4 commit 2：typesafe API 客户端（替换手写 ApiResponse/HealthResponse interface）
 */
class ApiError extends Error {
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

const API_BASE = "/api";  // dev: Vite proxy → :8521；prod: 同源

// ---- 类型化 endpoint 快捷方式 ----

export const api = {
  // health
  health: () => request<Record<string, unknown>>("/health").catch(() => ({ status: "down", version: "?" })),

  // CAD
  cad: {
    parse: (body: components["schemas"]["ParseRequest"]) =>
      request<components["schemas"]["ParseResponse"]>("/cad/parse", {
        method: "POST", body: JSON.stringify(body),
      }),
    viewport: (body: components["schemas"]["ViewportQuery"]) =>
      request<{ items: any[]; total: number }>("/cad/viewport", {
        method: "POST", body: JSON.stringify(body),
      }),
    metadata: (sheetId: number) =>
      request<Record<string, unknown>>(`/cad/metadata?sheet_id=${sheetId}`),
    sheets: (projectId: number) =>
      request<{ items: any[]; total: number }>(`/cad/sheets?project_id=${projectId}`),
    layers: (sheetId: number) =>
      request<{ items: any[]; total: number }>(`/cad/layers?sheet_id=${sheetId}`),
    blocks: (sheetId: number) =>
      request<{ items: any[]; total: number }>(`/cad/blocks?sheet_id=${sheetId}`),
    entities: (sheetId: number, params?: { layer?: string; block_name?: string; dxf_type?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams({ sheet_id: String(sheetId), ...(params || {}) } as any).toString();
      return request<{ items: any[]; limit: number; offset: number }>(`/cad/entities?${qs}`);
    },
  },

  // Binding
  binding: {
    generate: (body: components["schemas"]["GenerateCandidatesRequest"]) =>
      request<components["schemas"]["GenerateCandidatesResponse"]>("/binding/generate", {
        method: "POST", body: JSON.stringify(body),
      }),
    confirm: (body: components["schemas"]["ConfirmBindingRequest"]) =>
      request<Record<string, unknown>>("/binding/confirm", {
        method: "POST", body: JSON.stringify(body),
      }),
    reject: (body: components["schemas"]["RejectBindingRequest"]) =>
      request<Record<string, unknown>>("/binding/reject", {
        method: "POST", body: JSON.stringify(body),
      }),
  },

  // BOQ
  boq: {
    parse: (body: components["schemas"]["ParseBoqRequest"]) =>
      request<components["schemas"]["ParseBoqResponse"]>("/boq/parse", {
        method: "POST", body: JSON.stringify(body),
      }),
    writeback: (body: components["schemas"]["WritebackRequest"]) =>
      request<components["schemas"]["WritebackResponse"]>("/boq/writeback", {
        method: "POST", body: JSON.stringify(body),
      }),
    writebackAudited: (body: { project_id: number; project_scale?: number; source_file_path: string }) =>
      request<{ project_id: number; written: number; failed: number; file_sha256: string; audited_rows: number }>(
        "/boq/writeback-audited",
        { method: "POST", body: JSON.stringify(body) }
      ),
    export: (body: components["schemas"]["ExportBoqRequest"]) =>
      request<components["schemas"]["ExportBoqResponse"]>("/boq/export", {
        method: "POST", body: JSON.stringify(body),
      }),
  },

  // Dataset
  dataset: {
    list: () => request<{ entries: any[]; total: number; backend: string }>("/dataset"),
    mark: (body: { name: string; project_id: number; file_path: string; data_type: string; note?: string }) =>
      request<Record<string, unknown>>("/dataset/mark", {
        method: "POST", body: JSON.stringify(body),
      }),
    deactivate: (body: { entry_id: number }) =>
      request<{ ok: boolean; entry_id: number }>("/dataset/deactivate", {
        method: "POST", body: JSON.stringify(body),
      }),
    manifests: () => request<{ datasets: string[]; total: number }>("/dataset/manifests"),
    manifest: (datasetId: string = "lbh") =>
      request<{ manifest: any; missing_fields: string[]; valid: boolean }>(
        `/dataset/manifest?dataset_id=${datasetId}`
      ),
    updateManifest: (body: { dataset_id?: string; key: string; value: string }) =>
      request<{ updated: boolean; manifest: any }>("/dataset/manifest", {
        method: "POST", body: JSON.stringify(body),
      }),
  },

  // Jobs
  jobs: {
    list: (status?: string) => {
      const qs = status ? `?status=${status}` : "";
      return request<{ jobs: any[]; total: number }>(`/jobs${qs}`);
    },
    get: (jobId: string) => request<Record<string, unknown>>(`/jobs/${jobId}`),
    submit: (body: { name: string; payload?: Record<string, unknown> }) =>
      request<Record<string, unknown>>("/jobs/submit", {
        method: "POST", body: JSON.stringify(body),
      }),
    cancel: (jobId: string) =>
      request<{ ok: boolean; job_id: string }>(`/jobs/${jobId}/cancel`, { method: "POST" }),
  },

  // Extraction
  extraction: {
    run: (body: components["schemas"]["ExtractionRequest"]) =>
      request<components["schemas"]["ExtractionResponse"]>("/extraction/run", {
        method: "POST", body: JSON.stringify(body),
      }),
    listEos: (projectId: number, params?: { object_type?: string; sheet_id?: number }) => {
      const qs = new URLSearchParams({ project_id: String(projectId), ...(params || {}) } as any).toString();
      return request<components["schemas"]["EngineeringObjectRead"][]>(`/extraction/eos?${qs}`);
    },
  },

  // Takeoff
  takeoff: {
    run: (body: components["schemas"]["TakeoffRequest"]) =>
      request<components["schemas"]["TakeoffResponse"]>("/takeoff/run", {
        method: "POST", body: JSON.stringify(body),
      }),
  },

  // LLM
  llm: {
    getSettings: () => request<components["schemas"]["LlmSettingsRead"]>("/llm/settings"),
    updateSettings: (body: components["schemas"]["LlmSettingsUpdate"]) =>
      request<components["schemas"]["LlmSettingsRead"]>("/llm/settings", {
        method: "PUT", body: JSON.stringify(body),
      }),
    chat: (body: components["schemas"]["ChatRequest"]) =>
      request<components["schemas"]["ChatResponse"]>("/llm/chat", {
        method: "POST", body: JSON.stringify(body),
      }),
  },

  // Audit
  audit: {
    llmRuns: (projectId: number, taskType?: string, limit: number = 100) => {
      const qs = new URLSearchParams({ project_id: String(projectId), limit: String(limit), ...(taskType ? { task_type: taskType } : {}) }).toString();
      return request<{ items: any[]; total: number }>(`/audit/llm-runs?${qs}`);
    },
    overview: (projectId: number) =>
      request<components["schemas"]["OverviewResponse"]>(`/audit/overview?project_id=${projectId}`),
    precheck: (projectId: number) =>
      request<Record<string, unknown>>(`/audit/precheck?project_id=${projectId}`),
  },

  // Cad-Standard (v1.0 §26 5 规则)
  cadStandard: {
    list: () => request<{ files: string[]; total: number; directory: string }>("/cad-standard/rules"),
    get: (name: string) =>
      request<{ name: string; content: Record<string, unknown> }>(`/cad-standard/rules/${name}`),
    update: (name: string, content: Record<string, unknown>) =>
      request<{ updated: boolean; name: string }>(`/cad-standard/rules/${name}`, {
        method: "PUT", body: JSON.stringify({ content }),
      }),
  },
};

// Re-export 类型供业务使用
export type { paths, components } from "./types";
