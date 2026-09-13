// 跨专业总览页（P6-4，dataviz 集成点①）
// 无依赖 SVG 图表：各专业核对率柱状图 + Takability donut + BOQ 覆盖 + 版本冲突/重复计价告警
// 数据源：/api/audit/overview + /api/audit/precheck + /api/binding/version-conflicts + /api/binding/duplicate-pricing
import { useEffect, useState } from "react";
import { api } from "../api/client";

const PROJECT_ID = 1; // TODO: 项目选择器接线后替换

interface DisciplineRow {
  discipline: string;
  eo_total: number;
  confirmed: number;
  rate: number;
}

const DISC_COLORS: Record<string, string> = {
  ELV: "#3b82f6",      // 电气 primary
  MECH: "#10b981",     // 机械 success
  ARCH: "#f59e0b",     // 建筑 warning
  STRU: "#ef4444",     // 结构 danger
};

const TAK_COLORS: Record<string, string> = {
  UNKNOWN: "#64748b",
  PENDING: "#3b82f6",
  PARTIAL: "#f59e0b",
  COMPLETE: "#10b981",
  PROVISIONAL: "#a855f7",
  CONFLICT: "#ef4444",
};

function card(title: string, children: React.ReactNode) {
  return (
    <div style={{ background: "var(--bg-panel)", borderRadius: 8, padding: 14, minWidth: 0 }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 10, fontSize: 13 }}>{title}</div>
      {children}
    </div>
  );
}

/** 各专业核对率横向柱状图（rate 0~1，双条：总数 vs 已确认） */
function DisciplineBars({ rows }: { rows: DisciplineRow[] }) {
  if (!rows.length) {
    return <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: 16 }}>暂无工程对象数据</div>;
  }
  const max = Math.max(...rows.map((r) => r.eo_total), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {rows.map((r) => (
        <div key={r.discipline}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-secondary)", marginBottom: 3 }}>
            <span style={{ fontWeight: 600, color: W_COL(r.discipline) }}>{r.discipline}</span>
            <span>{r.confirmed}/{r.eo_total} · {(r.rate * 100).toFixed(0)}%</span>
          </div>
          <div style={{ background: "var(--bg-card)", borderRadius: 2, height: 8, position: "relative" }}>
            <div style={{ width: `${(r.eo_total / max) * 100}%`, background: "var(--bg-border)", height: 8, borderRadius: 2 }} />
            <div style={{ width: `${(r.confirmed / max) * 100}%`, background: W_COL(r.discipline), height: 8, borderRadius: 2, position: "absolute", top: 0, left: 0 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function W_COL(d: string) {
  return DISC_COLORS[d] ?? "#94a3b8";
}

/** Takability donut（SVG circle stroke-dasharray） */
function TakabilityDonut({ rows }: { rows?: { takability: string; n: number }[] }) {
  const total = (rows || []).reduce((s, r) => s + r.n, 0);
  if (!total) {
    return <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: 16 }}>暂无回写审计数据</div>;
  }
  const R = 34;
  const CIRC = 2 * Math.PI * R;
  let acc = 0;
  const segs = (rows || []).map((r) => {
    const frac = r.n / total;
    const seg = { ...r, g: Math.max(frac * CIRC - 1, 0.5), offset: -acc * CIRC };
    acc += frac;
    return seg;
  });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <svg width={96} height={96} viewBox="0 0 96 96">
        <circle cx={48} cy={48} r={R} fill="none" stroke="var(--bg-card)" strokeWidth={12} />
        {segs.map((s) => (
          <circle key={s.takability} cx={48} cy={48} r={R} fill="none"
            stroke={TAK_COLORS[s.takability] || "#64748b"} strokeWidth={12}
            strokeDasharray={`${s.g} ${CIRC - s.g}`} strokeDashoffset={-s.offset} transform="rotate(-90 48 48)" />
        ))}
        <text x={48} y={52} textAnchor="middle" fill="var(--text-primary)" fontSize={14} fontWeight={600}>{total}</text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, color: "var(--text-secondary)" }}>
        {(rows || []).map((r) => (
          <div key={r.takability} style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: TAK_COLORS[r.takability] || "#64748b" }} />
            <span>{r.takability}</span><span style={{ color: "var(--text-muted)" }}>{r.n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 告警卡（版本冲突 / 重复计价） */
function AlertCard({ title, n, items, color, hint }: { title: string; n: number; items: any[]; color: string; hint: string }) {
  if (typeof n === "undefined") {
    return null;
  }
  return (
    <div style={{ background: "var(--bg-panel)", borderRadius: 8, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 13 }}>{title}</span>
        <span style={{ color: n > 0 ? color : "var(--text-muted)", fontWeight: 700, fontSize: 16 }}>
          {n > 0 ? `⚠ ${n}` : "✓ 0"}
        </span>
      </div>
      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{hint}</div>
      {n > 0 && items.length > 0 && (
        <div style={{ marginTop: 8, maxHeight: 120, overflow: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
          {items.slice(0, 6).map((it, i) => (
            <div key={i} style={{ fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-card)", borderRadius: 4, padding: "4px 8px", fontFamily: "monospace" }}>
              {it.filename || it.anchor || it.block_name || JSON.stringify(it).slice(0, 60)}
            </div>
          ))}
          {items.length > 6 && <div style={{ fontSize: 10, color: "var(--text-muted)" }}>+{items.length - 6} 更多…</div>}
        </div>
      )}
    </div>
  );
}

export function OverviewPanel() {
  const [overview, setOverview] = useState<{ boq_count: number; mapping_count: number; by_discipline: DisciplineRow[]; writeback_by_takability?: { takability: string; n: number }[] } | null>(null);
  const [precheck, setPrecheck] = useState<Record<string, unknown> | null>(null);
  const [vc, setVc] = useState<Record<string, unknown> | null>(null);
  const [dp, setDp] = useState<{ total: number; items: any[] } | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [ov, pc, v1, v2] = await Promise.all([
          api.audit.overview(PROJECT_ID),
          api.audit.precheck(PROJECT_ID),
          api.binding.versionConflicts(PROJECT_ID),
          api.binding.duplicatePricing(PROJECT_ID),
        ]);
        if (!alive) return;
        setOverview(ov as any);
        setPrecheck(pc);
        setVc(v1);
        setDp(v2);
      } catch (e: any) {
        if (alive) setError(e?.message || String(e));
      }
    })();
    return () => { alive = false; };
  }, []);

  const cov = (precheck?.coverage || {}) as Record<string, unknown>;
  const staleSheets = (vc?.stale_sheets as any[]) || [];
  const staleMappings = (vc?.stale_mappings as any[]) || [];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, color: "var(--text-secondary)" }}>
      <div style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: 14 }}>📊 跨专业总览</div>
      {error && <div style={{ color: "var(--accent-danger)", fontSize: 12 }}>加载失败: {error}</div>}

      {/* 统计 tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        {[
          { k: "BOQ 条目", v: overview?.boq_count ?? "—" },
          { k: "已绑定 mapping", v: overview?.mapping_count ?? "—" },
          { k: "BOQ 覆盖率", v: `${cov.boq_coverage_pct ?? "—"}%` },
        ].map((t) => (
          <div key={t.k} style={{ background: "var(--bg-panel)", borderRadius: 8, padding: "12px 14px" }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{t.k}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)" }}>{t.v}</div>
          </div>
        ))}
      </div>

      {/* 各专业核对率 */}
      {card("各专业核对率", <DisciplineBars rows={overview?.by_discipline || []} />)}

      {/* Takability donut + 告警 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {card("计量回写状态 (Takability)", <TakabilityDonut rows={overview?.writeback_by_takability} />)}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <AlertCard title="版本冲突" n={staleMappings.length} items={staleMappings} color="var(--accent-warning)"
            hint={vc?.has_revision_info === false ? "当前库无 revision 信息（SQLite 降级）" : `stale 图纸 ${staleSheets?.length || 0} 张，其中已绑定 ${staleMappings.length} 条`} />
          <AlertCard title="重复计价候选" n={dp?.total || 0} items={dp?.items || []} color="var(--accent-danger)"
            hint="同锚点绑定 ≥2 个不同 BOQ 子项，可能合法（标 needs_review 不阻断）" />
        </div>
      </div>

      {/* LLM 运行摘要 */}
      {(() => {
        const runs = (overview as any)?.llm_runs_by_task || [];
        if (!runs.length) return null;
        return card("LLM 运行统计", (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            {runs.map((r: any) => (
              <div key={r.task_type} style={{ display: "flex", justifyContent: "space-between" }}>
                <span>{r.task_type}</span>
                <span style={{ color: "var(--text-muted)" }}>{r.n} 次 · 均 {Math.round(r.avg_ms || 0)}ms</span>
              </div>
            ))}
          </div>
        ));
      })()}
    </div>
  );
}