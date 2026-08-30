# 图纸算量工具（cad-boq-tool）

轻量桌面应用：**读取 CAD 图纸 → 导入 BOQ 清单 → 人工将图形与清单对应 → 自动算量导出 Excel**。

个人自用 / 可开源（MIT 独立实现，不复用 OpenConstructionERP 代码）。

## 环境要求

- Windows / Python 3.11+（本项目 venv 已就绪）
- 依赖：PySide6、ezdxf、openpyxl、shapely、numpy（已在 `.venv` 中）

## 启动

```bash
cd D:\workbuddy work\AICAD\cad-boq-tool
.venv\Scripts\python.exe main.py
```

## 操作流程

1. **文件 → 新建项目**（输入项目名）
2. **文件 → 打开图纸**（DWG/DXF；大图出现进度条，请耐心等待）
3. **文件 → 导入 BOQ 清单**（Excel，自动识别中文表头：编号/项目名称/单位/数量）
4. 右侧选中清单条目，然后：
   - 图纸上**双击**图形 → 点选映射
   - **Shift + 左键拖拽** → 框选映射
   - 左栏图层树**右键** → 整层/整块批量关联（块名映射自动设为"数量"规则）
5. 设置条目的**计量规则**（长度/面积/数量）与**比例因子**（图纸 mm→实际 m 填 0.001，面积自动平方）
6. **导出算量清单** → Excel（编号/描述/单位/图纸计量数量/原清单数量/差值/映射方式/比例因子；差值红=超出、绿=不足）

## 快捷键

| 操作 | 方式 |
|---|---|
| 缩放 | 滚轮（以光标为中心） |
| 平移 | 中键拖拽 |
| 框选 | Shift + 左键拖拽 |
| 点选 | 双击 |

## DWG 支持

需安装免费 **ODA File Converter**（自动探测 `C:\Program Files\ODA\ODAFileConverter`）。
未安装时提示指引；DXF 无需任何额外依赖。

## 数据存储

- 数据库：`~/.cad-boq-tool/projects.db`（SQLite WAL）
- 项目/图纸/实体/BOQ/映射五表，`entity.handle` 跨会话稳定，重启后映射与计量结果保留
- 块几何缓存于图纸记录（`blocks_json`），切换图纸免重新解析

## 测试

本仓库不含独立测试脚本（`test_core.py` / `test_e2e.py` / `gui_smoke.py` 为历史仓库遗留名称，未迁移到本目录）。
可用的自检入口：

```bash
.venv\Scripts\python.exe -c "import app; print('app OK')"   # 模块导入自检
.venv\Scripts\python.exe main.py                             # 启动应用（冒烟）
```

历史验证报告见 `../hospital-boq-analysis/16_implementation_report.md`（外部仓库，仅作参考）。
