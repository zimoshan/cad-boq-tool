import React, { useState } from "react";
import { api } from "../api/client";

interface Candidate { id: number; boq_item_id: number; score: number; confidence: number; reason: string; status: string; }
interface GenerateResult { project_id: number; use_llm: boolean; candidates_created: number; stats: Record<string, number>; }

export function BindingWorkbench() {
  const [projectId, setProjectId] = useState(1);
  const [sheetId, setSheetId] = useState(1);
  const [useLlm, setUseLlm] = useState(true);
  const [topN, setTopN] = useState(5);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);

  const handleGenerate = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await api.binding.generate({ project_id: projectId, sheet_id: sheetId, use_llm: useLlm, top_n: topN });
      setResult(r);
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "请求失败");
    } finally { setBusy(false); }
  };

  return (
    <div style={{ padding: 16, color: "var(--text-secondary)" }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 12, fontSize: 14 }}>🔗 绑定工作台</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <label>项目 ID: <input type="number" value={projectId} onChange={e => setProjectId(Number(e.target.value))} style={inp} /></label>
        <label>图纸 ID: <input type="number" value={sheetId} onChange={e => setSheetId(Number(e.target.value))} style={inp} /></label>
        <label>Top N: <input type="number" min={1} max={20} value={topN} onChange={e => setTopN(Number(e.target.value))} style={inp} /></label>
        <label><input type="checkbox" checked={useLlm} onChange={e => setUseLlm(e.target.checked)} /> LLM</label>
        <button onClick={handleGenerate} disabled={busy} style={btn}>{busy ? "生成中..." : "生成绑定候选"}</button>
      </div>
      {error && <div style={{ color: "var(--accent-danger)", padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8 }}>❌ {error}</div>}
      {result && (
        <div style={{ padding: 12, background: "var(--bg-card)", borderRadius: 4, marginBottom: 12 }}>
          <div style={{ color: "var(--accent-success)" }}>✅ 生成 {result.candidates_created} 个候选</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>stats: {JSON.stringify(result.stats)}</div>
        </div>
      )}
      {candidates.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>最近候选（前 10）:</div>
          {candidates.slice(0, 10).map(c => (
            <div key={c.id} style={{ padding: 8, borderBottom: "1px solid var(--bg-border)" }}>
              <div>Candidate #{c.id} | BOQ #{c.boq_item_id} | score={c.score.toFixed(2)} conf={c.confidence.toFixed(2)}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{c.reason}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const inp: React.CSSProperties = { width: 70, padding: "4px 6px", background: "var(--bg-primary)", border: "1px solid var(--bg-border)", color: "var(--text-primary)", borderRadius: 3, marginRight: 8 };
const btn: React.CSSProperties = { padding: "6px 12px", background: "var(--accent-primary)", color: "white", border: "none", borderRadius: 4, cursor: "pointer" };
