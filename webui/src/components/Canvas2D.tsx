import React, { useRef, useEffect, useState, useCallback } from "react";

// ---- Entity 类型 ----
interface Entity {
  handle: string;
  dxf_type: string;
  layer: string;
  block_name: string;
  bbox: number[]; // [min_x, min_y, max_x, max_y]
  geom: Record<string, unknown>;
  length?: number;
  area?: number;
  color: number[];
}

interface EntityData {
  entities: Entity[];
  count: number;
}

// ---- 视口状态 ----
interface Viewport {
  ox: number; // 原点 x（屏幕左上角对应的 CAD 坐标）
  oy: number; // 原点 y
  scale: number; // 像素/单位
}

// ---- 图层颜色映射（dxf_type → 默认颜色）----
const DXF_COLORS: Record<string, string> = {
  LINE: "#8899aa",
  LWPOLYLINE: "#66aa88",
  POLYLINE: "#66aa88",
  CIRCLE: "#dd7766",
  ARC: "#dd7766",
  INSERT: "#aa88dd",
  TEXT: "#ccaa44",
  MTEXT: "#ccaa44",
  HATCH: "#556677",
  SPLINE: "#66aadd",
  DIMENSION: "#999999",
};

// ---- Canvas 组件 ----
export function Canvas2D() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [layers, setLayers] = useState<string[]>([]);
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set());
  const [viewport, setViewport] = useState<Viewport>({ ox: 0, oy: 0, scale: 0.01 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState("");
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  // ---- 加载数据 ----
  useEffect(() => {
    fetch("/parsed/json/v2/LBH-E-073/entities.json")
      .then((r) => r.json())
      .then((data: EntityData) => {
        setEntities(data.entities);
        const layerSet = new Set(data.entities.map((e) => e.layer));
        const sorted = [...layerSet].sort();
        setLayers(sorted);
        setVisibleLayers(new Set(sorted));

        // 计算全局 bbox → 自动居中
        const allXs = data.entities.flatMap((e) => [e.bbox[0], e.bbox[2]]);
        const allYs = data.entities.flatMap((e) => [e.bbox[1], e.bbox[3]]);
        const minX = Math.min(...allXs);
        const minY = Math.min(...allYs);
        setViewport({ ox: minX, oy: minY, scale: 1 });
        setInfo(`${data.count} entities | ${sorted.length} layers`);
        setLoading(false);
      })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }, []);

  // ---- 绘制 ----
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const W = canvas.width;
    const H = canvas.height;

    ctx.fillStyle = "#1a1b26"; // 深色背景
    ctx.fillRect(0, 0, W, H);

    const { ox, oy, scale } = viewport;

    // CAD → 屏幕变换：x' = (x - ox) * scale, y' = H - (y - oy) * scale (y轴翻转)
    const toScreenX = (x: number) => (x - ox) * scale;
    const toScreenY = (y: number) => H - (y - oy) * scale;

    // 过滤可见图层
    const visible = entities.filter((e) => visibleLayers.has(e.layer));

    // 绘制
    for (const e of visible) {
      if (!e.bbox || e.bbox.length < 4) continue;
      const color = e.color?.length === 3
        ? `rgb(${e.color[0]},${e.color[1]},${e.color[2]})`
        : DXF_COLORS[e.dxf_type] || "#556677";
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.8;

      const [minX, minY, maxX, maxY] = e.bbox;
      const sx = toScreenX(minX);
      const sy = toScreenY(maxY); // max_y → 屏幕顶部
      const sw = (maxX - minX) * scale;
      const sh = (maxY - minY) * scale;

      // 跳过屏幕外的实体（视口裁剪）
      if (sx + sw < 0 || sx > W || sy + sh < 0 || sy > H) continue;

      // 根据 dxf_type 绘制
      switch (e.dxf_type) {
        case "LINE": {
          const pts = (e.geom as { points?: number[][] }).points;
          if (pts && pts.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(toScreenX(pts[0][0]), toScreenY(pts[0][1]));
            ctx.lineTo(toScreenX(pts[1][0]), toScreenY(pts[1][1]));
            ctx.stroke();
            break;
          }
          // fallback: bbox rect
          ctx.strokeRect(sx, sy, sw, sh);
          break;
        }
        case "LWPOLYLINE":
        case "POLYLINE": {
          const pts = (e.geom as { points?: number[][] }).points;
          if (pts && pts.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(toScreenX(pts[0][0]), toScreenY(pts[0][1]));
            for (let i = 1; i < pts.length; i++) {
              ctx.lineTo(toScreenX(pts[i][0]), toScreenY(pts[i][1]));
            }
            // 闭合判断
            if ((e.geom as { closed?: boolean }).closed) ctx.closePath();
            ctx.stroke();
            break;
          }
          ctx.strokeRect(sx, sy, sw, sh);
          break;
        }
        case "CIRCLE": {
          const g = e.geom as { center?: number[]; radius?: number };
          if (g.center && g.radius) {
            const cx = toScreenX(g.center[0]);
            const cy = toScreenY(g.center[1]);
            const r = g.radius * scale;
            ctx.beginPath();
            ctx.arc(cx, cy, Math.max(r, 1), 0, Math.PI * 2);
            ctx.stroke();
            break;
          }
          ctx.strokeRect(sx, sy, sw, sh);
          break;
        }
        case "ARC": {
          const g = e.geom as { center?: number[]; radius?: number; start_angle?: number; end_angle?: number };
          if (g.center && g.radius) {
            const cx = toScreenX(g.center[0]);
            const cy = toScreenY(g.center[1]);
            const r = g.radius * scale;
            const start = ((g.start_angle || 0) * Math.PI) / 180;
            const end = ((g.end_angle || 360) * Math.PI) / 180;
            ctx.beginPath();
            ctx.arc(cx, cy, Math.max(r, 1), start, end);
            ctx.stroke();
            break;
          }
          ctx.strokeRect(sx, sy, sw, sh);
          break;
        }
        case "TEXT":
        case "MTEXT": {
          // 小矩形 + 文字提示（太小的不渲染文字）
          if (scale > 0.05) {
            const text = (e.geom as { text?: string }).text || "";
            ctx.font = "10px monospace";
            ctx.fillStyle = color;
            ctx.fillText(text.slice(0, 20), sx, sy + 10);
          } else {
            ctx.strokeRect(sx, sy, Math.max(sw, 2), Math.max(sh, 2));
          }
          break;
        }
        case "INSERT":
        case "HATCH":
        case "SPLINE":
        case "DIMENSION":
        default:
          // bbox 矩形
          ctx.strokeRect(sx, sy, Math.max(sw, 1), Math.max(sh, 1));
          break;
      }
    }
    ctx.globalAlpha = 1;
  }, [entities, visibleLayers, viewport]);

  // ---- 视口适配（首次加载时自动缩放到 canvas 尺寸）----
  useEffect(() => {
    if (!canvasRef.current || entities.length === 0) return;
    const canvas = canvasRef.current;
    const W = canvas.width;
    const H = canvas.height;
    const allXs = entities.flatMap((e) => [e.bbox[0], e.bbox[2]]);
    const allYs = entities.flatMap((e) => [e.bbox[1], e.bbox[3]]);
    const minX = Math.min(...allXs);
    const maxX = Math.max(...allXs);
    const minY = Math.min(...allYs);
    const maxY = Math.max(...allYs);
    const cadW = maxX - minX || 1;
    const cadH = maxY - minY || 1;
    const margin = 0.9;
    const scaleX = (W * margin) / cadW;
    const scaleY = (H * margin) / cadH;
    const scale = Math.min(scaleX, scaleY);
    setViewport({
      ox: minX - (W / scale - cadW) / 2,
      oy: minY - (H / scale - cadH) / 2,
      scale,
    });
  }, [entities]);

  useEffect(() => { draw(); }, [draw, viewport]);

  // ---- 鼠标交互（拖拽平移 + 滚轮缩放）----
  const handleMouseDown = (e: React.MouseEvent) => { dragRef.current = { x: e.clientX, y: e.clientY }; };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.x;
    const dy = e.clientY - dragRef.current.y;
    dragRef.current = { x: e.clientX, y: e.clientY };
    setViewport((v) => ({ ...v, ox: v.ox - dx / v.scale, oy: v.oy + dy / v.scale }));
  };
  const handleMouseUp = () => { dragRef.current = null; };
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const H = canvas.height;
    // 鼠标位置对应的 CAD 坐标（缩放前）
    const cadX = viewport.ox + mx / viewport.scale;
    const cadY = viewport.oy + (H - my) / viewport.scale;
    const newScale = viewport.scale * factor;
    // 缩放后重新计算原点，让鼠标位置不变
    setViewport({
      ox: cadX - mx / newScale,
      oy: cadY - (H - my) / newScale,
      scale: newScale,
    });
  };

  // ---- 图层切换 ----
  const toggleLayer = (layer: string) => {
    setVisibleLayers((s) => {
      const next = new Set(s);
      next.has(layer) ? next.delete(layer) : next.add(layer);
      return next;
    });
  };

  // ---- 适配 canvas 尺寸 ----
  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const parent = canvas.parentElement!;
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
      draw();
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [draw]);

  if (loading) return <div style={{ padding: 20, color: "var(--text-secondary)" }}>加载中...</div>;
  if (error) return <div style={{ padding: 20, color: "var(--accent-danger)" }}>❌ {error}</div>;

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--bg-primary)" }}>
      {/* 图层面板 */}
      <div style={{ width: 180, borderRight: "1px solid var(--bg-border)", overflow: "auto", padding: 8, fontSize: 11 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--text-primary)" }}>📐 图层 ({layers.length})</div>
        {layers.map((l) => (
          <label key={l} style={{ display: "flex", gap: 4, marginBottom: 2, cursor: "pointer", color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={visibleLayers.has(l)} onChange={() => toggleLayer(l)} style={{ accentColor: "var(--accent-primary)" }} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l}</span>
          </label>
        ))}
      </div>
      {/* Canvas 主体 */}
      <div style={{ flex: 1, position: "relative" }}>
        <canvas
          ref={canvasRef}
          style={{ display: "block", cursor: dragRef.current ? "grabbing" : "grab" }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        />
        <div style={{ position: "absolute", bottom: 8, left: 8, fontSize: 10, color: "var(--text-muted)", background: "rgba(0,0,0,0.5)", padding: "2px 6px", borderRadius: 3 }}>
          {info} | scale={viewport.scale.toFixed(4)}
        </div>
      </div>
    </div>
  );
}
