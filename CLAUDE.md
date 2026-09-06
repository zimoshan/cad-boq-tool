## 待办管理

所有待办事项（功能/优化/缺陷/验证项）统一登记在 [docs/BACKLOG.md](docs/BACKLOG.md)，状态标准与登记规范见该文件 §0。其他文档不设待办清单；新需求先入 BACKLOG（带编号/优先级/验收标准）再实施，完成后回填状态与日期并保持与实际代码一致。

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
