# cad-boq-tool WebUI

> Vite + React 18 + TypeScript 前端（2026-09-06 Web 化 Phase 0 骨架）

## 启动

```bash
# 1. 安装依赖（首次）
cd webui
npm install

# 2. 启动 dev server
npm run dev
# → http://localhost:5173

# 3. 同时启动 webapi 后端（另开终端）
cd ..
docker compose up -d
# → webapi: http://localhost:8521
# dev 期 Vite 已配 proxy：/api/* → :8521
```

## 目录结构

```
webui/
├── public/cdn/          # P0-19 CDN 资源本地化（待下载）
├── src/
│   ├── main.tsx         # React 入口
│   ├── App.tsx          # v3 蓝本 1:1 占位（Phase 0 骨架）
│   ├── theme.ts         # 色板/尺寸常量（slate palette）
│   ├── theme.css        # CSS 变量（待 Tailwind 集成）
│   └── api/
│       └── client.ts    # webapi fetch wrapper + ApiError
├── index.html
├── package.json
├── vite.config.ts       # dev proxy /api → :8521
├── tsconfig.json
└── tsconfig.node.json
```

## 组件清单（Phase 0 占位 → Phase 1+ 完整实现）

| 组件 | Phase 0 | Phase 1+ |
|---|---|---|
| Topbar | 占位（3 按钮 + 健康指示）| 项目下拉 + AI 算量 + LLM 状态 |
| Rail | 5 按钮占位（绑定/清单/计量/属性/记录）| 实际切换 RAIL_TAB_INDEX |
| Canvas | "渲染器占位" 文案 | Phase 3 Canvas 2D 实现（1.2 万小图先验）|
| StatusBar | 5 字段占位 | 实数据：项目/图纸/模式/单位/统计 |
| Toast | 简单浮层 | 队列 + 类型（info/warn/error）|
| 右侧面板 | "面板内容占位" | 按 BACKLOG §1.A.6~A.10 实现 |

## 与 webapi 对接

通过 `src/api/client.ts` 统一封装（`api.cad/binding/boq/health`），所有端点路径与 [docs/BACKLOG §1.A.1 P0-18](docs/BACKLOG.md) 同步。

## P0-19 CDN 本地化（#11）

当前 `index.html` 注释中预留了 Tailwind/Iconify 引用位置。Phase 1 期间执行：
```bash
mkdir -p public/cdn
curl -L https://cdn.jsdelivr.net/npm/tailwindcss@3.4.10/dist/tailwind.min.css -o public/cdn/tailwind.min.css
curl -L https://cdn.jsdelivr.net/npm/@iconify/iconify@3.1.1/dist/iconify.min.js -o public/cdn/iconify.min.js
# 设计稿 modao.cc 的图标集合可下载到 public/cdn/icons.json
```
然后改 `index.html` 引用本地 `/cdn/...` 路径。
