# 桌面端程序 Web 化改造任务

你现在作为本项目的**资深全栈架构师 + 前端工程师 + 后端工程师 + 桌面应用迁移专家**，负责将当前已有的桌面端程序逐步改造为 Web 应用。
先执行 git status、git log -10，确认当前工作区状态和最近修改，禁止覆盖或回滚我现有未提交的修改。所有改造均通过独立 commit 管理。

## 一、核心目标

当前项目已经具备：

1. 一个可以运行的桌面端程序；
2. 一个已经完成的 Web Demo；
3. 原桌面端已经存在较成熟的业务逻辑、数据结构和工作流程。

本次任务**不是简单重写 UI，也不是推倒重来**。

你的核心目标是：

> 在最大程度复用现有业务逻辑、算法、数据结构和已有能力的基础上，将桌面端程序完整迁移/演进为真正可用的 Web 应用。

最终 Web 版本应该能够覆盖桌面端的核心业务能力，同时解决桌面端在跨设备访问、部署、协作、扩展和维护方面的问题。

---

# 二、第一阶段：严禁直接修改代码，先进行项目逆向分析

在开始任何代码修改之前，必须完整检查项目。

首先识别：

- 项目整体目录结构
- 前端技术栈
- 后端技术栈
- 桌面端框架
- Web Demo 使用的技术栈
- 数据存储方式
- 配置文件
- API
- 核心业务模块
- 核心算法
- 文件处理逻辑
- CAD/DWG/DXF 等文件处理逻辑（如果存在）
- 本地文件读写
- 数据库读写
- Python/Node/Java/C++ 等外部程序调用
- 本地进程调用
- 系统 API 调用
- 桌面端专属能力
- Web Demo 当前已经实现的能力

重点查找：

```text
Electron
Tauri
Qt
PyQt
PySide
.NET
C#
Python
Node.js
React
Vue
TypeScript
FastAPI
Flask
Express
NestJS
SQLite
PostgreSQL
MySQL
Redis
WebSocket
REST API
GraphQL
```

以及所有项目实际使用的技术。

---

# 三、建立“桌面端 → Web”的功能映射表

分析完成后，建立一份完整的：

```text
DESKTOP_TO_WEB_MAPPING.md
```

至少包含：

| 桌面端功能 | 当前实现位置 | Web Demo | Web目标实现 | 是否可直接复用 | 改造难度 |
|---|---|---|---|---|---|
| 功能A | xxx | 已实现 | xxx | 是 | 低 |
| 功能B | xxx | 未实现 | xxx | 部分 | 中 |
| 功能C | xxx | 未实现 | xxx | 否 | 高 |

必须把桌面端所有主要功能进行梳理，而不是只分析界面。

特别区分：

### 1. UI 层

例如：

- 菜单
- 工具栏
- 左侧导航
- 属性面板
- 表格
- 弹窗
- 文件选择
- 设置
- 图形显示
- 拖拽
- 快捷键

### 2. 业务层

例如：

- 数据处理
- 算量
- 设备识别
- BOQ 映射
- 工程量计算
- 数据转换
- 项目管理
- 用户操作流程

### 3. 算法层

例如：

- CAD 解析
- 图形识别
- 几何计算
- 规则匹配
- AI 自动匹配
- 数量计算
- 数据清洗

### 4. 基础设施层

例如：

- 数据库
- 文件系统
- 缓存
- 配置
- 日志
- 后台任务
- 外部程序

---

# 四、第二阶段：重点分析桌面端与 Web Demo 的差异

不要只看代码文件，要从“架构能力”的角度判断。

回答以下问题：

## 1. 哪些代码可以直接复用？

例如：

```text
纯业务逻辑
算法
数据模型
数据库模型
Python计算模块
CAD解析模块
AI模块
```

## 2. 哪些代码必须重构？

例如：

```text
直接操作本地文件
Windows API
桌面窗口
Electron IPC
Qt Signal/Slot
本地进程
本地路径
系统剪贴板
系统托盘
```

## 3. 哪些能力必须转换成 API？

例如：

```text
文件上传
项目创建
项目读取
数据计算
任务执行
结果查询
导出
AI处理
CAD解析
```

## 4. 哪些任务需要异步执行？

特别检查：

- 大型 CAD 文件
- DWG/DXF 解析
- 大规模工程量计算
- AI 推理
- 大文件导入
- 数据转换
- 报表生成

如果这些任务直接在 HTTP 请求中同步执行，会造成 Web 请求阻塞。

必须评估：

```text
Background Job
Task Queue
Worker
WebSocket
SSE
Polling
```

哪一种更适合当前项目。

---

# 五、第三阶段：分析 Web Demo

Web Demo 不要简单视为“参考页面”。

需要判断它：

1. 哪些页面已经可以直接作为正式版基础；
2. 哪些只是视觉 Demo；
3. 哪些组件可以复用；
4. 哪些页面需要重新设计；
5. 当前 Demo 的数据是否真实；
6. 当前 Demo 是否已经有 API；
7. API 与桌面端业务逻辑是否一致。

建立：

```text
WEB_DEMO_ANALYSIS.md
```

包括：

```text
页面结构
组件结构
路由
状态管理
API
数据模型
交互流程
存在的问题
可以复用的部分
需要重构的部分
```

---

# 六、第四阶段：提出 Web 化总体架构

在修改代码之前，先给出推荐架构。

优先考虑：

```text
Browser
   │
   ▼
Web Frontend
   │
   ▼
API Gateway / Backend
   │
   ├── Business Service
   │
   ├── Calculation Engine
   │
   ├── CAD Processing
   │
   ├── AI Service
   │
   ├── File Service
   │
   └── Task/Worker
          │
          ▼
       Database
          │
          ▼
      File Storage
```

但不要机械套用这个架构。

必须根据当前项目实际代码判断。

如果当前项目规模不大，不要为了“微服务”而微服务。

优先：

> 模块化单体 + 清晰 API + 可异步扩展

而不是一开始拆成大量微服务。

---

# 七、第五阶段：制定迁移策略

不要一次性重写整个项目。

采用：

> Strangler Fig / 渐进式迁移

原则：

```text
现有桌面端
     │
     ├── 保留稳定模块
     │
     ├── 抽离公共业务逻辑
     │
     └── Web逐步接管
```

建议按照以下顺序：

### Phase 1
完成架构分析和功能映射。

### Phase 2
抽离核心业务逻辑。

### Phase 3
建立 Backend API。

### Phase 4
接入 Web Demo。

### Phase 5
迁移核心业务页面。

### Phase 6
迁移复杂计算任务。

### Phase 7
迁移文件/CAD处理。

### Phase 8
迁移 AI 能力。

### Phase 9
完善权限、日志、任务管理。

### Phase 10
完整测试并逐步替代桌面端。

---

# 八、特别关注文件系统问题

桌面端和 Web 最大的架构区别之一是：

```text
Desktop:
用户电脑
   ↓
直接访问文件系统
```

Web：

```text
Browser
   ↓
Upload
   ↓
Server
   ↓
File Storage
   ↓
Processing
```

因此必须检查项目中所有：

```text
open()
read()
write()
path
file path
directory
temp file
export
import
```

判断哪些地方依赖 Windows 本地路径。

不能简单把：

```text
C:\xxx\xxx
```

改成 Linux 路径。

应该重新设计：

```text
File ID
Project ID
Storage Path
Object Storage
Temporary File
Processing Workspace
```

---

# 九、如果项目涉及 CAD / DWG / DXF

重点分析：

```text
CAD文件上传
       ↓
文件解析
       ↓
几何数据
       ↓
JSON / Database
       ↓
图形展示
       ↓
工程量计算
       ↓
BOQ
```

明确：

1. CAD 解析是在前端还是后端；
2. 当前桌面端使用什么解析库；
3. Web 环境能否直接运行；
4. 是否需要 Python Worker；
5. 是否需要转换为 JSON；
6. 是否应该保留原始 CAD 文件；
7. 是否应该生成中间格式；
8. 如何保存大型 CAD 项目；
9. 如何实现 Web Canvas / SVG / WebGL 展示；
10. 如何保证计算结果与桌面端一致。

如果涉及工程量计算，不允许为了 Web 化而改变原算法结果。

必须建立：

```text
Desktop Calculation Result
        VS
Web Calculation Result
```

的自动化对比测试。

---

# 十、AI 功能迁移

如果项目存在 AI 能力，需要明确：

```text
Web Frontend
      ↓
Backend
      ↓
AI Service
      ↓
LLM
```

不要让浏览器直接管理 API Key。

如果目前使用：

```text
Ollama
Claude
OpenAI
Qwen
其他模型
```

需要将模型调用封装成统一接口，例如：

```text
LLMService
```

避免前端绑定具体模型。

---

# 十一、Web UI 改造要求

Web 版本不能只是把桌面 UI “搬到浏览器”。

需要重新考虑：

### 桌面端

```text
菜单
工具栏
窗口
弹窗
文件夹
本地路径
```

### Web

应该转换为：

```text
Sidebar
Topbar
Workspace
Panel
Modal
Drawer
Upload
Project
Task
```

重点优化：

- 响应式布局
- 大屏显示
- 1366×768
- 1920×1080
- 2560×1440
- 浏览器缩放
- Sidebar 可收缩
- Panel 可调整
- 大数据表格
- Loading
- Empty State
- Error State
- Progress
- Task Status

不要为了追求“漂亮”而破坏专业软件的信息密度。

---

# 十二、不要擅自改变业务逻辑

这是本次改造的重要原则。

除非发现明确 Bug，否则：

```text
不要改变算法
不要改变计算公式
不要改变数据库含义
不要改变业务规则
不要删除已有功能
不要为了简化代码而删除复杂逻辑
```

如果发现桌面端存在明显问题：

记录到：

```text
WEB_MIGRATION_ISSUES.md
```

不要直接偷偷修改。

---

# 十三、代码修改规则

每次修改前：

1. 先定位相关代码；
2. 阅读上下游调用关系；
3. 理解数据流；
4. 判断是否影响桌面端；
5. 判断是否影响 Web Demo；
6. 再进行修改。

禁止：

```text
看到一个文件就直接重写
为了消除报错删除功能
为了让 Demo 能运行而伪造数据
用 Mock 数据掩盖后端没有实现
大规模复制代码
重复实现已有业务逻辑
```

---

# 十四、API 设计要求

如果当前没有正式 API，需要建立规范 API。

例如：

```text
/api/projects
/api/projects/{id}
/api/files
/api/files/{id}
/api/tasks
/api/tasks/{id}
/api/cad
/api/calculation
/api/boq
/api/ai
```

但不要机械使用这些路径。

必须根据现有业务模型设计。

API 应考虑：

```text
认证
权限
参数校验
错误处理
分页
文件上传
任务状态
幂等性
日志
版本控制
```

---

# 十五、任务系统

对于耗时操作，不允许：

```text
POST /calculate
```

然后让 HTTP 请求一直等待。

应该设计：

```text
POST /tasks
       ↓
返回 task_id
       ↓
Worker 执行
       ↓
progress
       ↓
completed / failed
       ↓
Frontend 获取结果
```

前端需要能够显示：

```text
等待中
处理中
进度
成功
失败
取消
```

如果当前项目已经有任务机制，优先复用。

---

# 十六、数据库和数据迁移

检查当前数据库：

```text
SQLite
MySQL
PostgreSQL
JSON
CSV
本地文件
```

判断：

1. Web 是否可以直接使用；
2. 是否需要迁移；
3. 是否存在并发问题；
4. 是否需要增加 Project/User/Task 等实体；
5. 是否需要数据库 Migration。

禁止直接删除旧数据库。

必须设计：

```text
Backup
Migration
Rollback
```

---

# 十七、开发过程必须保留文档

至少建立：

```text
WEB_MIGRATION_PLAN.md
DESKTOP_TO_WEB_MAPPING.md
WEB_DEMO_ANALYSIS.md
WEB_ARCHITECTURE.md
WEB_MIGRATION_ISSUES.md
API_DESIGN.md
```

如果项目已经存在类似文档，先判断是否应该更新，而不是重复创建。

---

# 十八、测试要求

至少建立：

## 1. 功能测试

确认：

```text
桌面端功能
=
Web功能
```

## 2. API测试

检查：

```text
正常请求
错误请求
非法参数
权限
文件上传
大文件
```

## 3. 算法一致性测试

对于核心计算：

```text
Desktop Result
=
Web Result
```

建立自动化测试。

## 4. 前端测试

检查：

```text
1366×768
1920×1080
2560×1440
```

以及浏览器：

```text
Chrome
Edge
```

---

# 十九、执行模式

整个任务按照：

```text
分析
↓
方案
↓
确认架构
↓
小范围实施
↓
测试
↓
继续迁移
```

进行。

不要一次性修改大量代码。

每完成一个阶段：

1. 汇报完成内容；
2. 列出修改文件；
3. 列出新增文件；
4. 列出测试结果；
5. 列出遗留问题；
6. 给出下一阶段计划。

---

# 二十、现在立即执行

当前第一步：

**不要修改任何代码。**

请首先：

### Step 1
扫描整个项目目录。

### Step 2
识别所有技术栈。

### Step 3
分析桌面端架构。

### Step 4
分析 Web Demo。

### Step 5
建立桌面端功能 → Web 功能映射。

### Step 6
找出桌面端依赖本地环境的所有部分。

### Step 7
找出核心业务逻辑和核心算法。

### Step 8
分析数据流。

### Step 9
提出至少两种 Web 化架构方案。

### Step 10
比较不同方案：

```text
开发成本
改造难度
代码复用率
性能
扩展性
部署难度
维护成本
数据安全
```

### Step 11
给出你推荐的方案，并解释原因。

### Step 12
制定分阶段迁移路线。

---

# 最终输出格式

第一次分析结束后，只输出：

## 1. 项目现状

## 2. 技术栈

## 3. 桌面端架构

## 4. Web Demo 架构

## 5. 桌面端功能清单

## 6. Web Demo 功能清单

## 7. Desktop → Web 映射

## 8. 核心业务逻辑

## 9. 核心算法

## 10. 本地依赖

## 11. 数据流

## 12. 当前主要技术债务

## 13. Web 化架构方案 A

## 14. Web 化架构方案 B

## 15. 两种方案对比

## 16. 推荐方案

## 17. 分阶段迁移计划

## 18. 风险清单

## 19. 需要我确认的关键决策

完成以上分析之后**暂停，不要开始大规模编码**。

等我确认架构方案后，再进入实施阶段。

---

# 最重要的原则

你不是在“重新开发一个 Web Demo”。

你是在：

> **将一个已经存在业务逻辑和算法能力的桌面工程软件，渐进式演进成正式的 Web 工程软件。**

因此：

**先理解，再设计；先抽象，再迁移；先复用，再重构；先验证，再替换。**