import React, { useState } from "react";
import { api } from "../api/client";

interface TakeoffResult {
  project_id: number;
  sheet_id?: number | null;
  folder_path?: string;
  result: Record<string, unknown>;
}

export function MeasurementPanel() {
  const [projectId, setProjectId] = useState(25);
  const [mode, setMode] = useState<"sheet" | "folder">("sheet");
  const [sheetId, setSheetId] = useState(73);
  const [folderPath, setFolderPath] = useState("D:/dwg");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TakeoffResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      const body = mode === "sheet"
        ? { project_id: projectId, sheet_id: sheetId, folder_path: "" }
        : { project_id: projectId, sheet_id: null, folder_path: folderPath };
      const r = await api.takeoff.run(body);
      setResult(r as TakeoffResult);
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "请求失败");
    } finally { setBusy(false); }
  };

  return (
    <div style={{ padding: 16, color: "var(--text-secondary)" }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 12, fontSize: 14 }}>📐 AI 算量（Takeoff）</div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <label>项目 ID: <input type="number" value={projectId} onChange={e => setProjectId(Number(e.target.value))} style={inp} /></label>

        <label style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <input type="radio" checked={mode === "sheet"} onChange={() => setMode("sheet")} /> 单图
        </label>
        <label style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <input type="radio" checked={mode === "folder"} onChange={() => setMode("folder")} /> 文件夹
        </label>

        {mode === "sheet" ? (
          <label>图纸 ID: <input type="number" value={sheetId} onChange={e => setSheetId(Number(e.target.value))} style={inp} /></label>
        ) : (
          <label>文件夹: <input type="text" value={folderPath} onChange={e => setFolderPath(e.target.value)} style={{ ...inp, width: 220 }} /></label>
        )}

        <button onClick={handleRun} disabled={busy} style={btn}>{busy ? "算量中..." : "运行算量"}</button>
      </div>

      {error && <div style={{ color: "var(--accent-danger)", padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8 }}>❌ {error}</div>}

      {result && (
        <div style={{ padding: 12, background: "var(--bg-card)", borderRadius: 4 }}>
          <div style={{ color: "var(--accent-success)", marginBottom: 8 }}>
            ✅ 算量完成{mode === "sheet" ? `（sheet ${result.sheet_id ?? "?"}）` : `（${result.folder_path ?? "?"}）`}
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <tbody>
              {Object.entries(result.result ?? {}).map(([k, v]) => (
                <tr key={k} style={{ borderBottom: "1px solid var(--bg-border)" }}>
                  <td style={{ ...td, color: "var(--text-muted)", width: 180 }}>{k}</td>
                  <td style={{ ...td, color: "var(--text-primary)" }}>
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const inp: React.CSSProperties = { width: 70, padding: "4px 6px", background: "var(--bg-primary)", border: "1px solid var(--bg-border)", color: "var(--text-primary)", borderRadius: 3, marginRight: 8 };
const btn: React.CSSProperties = { padding: "6px 12px", background: "var(--accent-primary)", color: "white", border: "none", borderRadius: 4, cursor: "pointer" };
const td: React.CSSProperties = { padding: "4px 8px" };