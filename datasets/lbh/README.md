# LBH Regression Dataset（v1.0 §7 占位结构）

> 2026-09-06 Web 化 Phase 0 启动版。**真实 DWG/DXF 数据需用户从 D:\ifc_2026-08-24_0536 手动整理**。
> 目录结构遵循 v1.0 §7 / §8 / §9 / §10 / §11 规范。

## 目录约定

```
datasets/lbh/
├── README.md                     # 本文件
├── manifest.json                 # v1.0 §8 数据集元数据（schema_version + files[]）
├── source/
│   └── dwg/                      # 原始 DWG（v1.0 §6 "Original Source"）
│       └── LBH-E-101.dwg
├── converted/
│   └── dxf/                      # v1.0 §10 Derived Conversion Artifact
│       └── v2/                   # 不可变版本（v1.0 §9）
│           └── LBH-E-101/
│               └── LBH-E-101.dxf
├── parsed/                       # v1.0 §11 JSON 4 文件拆解
│   ├── json/                     # 中小规模响应
│   │   └── v2/
│   │       └── LBH-E-101/
│   │           ├── metadata.json
│   │           ├── layers.json
│   │           ├── blocks.json
│   │           └── entities.json
│   └── parquet/                  # 大量 Entity（v1.0 §6 大量 CAD Entity）
│       └── v2/
│           └── LBH-E-101/
│               └── entities.parquet
├── render/                       # v1.0 §14 浏览器 Canvas/WebGL 专用
│   └── LBH-E-101/
│       ├── overview.json
│       ├── lod0.bin
│       ├── lod1.bin
│       ├── lod2.bin
│       └── tiles/
├── boq/                          # v1.0 §7 业务数据
│   ├── LBH-001-electrical.xlsx
│   ├── LBH-001-electrical-rev1.xlsx
│   ├── LBH-002-mechanical.xlsx
│   ├── LBH-003-architecture.xlsx
│   └── LBH-004-structure.xlsx
├── labels/                       # v1.0 §16/§17 人工标定（正负样本）
│   ├── engineering_objects/
│   ├── bindings/                 # positive samples
│   ├── rejected_bindings/        # negative samples（v1.0 §17）
│   ├── takability/
│   ├── drawing_types/
│   └── specifications/
├── expected/                     # v1.0 §7 回归预期
│   └── quantities/
└── snapshots/                    # v1.0 §9 不可变版本快照
```

## manifest.json 模板（v1.0 §8）

```json
{
  "dataset_id": "LBH-2026-08",
  "project": "Euesperides Medical Hospital",
  "schema_version": "cad-1.0",
  "parser_version": "v2",
  "source_revision": "R4",
  "generated_at": "2026-09-06T...",
  "files": [
    {
      "drawing_id": "LBH-E-101",
      "filename": "E-101.dwg",
      "sha256": "...",
      "discipline": "Electrical",
      "drawing_type": "plan",
      "level": "L01",
      "zone": "WARD-A",
      "revision": "R4",
      "entity_count": 41511,
      "json_path": "parsed/json/v2/LBH-E-101/",
      "parquet_path": "parsed/parquet/v2/LBH-E-101/"
    }
  ]
}
```

## 不变性原则（v1.0 §9）

- Regression Dataset 不允许算法运行时覆盖
- Parser v2 / Parser v3 必须分目录（`parsed/v2/` `parsed/v3/`），不可覆盖原文件
- 人工标定新增版本可独立

## DXF 管理（v1.0 §10）

- 永久保留的测试 DXF：`datasets/<dataset>/converted/dxf/<version>/<drawing_id>/`
- 临时 DXF：`data/temp/`（解析完成自动清理）
- 禁止项目根目录散落 `test.dxf` / `new.dxf` / `output.dxf`

## 当前状态

- ⏳ DWG 原始数据：未导入（等 D 盘数据接入）
- ⏳ DXF 转换：未启动（需 ODA 二进制）
- ⏳ 解析结果：未生成
- ✅ 目录结构：已就绪（P0-30 占位）
- ✅ manifest.json schema：已定义（v1.0 §8）
