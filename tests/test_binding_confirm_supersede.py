"""绑定确认 + 跨图纸 supersede + 唯一性校验（BACKLOG 2.3.1/2.3.2/2.2.2）集成测试。

用真实 SQLite（tmp_path 指配置 DB_PATH），走完整确认链路：
- 确认后跨图纸同名块候选 SUPERSEDED（2.3.1）
- 同名块已绑定到另一 BOQ → 重复确认被拒（2.3.2）
- 确认后同 EO 其余候选不再可见（2.2.2）
- 同 EO 候选排序最高置信置顶（2.2.1，db 默认排序）
```
python -m pytest tests/test_binding_confirm_supersede.py -q
"""
from __future__ import annotations

import json

import pytest

from app import db
from app.binding import reviewer, candidate as cand


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    return tmp_path


def _add_boq(project_id, rows):
    """rows: [(code, description, unit), ...] → 返回 boq_item_id 列表"""
    with db.get_conn() as conn:
        ids = []
        for i, (code, desc, unit) in enumerate(rows, start=1):
            cur = conn.execute(
                "INSERT INTO boq_item(project_id, row_index, code, description, unit) "
                "VALUES(?,?,?,?,?)", (project_id, i, code, desc, unit))
            ids.append(cur.lastrowid)
    return ids


def test_confirm_supersedes_same_block_cross_sheet(temp_db):
    pid = db.create_project("p1")
    sid1, sid2, eo1, eo2 = _make_sheet_pair(pid)
    b1, b2 = _add_boq(pid, [("CY-01", "CCTV camera", "套"),
                            ("FA-01", "Fire panel", "套")])
    c1 = db.create_binding_candidate(pid, eo1, b1, method=cand.METHOD_RULE,
                                     score=0.9, confidence=0.9, reason="候选1")
    db.create_binding_candidate(pid, eo2, b1, method=cand.METHOD_RULE,
                                score=0.8, confidence=0.8, reason="候选2")
    db.create_binding_candidate(pid, eo2, b2, method=cand.METHOD_EMBEDDING,
                                score=0.6, confidence=0.6, reason="候选3")
    # 确认 eo1 → CCTV-CAM→b1
    res = reviewer.confirm_binding(pid, c1)
    assert res["mapping_mode"] == "block"
    # 跨图纸同名块的两条候选全部 SUPERSEDED
    pend = db.get_pending_candidates(pid)
    assert all(p.engineering_object_id != eo2 for p in pend)
    row = db.get_candidates(pid, status="SUPERSEDED", engineering_object_id=eo2)
    assert len(row) == 2


def test_duplicate_binding_rejected(temp_db):
    pid = db.create_project("dup")
    sid1, _sid2, eo1, _eo2 = _make_sheet_pair(pid)
    b1, b2 = _add_boq(pid, [("CY-01", "CCTV camera", "套"),
                            ("FA-01", "Fire panel", "套")])
    cid = db.create_binding_candidate(pid, eo1, b1, method="MANUAL", score=1.0, confidence=1.0)
    reviewer.confirm_binding(pid, cid)
    # 同一块再确认到另一条 BOQ → 拒绝（唯一性守卫）
    cid2 = db.create_binding_candidate(pid, eo1, b2, method="MANUAL", score=1.0, confidence=1.0)
    with pytest.raises(reviewer.ReviewError):
        reviewer.confirm_binding(pid, cid2)


def test_duplicate_via_existing_mapping(temp_db):
    """已存在正式 mapping（手动建）→ 确认候选被拒防一图块多 BOQ。"""
    pid = db.create_project("map")
    sid = db.add_sheet(pid, "S.dwg", "")
    _seed_entities(sid, "CAM-1", "L")
    eo = db.create_engineering_object(pid, sheet_id=sid, object_type="equipment",
                                      block_name="CAM-1", layer_name="L")
    b1, b2 = _add_boq(pid, [("CY-01", "CCTV camera", "套"),
                            ("PS-01", "Power socket", "个")])
    db.add_mapping(b1, sid, "block", block_name="CAM-1")
    new_cid = db.create_binding_candidate(pid, eo, b2, method="MANUAL", score=1.0, confidence=1.0)
    with pytest.raises(reviewer.ReviewError):
        reviewer.confirm_binding(pid, new_cid)


def test_candidate_default_sort_conf_desc(temp_db):
    """2.2.1 落库顺序：同 EO 候选默认 confidence 降序（最高置顶）。"""
    pid = db.create_project("sort")
    sid = db.add_sheet(pid, "S.dwg", "")
    eid = db.create_engineering_object(pid, sheet_id=sid, object_type="equipment",
                                       block_name="CAM", layer_name="L")
    b1, _ = _add_boq(pid, [("A-01", "CCTV", "套"), ("B-01", "面板", "套")])
    db.create_binding_candidate(pid, eid, b1, method="EMBEDDING", score=0.5, confidence=0.5)
    db.create_binding_candidate(pid, eid, b1 + 1, method="RULE", score=0.95, confidence=0.95)
    rows = db.get_candidates(pid, engineering_object_id=eid)
    assert len(rows) == 2
    assert rows[0].confidence >= rows[1].confidence


def _seed_entities(sid, block, layer, n=2):
    with db.get_conn() as conn:
        for i in range(n):
            conn.execute(
                "INSERT INTO entity(sheet_id, handle, dxf_type, layer, block_name, "
                "bbox, geom_json, length, area, color) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sid, f"h{i}-{block}", "INSERT", layer, block,
                 "[0,0,1,1]", json.dumps({"type": "insert", "name": block,
                                          "insert": [0, 0], "scale": [1, 1], "rotation": 0}),
                 0, 0, "[255,255,255]"))


def _make_sheet_pair(pid, block="CCTV-CAM", layer="L-CCTV"):
    sid1 = db.add_sheet(pid, "S1.dwg", "")
    sid2 = db.add_sheet(pid, "S2.dwg", "")
    _seed_entities(sid1, block, layer)
    _seed_entities(sid2, block, layer)
    eo1 = db.create_engineering_object(pid, sheet_id=sid1, object_type="equipment",
                                       block_name=block, layer_name=layer)
    eo2 = db.create_engineering_object(pid, sheet_id=sid2, object_type="equipment",
                                       block_name=block, layer_name=layer)
    return sid1, sid2, eo1, eo2