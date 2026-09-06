// App 主组件（v3 蓝本 1:1 占位）
// 2026-09-06 Web 化 Phase 0
// 完整设计稿见 design/main.html；本组件为占位骨架，Phase 3 完整实现

import { useState, useEffect } from "react";
import { api } from "./api/client";
import { theme } from "./theme";

const RAIL_TABS = [
  { key: "binding", label: "绑定", icon: "🔗" },
  { key: "boq", label: "清单", icon: "📋" },
  { key: "measure", label: "计量", icon: "📐" },
  { key: "properties", label: "属性", icon: "🏷️" },
  { key: "history", label: "记录", icon: "🕘" },
] as const;

type RailKey = (typeof RAIL_TABS)[number]["key"];

export default function App() {
  const [activeRail, setActiveRail] = useState<RailKey>("binding");
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth);
  }, []);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2600);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: theme.bg.primary }}>
      {/* 顶栏 */}
      <header
        style={{
          height: theme.size.topbarHeight,
          background: theme.bg.panel,
          borderBottom: `1px solid ${theme.bg.border}`,
          display: "flex",
          alignItems: "center",
          padding: "0 16px",
          gap: 12,
        }}
      >
        <div style={{ fontWeight: 600, color: theme.accent.primary }}>CAD·BOQ</div>
        <div style={{ flex: 1, color: theme.text.muted }}>v{String(health?.version ?? "...")}</div>
        <button onClick={() => showToast("AI 算量：待 Phase 5 实现")} style={btnStyle}>AI 算量 ▾</button>
        <button onClick={() => showToast("导出：待 Phase 4 实现")} style={btnStyle}>导出</button>
        <button onClick={() => showToast("更多菜单：待 Phase 2 补全")} style={btnStyle}>更多 ▾</button>
        <span style={{ color: health?.status === "ok" ? theme.accent.success : theme.accent.danger }}>
          {health?.status === "ok" ? "● webapi ok" : "○ webapi down"}
        </span>
      </header>

      {/* 主体三栏 */}
      <main style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* 左侧（图纸列表 + 图层树） */}
        <aside style={{ width: 280, background: theme.bg.panel, borderRight: `1px solid ${theme.bg.border}`, padding: 12, overflow: "auto" }}>
          <div style={{ marginBottom: 12 }}>
            <input
              type="search"
              placeholder="搜索图纸/图层..."
              style={{ width: "100%", padding: "6px 10px", background: theme.bg.primary, border: `1px solid ${theme.bg.border}`, color: theme.text.primary, borderRadius: theme.radius.sm }}
            />
          </div>
          <div style={{ color: theme.text.muted, fontSize: 12 }}>图纸列表（待 Phase 3 实现）</div>
        </aside>

        {/* 中间画布 */}
        <section style={{ flex: 1, background: theme.bg.primary, display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
          <div style={{ color: theme.text.muted, fontSize: 14, textAlign: "center" }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>🎨</div>
            <div>Canvas 2D 渲染器（待 Phase 3 实现）</div>
            <div style={{ fontSize: 11, marginTop: 4, opacity: 0.6 }}>1.2 万小图先验 → 7.9 万全图</div>
          </div>
        </section>

        {/* 右侧 rail + 面板 */}
        <aside style={{ display: "flex", background: theme.bg.panel, borderLeft: `1px solid ${theme.bg.border}` }}>
          <nav style={{ width: theme.size.railWidth, background: theme.bg.panel, display: "flex", flexDirection: "column", alignItems: "center", padding: "8px 0" }}>
            {RAIL_TABS.map((tab) => (
              <button
                key={tab.key}
                title={tab.label}
                onClick={() => setActiveRail(tab.key)}
                style={{
                  width: 40,
                  height: 40,
                  margin: "4px 0",
                  background: activeRail === tab.key ? theme.bg.card : "transparent",
                  border: "none",
                  borderRadius: theme.radius.sm,
                  color: activeRail === tab.key ? theme.accent.primary : theme.text.muted,
                  fontSize: 18,
                }}
              >
                {tab.icon}
              </button>
            ))}
          </nav>
          <div style={{ width: 380, padding: 12, overflow: "auto", color: theme.text.secondary }}>
            <div style={{ color: theme.text.primary, fontWeight: 600, marginBottom: 8 }}>
              {RAIL_TABS.find((t) => t.key === activeRail)?.label}
            </div>
            <div style={{ color: theme.text.muted, fontSize: 12 }}>
              面板内容（待 Phase 2-4 按 BACKLOG 顺序实现）
            </div>
          </div>
        </aside>
      </main>

      {/* 状态栏 */}
      <footer
        style={{
          height: theme.size.statusbarHeight,
          background: theme.bg.panel,
          borderTop: `1px solid ${theme.bg.border}`,
          display: "flex",
          alignItems: "center",
          padding: "0 12px",
          gap: 12,
          fontSize: 11,
          color: theme.text.muted,
        }}
      >
        <span>项目: --</span>
        <span>图纸: --</span>
        <span>模式: {activeRail}</span>
        <span style={{ marginLeft: "auto" }}>{toast || "就绪"}</span>
      </footer>

      {/* Toast 浮层 */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: 60,
            right: 16,
            background: theme.bg.card,
            color: theme.text.primary,
            padding: "10px 16px",
            borderRadius: theme.radius.md,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            zIndex: 1000,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: "transparent",
  border: `1px solid ${theme.bg.border}`,
  color: theme.text.secondary,
  padding: "4px 10px",
  borderRadius: theme.radius.sm,
  fontSize: 12,
};
