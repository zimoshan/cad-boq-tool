import React, { useCallback, useEffect, useState } from "react";
import { api, components } from "../api/client";

type GenerateResult = components["schemas"]["GenerateCandidatesResponse"];

interface Candidate {
  id: number;
  project_id: number;
  engineering_object_id: number;
  boq_item_id: number;
  method: string;
  score: number;
  confidence: number;
  reason: string;
  status: string;
  created_at: string;
  eo_tag: string;
  eo_block: string;
  boq_description: string;
  boq_code: string;
  boq_unit: string;
}

const STATUS_COLORS: Record<string, string> = {
  PENDING: "#f0b429",        // amber
  ACCEPTED: "#35b04a",       // green
  REJECTED: "#e5534b",       // red
  SUPERSEDED: "#6b7280",     // gray
};

function CandidateRow({ c, onAction, busy }: {
  c: Candidate;
  onAction: (id: number, action: "confirm" | "reject") => void;
  busy: boolean;
}) {
  const statusColor = STATUS_COLORS[c.status] || "var(--text-muted)";
  return (
    <tr style={{ borderBottom: "1px solid var(--bg-border)" }}>
      <td style={td}>{c.id}</td>
      <td style={td}>
        <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: 12 }}>
          {c.boq_code} {c.boq_description}
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 11 }}>
          工程对象: {c.eo_block || c.eo_tag || `EO#${c.engineering_object_id}`}{c.boq_unit ? ` · ${c.boq_unit}` : ""}
        </div>
      </td>
      <td style={td}>
        <span style={{ color: "var(--text-secondary)", fontSize: 11 }}>{c.method}</span>
      </td>
      <td style={td}>
        <span style={{ color: "var(--text-secondary)", fontSize: 11 }}>{(c.confidence * 100).toFixed(0)}%</span>
      </td>
      <td style={td}><span style={{ color: "var(--text-muted)", fontSize: 11 }}>{c.reason || "-"}</span></td>
      <td style={td}>
        <span style={{ color: statusColor, fontSize: 11, fontWeight: 600 }}>{c.status}</span>
      </td>
      <td style={td}>
        {c.status === "PENDING" ? (
          <div style={{ display: "flex", gap: 6 }}>
            <button disabled={busy} onClick={() => onAction(c.id, "confirm")} style={{ ...btnSm, background: "var(--accent-success)" }}>
              ✔ 确认
            </button>
            <button disabled={busy} onClick={() => onAction(c.id, "reject")} style={{ ...btnSm, background: "var(--accent-danger)" }}>
              ✖ 拒绝
            </button>
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)", fontSize: 11 }}>-</span>
        )}
      </td>
    </tr>
  );
}

export function BindingWorkbench() {
  const [projectId, setProjectId] = useState(25);
  const [sheetId, setSheetId] = useState(73);
  const [useLlm, setUseLlm] = useState(false);
  const [topN, setTopN] = useState(5);
  const [busy, setBusy] = useState(false);
  const [genResult, setGenResult] = useState<GenerateResult | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    try {
      const r = await api.binding.candidates(projectId, statusFilter || undefined);
      setCandidates(r.items as Candidate[]);
    } catch {
      setCandidates([]);
    }
  }, [projectId, statusFilter]);

  useEffect(() => { loadCandidates(); }, [loadCandidates]);

  const handleGenerate = async () => {
    setBusy(true); setError(null); setMsg(null);
    try {
      const r = await api.binding.generate({ project_id: projectId, sheet_id: sheetId, use_llm: useLlm, top_n: topN });
      setGenResult(r);
      setMsg(`生成 ${r.candidates_created} 个候选`);
      await loadCandidates();
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "请求失败");
    } finally { setBusy(false); }
  };

  const handleAction = async (id: number, action: "confirm" | "reject") => {
    setActionBusy(id); setError(null);
    try {
      if (action === "confirm") {
        await api.binding.confirm({ candidate_id: id, by_user: "sysadmin" });
      } else {
        await api.binding.reject({ candidate_id: id, reason: "人工拒绝", by_user: "sysadmin" });
      }
      setMsg(`候选 #${id} ${action === "confirm" ? "已确认" : "已拒绝"}`);
      await loadCandidates();
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "操作失败");
    } finally { setActionBusy(null); }
  };

  return (
    <div style={{ padding: 16, color: "var(--text-secondary)" }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 12, fontSize: 14 }}>🔗 绑定工作台</div>

      {/* 生成候选 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <label>项目 ID: <input type="number" value={projectId} onChange={e => setProjectId(Number(e.target.value))} style={inp} /></label>
        <label>图纸 ID: <input type="number" value={sheetId} onChange={e => setSheetId(Number(e.target.value))} style={inp} /></label>
        <label>Top N: <input type="number" min={1} max={20} value={topN} onChange={e => setTopN(Number(e.target.value))} style={inp} /></label>
        <label><input type="checkbox" checked={useLlm} onChange={e => setUseLlm(e.target.checked)} /> LLM</label>
        <button onClick={handleGenerate} disabled={busy} style={btn}>{busy ? "生成中..." : "生成绑定候选"}</button>
      </div>

      {/* 状态过滤 + 刷新 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, fontSize: 12 }}>
        <span>筛选:</span>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ ...inp, width: 130, background: "var(--bg-primary)", border: "1px solid var(--bg-border)", color: "var(--text-primary)" }}>
          <option value="">全部</option>
          <option value="PENDING">PENDING</option>
          <option value="ACCEPTED">ACCEPTED</option>
          <option value="REJECTED">REJECTED</option>
          <option value="SUPERSEDED">SUPERSEDED</option>
        </select>
        <button onClick={loadCandidates} style={{ ...btnSm, background: "transparent", color: "var(--text-secondary)", border: "1px solid var(--bg-border)" }}>🔄 刷新</button>
        <span style={{ color: "var(--text-muted)" }}>{candidates.length} 条</span>
      </div>

      {error && <div style={{ color: "var(--accent-danger)", padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8 }}>❌ {error}</div>}
      {msg && <div style={{ color: "var(--accent-success)", padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8 }}>✅ {msg}</div>}
      {genResult && !msg && (
        <div style={{ padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8, fontSize: 12 }}>
          ✅ 生成 {genResult.candidates_created} 个候选 | stats: <span style={{ color: "var(--text-muted)" }}>{JSON.stringify(genResult.stats ?? {})}</span>
        </div>
      )}

      {/* 候选列表 */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead><tr style={{ background: "var(--bg-card)" }}>
            <th style={th}>ID</th><th style={th}>候选（EO ↔ BOQ）</th><th style={th}>方法</th>
            <th style={th}>置信</th><th style={th}>理由</th><th style={th}>状态</th><th style={th}>操作</th>
          </tr></thead>
          <tbody>
            {candidates.length === 0 && (
              <tr><td colSpan={7} style={{ ...td, textAlign: "center", color: "var(--text-muted)", padding: 24 }}>
                无候选（先生成或改项目/筛选）
              </td></tr>
            )}
            {candidates.map(c => (
              <CandidateRow key={c.id} c={c} busy={actionBusy === c.id} onAction={handleAction} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const inp: React.CSSProperties = { width: 70, padding: "4px 6px", background: "var(--bg-primary)", border: "1px solid var(--bg-border)", color: "var(--text-primary)", borderRadius: 3, marginRight: 8 };
const btn: React.CSSProperties = { padding: "6px 12px", background: "var(--accent-primary)", color: "white", border: "none", borderRadius: 4, cursor: "pointer" };
const btnSm: React.CSSProperties = { padding: "3px 8px", color: "white", border: "none", borderRadius: 3, cursor: "pointer", fontSize: 11 };
const th: React.CSSProperties = { padding: "6px 8px", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { padding: "4px 8px" };