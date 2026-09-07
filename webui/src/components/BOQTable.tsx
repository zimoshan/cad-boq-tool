import React, { useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/types";

type ParseResponse = components["schemas"]["ParseBoqResponse"];
type WritebackExcelResponse = components["schemas"]["WritebackToExcelResponse"];

export function BOQTable() {
  const [projectId, setProjectId] = useState(25);
  const [filePath, setFilePath] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [wb, setWb] = useState<WritebackExcelResponse | null>(null);
  const [writebackBusy, setWritebackBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const handleParse = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await api.boq.parse({ project_id: projectId, file_path: filePath });
      setResult(r);
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "请求失败");
    } finally { setBusy(false); }
  };

  const handleWriteback = async () => {
    if (!filePath) { setError("请先填 Excel 源文件路径"); return; }
    setWritebackBusy(true); setError(null); setWb(null);
    try {
      const r = await api.boq.writebackToExcel({ project_id: projectId, source_file_path: filePath, project_scale: 1.0 });
      setWb(r);
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      setError(err.detail?.message || err.message || "回写失败");
    } finally { setWritebackBusy(false); }
  };

  const handleExport = async () => {
    if (!result) return;
    try {
      const out = window.prompt("输出 xlsx 路径", "D:/LBH-out.xlsx");
      if (!out) return;
      await api.boq.export({ project_id: projectId, output_path: out, overwrite_original: false });
      alert("导出完成：" + out);
    } catch (e: unknown) {
      const err = e as { detail?: { message?: string }; message?: string };
      alert("导出失败：" + (err.detail?.message || err.message || ""));
    }
  };

  return (
    <div style={{ padding: 16, color: "var(--text-secondary)" }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 12, fontSize: 14 }}>📋 BOQ 清单</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <label>项目 ID: <input type="number" value={projectId} onChange={e => setProjectId(Number(e.target.value))} style={inp} /></label>
        <label>Excel 路径: <input type="text" value={filePath} onChange={e => setFilePath(e.target.value)} style={{ ...inp, width: 220 }} /></label>
        <button onClick={handleParse} disabled={busy} style={btn}>{busy ? "解析中..." : "解析 BOQ"}</button>
        <button onClick={handleWriteback} disabled={writebackBusy} style={writeBtn}>{writebackBusy ? "回写中..." : "↩ 回写 Excel"}</button>
        {result && <button onClick={handleExport} style={btnSec}>导出 xlsx</button>}
      </div>
      <input type="text" placeholder="过滤项目/分部..." value={filter} onChange={e => setFilter(e.target.value)} style={{ ...inp, width: "100%", marginBottom: 12 }} />
      {error && <div style={{ color: "var(--accent-danger)", padding: 8, background: "var(--bg-card)", borderRadius: 4, marginBottom: 8 }}>❌ {error}</div>}
      {wb && (
        <div style={{ padding: 12, background: "var(--bg-card)", borderRadius: 4, marginBottom: 12 }}>
          <div style={{ color: wb.verified ? "var(--accent-success)" : "var(--accent-danger)", fontWeight: 600, marginBottom: 8 }}>
            {wb.verified ? "✅ 回写完成 + 完整性校验通过" : "⚠️ 回写完成但校验未通过"}：{wb.written}/{wb.total_items} 项写入 {wb.failed > 0 ? `（${wb.failed} 失败）` : ""}
          </div>
          <div style={{ fontSize: 12, lineHeight: 1.8 }}>
            <div>输出文件: <span style={{ color: "var(--text-primary)" }}>{wb.output_path}</span></div>
            <div>新增列: <span style={{ color: "var(--text-primary)" }}>第 {wb.target_col} 列</span> · SHA-256: <span style={{ color: "var(--text-muted)" }}>{wb.file_sha256.slice(0, 16)}…</span></div>
            <div>
              完整性: 公式 <span style={{ color: "var(--text-primary)" }}>{wb.integrity?.formula_count ?? "?"}</span> · 合并格 <span style={{ color: "var(--text-primary)" }}>{wb.integrity?.merged_ranges ?? "?"}</span>
              {" "}· 冻结 <span style={{ color: "var(--text-primary)" }}>{wb.integrity?.freeze_panes ?? "-"}</span> · 原列 diff <span style={{ color: "var(--text-primary)" }}>{wb.integrity?.diffs ?? "?"}</span>
            </div>
          </div>
        </div>
      )}
      {result && (
        <div>
          <div style={{ color: "var(--accent-success)", marginBottom: 8 }}>✅ 解析完成：{result.item_count} 项</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead><tr style={{ background: "var(--bg-card)" }}>
                <th style={th}>项目编号</th><th style={th}>描述</th><th style={th}>单位</th>
                <th style={th}>原数量</th><th style={th}>分部</th>
              </tr></thead>
              <tbody>
                {Array.from({ length: result.item_count }).map((_, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--bg-border)" }}>
                    <td style={td}>r{i + 1}</td><td style={td}>Item {i + 1}</td>
                    <td style={td}>No.</td><td style={td}>{(i + 1) * 10}</td>
                    <td style={td}>{filter || "(从 server 拉详细列表)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>说明：表格预览仅显示前 {result.item_count} 条占位，详细数据从 webapi /api/boq/export 导出</div>
        </div>
      )}
    </div>
  );
}

const inp: React.CSSProperties = { width: 70, padding: "4px 6px", background: "var(--bg-primary)", border: "1px solid var(--bg-border)", color: "var(--text-primary)", borderRadius: 3, marginRight: 8 };
const btn: React.CSSProperties = { padding: "6px 12px", background: "var(--accent-primary)", color: "white", border: "none", borderRadius: 4, cursor: "pointer" };
const btnSec: React.CSSProperties = { padding: "6px 12px", background: "transparent", color: "var(--text-secondary)", border: "1px solid var(--bg-border)", borderRadius: 4, cursor: "pointer" };
const writeBtn: React.CSSProperties = { padding: "6px 12px", background: "var(--accent-success)", color: "white", border: "none", borderRadius: 4, cursor: "pointer" };
const th: React.CSSProperties = { padding: "6px 8px", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { padding: "4px 8px" };
