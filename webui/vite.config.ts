import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite 配置（2026-09-06）
// dev server: http://localhost:5173（默认），可与 webapi FastAPI :8521 跨域联调
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 开发期代理：把 /api/* 转到 FastAPI webapi（:8521），避免 CORS
      "/api": {
        target: "http://localhost:8521",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
