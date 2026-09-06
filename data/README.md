# data/ 顶层目录（v1.0 §33）

```
data/
├── projects/    # 项目数据（PG/JSON）
├── datasets/    # 回归测试资产（只读）
├── cache/       # 解析缓存（可删）
├── temp/        # 临时文件（自动清理）
├── logs/        # 应用日志
└── exports/     # 用户交付物
```

env 路径对应：
- `DRAWING_CACHE_DIR` → `data/cache/`
- `EMBEDDING_CACHE_DIR` → `data/cache/embeddings/`
- `BLOCK_GEOMETRY_DIR` → `data/cache/block_geometry/`
- `LOG_DIR` → `data/logs/`
- `TEST_DATA_REGISTRY_PATH` → `data/projects/test_data_registry.json`
- 临时 DXF/转换 → `data/temp/`
- 回归数据集 → `datasets/lbh/`（独立顶层，不在 data/ 下，因 v1.0 §33 把 dataset 单独标）
