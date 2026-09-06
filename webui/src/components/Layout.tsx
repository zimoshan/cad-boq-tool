import React from "react";
const RAIL_TABS = [
  { key: "binding", label: "绑定", icon: "🔗" },
  { key: "boq", label: "清单", icon: "📋" },
  { key: "measure", label: "计量", icon: "📐" },
  { key: "properties", label: "属性", icon: "🏷️" },
  { key: "history", label: "记录", icon: "🕘" },
] as const;
export type RailKey = (typeof RAIL_TABS)[number]["key"];
export function Layout(props: { activeRail: RailKey; onRailChange: (k: RailKey) => void; statusBar: React.ReactNode; children: React.ReactNode; theme: { size: { topbarHeight: number; railWidth: number } } }) {
  const { activeRail, onRailChange, statusBar, children, theme } = props;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header style={{ height: theme.size.topbarHeight, background: "var(--bg-panel)", borderBottom: "1px solid var(--bg-border)", display: "flex", alignItems: "center", padding: "0 16px", gap: 12 }}>
        <div style={{ fontWeight: 600, color: "var(--accent-primary)" }}>CAD·BOQ</div>
        <div style={{ flex: 1, color: "var(--text-muted)" }}>v0.2.0-webify</div>
      </header>
      <main style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <aside style={{ width: 240, background: "var(--bg-panel)", borderRight: "1px solid var(--bg-border)", padding: 12, overflow: "auto" }}>
          <div style={{ color: "var(--text-muted)", fontSize: 12 }}>图纸列表</div>
        </aside>
        <section style={{ flex: 1, background: "var(--bg-primary)", position: "relative", overflow: "auto" }}>{children}</section>
        <aside style={{ display: "flex", background: "var(--bg-panel)", borderLeft: "1px solid var(--bg-border)" }}>
          <nav style={{ width: theme.size.railWidth, display: "flex", flexDirection: "column", alignItems: "center", padding: "8px 0" }}>
            {RAIL_TABS.map((tab) => (
              <button key={tab.key} title={tab.label} onClick={() => onRailChange(tab.key)} style={{ width: 40, height: 40, margin: "4px 0", background: activeRail === tab.key ? "var(--bg-card)" : "transparent", border: "none", borderRadius: 4, color: activeRail === tab.key ? "var(--accent-primary)" : "var(--text-muted)", fontSize: 18 }}>{tab.icon}</button>
            ))}
          </nav>
          <div style={{ width: 380, padding: 12, overflow: "auto", color: "var(--text-secondary)" }}>{statusBar}</div>
        </aside>
      </main>
      <footer style={{ height: 28, background: "var(--bg-panel)", borderTop: "1px solid var(--bg-border)", display: "flex", alignItems: "center", padding: "0 12px", gap: 12, fontSize: 11, color: "var(--text-muted)" }}>
        <span>项目: --</span><span>图纸: --</span><span>模式: {activeRail}</span><span style={{ marginLeft: "auto" }}>就绪</span>
      </footer>
    </div>
  );
}
