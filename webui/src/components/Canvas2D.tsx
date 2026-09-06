export function Canvas2D() {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-primary)", color: "var(--text-muted)" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>🎨</div>
        <div>Canvas 2D 渲染器（Phase 3 待实现）</div>
        <div style={{ fontSize: 10, marginTop: 12, opacity: 0.6 }}>后端 /api/cad/* 已就绪</div>
      </div>
    </div>
  );
}
