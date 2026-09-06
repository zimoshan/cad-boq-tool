// 入口（Vite + React 18 + TS）
// 2026-09-06 Web 化 Phase 0
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
