# 绑定工作流 - 候选生成详细流程

## 当前实现（分层覆盖模式，2026-08-26 已落地）

> `app/binding/matcher.py::generate_candidates` 已从「二选一」重构为分层覆盖：
> LLM 只是第 4 层增强（`use_llm` 只控制该层是否启用），不再与规则互斥；
> 单测见 `tests/test_binding_matcher_layered.py`。

## 期望实现（分层覆盖模式）

```
┌─────────────────────────────────────────────────────────────────┐
│                    generate_candidates()                         │
│                    (分层覆盖，100%覆盖)                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 遍历所有未绑定的工程对象 (EO)                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 第1层: 历史确认复用 (最高优先级，0成本)                   │   │
│  │   ├─ 查询: 同块名/同图层的ACCEPTED候选                   │   │
│  │   ├─ 命中: 直接创建PENDING候选 (score=1.0)              │   │
│  │   └─ 未命中: 进入第2层                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 第2层: 规则匹配 (确定性，0成本)                          │   │
│  │   ├─ 关键词匹配: block_name/layer_name/system/spec      │   │
│  │   ├─ 学科冲突检测: 避免跨专业误匹配                      │   │
│  │   ├─ 命中: 创建PENDING候选 (score=0.7-0.95)             │   │
│  │   └─ 未命中: 进入第3层                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 第3层: 语义召回 (Embedding相似度，低成本)                 │   │
│  │   ├─ 构建EO富文本: block+layer+system+spec+tag+知识库   │   │
│  │   ├─ 计算嵌入向量: EO文本 ↔ BOQ文本                     │   │
│  │   ├─ 余弦相似度 > 0.3 → 候选子集                       │   │
│  │   ├─ 命中: 创建PENDING候选 (score=0.5-0.8)              │   │
│  │   └─ 未命中: 进入第4层                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 第4层: LLM重排序 (大模型分析，高成本)                    │   │
│  │   ├─ 构建提示词: CAD对象 + Top-N候选BOQ                 │   │
│  │   ├─ 调用Qwen大模型: 在候选子集内选择/排序               │   │
│  │   ├─ 输出: selected_boq_id + confidence + reason        │   │
│  │   ├─ 失败保底: 返回原候选集                             │   │
│  │   └─ 创建PENDING候选 (score=LLM置信度)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 过滤被拒绝的组合 (REJECTED不再推荐)                      │   │
│  │ → 写入binding_candidate表 (status=PENDING)              │   │
│  │ → 人工审核队列                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ✅ 优势: 100%覆盖所有待定图块，成本分层控制                    │
└─────────────────────────────────────────────────────────────────┘
```

## 分层覆盖的详细逻辑

### 第1层: 历史确认复用
```python
# 查询同块名/同图层的ACCEPTED候选
hist = historical_confirmed(project_id, eo)
if hist:
    for boq_id, reason in hist:
        if boq_id not in rejected:
            # 直接创建候选，score=1.0 (最高优先级)
            db.create_binding_candidate(
                project_id, eo.id, boq_id,
                method="RULE",
                score=1.0, confidence=1.0,
                reason=reason)
    return  # 已找到高置信候选，无需继续
```

### 第2层: 规则匹配
```python
# 关键词匹配 + 学科冲突检测
base = match_rule(project_id, eo)
if base:
    for bid, score, reason in base:
        if bid not in rejected:
            # 创建候选，score=0.7-0.95
            db.create_binding_candidate(
                project_id, eo.id, bid,
                method="RULE",
                score=score, confidence=score,
                reason=reason)
    # 规则匹配成功，可选择是否继续LLM
    # return  # 如果要100%覆盖，不return，继续LLM
```

### 第3层: 语义召回
```python
# Embedding相似度匹配
emb = semantic_candidates(project_id, eo)
if emb:
    for bid, score, reason in emb:
        if bid not in rejected:
            # 创建候选，score=0.5-0.8
            db.create_binding_candidate(
                project_id, eo.id, bid,
                method="EMBEDDING",
                score=score, confidence=score,
                reason=reason)
```

### 第4层: LLM重排序
```python
# 在候选子集内LLM选择
final = llm_rerank(project_id, eo, base, top_n=5)
for bid, score, reason, method, run_id in final:
    if bid not in rejected:
        # 创建候选，score=LLM置信度
        db.create_binding_candidate(
            project_id, eo.id, bid,
            method=method,
            score=score, confidence=score,
            reason=reason,
            llm_run_id=run_id)
```

## 覆盖率分析

### 当前实现（二选一）
```
非LLM模式覆盖率: ~60-70% (仅规则匹配)
LLM模式覆盖率: ~80-90% (仅语义+LLM)
总体覆盖率: 无法保证100%
```

### 期望实现（分层覆盖）
```
第1层历史确认: ~10-20% (高置信)
第2层规则匹配: ~40-50% (中置信)
第3层语义召回: ~20-30% (中置信)
第4层LLM重排序: ~10-20% (高置信)
总体覆盖率: 100% (所有待定图块)
```

## 成本控制策略

### 1. 早停机制
- 第1层命中高置信候选 → 可选停止（节省后续成本）
- 第2层规则匹配成功 → 可选停止（0成本）

### 2. 候选子集限制
- 每层最多生成Top-N候选（避免prompt过大）
- Embedding相似度阈值 > 0.3（过滤低相关）

### 3. LLM调用优化
- 只在候选子集内调用LLM（不是全量BOQ）
- 批量处理多个EO（减少API调用次数）
- 失败保底机制（避免重试成本）

## 实施建议

### 1. 修改generate_candidates函数
```python
def generate_candidates(project_id, sheet_id=None, use_llm=True, top_n=5):
    """分层覆盖模式：100%覆盖所有待定图块"""
    eos = db.get_engineering_objects(project_id)

    for eo in eos:
        if already_bound(eo):
            continue

        # 第1层: 历史确认复用
        hist = historical_confirmed(project_id, eo)
        if hist:
            # 创建高置信候选
            continue  # 可选：是否继续下一层

        # 第2层: 规则匹配
        rule_candidates = match_rule(project_id, eo)
        if rule_candidates:
            # 创建中置信候选
            pass  # 继续下一层，确保100%覆盖

        # 第3层: 语义召回 (仅当use_llm=True)
        if use_llm:
            emb = semantic_candidates(project_id, eo)
            if emb:
                # 创建中置信候选
                pass

            # 第4层: LLM重排序 (仅当use_llm=True)
            if rule_candidates or emb:
                base = rule_candidates + emb
                final = llm_rerank(project_id, eo, base, top_n)
                # 创建LLM候选
```

### 2. UI调整
- 移除"启用LLM"复选框（默认分层覆盖）
- 或改为"LLM增强模式"（启用第3-4层）
- 显示各层命中统计（历史/规则/语义/LLM）

### 3. 性能监控
- 记录每层命中率
- 监控LLM调用成本
- 优化阈值参数
