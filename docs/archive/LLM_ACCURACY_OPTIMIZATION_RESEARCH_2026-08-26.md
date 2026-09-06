# CAD-BOQ 工具 LLM 准确率优化调研

**调研日期：2026-08-26**  
**范围：** CAD 工程对象分类、EO→BOQ 绑定、候选召回、人工复核与 LLM 运行治理。

## 1. 结论摘要

当前系统已经具备正确的基础分层：CAD 矢量解析 → 工程对象 → Embedding/关键词召回 → LLM 重排 → Pydantic 校验 → 人工确认回写知识库。当前准确率的主要上限不在 JSON 解析，而在以下三点：

1. **召回上限：** LLM 只能从 `base_candidates` 中选择，候选集中没有正确 BOQ 时，模型无法修复召回错误。
2. **语义证据不足：** Prompt 主要使用 block/layer/system/spec/tag，未稳定提供图纸上下文、专业约束、历史确认样例和 BOQ 层级关系。
3. **没有可靠的拒答与评测闭环：** 当前 schema 强制 `selected_boq_id`，不允许 `NO_MATCH`；`confidence` 是模型自报值，未按人工结果校准，也没有以 Top-k 召回率和绑定准确率作为版本门禁。

**建议目标架构：** 混合召回（关键词/BM25 + 向量 + 规则/元数据）→ 候选去重与分组 → LLM/交叉编码器重排 → 业务约束校验 → 低置信拒答 → 人工确认 → 标注集和知识库回流。LLM 应是受约束的决策组件，不应成为唯一检索器或数量计算器。

## 2. 当前方案审计

### 2.1 已有优点

- `app/binding/matcher.py` 将 LLM 模式与离线规则模式分开，避免 LLM 覆盖已绑定对象。
- `app/binding/embedding_matcher.py` 已支持富文本 EO 和知识库规格补充。
- `app/binding/llm_matcher.py` 将 LLM 限制在候选子集内，避免把整张 DWG 放进上下文。
- `app/llm/schema.py` 已做 JSON、Pydantic 类型/范围和候选集成员校验。
- `app/llm/audit.py`/`llm_run` 保留模型、Prompt 版本、输入输出和耗时，具备可追溯基础。
- 人工确认已经写回 `symbol_library`，具备项目越用越准的基础。

### 2.2 影响准确率的具体缺口

| 优先级 | 位置 | 现状 | 影响 |
|---|---|---|---|
| P0 | `app/llm/schema.py`、`prompts.py` | `selected_boq_id` 必填，模型必须从候选中选一个 | 候选都不匹配时产生“最接近项”错绑，且可能高置信 |
| P0 | `app/binding/embedding_matcher.py` | 仅一个 embedding 表示、固定 `s > 0.3` 阈值、只取 Top-N | 同义词、缩写、跨语言、规格数字差异会导致漏召回 |
| P0 | `app/binding/matcher.py` | LLM 兜底使用自定义字符串拆词和子串命中 | `4MP`、`FA`、`TV/CCTV` 等短词容易误命中或被噪声污染 |
| P0 | `app/llm/runner.py` | 文档描述的 quality fallback 仅在调用/校验失败时发生 | “模型成功但语义低置信”不会真正触发第二模型复核 |
| P1 | `app/binding/llm_matcher.py` | LLM 接收候选，但未接收每个候选的可解释匹配特征 | 模型无法系统比较专业、系统、规格、单位冲突 |
| P1 | `app/llm/schema.py` | `confidence` 直接落为候选 confidence | 自报置信度未校准，不能直接用作自动确认阈值 |
| P1 | `app/engineering/llm_classify.py` | 分类结果写回知识库，但未区分人工真值和 LLM 推断的可信等级 | 错误分类可能被后续召回重复放大 |
| P1 | `app/takeoff/llm_backends.py` | 不同后端的结构化输出参数未统一下发；DashScope 模型配置也未完全使用 | 输出稳定性和跨后端可比性不足 |
| P2 | `app/llm/embeddings.py` | embedding 批量计算但不持久化 BOQ 向量 | 每次重新计算，难以固定版本、复现和做大规模评测 |

## 3. 推荐的准确率优化方案

### 3.1 第一阶段：先建立可测量基线

不要先换模型。先从历史人工确认、拒绝、手工绑定中构造标注集，每条样本至少保存：

```json
{
  "eo_id": 123,
  "features": {"block_name": "...", "layer_name": "...", "specification": "...", "tag": "..."},
  "gold_boq_id": 456,
  "discipline": "ELV",
  "system": "CCTV",
  "is_abstain": false,
  "source": "manual_confirm"
}
```

至少按专业、系统、来源图纸、是否有规格、是否跨语言分层统计：

- **Recall@1 / Recall@3 / Recall@5：** 正确 BOQ 是否进入候选集；这是区分召回问题和 LLM 决策问题的关键。
- **Binding accuracy：** 最终 Top-1 与人工真值一致的比例。
- **Abstention precision/recall：** 拒答是否真的对应无匹配或证据不足。
- **Calibration：** 按 confidence 分桶比较预测置信度和真实正确率，报告 ECE/Brier score。
- **人工复核率、每 EO 延迟、token 成本、失败率：** 防止准确率提升但不可用。

建议把每次 Prompt、模型、embedding 模型、候选列表、最终人工结果作为不可变评测记录；同一组固定样本做离线回归，版本升级必须比较差异。

### 3.2 第二阶段：把召回改为混合召回

对 BOQ 候选生成采用并集，而不是“Embedding 可用就只用 Embedding”：

```text
候选 = 规则/元数据 Top-K
     ∪ BM25/中文分词 Top-K
     ∪ dense embedding Top-K
     ∪ 同专业/同系统知识库候选
```

建议实现：

1. 规范化文本：统一大小写、全角半角、中文/英文同义词、单位、规格数字和连接符。
2. 将 BOQ 拆成可检索字段：专业、系统、项目描述、规格、单位、编码，而不是只拼一段字符串。
3. 对专业、系统、单位做硬过滤或加权；例如 `CCTV` 不应与普通 `TV` 仅因字符串包含关系获得高分。
4. 对规格使用 token/数值匹配：`4MP`、`2x1.5mm2`、`DN100`、`6mm2` 应避免普通子串启发式误判。
5. 持久化 BOQ embedding 及 `embedding_model/version`，只在 BOQ 变化或模型变化时重算。
6. 先把候选集扩大到 20~50，再由重排器压缩到 3~5；当前 `EMBEDDING_TOP_N=5` 偏早截断。

第一版可不引入向量数据库，SQLite + 本地向量缓存仍适合当前规模；重点是混合召回和可复现，而不是基础设施复杂度。

### 3.3 第三阶段：改造 LLM 决策协议

把“强制选择”改成“选择或拒答”，并让模型逐候选给出受限证据：

```json
{
  "decision": "match|no_match|review",
  "selected_boq_id": "...",
  "confidence": 0.0,
  "evidence": {
    "discipline_match": true,
    "system_match": true,
    "spec_match": "exact|partial|unknown|conflict",
    "unit_match": true
  },
  "alternative_boq_ids": [],
  "needs_review": true,
  "reason_code": "SPEC_CONFLICT"
}
```

Prompt 需要明确：

- 先判断专业/系统，再比较 BOQ；不能只按名称相似度选择。
- 规格冲突、单位冲突、专业冲突优先于文字相似度。
- 证据不足时返回 `review`，禁止猜测。
- 只能使用候选的稳定 ID，不使用易混淆的显示序号。
- reason 使用固定枚举，详细解释另存审计字段，减少自由文本漂移。

对支持该能力的后端，使用原生 JSON Schema/structured output 或 grammar constrained decoding；Pydantic 解析仍保留，作为服务端不可用时的第二道校验。结构化输出只能保证格式，不能保证 BOQ 语义正确，必须继续保留业务校验和人工复核。

### 3.4 第四阶段：引入二阶段重排与验证

推荐成本/效果平衡的链路：

```text
混合召回 20~50
  -> 元数据过滤/加权
  -> Cross-Encoder 或小型 LLM 重排到 5
  -> 主 LLM 结构化决策
  -> 规则校验 + 独立 verifier
  -> 自动确认或人工复核
```

Verifier 不重新自由选择，而只回答：

1. 选中 BOQ 是否与 EO 专业/系统一致？
2. 规格、单位是否冲突？
3. 证据是否足够支持自动确认？

主模型与 verifier 使用不同提示词；对高风险类别（消防、医疗气体、配电柜、规格冲突）可升级到更强模型或强制人工复核。不要使用“让同一个模型再想一遍”作为主要质量保证，它通常只是增加延迟，并不能提供独立校验。

### 3.5 第五阶段：置信度校准和人工闭环

模型的 `confidence` 只作为一个特征，不直接等同于正确率。用历史真值训练轻量校准器，例如 Logistic Regression/Isotonic Regression，输入：

```text
LLM confidence
embedding score
BM25 score
Top1 - Top2 margin
专业/系统/单位/规格匹配特征
是否存在人工历史确认
```

输出 `calibrated_probability`，再制定策略：

- 高概率且无冲突：自动确认。
- 中间区间：进入人工复核队列。
- 低概率、无匹配或存在硬冲突：拒答/要求补充图纸信息。

人工界面应优先展示低置信、Top1/Top2 接近、历史上经常错的类别。确认、拒绝、改选都写入训练/评测数据；LLM 推断只能写入低可信知识，人工确认才升级为强规则或高可信样本。

## 4. 模型与部署建议

### 本地 Ollama

适合数据不出本机、成本敏感和离线环境。7B 模型可用于普通分类和初筛，但对跨语言图层名、规格冲突和复杂 BOQ 区分应通过扩大召回、结构化约束和人工复核补足。若显存允许，用更大指令模型做 verifier 或难例路由，不必让所有 EO 都调用大模型。

### OpenAI 兼容云端 / DeepSeek / Qwen 云端

适合难例复核和模型 A/B。应统一：system/user 消息、temperature、max_tokens、JSON Schema、超时、重试和审计字段，避免不同 backend 的“可用但行为不一致”。API key 只存配置，不写入 prompt 或日志。

### vLLM / 自托管服务

如果后续需要统一 OpenAI 兼容接口，可评估 vLLM。其文档当前支持 JSON Schema、choice、regex、grammar 等结构化输出方式，可用于替换“自由文本 + 本地解析 + 重试”的部分流程；但它仍然不解决召回数据错误和领域知识不足。

### 视觉模型

不要直接把整张 DWG 截图交给视觉模型替代矢量解析。推荐只在以下情况使用：块名/图层信息缺失、符号需要结合局部图例、矢量语义与图例存在冲突。输入应是带坐标、图层、比例和上下文说明的局部裁剪图，并把视觉结论作为证据字段参与 verifier，而不是直接改写数量。

## 5. 分阶段落地顺序

| 阶段 | 工作项 | 预期收益 | 验收指标 |
|---|---|---|---|
| P0 | 建立人工真值集、Recall@K/Accuracy/校准报表 | 找准真实瓶颈 | 固定测试集可重复运行 |
| P0 | 增加 `no_match/review`，禁止强制错绑 | 降低高置信错绑 | 错绑率下降，拒答精度可测 |
| P0 | 混合召回 + 规格/专业/单位规范化 | 提高候选覆盖 | Recall@5 明显高于当前基线 |
| P1 | 结构化证据字段、硬冲突校验 | 提高可解释性 | 冲突样本拦截率 |
| P1 | verifier + 难例路由 | 提高高风险样本准确率 | 高风险类别 precision |
| P1 | confidence 校准 + 自动确认阈值 | 减少人工量且可控 | ECE/Brier、人工复核率 |
| P2 | 持久化 embedding、A/B 模型和 Prompt | 提升复现与维护效率 | 版本可回放、无回归 |
| P2 | 局部图例/截图视觉证据 | 覆盖矢量语义缺失样本 | 视觉难例专项集准确率 |

## 6. 参考资料

- OpenAI Structured Outputs：<https://developers.openai.com/api/docs/guides/structured-outputs>
- OpenAI Evals：<https://developers.openai.com/api/docs/guides/evals>
- vLLM Structured Outputs：<https://docs.vllm.ai/en/latest/features/structured_outputs.html>
- LangChain Retrieval / Hybrid RAG 概念：<https://docs.langchain.com/oss/python/langchain/retrieval>

## 7. 最终建议

近期最值得做的不是直接把 `qwen2.5:7b` 换成更大的模型，而是按 **“可评测基线 → 混合召回 → 可拒答 schema → 证据校验 → 置信度校准”** 的顺序推进。只要正确 BOQ 不在候选集中，任何 LLM 都只能做错误选择；只要系统不允许拒答，模型就会把不确定性伪装成绑定结果。先解决这两个结构性问题，再用难例路由和更强模型投入，收益和风险才可量化。