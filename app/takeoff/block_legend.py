"""块图例标定：把 DWG 中识别到的块名映射为人工可读的设备语义。

设计目标（对应需求）：
1. 标定已识别线缆/设备块 —— 让大模型汇总数据时直接采用人工校准的语义；
2. 图例按项目配置 —— block_legend 表以 (project_id, block_name) 唯一，不跨项目复用；
3. 大模型辅助判断 + 人工复核 —— llm_suggest_legend() 产出建议（source=llm, confirmed=0），
   人工在面板里确认（confirmed=1）后才生效。

本模块只负责「数据 + LLM 建议」，UI 在 app/ui/legend_panel.py，接管算量在 orchestrator.py。
"""
from __future__ import annotations

import json
import re

from .. import db


# 类别与规则的合法取值（供 UI ComboBox 与校验复用）
# 「建筑」= 门/窗/墙/柱/洁具/家具/轴线/标注等非算量图元（LLM 快筛先行，UI 默认隐藏）
CATEGORIES = ["设备", "线缆", "建筑", "其他"]
COUNT_RULES = ["count", "length", "manual"]
UNITS = ["个", "套", "台", "m", "米", "处", "组"]

# LLM 分批大小：单批输出 JSON 需控制在 num_predict 上限内
# （中文 device_type/reasoning 每条约 100-150 token，20 条/批 + 8192 上限留足余量）
LLM_BATCH_SIZE = 20
LLM_NUM_PREDICT = 8192

# 设备块快筛（轻量分类）批量：只输出 块名→类别，每条约 10-15 token，可大批量
FILTER_BATCH_SIZE = 100
FILTER_NUM_PREDICT = 4096


# ---------------------------------------------------------------------------
# 设备块快筛：建筑元素规则预筛（零成本，先于 LLM）
# ---------------------------------------------------------------------------
# 拉丁 token 整词匹配（块名按非字母数字汉字切分后全等比较，
# 避免 WALL 子串误伤 WALLDIM 之类；WIN 整词不会命中 WINDOWX）
BUILDING_TOKENS = {
    "DOOR", "DOORS", "WIN", "WINDOW", "WINDOWS", "WALL", "WALLS",
    "COLUMN", "COLUMNS", "AXIS", "AXES", "GRID",
    "DIM", "DIMS", "DIMENSION", "TEXT", "TITLE", "TITLEBLOCK", "FRAME",
    "ARROW", "NORTH", "SYMBOL", "SYM", "DESK", "CHAIR", "SOFA", "BED",
    "WC", "TOILET", "LAVATORY", "BASIN", "SINK", "SHOWER", "BATHTUB", "URINAL",
    "FURNITURE", "ANNOTATION", "ELEVATION", "SECTION",
}
# 中文多字关键词子串匹配（保守：不用单字，避免误伤「门禁」「窗式空调」等设备块）
BUILDING_SUBSTRINGS = (
    "防火门", "平开门", "推拉门", "卷帘门", "折叠门", "门扇", "门框", "门洞",
    "木门", "钢门", "玻璃门", "弹簧门", "门联窗",
    "固定窗", "平开窗", "推拉窗", "飘窗", "窗扇", "窗台", "幕墙",
    "墙体", "隔墙", "砌体", "剪力墙", "挡土墙",
    "框架柱", "构造柱", "柱子", "暗柱",
    "洁具", "马桶", "坐便", "蹲便", "洗脸盆", "洗手盆", "小便斗",
    "淋浴", "浴缸", "拖布池", "水槽",
    "家具", "办公桌", "餐桌", "座椅", "沙发", "病床",
    "轴线", "轴网", "标注", "尺寸", "图框", "标题栏", "指北针", "箭头", "剖切",
)


def _name_tokens(bname: str) -> list:
    """按非字母数字汉字字符切分块名 → 大写 token 列表"""
    return [t for t in re.split(r"[^A-Za-z0-9\u4e00-\u9fff]+", bname.upper()) if t]


def is_building_by_rule(bname: str) -> bool:
    """规则预筛：明显是建筑元素（门窗墙柱洁具家具轴线标注）的块名直接判「建筑」。

    保守设计：拉丁词整 token 匹配 + 中文多字关键词子串匹配，
    宁可漏判交给 LLM，不误杀设备块（漏判代价小：LLM 兜底）。
    """
    if not bname:
        return False
    if any(t in BUILDING_TOKENS for t in _name_tokens(bname)):
        return True
    return any(k in bname for k in BUILDING_SUBSTRINGS)


def collect_blocks(project_id: int) -> list:
    """聚合项目下所有图纸的块引用 -> [(block_name, total_count, sheet_count)]"""
    return db.collect_blocks(project_id)


def legend_map(project_id: int) -> dict:
    """{block_name: legend_dict}"""
    return db.get_block_legend_map(project_id)


# ---------------------------------------------------------------------------
# LLM 辅助标定
# ---------------------------------------------------------------------------
LEGEND_SYSTEM_PROMPT = """你是中国工程造价师，精通 CAD 电气/给排水/暖通图纸中的设备图块。

# 任务
输入是一份 CAD 图纸里被 INSERT 引用的「块名」清单（含引用次数与样例规格文本）。
请依据块名命名习惯、行业常识，推断每个块对应的真实设备语义，输出结构化 JSON。

# 字段约定
- category: 设备 / 线缆 / 其他
- device_type: 人工可读的设备类型，如「单联单控开关」「阻燃铜芯电缆」「PVC 接线盒」
- spec: 规格型号（若块名或样例文本能看出，如 WDZ-YJY-4x25+1x16、SC20；看不出留空）
- unit: 计量单位，数量类用「个」，线缆长度类用「m」
- count_rule: 该块在算量时的计量方式 ——
    * count：按引用次数计数（绝大多数设备块）
    * length：块代表一段线缆/导管，应按其几何长度计量（极少）
    * manual：无法自动计量，需人工处理
- confidence: 0~1 你对推断的把握
- reasoning: 1 句话依据，不超过 15 个字

# 严格约束
- 数值/规格必须来自输入，严禁编造
- 严格 JSON 输出，不要 ```json 或任何解释文字
- 每个输入块都必须给出一条结果，block_name 须原样保留
"""

LEGEND_USER_TEMPLATE = """# 项目
- 项目类型: {project_type}
- 专业范围: {specialty}

# 已识别块清单（block_name | 引用次数 | 样例规格文本）
{block_lines}

# 你已人工标定的部分（请尊重，不要改写，仅在输出中原样保留）
{existing_lines}

# 输出格式
{{"legend": [{{"block_name": "...", "category": "设备/线缆/其他", "device_type": "...", "spec": "...", "unit": "个/m", "count_rule": "count/length/manual", "confidence": 0.0, "reasoning": "..."}}]}}
"""


def build_legend_prompt(blocks: list, project_type: str, specialty: str,
                        existing: dict = None) -> tuple[str, str]:
    """构建 (system, user)。
    blocks: [(block_name, count[, sheet_count])]  2 元组或 3 元组均可
    existing: {block_name: legend_dict} 已标定的条目（提示 LLM 尊重）
    """
    lines = []
    for b in blocks:
        bname, cnt = b[0], b[1]
        lines.append(f"{bname} | {cnt}")
    block_lines = "\n".join(lines) if lines else "（无）"

    ex_lines = []
    if existing:
        for bname, row in existing.items():
            if row.get("confirmed") or row.get("device_type"):
                ex_lines.append(
                    f"{bname} => {row.get('category','')}/{row.get('device_type','')}"
                    f"/{row.get('spec','')}/{row.get('unit','')}/{row.get('count_rule','')}")
    existing_lines = "\n".join(ex_lines) if ex_lines else "（无）"

    user = LEGEND_USER_TEMPLATE.format(
        project_type=project_type, specialty=specialty,
        block_lines=block_lines, existing_lines=existing_lines)
    return LEGEND_SYSTEM_PROMPT, user


def parse_suggestions(content: str) -> dict:
    """鲁棒解析 LLM 输出 -> {block_name: suggestion_dict}；无法解析返回 {}"""
    if not content:
        return {}
    content = content.strip()
    # 1) 剥 ```json 围栏
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        content = m.group(1)
    # 2) 整体是一个 JSON 文档：直接解析
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("legend"), list):
        out = {}
        for it in parsed["legend"]:
            e = _entry_dict(it)
            if e:
                out[it["block_name"]] = e
        return out
    # 3) 容错：模型可能输出多个独立 {"legend": [...]} 文档，或输出被
    #    num_predict 截断导致整份 JSON 不完整 —— 扫描全部顶层平衡对象，
    #    既收集 legend 文档内的条目，也收集裸条目对象，合并结果
    return _extract_entry_objects(content)


def _entry_dict(obj: dict) -> dict | None:
    """归一化一个条目对象；不是条目则返回 None"""
    if not isinstance(obj, dict) or not obj.get("block_name"):
        return None
    return {
        "category": obj.get("category", ""),
        "device_type": obj.get("device_type", ""),
        "spec": obj.get("spec", ""),
        "unit": obj.get("unit", "个"),
        "count_rule": obj.get("count_rule", "count"),
        "confidence": float(obj.get("confidence", 0.0) or 0.0),
        "reasoning": obj.get("reasoning", ""),
    }


def _extract_entry_objects(content: str) -> dict:
    """扫描（可能多文档/截断的）输出，尽量恢复全部条目。

    两遍扫描并合并：
    1. 顶层平衡 JSON 对象 —— 兼容多个独立 {"legend": [...]} 文档（qwen2.5 常见）；
    2. 任意深度的扁平条目对象 {"block_name": ...} —— 兼容单个被截断、
       外层未闭合的 legend 文档（此时条目本身仍是完整平衡的）。
    """
    out = {}

    # ---- Pass 1: 顶层平衡对象 ----
    depth = 0
    start = -1
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict):
                    if isinstance(obj.get("legend"), list):
                        for it in obj["legend"]:
                            e = _entry_dict(it)
                            if e:
                                out[it["block_name"]] = e
                    else:
                        e = _entry_dict(obj)
                        if e:
                            out[obj["block_name"]] = e
                start = -1

    # ---- Pass 2: 任意深度的扁平条目对象（截断文档救底）----
    for m in re.finditer(r"\{[^{}]*\}", content):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        e = _entry_dict(obj)
        if e:
            out.setdefault(obj["block_name"], e)
    return out


def llm_suggest_legend(blocks: list, project_type: str = "医院", specialty: str = "电气",
                       model: str = "qwen2.5:7b",
                       host: str = "http://127.0.0.1:11434", timeout: int = 300,
                       existing: dict = None,
                       progress_cb=None) -> dict:
    """调用本地 Ollama 产出块图例建议（自动过滤匿名块并分批调用）。

    大图纸单项目可能有两千多个块引用，一次性发给 LLM 会导致：
      1) 输出 token 上限内 JSON 必然截断、解析失败；
      2) 匿名块（*U2184 等）本就无名可判。
    因此这里：
      - 过滤空名与 * 开头的匿名块；
      - 命名块按引用次数降序、按 LLM_BATCH_SIZE 分批调用并聚合。

    Args:
        blocks: [(block_name, total_count, sheet_count)]
        progress_cb: 可选回调 (done, total, batch_info_str)
    Returns: {block_name: suggestion_dict}
    Raises: RuntimeError（无命名块 / Ollama 不可用 / 全部批次失败）
    """
    import ollama  # 运行时 import

    # 匿名块（AutoCAD *U 前缀）与空名块：无名可判，不发给 LLM
    named = [(b[0], b[1]) for b in blocks
             if b and b[0] and not b[0].strip().startswith("*")]
    if not named:
        raise RuntimeError(
            "项目中只有匿名块（*U 开头）或无名块，LLM 无法按块名判断语义，"
            "请使用「手动标定」直接在表格内填写。")
    # 引用次数多的优先（重要的块先标定）
    named.sort(key=lambda x: -x[1])

    try:
        client = ollama.Client(host=host, timeout=timeout)
    except TypeError:  # 旧版 ollama-python 不支持 timeout
        client = ollama.Client(host=host)

    batches = [named[i:i + LLM_BATCH_SIZE] for i in range(0, len(named), LLM_BATCH_SIZE)]
    total = len(batches)
    suggestions: dict = {}
    failures = []
    for i, batch in enumerate(batches, 1):
        if progress_cb:
            progress_cb(i, total, f"批次 {i}/{total}（{len(batch)} 块）")
        system, user = build_legend_prompt(batch, project_type, specialty, existing)
        try:
            resp = client.chat(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                options={"temperature": 0.1, "num_predict": LLM_NUM_PREDICT})
            content = resp["message"]["content"]
            sugg = parse_suggestions(content)
            if not sugg:
                failures.append(f"批次 {i}（{batch[0][0]} 等 {len(batch)} 块）输出无法解析")
                continue
            suggestions.update(sugg)
        except Exception as e:  # noqa: BLE001 单批失败不终止
            failures.append(f"批次 {i}: {e}")
            continue

    if not suggestions:
        raise RuntimeError(
            "LLM 全部批次调用失败：\n" + "\n".join(failures[:5]))
    return suggestions


def apply_suggestions(project_id: int, suggestions: dict,
                      existing_map: dict = None) -> list:
    """把 LLM 建议转成待保存行。

    规则：
    - 已人工确认(confirmed=1)的条目不被覆盖；
    - 已存在的未确认条目，用建议刷新（保留已填的 spec/device_type 若更具体则保留）；
    - 新块直接采用建议。
    返回 list[dict]（可直接 save_block_legend 的行）。
    """
    existing_map = existing_map or {}
    rows = []
    for bname, sug in suggestions.items():
        prev = existing_map.get(bname)
        # 人工已确认的，跳过（不覆盖人工判断）
        if prev and prev.get("confirmed"):
            continue
        if prev:
            # 未确认：以建议为主，但保留人工已填的更具体字段
            device_type = sug.get("device_type") or prev.get("device_type", "")
            spec = sug.get("spec") or prev.get("spec", "")
            category = sug.get("category") or prev.get("category", "")
            unit = sug.get("unit") or prev.get("unit", "个")
            count_rule = sug.get("count_rule") or prev.get("count_rule", "count")
        else:
            device_type = sug.get("device_type", "")
            spec = sug.get("spec", "")
            category = sug.get("category", "")
            unit = sug.get("unit", "个")
            count_rule = sug.get("count_rule", "count")
        rows.append({
            "project_id": project_id,
            "block_name": bname,
            "category": category,
            "device_type": device_type,
            "spec": spec,
            "unit": unit,
            "count_rule": count_rule,
            "confirmed": 0,             # 待人工复核
            "source": "llm",
            "note": sug.get("reasoning", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# LLM 设备块快筛（轻量分类）：先筛掉门窗墙柱洁具等建筑元素，再按需完整标定
# ---------------------------------------------------------------------------
FILTER_SYSTEM_PROMPT = """你是中国工程造价师，熟悉 CAD 图纸中的图块命名习惯。

# 任务
输入是一份 CAD 图纸中的「块名」清单。请判断每个块属于哪一类：
- 设备：电气/暖通/给排水/消防等专业的算量设备（灯具、开关、插座、配电箱、
  风机、水泵、喷淋头、探测器、摄像机等）
- 线缆：电线电缆、桥架、线槽、导管等线性材料
- 建筑：门/窗/墙/柱/卫生洁具/家具/轴线/标注/图框/符号等非设备图元
- 其他：以上都不是或无法判断

# 严格约束
- 只输出 JSON，不要 ```json 围栏或任何解释文字
- 格式：{"blocks": [{"block_name": "...", "category": "设备/线缆/建筑/其他"}]}
- block_name 原样保留，每个输入块必须给出一条结果
"""

FILTER_USER_TEMPLATE = """# 项目
- 项目类型: {project_type}
- 专业范围: {specialty}

# 块名清单
{block_lines}

# 你已人工标定的部分（请尊重已有判断，原样输出该类别）
{existing_lines}
"""


def build_filter_prompt(block_names: list, project_type: str, specialty: str,
                        existing: dict = None) -> tuple[str, str]:
    """构建快筛 (system, user)。block_names: [block_name]"""
    lines = [f"{i + 1}. {b}" for i, b in enumerate(block_names)]
    ex_lines = []
    if existing:
        for bname, row in existing.items():
            if row.get("confirmed") and row.get("category"):
                ex_lines.append(f"{bname} => {row['category']}")
    user = FILTER_USER_TEMPLATE.format(
        project_type=project_type, specialty=specialty,
        block_lines="\n".join(lines) if lines else "（无）",
        existing_lines="\n".join(ex_lines) if ex_lines else "（无）")
    return FILTER_SYSTEM_PROMPT, user


def _filter_entry(obj) -> str | None:
    """归一化一个快筛条目 -> 合法类别字符串；不是条目返回 None"""
    if not isinstance(obj, dict) or not obj.get("block_name"):
        return None
    cat = str(obj.get("category", "") or "").strip()
    if cat in CATEGORIES:
        return cat
    # 兼容 is_device 布尔输出
    if "is_device" in obj:
        return "设备" if obj["is_device"] else "建筑"
    return None


def _collect_filter_obj(obj: dict, out: dict, only_flat: bool = False):
    """从 JSON 对象收集快筛条目：优先 blocks/legend/results 列表，否则视为扁平条目。"""
    if not isinstance(obj, dict):
        return
    if not only_flat:
        for key in ("blocks", "legend", "results"):
            if isinstance(obj.get(key), list):
                for it in obj[key]:
                    e = _filter_entry(it)
                    if e:
                        out.setdefault(it["block_name"], e)
                return
    e = _filter_entry(obj)
    if e:
        out.setdefault(obj["block_name"], e)


def parse_filter_result(content: str) -> dict:
    """鲁棒解析 LLM 快筛输出 -> {block_name: category}；无法解析返回 {}

    兼容：```json 围栏 / 整体 JSON 文档 / 多个独立文档（qwen 常见）/
    num_predict 截断后的扁平条目对象。
    """
    if not content:
        return {}
    content = content.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        content = m.group(1)
    out: dict = {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        _collect_filter_obj(parsed, out)
        if out:
            return out
    # 容错：多个独立文档 / 截断 —— 两遍扫描（顶层平衡对象 + 扁平条目）
    depth = 0
    start = -1
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict):
                    _collect_filter_obj(obj, out)
                start = -1
    for m2 in re.finditer(r"\{[^{}]*\}", content):
        try:
            obj = json.loads(m2.group(0))
        except json.JSONDecodeError:
            continue
        _collect_filter_obj(obj, out, only_flat=True)
    return out


def llm_filter_devices(blocks: list, project_type: str = "医院",
                       specialty: str = "电气", model: str = "qwen2.5:7b",
                       host: str = "http://127.0.0.1:11434", timeout: int = 300,
                       existing: dict = None, progress_cb=None) -> dict:
    """LLM 快筛：判断每个块属于 设备/线缆/建筑/其他。

    两级筛选：
      1) 规则预筛（is_building_by_rule）：门窗墙柱洁具等明显建筑块直接判「建筑」，零成本；
      2) 剩余命名块按 FILTER_BATCH_SIZE 分批调 LLM 轻量分类
         （只输出 块名→类别，比完整标定快数倍）。

    已人工确认(confirmed=1)且已有类别的条目跳过（尊重人工判断）。
    Args:
        blocks: [(block_name, total_count[, sheet_count])]
        progress_cb: 可选回调 (done, total, batch_info_str)
    Returns: {block_name: "设备"/"线缆"/"建筑"/"其他"}
    Raises: RuntimeError（存在待判块但 LLM 全部批次失败）
    """
    import ollama  # 运行时 import

    existing = existing or {}
    result: dict = {}
    todo: list = []
    for b in blocks:
        bname = b[0] if b else ""
        if not bname or bname.strip().startswith("*"):
            continue
        prev = existing.get(bname)
        if prev and prev.get("confirmed") and (prev.get("category") or "").strip():
            result[bname] = prev["category"].strip()      # 人工已确认，尊重
            continue
        if is_building_by_rule(bname):
            result[bname] = "建筑"                        # 规则预筛命中，零成本
            continue
        todo.append(bname)
    if not todo:
        return result

    try:
        client = ollama.Client(host=host, timeout=timeout)
    except TypeError:  # 旧版 ollama-python 不支持 timeout
        client = ollama.Client(host=host)

    batches = [todo[i:i + FILTER_BATCH_SIZE]
               for i in range(0, len(todo), FILTER_BATCH_SIZE)]
    total = len(batches)
    failures = []
    for i, batch in enumerate(batches, 1):
        if progress_cb:
            progress_cb(i, total, f"批次 {i}/{total}（{len(batch)} 块）")
        system, user = build_filter_prompt(batch, project_type, specialty, existing)
        try:
            resp = client.chat(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                options={"temperature": 0.1, "num_predict": FILTER_NUM_PREDICT})
            got = parse_filter_result(resp["message"]["content"])
            if not got:
                failures.append(f"批次 {i}（{batch[0]} 等 {len(batch)} 块）输出无法解析")
                continue
            result.update(got)
        except Exception as e:  # noqa: BLE001 单批失败不终止
            failures.append(f"批次 {i}: {e}")
            continue

    if not any(b in result for b in todo):
        raise RuntimeError("LLM 快筛全部批次调用失败：\n" + "\n".join(failures[:5]))
    return result


def apply_filter(project_id: int, classification: dict,
                 existing_map: dict = None) -> list:
    """把快筛分类转成待保存行（只更新 category，不动 device_type/spec 等字段）。

    规则：
    - 已人工确认(confirmed=1)且已有类别的条目不覆盖；
    - 已人工标定(source=manual)且已有类别的条目不覆盖（右键纠正优先）；
    - 已存在未确认条目：仅刷新 category，保留其他已填字段；
    - 新块：落 category，其余留空待完整标定。
    返回 list[dict]（可直接 save_block_legend 的行）。
    """
    existing_map = existing_map or {}
    rows = []
    for bname, cat in classification.items():
        if cat not in CATEGORIES:
            continue
        prev = existing_map.get(bname)
        if prev:
            if prev.get("confirmed") and (prev.get("category") or "").strip():
                continue    # 人工已确认，不覆盖
            if prev.get("source") == "manual" and (prev.get("category") or "").strip():
                continue    # 人工右键纠正过，不覆盖
            row = dict(prev)
            row["category"] = cat
            row["source"] = prev.get("source") or "llm"
        else:
            row = {
                "project_id": project_id,
                "block_name": bname,
                "category": cat,
                "device_type": "",
                "spec": "",
                "unit": "个",
                "count_rule": "count",
                "confirmed": 0,
                "source": "llm",
                "note": "",
            }
        rows.append(row)
    return rows
