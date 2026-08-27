"""规则匹配：EngineeringObject → BOQ 候选（确定性，0 LLM 成本）。

优先级：
  1. 项目级历史确认（ACCEPTED 候选，同 block/layer）—— score=1.0
  2. block_legend 已确认语义 → BOQ 关键词
  3. discipline/system/规格 关键词命中

关键词来源：EO 的 block_name 分词 / layer_name / specification / system / category；
BOQ 侧匹配 code + description + unit。
"""
from __future__ import annotations

import re

from .. import db
from ..models import EngineeringObject
from ..engineering.classifier import infer_system, infer_discipline
from .text_norm import normalize, compact, contains_spec

# 命中加权
W_SYSTEM = 0.6        # system 词命中（如 CCTV）
W_SPEC = 0.4          # 规格命中（如 4MP / DN100）
W_BLOCK_WORD = 0.3    # 块名分词命中（如 CAM）
W_LAYER_WORD = 0.25   # 图层名分词命中
W_CATEGORY = 0.2      # 中文大类命中
MAX_RESULTS = 5

# 噪声词（块名分词过滤）
_STOPWORDS = {"BLOCK", "INSERT", "TYPE", "CAD", "DWG", "DETAIL", "SYM", "SYMBOL"}


def _tokens(name: str) -> list:
    """名称分词：CAM_DOME_4MP → [CAM, DOME, 4MP]（去停用词/单字符）"""
    if not name:
        return []
    parts = re.split(r"[\s_\-/\\.,()\[\]]+", name.upper())
    return [p for p in parts if len(p) >= 2 and p not in _STOPWORDS and not p.isdigit()]


def eo_keywords(eo: EngineeringObject) -> list:
    """EO 侧关键词（去重保序）：system + spec + 块名/图层名分词"""
    kws = []
    if eo.system:
        kws.append(eo.system.upper())
    if eo.specification:
        for s in re.split(r"\s+", eo.specification.upper()):
            if s and s not in kws:
                kws.append(s)
    for t in _tokens(eo.block_name):
        if t not in kws:
            kws.append(t)
    for t in _tokens(eo.layer_name):
        if t not in kws:
            kws.append(t)
    return kws


def _score_boq(boq_text: str, kws: list, system: str, spec: str) -> tuple[float, list]:
    """返回 (score, 命中的关键词)

    字段规范化（P1）：文本先经 text_norm 规范（全角→半角/UPPER），规格命中
    用 ``contains_spec`` 支持 ``4MP`` vs ``4 MP``/``DN 100`` vs ``DN100`` 等
    隔符差异，避免子串启发式因一个空格失配。
    """
    text = normalize(boq_text)
    comp_text = compact(boq_text)
    hits = []
    score = 0.0
    for kw in kws:
        if not kw:
            continue
        # 关键词（块名/图层/system 词）在规范文本中子串命中
        if kw in text or kw in comp_text:
            hits.append(kw)
            if system and kw == system.upper():
                score += W_SYSTEM
            elif spec and contains_spec(f"{text} @@ {comp_text}", spec):
                score += W_SPEC
            else:
                score += W_BLOCK_WORD
    return round(min(0.95, score), 3), hits


def historical_confirmed(project_id: int, eo: EngineeringObject) -> list:
    """项目级历史确认：同 block/layer 的 ACCEPTED 候选 → [(boq_item_id, reason)]"""
    accepted = db.get_candidates(project_id, status="ACCEPTED")
    out = []
    for c in accepted:
        ceo = db.get_engineering_object(c.engineering_object_id)
        if not ceo:
            continue
        same = (eo.block_name and ceo.block_name == eo.block_name) or \
               (eo.layer_name and ceo.layer_name == eo.layer_name)
        if same:
            out.append((c.boq_item_id, f"历史确认复用: 同{'块' if eo.block_name else '图层'} {eo.block_name or eo.layer_name}"))
    return out


def already_bound(eo: EngineeringObject) -> bool:
    """该 EO 是否已有正式绑定（mapping 已覆盖或 ACCEPTED 候选）"""
    if db.get_candidates(eo.project_id, status="ACCEPTED", engineering_object_id=eo.id):
        return True
    if not eo.sheet_id:
        return False
    for m in db.get_mappings(sheet_id=eo.sheet_id):
        if eo.block_name and m.mode == "block" and m.block_name == eo.block_name:
            return True
        if eo.layer_name and m.mode == "layer" and m.layer_name == eo.layer_name:
            return True
    return False


def match_rule(project_id: int, eo: EngineeringObject, items: list = None) -> list:
    """规则匹配 → [(boq_item_id, score, reason)] 按分降序。

    Args:
        items: 预加载的 BOQ 项（分层编排外层加载一次复用，避免每 EO 全量查库）
    Returns:
        list of (boq_item_id, score, reason)，空 = 无规则命中（交给 Embedding/LLM）
    """
    if items is None:
        items = db.get_boq_items(project_id)
    if not items:
        return []

    # 候选过滤（任务十）：discipline/system 预筛，避免全量打分
    sys_name = eo.system or infer_system(eo.block_name, eo.layer_name)
    disc = eo.discipline or infer_discipline(eo.layer_name, eo.block_name)
    kws = eo_keywords(eo)
    if not kws:
        return []

    scored = []
    for it in items:
        text = f"{it.code} {it.description} {it.unit}"
        # discipline 强过滤：EO 已知 discipline 且 BOQ 明显属于其他专业 → 跳过
        if disc and _boq_discipline_conflict(it, disc):
            continue
        score, hits = _score_boq(text, kws, sys_name, eo.specification)
        if score > 0 and hits:
            reason = f"规则命中: {', '.join(hits[:4])}（BOQ {it.code}）"
            scored.append((it.id, score, reason))
    scored.sort(key=lambda x: -x[1])
    return scored[:MAX_RESULTS]


_DISCIPLINE_KW = {
    "ELV": ["CCTV", "CAM", "DATA", "TELE", "FA-", "FIRE ALARM", "AV-", "AP-"],
    "LV": ["PANEL", "LIGHT", "LUMINAIRE", "OUTLET", "SWITCH", "CABLE TRAY"],
    "FIRE": ["SPRINKLER", "FIRE", "消火栓", "喷淋", "FIRE PIPE"],
    "HVAC": ["DUCT", "AHU", "VAV", "FCU", "风管", "风机"],
    "PLUMBING": ["PIPE", "WATER", "DRAIN", "管", "给水", "排水"],
}


def _boq_discipline_conflict(item, disc: str) -> bool:
    """BOQ 明显属于其他 discipline 且与 EO discipline 冲突 → True（跳过）"""
    text = f"{item.code} {item.description}".upper()
    for other, kws in _DISCIPLINE_KW.items():
        if other == disc:
            continue
        if any(k.upper() in text for k in kws):
            return True
    return False
