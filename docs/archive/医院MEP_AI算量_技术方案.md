# 医院 MEP 机电 AI 算量 · 双技术路线开源实现与技术方案

> 适用对象：医院新建/改扩建项目的机电（暖通 HVAC、给排水、电气、消防、医用气体）工程量自动提取
> 视角：市场调研专家 + 技术选型（含开源实现、人工标定与人机协作闭环）
> 说明：本文中"两条技术路线"对应前序文章的核心分野——**矢量原生** vs **栅格视觉检测**；另补充一条对医院 MEP 极有价值的 **IFC/BIM 原生路线**作为对比基线。

---

## 一、执行摘要（结论先行）

| 维度 | 路线 A：矢量原生 | 路线 B：栅格视觉检测 | 路线 C：IFC/BIM 原生（基线） |
|---|---|---|---|
| 核心思路 | 直接解析 DWG/DXF 图元（线/弧/块/图层） | CAD→图片后用 YOLO/分割识别符号 | 解析 IFC 模型自带几何与属性 |
| 精度 | 高（坐标无损，误差<0.5%） | 中（依赖分辨率，受栅格化损耗） | 最高（模型即真值） |
| 工程速度 | 中（需图层/块规范） | 快（分钟级批量） | 快（若已有 IFC） |
| 对医院 MEP 适配 | 强（2D 施工图普遍） | 强（符号计数型算量） | 最强（但医院常只有 2D 图） |
| 开源成熟度 | 中（解析成熟，识别需自研） | 高（YOLOplan 直接可用） | 高（IfcOpenShell 生产级） |
| 人工介入点 | 图层映射规则、块属性校准 | 标注样本、误检校正 | 模型合规、属性补全 |

**推荐落地策略**：以 **路线 B（YOLOplan 开源）快速出原型** 验证医院 MEP 符号识别价值，同时 **路线 A 做精度兜底与属性回填**，并以 **人工标定闭环（CVAT/Label Studio + 主动学习）** 持续迭代。若医院能提供 IFC 模型，优先路线 C 直出工程量清单。

---

## 二、背景与目标

### 2.1 医院 MEP 算量痛点
- 机电系统多（HVAC、给排水、强/弱电、消防喷淋、医用气体、智能化），图纸张数大、图例符号繁杂。
- 传统人工算量：天级周期、易错、改版需重算、数据不可复用。
- 医院项目常有"边设计边施工"和大量签证变更，算量频次高。

### 2.2 目标
- 将 2D CAD 施工图转化为**可计算、可联动、可追溯**的结构化工程量清单（BOQ）。
- 支持**人工标定与协作**：人在环（Human-in-the-Loop）校正 + 多人协同标注 + 持续训练。
- 全部基于**可审计的开源组件**，规避商业授权与数据出境风险（契合腾讯合规要求）。

---

## 三、路线 A：矢量原生（Vector-native）

直接解析 CAD 底层矢量数据，保留几何坐标与图层语义，避免栅格化信息降维。

### 3.1 开源实现

| 层级 | 开源项目 | 语言/协议 | 关键能力 | 许可注意 |
|---|---|---|---|---|
| DWG 解析 | **LibreDWG** | C / GPLv3 | 读/写多版本 DWG | ⚠️ GPLv3 强 copyleft，商用需隔离进程调用 |
| DWG/DXF 解析 | **ACadSharp** | C# / MIT | 读写 DXF+DWG，多版本兼容 | ✅ 商用友好 |
| DXF 解析 | **ezdxf** | Python / MIT | 分层解析、实体操作、几何计算 | ✅ 最易上手，首选 |
| 几何内核 | **OpenCASCADE / pythonOCC** | C++/Python / LGPL | B-Rep、布尔、求交 | ⚠️ LGPL，动态链接可接受 |
| 转换桥 | **ODA File Converter** | 免费CLI（非开源） | DWG→DXF 命令行批量 | 商用需 ODA 授权 |
| 矢量 ML（研究） | **DeepCAD** | Python / MIT | CAD 序列向量化表示、生成模型 | 偏 3D 生成，2D 算量需改造 |
| 矢量 ML（研究） | **CAD as Language** | Python / MIT | 草图 token 序列、Transformer | DeepMind，序列化思路可借鉴 |
| 图结构 | **SketchGraphs** | Python / MIT | 1500 万 2D 草图图结构 | 可作预训练语料 |

### 3.2 实现骨架
```
DWG/DXF
  └─ ezdxf / ACadSharp 解析 → 图元集合（LINE/ARC/LWPOLYLINE/INSERT/BLOCK）
       └─ 图层规则引擎（Layer Map）：轴线/风管/水管/桥架/设备 → 语义类别
            └─ 块属性提取（INSERT → 设备型号/规格/数量）
                 └─ 几何计算：管线长度(∑段长)、面积、数量
                      └─ 输出结构化 JSON / BOQ（可回写原坐标系）
```
### 3.3 优劣
- ✅ 坐标无损、可回写、可审计；对"管径/长度/材质"等属性提取最准。
- ❌ 强依赖**图层命名规范**与**块（Block）标准化**；国内医院图纸图层混乱时需大量规则配置。
- ❌ 直接可用的"识别模型"少，实例级语义识别需自研（GNN/Transformer 偏研究阶段）。

---

## 四、路线 B：栅格视觉检测（Raster + CV）

将 CAD 转成高分辨率图片，用目标检测/分割识别图例符号并计数、量距。

### 4.1 开源实现（重点：**YOLOplan**）

| 组件 | 开源项目 | 协议 | 说明 |
|---|---|---|---|
| **MEP 检测核心** | **YOLOplan（DynMEP）** | AGPL-3.0 | YOLO11 针对电气/HVAC 符号检测计数，生产级，支持 PDF/JPG/PNG，导出 CSV/Excel/JSON + 网表 | ⚠️ AGPL-3.0：网络服务需开源衍生代码 |
| 检测基线 | **AECVision** | 自定 | YOLOv5 建筑平面图（墙/门窗），可借鉴管线 | 样本量小 |
| PDF→图 | **PyMuPDF (fitz)** | LGPL | 400 DPI 栅格化 | 商用友好 |
| 标注 | **CVAT** | Apache-2.0 (服务端) | 团队协作标注、AI 辅助预标、任务分发 | ✅ 协同首选 |
| 标注 | **Label Studio** | Apache-2.0 | 多模态标注、模型辅助 | ✅ |
| 标注 | **labelme** | MIT | 轻量本地多边形/矩形 | 单人可行 |
| 训练 | **Ultralytics YOLO11** | AGPL-3.0 | 检测/分割训练 | ⚠️ 同 YOLOplan |

### 4.2 YOLOplan 关键能力（已核实）
- YOLO11 集成，支持 PDF/图片批量、自定义训练、CSV/Excel/JSON 导出、电气原理图**网表（Netlist）生成**、Optuna 超参优化、合成数据增强。
- 性能：YOLO11s 推荐（mAP50≈47%，推理 2.3ms）；100 epoch 训练约 1–3 小时（GPU）。
- 托管版 mepdetect.com 已训好 MEP 符号集——但医院数据敏感，建议**私有化自训**。

### 4.3 实现骨架
```
CAD/PDF → PyMuPDF 栅格化(400DPI) → YOLOplan 检测符号/设备
   └─ 计数（设备数量）+ 线段检测（管线长度）
        └─ 规则引擎按清单口径汇总 → BOQ
             └─ 人工校正误检/漏检 → 回标样本 → 再训练
```
### 4.4 优劣
- ✅ 开箱即用、对"设备数量/图例计数"型算量极快；标注友好、生态成熟。
- ❌ 栅格化**丢失精确坐标**，长度量取依赖像素比例换算，精度弱于矢量路线。
- ❌ AGPL-3.0 传染性——若以 SaaS 对内提供服务，需评估开源义务（可改用自训 YOLOv8/v5 或闭源检测头规避）。

---

## 五、路线 C：IFC/BIM 原生（医院 MEP 推荐基线）

若医院设计院交付 IFC（或 Revit 可导出 IFC），则**模型自带几何与属性，算量精度最高、最省事**。

| 组件 | 开源项目 | 协议 | 能力 |
|---|---|---|---|
| IFC 处理 | **IfcOpenShell** | LGPL | 读取/几何计算/属性提取，Python API |
| 开源 BIM | **Bonsai（BlenderBIM Add-on）** | GPL | 原生 IFC 建模、工程量统计、成本规划、碰撞检查 |
| 协同服务器 | **BIMserver** | GPL/AGPL | IFC 存储、版本、多用户协作 |
| .NET 栈 | **xBIM Toolkit** | CDDL | IFC 读写、可视化（微软生态） |

示例（IfcOpenShell 提取墙体工程量）：
```python
import ifcopenshell
model = ifcopenshell.open("hospital.ifc")
walls = model.by_type("IfcWall")
for w in walls:
    print(w.Name, ifcopenshell.geom.calculate_area(w))
```
> 对 MEP：可用 `IfcPipeSegment` / `IfcDuctSegment` / `IfcFlowTerminal` 等类型直接提取长度、口径、数量；Bonsai 提供原生成本规划与自动算量模块。

**结论**：路线 C 是"如果有 BIM 模型"的最优解；本文两条主线（A/B）解决的是**医院大量仅有的 2D CAD 施工图**场景。

---

## 六、人工标定与人机协作（核心增强，两条路线共用）

无论选 A 还是 B，**人工标定闭环**是落地医院 MEP 的关键——医院图例符号高度定制，必须有人校正样本。

### 6.1 标注工具选型
| 工具 | 适用 | 协同能力 | 协议 |
|---|---|---|---|
| **CVAT** | 团队标注、AI 预标、任务队列 | 强（多标注员/审核员/角色） | Apache-2.0 |
| **Label Studio** | 多模态、模型辅助、Web | 强 | Apache-2.0 |
| **labelme** | 单人轻量、本地 | 弱 | MIT |

### 6.2 人在环（HITL）工作流
```
1. 预标注：YOLOplan/规则引擎 产出初稿（自动）
2. 人工校正：CVAT 中标注员修正漏检/误检、补属性（型号/口径）
3. 回写：校正结果存为带版本的结构化 JSON + 标注样本库
4. 主动学习：低置信度样本自动排队进入下一轮标注（难例挖掘）
5. 再训练：增量训练 YOLOplan / 更新图层规则 → 精度螺旋上升
6. 审计：每次算量可追溯到"哪张图、哪个符号、谁校正、用哪版模型"
```

### 6.3 多人协同架构建议
- **标注协同**：CVAT 服务端（内网部署）+ 角色（标注员/审核员/专业工程师）。
- **数据协同**：图纸与 BOQ 版本用 Git 或 BIMserver 管理，支持"改版自动重算 + 差异比对"。
- **知识沉淀**：图例符号库（医院专属）与图层映射规则作为组织资产持续积累。

---

## 七、推荐混合架构（Hybrid）

```
┌──────────── 输入 ────────────┐
│ 医院 CAD(DWG/DXF) / PDF / IFC │
└──────────────┬───────────────┘
               │
   ┌───────────┴────────────┐
   │  预处理路由（按源类型） │
   └───┬───────────────┬─────┘
       │               │
  [矢量分支 A]      [栅格分支 B]      [IFC分支 C]
  ezdxf解析         PyMuPDF栅格化      IfcOpenShell
  图层规则引擎        YOLOplan检测       Bonsai算量
       │               │               │
       └──────┬────────┴───────┬───────┘
              │ 统一结构化模型(JSON) │
              └───────┬───────────┘
        ┌─────────────┴─────────────┐
        │ 算量规则引擎（BOQ 口径）    │
        │ + 人工标定校正（CVAT HITL） │
        └─────────────┬─────────────┘
                 输出：BOQ / Excel / 审计日志
```

---

## 八、实施路线（分阶段，含里程碑）

| 阶段 | 目标 | 关键动作 | 周期(估) |
|---|---|---|---|
| P0 验证 | 跑通一条路线出 BOQ | 用 YOLOplan + 20 张医院样本，人工标 50 图例，出设备清单 | 2 周 |
| P1 精度 | 双路线对比 | A 路线用 ezdxf 做管线长度；B 路线测符号计数；交叉校验 | 4 周 |
| P2 协作 | 标定闭环上线 | 内网部署 CVAT，建立图例库+图层规则，HITL 跑通 | 4 周 |
| P3 生产 | 可审计算量服务 | BOQ 导出、版本差异、审计日志、主动学习再训练 | 6 周 |

---

## 九、风险与验收标准

### 9.1 主要风险
1. **许可风险**：YOLOplan / Ultralytics 为 AGPL-3.0；LibreDWG 为 GPLv3。对内 SaaS 需评估开源义务→建议检测头自训或走闭源推理包装，解析层用 MIT 的 ACadSharp/ezdxf 规避。
2. **图纸规范风险**：医院图层/块不统一→需"每张院/每专业"建映射规则，前期人力投入大。
3. **精度风险**：栅格化长度量取误差；矢量路线对未标准化块失效。

### 9.2 验收标准（建议阈值，待一手验证）
- 关键设备（风机/水泵/配电箱/末端）**召回率 ≥ 95%**，误报率 ≤ 3%。
- 管线长度相对人工抽量**误差 ≤ 2%**（矢量路线目标 <0.5%）。
- 单项目算量周期：天级 → **≤ 0.5 天**（含人工校正）。
- 每次算量产出**可追溯审计日志**（图源/模型版本/校正人）。

---

## 十、开源项目清单（附核实链接）

**路线 A（矢量原生）**
- ezdxf：https://github.com/mozman/ezdxf （MIT）
- ACadSharp：https://github.com/DomCR/ACadSharp （MIT）
- LibreDWG：https://github.com/LibreDWG/libredwg （GPLv3）
- OpenCASCADE：https://github.com/Open-Cascade-SAS/occt （LGPL）
- DeepCAD：https://github.com/rundiwu/DeepCAD （MIT）
- SketchGraphs / CAD as Language：Onshape 公开数据集（MIT）

**路线 B（栅格视觉）**
- YOLOplan：https://github.com/DynMEP/YOLOplan （AGPL-3.0）
- AECVision：https://github.com/PawelKinczyk/AECVision
- PyMuPDF：https://github.com/pymupdf/PyMuPDF （LGPL）
- CVAT：https://github.com/opencv/cvat （Apache-2.0）
- Label Studio：https://github.com/HumanSignal/label-studio （Apache-2.0）
- labelme：https://github.com/wkentaro/labelme （MIT）

**路线 C（IFC/BIM）**
- IfcOpenShell：https://github.com/IfcOpenShell/IfcOpenShell （LGPL）
- Bonsai/BlenderBIM：https://opensource.construction/projects/bonsai/ （GPL）
- BIMserver：https://github.com/opensourceBIM/BIMserver

---

## 十一、下一步建议（需一手验证的部分）
1. 向 1–2 家合作医院索取**真实 MEP 施工图样本**（脱敏），用 YOLOplan 跑 baseline 召回率。
2. 确认医院设计交付形态：仅有 2D CAD，还是含 IFC？决定主线 A/B 还是 C。
3. 法务确认 AGPL 组件在内网 SaaS 的使用边界，必要时替换为自训闭源检测头。
4. 建立"医院 MEP 图例符号标准库 v1"，作为所有路线共享的资产底座。

> 注：本文数据来自公开索引与项目主页交叉核对（2026-08），性能/精度数字为各项目自报或文献值，落地前需以贵司实测样本复核。
