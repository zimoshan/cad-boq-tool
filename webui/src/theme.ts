// 主题色板 + 间距（从 app/ui/theme.py 翻译）
// 2026-09-06 Web 化 Phase 0

export const theme = {
  // slate 色板
  bg: {
    primary: "#0f172a",     // slate-900
    panel: "#1e293b",       // slate-800
    card: "#334155",        // slate-700
    border: "#475569",      // slate-600
  },
  text: {
    primary: "#f1f5f9",     // slate-100
    secondary: "#cbd5e1",   // slate-300
    muted: "#94a3b8",       // slate-400
  },
  accent: {
    primary: "#3b82f6",     // blue-500
    success: "#10b981",     // emerald-500
    warning: "#f59e0b",     // amber-500
    danger: "#ef4444",      // red-500
  },
  // 窗口尺寸
  size: {
    topbarHeight: 52,
    railWidth: 52,
    statusbarHeight: 28,
    canvasBorder: 1,
  },
  // 圆角 + 间距
  radius: {
    sm: 2,
    md: 4,
    lg: 8,
  },
} as const;

export type Theme = typeof theme;
