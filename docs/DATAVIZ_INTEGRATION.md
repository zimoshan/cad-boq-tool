# dataviz skill 集成说明（P0-24，#17 决策）

> 2026-09-06 Phase 0 框架就绪，Phase 5/6 完整实现。

## 概述

`dataviz` 是 Claude Code 内置 skill，用于生成专业级数据可视化（图表/统计 tile/仪表盘）。
在 cad-boq-tool 中的应用场景：

- 跨专业总览页（电气/机械/建筑/结构 4 专业核对率对比柱状图）
- 项目级 BOQ 计量分布（按章节 pie chart）
- 绑定候选置信度分布（histogram）
- Takability 6 状态计数（donut）
- 性能监控（解析耗时/DB 查询耗时 时序图）

## 集成点（Phase 5+ 实施）

### 1. 跨专业总览页（Phase 6 计划）

```tsx
// webui/src/pages/Overview.tsx
import { useDataviz } from "@/hooks/useDataviz";

export default function OverviewPage() {
  const stats = useOverviewStats();  // 调用 /api/audit/overview
  return useDataviz({
    type: "groupedBar",
    data: stats.byDiscipline,  // { ELV: { measured: 348, verified: 231, rate: 0.664 }, ... }
    x: "discipline",
    y: ["measured", "verified"],
    color: ["#3b82f6", "#10b981"],
  });
}
```

### 2. 报告导出（Phase 4 计划）

调用 `app/report.py` 生成 Excel + dataviz 图表合并 PDF。

### 3. 实时统计（Phase 5 计划）

绑定工作台 + 计量面板嵌入 sparkline tile。

## 调色板

参考 [webui/src/theme.ts](../webui/src/theme.ts) `theme.accent`：
- `primary` `#3b82f6` 蓝
- `success` `#10b981` 绿
- `warning` `#f59e0b` 橙
- `danger` `#ef4444` 红

dataviz skill 默认使用中性调色板，可通过 `palette` 选项传入覆盖。

## Phase 0 状态

- ✅ dataviz 集成点规划明确（跨专业总览/报告/实时统计 3 处）
- ⬜ Phase 5/6 实际启用：与 dataviz skill 文档同步调色板与图表类型
- ⬜ Phase 5 报告页：BOQ 计量分布 / 绑定置信度分布
- ⬜ Phase 6 跨专业总览：电气/机械/建筑/结构 4 专业核对率对比

## 引用

- dataviz skill 文档：`~/.claude/skills/dataviz/SKILL.md`
- 主题常量：[webui/src/theme.ts](../webui/src/theme.ts)
- 跨专业核量数据源：[docs/CAD_BOQ_Web化_架构设计_v2.0.md §1.3](CAD_BOQ_Web化_架构设计_v2.0.md) LBH 4 份清单核对结果
