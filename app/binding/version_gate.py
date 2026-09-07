"""P6-1 版本冲突检测（v2.0 §6.4 四能力 ①）

同一图纸（filename 归一化）存在多 revision 时，旧版本图纸上挂的
mapping/计量数据不再代表最新设计意图 → 标记 stale，供闸门/界面提示。

架构（#19 业务逻辑归 app 层 + 双引擎容错，同 Phase 3 viewport 查询）：
  - `build_version_report()` 纯逻辑函数：输入 sheet 行（dict 或对象，
    须含 sheet_id/id/filename/revision），输出版本分组报告（SQL 无关）。
  - SQLite 本地库 sheet 表无 revision 列 → 上层查询容错降级为
    revision=""，报告 has_revision_info=False、不报错（P6-1 验收 ②）。
  - PG 生产库（alembic 0004 有 revision 列）→ webapi 侧填充真实行。

版本归一化规则：
  - 去扩展名（.dxf/.dwg）+ 去空白/下划线变体，小写作分组 key。
  - revision 非空才参与排序；同一 key 按自然序（R2 < R10）取最新。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# ---- 版本归一化 ----------------------------------------------------------


def _normalize_filename(name: str) -> str:
    """filename 归一化为版本分组 key：去扩展名 + 仅保留字母数字（连字符/下划线均等价）"""
    if not name:
        return ""
    base = re.sub(r"\.(dxf|dwg)$", "", name.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", base.lower())


def _natural_key(rev: str) -> tuple:
    """revision 自然排序 key（R2 < R10 而非 'R10' < 'R2'）"""
    if not rev or not str(rev).strip():
        return (0, "")
    rev = str(rev).strip()
    m = re.match(r"^\s*([A-Za-z]?)\s*(\d+)\s*$", rev)
    if m:
        return (2, m.group(1).lower(), int(m.group(2)))
    return (1, rev.lower(), 0)


def _row_get(row: Any, name: str, default: Any = ""):
    """兼容 dict / dataclass 形态的行字段读取"""
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


# ---- 结果模型 ------------------------------------------------------------


@dataclass
class SheetVersion:
    sheet_id: int
    filename: str
    revision: str
    version_key: str = ""
    is_latest: bool = True
    is_stale: bool = False  # 同 key 下非最新 revision
    latest_revision: str = ""


def _group_rows(rows: Iterable[Any]) -> list[list[SheetVersion]]:
    """按 filename 归一化分组，返回组列表（组内未排序）"""
    groups: dict[str, list[SheetVersion]] = {}
    for r in rows:
        name = _row_get(r, "filename", "") or ""
        rev = str(_row_get(r, "revision", "") or "").strip()
        sid = _row_get(r, "sheet_id", _row_get(r, "id", 0))
        key = _normalize_filename(name) or f"sheet-{sid}"
        groups.setdefault(key, []).append(SheetVersion(sheet_id=sid, filename=name, revision=rev, version_key=key))
    return list(groups.values())


def _latest_of(group: list[SheetVersion]) -> str:
    """组内最新 revision（自然序最大；全空 → ""）"""
    revs = [sv.revision for sv in group if sv.revision]
    if not revs:
        return ""
    return max(revs, key=_natural_key)


def build_version_report(rows: list[Any]) -> dict:
    """纯逻辑：从 sheet 行构建版本报告（P6-1 核心，SQL 无关）。

    Args:
        rows: sheet 行（dict / 对象，须含 sheet_id/id、filename、revision；
              无 revision 的行按 "" 处理，合法输入）。

    Returns:
        {has_revision_info, total_sheets, versioned_groups, multi_sheet_groups,
         stale_sheets: [SheetVersion], version_breakdown: [...]}
    """
    groups: list[list[SheetVersion]] = _group_rows(rows)
    stale: list[SheetVersion] = []
    breakdown: list[dict] = []
    has_info = False

    for g in groups:
        latest = _latest_of(g)
        if latest:
            has_info = True
        for sv in sorted(g, key=lambda x: (_natural_key(x.revision), x.sheet_id)):
            sv.latest_revision = latest
            sv.is_latest = bool(latest) and sv.revision == latest
            sv.is_stale = bool(latest) and not sv.is_latest
            if sv.is_stale:
                stale.append(sv)
        breakdown.append(
            {
                "key": g[0].version_key,
                "filename": min((sv.filename for sv in g if sv.filename), default=""),
                "revisions": sorted({sv.revision for sv in g if sv.revision}, key=_natural_key),
                "sheet_count": len(g),
                "latest_revision": latest,
            }
        )

    breakdown.sort(key=lambda b: (-b["sheet_count"], b["key"]))
    return {
        "has_revision_info": has_info,
        "total_sheets": len(rows),
        "versioned_groups": sum(1 for b in breakdown if len(b["revisions"]) >= 2),
        "multi_sheet_groups": sum(1 for b in breakdown if b["sheet_count"] >= 2),
        "stale_sheets": stale,
        "version_breakdown": breakdown,
    }


def detect_version_conflicts(project_id: int) -> dict:
    """SQLite 路径：从 app.db 读 sheets → 版本报告（无 revision 列容错）。

    SQLite 本地库 sheet 表无 revision 列 → 行不带 revision → 报告
    has_revision_info=False、stale 为空，不报错（P6-1 验收②）。
    """
    # 延迟 import：避免 app.db 顶层依赖环（app.db 不 import binding）
    from .. import db

    try:
        sheets = db.get_sheets(project_id)
    except Exception:
        return {"has_revision_info": False, "total_sheets": 0, "stale_sheets": [], "version_breakdown": []}
    rows = [{"sheet_id": s.id, "filename": s.filename, "revision": getattr(s, "revision", "")} for s in sheets]
    r = build_version_report(rows)
    r["stale_sheets"] = [vars(sv) for sv in r["stale_sheets"]]
    return r
