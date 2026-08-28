"""SQLite 数据层"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time

from .config import DB_PATH
from .models import (Project, Sheet, Entity, BoqItem, Mapping,
                     EngineeringObject, BindingCandidate, LlmRun,
                     SymbolLibrary)

logger = logging.getLogger(__name__)

# 线程本地连接池（P0-b 性能优化）：每线程复用一条连接，避免热路径频繁 sqlite3.connect()
_thread_local = threading.local()


def _close_thread_conn() -> None:
    """关闭当前线程持有的连接（测试/退出时调用，避免句柄泄漏）。"""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _thread_local.conn = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT DEFAULT '',
    boq_path TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    src_path TEXT DEFAULT '',
    dxf_path TEXT DEFAULT '',
    status TEXT DEFAULT 'ready',
    scale REAL DEFAULT 1.0,
    entity_count INTEGER DEFAULT 0,
    layer_count INTEGER DEFAULT 0,
    blocks_json TEXT DEFAULT '',
    is_base INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL REFERENCES sheet(id) ON DELETE CASCADE,
    handle TEXT NOT NULL,
    dxf_type TEXT DEFAULT '',
    layer TEXT DEFAULT '',
    block_name TEXT DEFAULT '',
    bbox TEXT DEFAULT '',
    geom_json TEXT DEFAULT '',
    length REAL DEFAULT 0,
    area REAL DEFAULT 0,
    color TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_entity_sheet ON entity(sheet_id);
CREATE INDEX IF NOT EXISTS idx_entity_layer ON entity(sheet_id, layer);
CREATE INDEX IF NOT EXISTS idx_entity_block ON entity(sheet_id, block_name);
CREATE TABLE IF NOT EXISTS boq_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    row_index INTEGER DEFAULT 0,
    code TEXT DEFAULT '',
    description TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    original_qty REAL DEFAULT 0,
    rule_type TEXT DEFAULT 'length',
    scale_factor REAL DEFAULT 1.0,
    measured_qty REAL DEFAULT 0        -- 项目级实测数量（回写，原数量保留对照）
);
CREATE INDEX IF NOT EXISTS idx_boq_project ON boq_item(project_id);
CREATE TABLE IF NOT EXISTS mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boq_item_id INTEGER NOT NULL REFERENCES boq_item(id) ON DELETE CASCADE,
    sheet_id INTEGER NOT NULL REFERENCES sheet(id) ON DELETE CASCADE,
    mode TEXT DEFAULT 'entity',
    entity_id INTEGER,
    layer_name TEXT DEFAULT '',
    block_name TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mapping_item ON mapping(boq_item_id);
CREATE INDEX IF NOT EXISTS idx_mapping_entity ON mapping(entity_id);
CREATE TABLE IF NOT EXISTS block_legend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    block_name TEXT NOT NULL,
    category TEXT DEFAULT '',          -- 线缆 / 设备 / 其他
    device_type TEXT DEFAULT '',       -- 设备类型（人工可读）
    spec TEXT DEFAULT '',              -- 规格/型号
    unit TEXT DEFAULT '个',            -- 个 / 套 / 台 / m / 米
    count_rule TEXT DEFAULT 'count',  -- count / length / manual
    confirmed INTEGER DEFAULT 0,       -- 0=待复核 1=已确认
    source TEXT DEFAULT 'manual',      -- manual / llm
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_legend_proj_block ON block_legend(project_id, block_name);

-- ===== V2：工程对象 / 绑定候选 / LLM 审计 =====
CREATE TABLE IF NOT EXISTS engineering_object (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    sheet_id INTEGER REFERENCES sheet(id) ON DELETE CASCADE,
    object_type TEXT DEFAULT '',            -- equipment / linear / area
    discipline TEXT DEFAULT '',
    system TEXT DEFAULT '',
    subsystem TEXT DEFAULT '',
    block_name TEXT DEFAULT '',
    layer_name TEXT DEFAULT '',
    tag TEXT DEFAULT '',
    specification TEXT DEFAULT '',
    material TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    quantity_rule TEXT DEFAULT 'count',     -- count / length / area
    confidence REAL DEFAULT 0,
    source TEXT DEFAULT '',
    entity_ids TEXT DEFAULT '',             -- JSON [entity_id,...] 溯源锚点
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_eo_project ON engineering_object(project_id);
CREATE INDEX IF NOT EXISTS idx_eo_block ON engineering_object(project_id, block_name);
CREATE INDEX IF NOT EXISTS idx_eo_layer ON engineering_object(project_id, layer_name);

CREATE TABLE IF NOT EXISTS llm_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES project(id) ON DELETE CASCADE,
    task_type TEXT DEFAULT '',              -- legend / binding / classify / embedding
    model TEXT DEFAULT '',
    model_version TEXT DEFAULT '',
    prompt_version TEXT DEFAULT '',
    temperature REAL DEFAULT 0,
    input_hash TEXT DEFAULT '',
    output_hash TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    token_input INTEGER DEFAULT 0,
    token_output INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ok',               -- ok / error / retried
    error TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_lr_project ON llm_run(project_id);

-- V2：项目级配置（每项目独立保存图层/设备筛选规则 + 元数据）
CREATE TABLE IF NOT EXISTS project_config (
    project_id INTEGER PRIMARY KEY REFERENCES project(id) ON DELETE CASCADE,
    layer_rules TEXT DEFAULT '{}',   -- JSON: {equipment:[], linear:[], area:[], skip:[]}
    block_rules TEXT DEFAULT '{}',   -- JSON: {device_type:[], spec_keywords:[], skip:[]}
    meta TEXT DEFAULT '{}',          -- JSON: {type:"电气", region:"海外", specialty:"MEP", notes:""}
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS binding_candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    engineering_object_id INTEGER NOT NULL REFERENCES engineering_object(id) ON DELETE CASCADE,
    boq_item_id INTEGER NOT NULL REFERENCES boq_item(id) ON DELETE CASCADE,
    method TEXT DEFAULT 'LLM',              -- RULE / EMBEDDING / LLM / MANUAL
    score REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    reason TEXT DEFAULT '',
    model TEXT DEFAULT '',
    model_version TEXT DEFAULT '',
    prompt_version TEXT DEFAULT '',
    llm_run_id INTEGER REFERENCES llm_run(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'PENDING',          -- PENDING / ACCEPTED / REJECTED / SUPERSEDED
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bc_eo ON binding_candidate(engineering_object_id);
CREATE INDEX IF NOT EXISTS idx_bc_boq ON binding_candidate(boq_item_id);
CREATE INDEX IF NOT EXISTS idx_bc_status ON binding_candidate(project_id, status);
-- 候选状态热查询：get_candidates(project_id, engineering_object_id)（工作台 _obj_state / rejected 对）
CREATE INDEX IF NOT EXISTS idx_bc_proj_eo ON binding_candidate(project_id, engineering_object_id);
CREATE INDEX IF NOT EXISTS idx_bc_proj_eo_status ON binding_candidate(project_id, engineering_object_id, status);

-- ===== V2 LLM 配置中心（任务二十九：全局单例 llm_settings） =====
-- 设计要点：PK=1 强制单例；5 个 backend 字段全列化；fallback/quality 控制自动重跑；
-- 旧列兼容：config.py 的 MODEL_NAME/MODEL_PROVIDER 仍可作为初始回退值。
CREATE TABLE IF NOT EXISTS llm_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    active_backend TEXT DEFAULT 'ollama',                -- ollama / dashscope / openai / deepseek / custom
    -- Ollama（本地）
    ollama_host TEXT DEFAULT 'http://127.0.0.1:11434',
    ollama_model TEXT DEFAULT 'qwen2.5:7b',
    -- DashScope（阿里云 Qwen）
    dashscope_api_key TEXT DEFAULT '',
    dashscope_model TEXT DEFAULT 'qwen-vl-max-0809',
    -- OpenAI
    openai_api_key TEXT DEFAULT '',
    openai_model TEXT DEFAULT 'gpt-4o-mini',
    -- DeepSeek
    deepseek_api_key TEXT DEFAULT '',
    deepseek_model TEXT DEFAULT 'deepseek-chat',
    -- Custom OpenAI 兼容（Ollama / LocalAI / vLLM / LM Studio / 等）
    custom_base_url TEXT DEFAULT '',
    custom_api_key TEXT DEFAULT '',
    custom_model TEXT DEFAULT '',
    custom_embedding_model TEXT DEFAULT '',
    -- Fallback 配置
    fallback_enabled INTEGER DEFAULT 0,                   -- 0/1
    fallback_backend TEXT DEFAULT '',                     -- 备用 backend 名称
    quality_threshold REAL DEFAULT 0.7,                    -- 候选 confidence < 此值触发 fallback
    -- 通用项
    temperature REAL DEFAULT 0.1,
    timeout INTEGER DEFAULT 120,
    max_tokens INTEGER DEFAULT 4000,
    updated_at TEXT DEFAULT ''
);

-- ===== 图例符号知识库（可学习，人工标定沉淀） =====
-- 设计要点：block_name/layer_name 为键；人工确认/拒绝时写入；
-- 语义分类三重兜底（规则→知识库→LLM）与规格提取复用。
CREATE TABLE IF NOT EXISTS symbol_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    block_name TEXT DEFAULT '',
    layer_name TEXT DEFAULT '',
    discipline TEXT DEFAULT '',
    system TEXT DEFAULT '',
    spec TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    quantity_rule TEXT DEFAULT '',          -- count / length / area
    source TEXT DEFAULT 'manual',           -- manual / llm / rule
    confirmed_by TEXT DEFAULT '',
    confirmed_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    UNIQUE(project_id, block_name, layer_name)
);
CREATE INDEX IF NOT EXISTS idx_symlib_block ON symbol_library(block_name);
CREATE INDEX IF NOT EXISTS idx_symlib_layer ON symbol_library(layer_name);
"""


def _open_db() -> sqlite3.Connection:
    """主打开路径：WAL 模式 + FK 开启。

    stale-shm 自愈：
    触发：stale -shm/-wal 文件锁导致 PRAGMA journal_mode=WAL / 写入失败。
    表现：sqlite 报 'attempt to write a readonly database' 或 'disk I/O error'。
    处理：在 WAL 失败时关闭连接 → 尝试清 stale -shm/-wal → 重连一次；仍失败则向上抛。
    """
    base = str(DB_PATH)
    for attempt in (1, 2):
        conn = sqlite3.connect(base, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        # 性能优化：大缓存 + 内存映射 I/O（1.5GB 数据库需要更大缓存）
        conn.execute("PRAGMA cache_size = -65536")   # 256MB 页缓存（默认仅 8MB）
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB 内存映射
        if attempt == 1:
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys = ON")
                return conn
            except sqlite3.OperationalError:
                conn.close()
                # 第二次重试：尝试清理 stale -shm/-wal（仅 .db 旁的辅助文件，不影响数据）
                for suf in ("-shm", "-wal"):
                    p = base + suf
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except OSError:
                        pass
                continue
        else:
            # 第二次重试：降级到 DELETE 模式（性能稍差但功能完整）
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
    # 不会到这里
    raise sqlite3.OperationalError("get_conn: 无法打开 DB — 第二次重试也失败")


def db_usage() -> dict:
    """数据库碎片诊断（P1-2）：文件体积 / freelist 占用 / 有无可回收空间。

    Returns:
        {"file_bytes", "page_size", "freelist_pages", "freelist_bytes",
         "waste_ratio", "exists"}
    """
    sz = os.path.getsize(str(DB_PATH)) if os.path.exists(str(DB_PATH)) else 0
    if not sz:
        return {"file_bytes": 0, "free_pages": 0, "freelist_bytes": 0,
                "waste_ratio": 0.0, "exists": False}
    with get_conn() as conn:
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        free_pages = conn.execute("PRAGMA freelist_count").fetchone()[0]
    freelist_bytes = page_size * free_pages
    return {"file_bytes": sz, "free_pages": free_pages,
            "freelist_bytes": freelist_bytes,
            "waste_ratio": freelist_bytes / sz if sz else 0.0,
            "exists": True}


def vacuum_database() -> dict:
    """VACUUM 回收空闲页（1.6GB → ~170MB 场景）。单独连接执行，返回 before/after。

    VACUUM 不能用线程池连接（同线程被事务占用会报 'cannot VACUUM from within a
    transaction'），这里新建专用连接。大库（GB 级）可能耗时数秒~数十秒，调用方
    应在后台线程跑并显示进度。
    """
    before = db_usage()["file_bytes"]
    t0 = time.perf_counter()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("VACUUM")
    finally:
        conn.close()
    after = db_usage()["file_bytes"]
    return {"before_bytes": before, "after_bytes": after,
            "freed_bytes": max(0, before - after),
            "duration_ms": round((time.perf_counter() - t0) * 1000)}


def get_conn() -> sqlite3.Connection:
    """稳健版连接：WAL 时降级 DELETE 模式；同线程复用连接（性能优化）。

    每线程首次调用时建立连接并存入 ``threading.local()``，后续直接复用，
    避免热路径（N+1 循环）反复 sqlite3.connect() 的开销。进入 `with` 时
    sqlite3.Connection 的上下文管理器只 commit/rollback，不 close，
    因此复用在语义上等价于原来每条语句新建连接。
    """
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        return conn
    try:
        conn = _open_db()
    except sqlite3.OperationalError:
        # 极端情况：连 DB 文件本身都打不开 → 让异常向上传播（上层应处理）
        raise
    _thread_local.conn = conn
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """轻量迁移：为旧库补充新增列"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sheet)").fetchall()}
    if "blocks_json" not in cols:
        conn.execute("ALTER TABLE sheet ADD COLUMN blocks_json TEXT DEFAULT ''")
    if "is_base" not in cols:
        conn.execute("ALTER TABLE sheet ADD COLUMN is_base INTEGER DEFAULT 0")
    # P3：boq_item 实测数量列（工程量回写，旧库补充）
    bcols = {r[1] for r in conn.execute("PRAGMA table_info(boq_item)").fetchall()}
    if "measured_qty" not in bcols:
        conn.execute("ALTER TABLE boq_item ADD COLUMN measured_qty REAL DEFAULT 0")
    # llm_settings 新增 embedding 模型列（旧库补充）
    lcols = {r[1] for r in conn.execute("PRAGMA table_info(llm_settings)").fetchall()}
    if "custom_embedding_model" not in lcols:
        conn.execute("ALTER TABLE llm_settings ADD COLUMN custom_embedding_model TEXT DEFAULT ''")
    # prompt 分析：llm_run 保存完整输入/输出全文（旧库增量补充）
    lrcols = {r[1] for r in conn.execute("PRAGMA table_info(llm_run)").fetchall()}
    if "input_text" not in lrcols:
        conn.execute("ALTER TABLE llm_run ADD COLUMN input_text TEXT DEFAULT ''")
    if "output_text" not in lrcols:
        conn.execute("ALTER TABLE llm_run ADD COLUMN output_text TEXT DEFAULT ''")
    # P2-4：binding_candidate 复合索引（项目×对象 / 项目×对象×状态）——旧库增量补齐
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bc_proj_eo "
        "ON binding_candidate(project_id, engineering_object_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bc_proj_eo_status "
        "ON binding_candidate(project_id, engineering_object_id, status)")


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------- 项目 ----------
def create_project(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO project(name, created_at) VALUES(?,?)", (name, _now()))
        pid = cur.lastrowid
        # 初始化项目级配置行（V2 任务二十八）
        conn.execute(
            "INSERT OR IGNORE INTO project_config(project_id, layer_rules, block_rules, meta, updated_at) "
            "VALUES(?,?,?,?,?)",
            (pid, json.dumps(_DEFAULT_LAYER_RULES), json.dumps(_DEFAULT_BLOCK_RULES),
             json.dumps(_DEFAULT_META), _now()))
        return pid


def list_projects() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM project ORDER BY id DESC").fetchall()
    return [Project(**dict(r)) for r in rows]


def get_project(pid: int) -> Project | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM project WHERE id=?", (pid,)).fetchone()
    return Project(**dict(r)) if r else None


def rename_project(pid: int, name: str) -> None:
    """重命名项目。"""
    with get_conn() as conn:
        conn.execute("UPDATE project SET name=? WHERE id=?", (name, pid))


def update_project_boq(pid: int, boq_path: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE project SET boq_path=? WHERE id=?", (boq_path, pid))


# ===========================================================================
# V2 LLM 配置中心（任务二十九：llm_settings 全局单例 CRUD）
# ===========================================================================
_LLM_SETTINGS_ALLOWED = {
    "active_backend",
    "ollama_host", "ollama_model",
    "dashscope_api_key", "dashscope_model",
    "openai_api_key", "openai_model",
    "deepseek_api_key", "deepseek_model",
    "custom_base_url", "custom_api_key", "custom_model", "custom_embedding_model",
    "fallback_enabled", "fallback_backend", "quality_threshold",
    "temperature", "timeout", "max_tokens",
}


def ensure_llm_settings() -> None:
    """首次访问时插入默认行（PK=1 单例）。"""
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO llm_settings(id) VALUES(1)")


def get_llm_settings() -> dict:
    """读取 llm_settings 全局配置；若表为空则返回 _DEFAULT_LLM_SETTINGS 副本。"""
    ensure_llm_settings()
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM llm_settings WHERE id=1").fetchone()
    if not r:
        return dict(_DEFAULT_LLM_SETTINGS)
    out = dict(r)
    # 输出字段统一为 python bool（DB 是 INTEGER）
    out["fallback_enabled"] = bool(out.get("fallback_enabled", 0))
    return out


def set_llm_settings(**fields) -> None:
    """增量更新 llm_settings（白名单字段）。缺失 / 旧值保留。"""
    if not fields:
        return
    bad = set(fields) - _LLM_SETTINGS_ALLOWED
    if bad:
        raise ValueError(f"未知字段: {bad}")
    sets, args = [], []
    for k in _LLM_SETTINGS_ALLOWED:
        if k in fields:
            v = fields[k]
            if k == "fallback_enabled":
                v = int(bool(v))
            sets.append(f"{k}=?"); args.append(v)
    if not sets:
        return
    sets.append("updated_at=?")
    args.append(_now())
    args.append(1)
    ensure_llm_settings()
    with get_conn() as conn:
        conn.execute(f"UPDATE llm_settings SET {', '.join(sets)} WHERE id=?", args)


def activate_llm_backend(backend: str) -> None:
    """切换全局激活 backend。"""
    backend = (backend or "").strip().lower()
    if backend not in {"ollama", "dashscope", "openai", "deepseek", "custom"}:
        raise ValueError(f"未知 backend: {backend}")
    set_llm_settings(active_backend=backend)


# llm_settings 默认值（首启动 / 旧库 reset）
_DEFAULT_LLM_SETTINGS = {
    "active_backend": "ollama",
    "ollama_host": "http://127.0.0.1:11434",
    "ollama_model": "qwen2.5:7b",
    "dashscope_api_key": "",
    "dashscope_model": "qwen-vl-max-0809",
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "deepseek_api_key": "",
    "deepseek_model": "deepseek-chat",
    "custom_base_url": "",
    "custom_api_key": "",
    "custom_model": "",
    "custom_embedding_model": "",
    "fallback_enabled": False,
    "fallback_backend": "",
    "quality_threshold": 0.7,
    "temperature": 0.1,
    "timeout": 120,
    "max_tokens": 4000,
    "updated_at": "",
}


# ---------- LLM 设置 ----------


# ===========================================================================
# V2：项目级配置（layer_rules / block_rules / meta）
# ===========================================================================
_DEFAULT_LAYER_RULES = {"equipment": [], "linear": [], "area": [], "skip": []}
_DEFAULT_BLOCK_RULES = {"device_type": [], "spec_keywords": [], "skip": []}
_DEFAULT_META = {"type": "", "region": "", "specialty": "", "notes": ""}


def get_project_config(project_id: int) -> dict:
    """读取项目配置；项目不存在/无 config 行 → 返回空 dict。

    Returns:
        {"layer_rules": {...}, "block_rules": {...}, "meta": {...}, "updated_at": "..."}
    """
    with get_conn() as conn:
        r = conn.execute(
            "SELECT layer_rules, block_rules, meta, updated_at "
            "FROM project_config WHERE project_id=?",
            (project_id,)).fetchone()
    if not r:
        return {
            "layer_rules": dict(_DEFAULT_LAYER_RULES),
            "block_rules": dict(_DEFAULT_BLOCK_RULES),
            "meta": dict(_DEFAULT_META),
            "updated_at": "",
        }
    out = {"updated_at": r["updated_at"] or ""}
    for k, col, default in [
        ("layer_rules", r["layer_rules"], _DEFAULT_LAYER_RULES),
        ("block_rules", r["block_rules"], _DEFAULT_BLOCK_RULES),
        ("meta", r["meta"], _DEFAULT_META),
    ]:
        try:
            out[k] = json.loads(col) if col else dict(default)
        except (json.JSONDecodeError, TypeError):
            out[k] = dict(default)
    return out


def set_project_config(project_id: int, **fields) -> None:
    """增量更新项目配置字段。

    用法:
        set_project_config(pid, layer_rules={"equipment": [...]})
        set_project_config(pid, meta={"type": "电气"})
    传入的字段会全量覆盖对应 key；未传不动。
    自动 upsert config 行（兼容旧项目）。
    """
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO project_config(project_id) VALUES(?)",
                     (project_id,))
        if "layer_rules" in fields:
            conn.execute(
                "UPDATE project_config SET layer_rules=?, updated_at=? WHERE project_id=?",
                (json.dumps(fields["layer_rules"], ensure_ascii=False), _now(), project_id))
        if "block_rules" in fields:
            conn.execute(
                "UPDATE project_config SET block_rules=?, updated_at=? WHERE project_id=?",
                (json.dumps(fields["block_rules"], ensure_ascii=False), _now(), project_id))
        if "meta" in fields:
            conn.execute(
                "UPDATE project_config SET meta=?, updated_at=? WHERE project_id=?",
                (json.dumps(fields["meta"], ensure_ascii=False), _now(), project_id))


def import_project_config(project_id: int, config_dict: dict) -> None:
    """从 JSON 字典整体导入配置（覆盖式）。用于跨项目复用模板。"""
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO project_config(project_id) VALUES(?)",
                     (project_id,))
        for k in ("layer_rules", "block_rules", "meta"):
            if k in config_dict:
                conn.execute(
                    f"UPDATE project_config SET {k}=?, updated_at=? WHERE project_id=?",
                    (json.dumps(config_dict[k], ensure_ascii=False), _now(), project_id))


def export_project_config(project_id: int) -> dict:
    """导出项目配置（可序列化为 JSON 文件）"""
    return get_project_config(project_id)


def delete_project(pid: int) -> None:
    """级联删除项目全部数据（V2：含 block_legend 与新增三表，杜绝孤儿数据）。

    新库 schema 已带 ON DELETE CASCADE，此处显式删除兜底（幂等，FK 关闭时同样有效）。
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM binding_candidate WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM engineering_object WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM llm_run WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM block_legend WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM mapping WHERE boq_item_id IN (SELECT id FROM boq_item WHERE project_id=?)", (pid,))
        conn.execute("DELETE FROM boq_item WHERE project_id=?", (pid,))
        sheet_ids = [r[0] for r in conn.execute("SELECT id FROM sheet WHERE project_id=?", (pid,))]
        for sid in sheet_ids:
            conn.execute("DELETE FROM entity WHERE sheet_id=?", (sid,))
        conn.execute("DELETE FROM sheet WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM project_config WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM project WHERE id=?", (pid,))
    _invalidate_boq_embedding(pid)


# ---------- 图纸 ----------
def add_sheet(project_id: int, filename: str, src_path: str, dxf_path: str = "",
              status: str = "ready", scale: float = 1.0,
              entity_count: int = 0, layer_count: int = 0,
              blocks_json: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sheet(project_id, filename, src_path, dxf_path, status, scale, entity_count, layer_count, blocks_json) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id, filename, src_path, dxf_path, status, scale, entity_count, layer_count, blocks_json))
        return cur.lastrowid


def update_sheet_blocks(sid: int, blocks_json: str) -> None:
    """写入块几何缓存（JSON），避免切换图纸时重新解析 DXF"""
    with get_conn() as conn:
        conn.execute("UPDATE sheet SET blocks_json=? WHERE id=?", (blocks_json, sid))


def update_sheet_parse(sid: int, dxf_path: str, entity_count: int,
                       layer_count: int, blocks_json: str) -> None:
    """批量重解析后一次性回写：DXF 路径 + 统计 + 块几何缓存 + 状态（单事务）"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE sheet SET dxf_path=?, entity_count=?, layer_count=?, "
            "blocks_json=?, status='ready' WHERE id=?",
            (dxf_path, entity_count, layer_count, blocks_json, sid),
        )


def get_sheets(project_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sheet WHERE project_id=? ORDER BY id", (project_id,)).fetchall()
    return [Sheet(**dict(r)) for r in rows]


def update_sheet_status(sid: int, status: str, entity_count: int = None, layer_count: int = None) -> None:
    with get_conn() as conn:
        sets, args = ["status=?"], [status]
        if entity_count is not None:
            sets.append("entity_count=?"); args.append(entity_count)
        if layer_count is not None:
            sets.append("layer_count=?"); args.append(layer_count)
        args.append(sid)
        conn.execute(f"UPDATE sheet SET {', '.join(sets)} WHERE id=?", args)


def delete_sheet(sid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mapping WHERE sheet_id=?", (sid,))
        conn.execute("DELETE FROM engineering_object WHERE sheet_id=?", (sid,))
        conn.execute("DELETE FROM entity WHERE sheet_id=?", (sid,))
        conn.execute("DELETE FROM sheet WHERE id=?", (sid,))


def delete_sheets(sids: list[int]) -> None:
    """批量删除图纸（级联清理实体/工程对象/映射）。

    与 delete_sheet 同一套级联语义，单事务完成（大项目也要快）。
    """
    if not sids:
        return
    marks = ",".join("?" for _ in sids)
    with get_conn() as conn:
        conn.execute(f"DELETE FROM mapping WHERE sheet_id IN ({marks})", sids)
        conn.execute(f"DELETE FROM engineering_object WHERE sheet_id IN ({marks})", sids)
        conn.execute(f"DELETE FROM entity WHERE sheet_id IN ({marks})", sids)
        conn.execute(f"DELETE FROM sheet WHERE id IN ({marks})", sids)


# ---------- 建筑底图 ----------
# 图层减法原理：机电图图层集合 - 底图图层集合 = 纯设备/管线图层
# 每个项目只允许一张底图（设新底图时自动取消旧的）
_BASE_LAYER_EXCLUDE = {"0", ""}   # layer 0 / 空名不参与减法（AutoCAD 惯例 + 避免误隐藏直接实体）


def set_base_sheet(project_id: int, sheet_id: int) -> None:
    """设定某张图纸为项目底图（先清除旧底图标记，再标记新的）。"""
    with get_conn() as conn:
        conn.execute("UPDATE sheet SET is_base=0 WHERE project_id=?", (project_id,))
        conn.execute("UPDATE sheet SET is_base=1 WHERE id=? AND project_id=?",
                     (sheet_id, project_id))


def clear_base_sheet(project_id: int) -> None:
    """取消项目的底图标记。"""
    with get_conn() as conn:
        conn.execute("UPDATE sheet SET is_base=0 WHERE project_id=?", (project_id,))


def get_base_sheet(project_id: int) -> Sheet | None:
    """返回该项目的底图 Sheet（仅一张），无则 None。"""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM sheet WHERE project_id=? AND is_base=1 LIMIT 1",
            (project_id,)).fetchone()
    return Sheet(**dict(r)) if r else None


def get_base_layers(project_id: int) -> set:
    """返回底图的图层名集合（大小写保留，减法时 NOCASE 对比）。
    layer 0 和空名不参与减法（在 _BASE_LAYER_EXCLUDE 中排除）。
    """
    base = get_base_sheet(project_id)
    if base is None:
        return set()
    rows = distinct_layers(base.id)
    return {name for name, _cnt in rows
            if name not in _BASE_LAYER_EXCLUDE}


def get_base_blocks(project_id: int) -> set:
    """返回底图的块名集合（减法辅助用，准确度低于图层减法）。"""
    base = get_base_sheet(project_id)
    if base is None:
        return set()
    rows = distinct_blocks(base.id)
    return {name for name, _cnt in rows if name}


def get_block_insert_layers(sheet_id: int) -> dict:
    """返回 {block_name: set(layer_names)} — 每个块在哪些图层上有 INSERT 引用。

    用于底图减法：如果一个块的所有 INSERT 都在底图图层上 → 该块是建筑块 → 图例隐藏。
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT block_name, layer FROM entity "
            "WHERE sheet_id=? AND block_name!='' AND layer!='' ",
            (sheet_id,)).fetchall()
    out: dict[str, set] = {}
    for r in rows:
        bn = r["block_name"]
        if bn not in out:
            out[bn] = set()
        out[bn].add(r["layer"])
    return out


# ---------- 实体 ----------
def replace_entities(sheet_id: int, entities: list) -> None:
    """整张图纸重灌实体（先清后插）"""
    with get_conn() as conn:
        conn.execute("DELETE FROM entity WHERE sheet_id=?", (sheet_id,))
        rows = []
        for e in entities:
            rows.append((
                sheet_id, e.handle, e.dxf_type, e.layer, e.block_name,
                json.dumps(e.bbox), e.geom_json, e.length, e.area,
                json.dumps(list(e.color)),
            ))
        conn.executemany(
            "INSERT INTO entity(sheet_id, handle, dxf_type, layer, block_name, bbox, geom_json, length, area, color) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)", rows)


def get_entities(sheet_id: int, layer: str = None, block: str = None, limit: int = 200000) -> list:
    started = time.perf_counter()
    sql = "SELECT * FROM entity WHERE sheet_id=?"
    args = [sheet_id]
    if layer:
        sql += " AND layer=?"
        args.append(layer)
    if block:
        sql += " AND block_name=?"
        args.append(block)
    sql += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    query_elapsed = time.perf_counter() - started
    parse_started = time.perf_counter()
    out = []
    for r in rows:
        e = Entity(**{k: r[k] for k in r.keys() if k != "bbox" and k != "color"})
        e.bbox = tuple(json.loads(r["bbox"])) if r["bbox"] else (0, 0, 0, 0)
        e.color = tuple(json.loads(r["color"])) if r["color"] else (255, 255, 255)
        out.append(e)
    logger.debug("db get_entities: sheet_id=%s rows=%d limit=%d query_ms=%.1f parse_ms=%.1f",
                 sheet_id, len(out), limit, query_elapsed * 1000,
                 (time.perf_counter() - parse_started) * 1000)
    return out


def get_entity(sheet_id: int, entity_id: int) -> Entity | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM entity WHERE sheet_id=? AND id=?", (sheet_id, entity_id)).fetchone()
    if not r:
        return None
    e = Entity(**{k: r[k] for k in r.keys() if k != "bbox" and k != "color"})
    e.bbox = tuple(json.loads(r["bbox"])) if r["bbox"] else (0, 0, 0, 0)
    e.color = tuple(json.loads(r["color"])) if r["color"] else (255, 255, 255)
    return e


def distinct_layers(sheet_id: int) -> list:
    started = time.perf_counter()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT layer, COUNT(*) c FROM entity WHERE sheet_id=? AND layer!='' "
            "GROUP BY layer ORDER BY layer COLLATE NOCASE ASC",
            (sheet_id,)).fetchall()
    result = [(r[0], r[1]) for r in rows]
    logger.debug("db distinct_layers: sheet_id=%s rows=%d elapsed_ms=%.1f",
                 sheet_id, len(result), (time.perf_counter() - started) * 1000)
    return result


def layer_color_map(sheet_id: int) -> dict[str, tuple]:
    """Phase 2: 每图层取首个实体的颜色作为代表色"""
    started = time.perf_counter()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT layer, color FROM entity WHERE sheet_id=? AND layer!='' AND color IS NOT NULL "
            "GROUP BY layer", (sheet_id,)).fetchall()
    out = {}
    for r in rows:
        try:
            out[r[0]] = tuple(json.loads(r[1]))
        except Exception:
            out[r[0]] = (128, 128, 128)
    logger.debug("db layer_color_map: sheet_id=%s rows=%d elapsed_ms=%.1f",
                 sheet_id, len(out), (time.perf_counter() - started) * 1000)
    return out


def distinct_blocks(sheet_id: int) -> list:
    started = time.perf_counter()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT block_name, COUNT(*) c FROM entity WHERE sheet_id=? AND block_name!='' "
            "GROUP BY block_name ORDER BY block_name COLLATE NOCASE ASC", (sheet_id,)).fetchall()
    result = [(r[0], r[1]) for r in rows]
    logger.debug("db distinct_blocks: sheet_id=%s rows=%d elapsed_ms=%.1f",
                 sheet_id, len(result), (time.perf_counter() - started) * 1000)
    return result


# ---------- 轻量实体查询（仅 ID / 批量） ----------
def get_entity_ids_by_layer(sheet_id: int, layer: str) -> list[int]:
    """只返回指定图层的实体 ID，不做 JSON 反序列化（O(N) 不可避免但常数小）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM entity WHERE sheet_id=? AND layer=?",
            (sheet_id, layer)).fetchall()
    return [r["id"] for r in rows]


def get_entity_ids_by_block(sheet_id: int, block_name: str) -> list[int]:
    """只返回指定块名的实体 ID"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM entity WHERE sheet_id=? AND block_name=?",
            (sheet_id, block_name)).fetchall()
    return [r["id"] for r in rows]


def get_entities_by_ids(sheet_id: int, entity_ids: list[int]) -> list:
    """批量获取实体（单次查询替代 N 次 get_entity）"""
    if not entity_ids:
        return []
    # SQLite 参数占位符上限约 999，超过时分批
    out = []
    for i in range(0, len(entity_ids), 900):
        chunk = entity_ids[i:i+900]
        placeholders = ",".join("?" * len(chunk))
        with get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM entity WHERE sheet_id=? AND id IN ({placeholders})",
                [sheet_id] + chunk).fetchall()
        for r in rows:
            e = Entity(**{k: r[k] for k in r.keys() if k not in ("bbox", "color")})
            e.bbox = tuple(json.loads(r["bbox"])) if r["bbox"] else (0, 0, 0, 0)
            e.color = tuple(json.loads(r["color"])) if r["color"] else (255, 255, 255)
            out.append(e)
    return out


# ---------- BOQ 条目 ----------
def replace_boq_items(project_id: int, items: list) -> None:
    """整段替换 BOQ 条目（会删除旧条目 + 关联 mapping）"""
    with get_conn() as conn:
        conn.execute("DELETE FROM boq_item WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM mapping WHERE boq_item_id NOT IN (SELECT id FROM boq_item WHERE project_id=?)", (project_id,))
        conn.executemany(
            "INSERT INTO boq_item(project_id, row_index, code, description, unit, original_qty, rule_type, scale_factor, measured_qty) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            [(project_id, it.row_index, it.code, it.description, it.unit, it.original_qty,
              it.rule_type, it.scale_factor, getattr(it, "measured_qty", 0) or 0) for it in items])
    _invalidate_boq_embedding(project_id)


def reparse_boq(project_id: int) -> dict:
    """对已入库 BOQ 行做合同段落过滤 + 列位号自愈（仅修复，不删真条目）。

    返回 {"removed": N, "fixed_cols": N}。
    """
    import re
    CONTRACT_CUES = ("Contractor", "Quantities are taken", "Qty remaining",
                     "Material status", "Brand", "Item descriptions",
                     "Rates are to include", "Overhead, profit",
                     "design drawings form part of this Bill")
    HEADER_CODES = {"item", "no", "code", "section", "description",
                    "rate usd", "amount usd"}
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, code, description, unit FROM boq_item WHERE project_id=? ORDER BY id",
            (project_id,)).fetchall()
        removed = fixed = 0
        for r in rows:
            code = (r["code"] or "").strip()
            desc = (r["description"] or "").strip()
            unit = (r["unit"] or "").strip()
            # 0) 表头行（Excel 表头被识别为 code 列）
            if code.lower() in HEADER_CODES:
                conn.execute("DELETE FROM boq_item WHERE id=?", (r["id"],))
                conn.execute("DELETE FROM mapping WHERE boq_item_id=?", (r["id"],))
                removed += 1
                continue
            # 0b) 章节标题行（无 unit，仅 description 是大章节名）
            if not unit and not desc and code and "," in code and len(code) > 40:
                conn.execute("DELETE FROM boq_item WHERE id=?", (r["id"],))
                conn.execute("DELETE FROM mapping WHERE boq_item_id=?", (r["id"],))
                removed += 1
                continue
            # 0c) 仅 code 是大段英文/中文（疑似章节大标题），且无 unit/desc
            #     启发式：code 全字母空格或中文，空 ≥3 个单词，且不含型号字符 - . _ \d{4,}
            if not unit and code and len(code) >= 10:
                if re.search(r"[a-zA-Z]{2,}\s[a-zA-Z]", code) and not re.search(r"-\d", code):
                    conn.execute("DELETE FROM boq_item WHERE id=?", (r["id"],))
                    conn.execute("DELETE FROM mapping WHERE boq_item_id=?", (r["id"],))
                    removed += 1
                    continue
            # 1) 删除合同声明段落（"1. The Contractor..." 这种长串）
            full = " ".join(filter(None, [code, desc, unit]))
            if full and len(full) >= 100 and any(c in full for c in CONTRACT_CUES):
                conn.execute("DELETE FROM boq_item WHERE id=?", (r["id"],))
                conn.execute(
                    "DELETE FROM mapping WHERE boq_item_id=?",
                    (r["id"],))
                removed += 1
                continue
            # 2) 列位号形态自愈：desc 短且 unit 含大写型号
            if unit and desc and len(desc) < 30 and re.search(r"[A-Z0-9._-]{4,}", unit):
                conn.execute(
                    "UPDATE boq_item SET description=?, unit=? WHERE id=?",
                    (unit, desc, r["id"]))
                fixed += 1
        conn.commit()
    if removed or fixed:
        _invalidate_boq_embedding(project_id)
    return {"removed": removed, "fixed_cols": fixed}


def append_boq_items(project_id: int, items: list) -> int:
    """追加 BOQ 条目（不删除现有，已有 mapping 的 id 保持稳定）。

    Returns: 追加条数
    """
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO boq_item(project_id, row_index, code, description, unit, original_qty, rule_type, scale_factor, measured_qty) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            [(project_id, it.row_index, it.code, it.description, it.unit, it.original_qty,
              it.rule_type, it.scale_factor, getattr(it, "measured_qty", 0) or 0) for it in items])
    _invalidate_boq_embedding(project_id)
    return len(items)


def _invalidate_boq_embedding(project_id: int) -> None:
    """BOQ 变更后使 embedding 向量缓存失效（延迟导入避免循环依赖）。"""
    try:
        from .binding.embedding_matcher import invalidate_embedding_cache
        invalidate_embedding_cache(project_id)
    except Exception:
        pass


def get_boq_items(project_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM boq_item WHERE project_id=? ORDER BY row_index", (project_id,)).fetchall()
    return [BoqItem(**dict(r)) for r in rows]


def update_boq_item(item_id: int, rule_type: str = None, scale_factor: float = None,
                    unit: str = None, measured_qty: float = None) -> None:
    sets, args = [], []
    if rule_type is not None:
        sets.append("rule_type=?"); args.append(rule_type)
    if scale_factor is not None:
        sets.append("scale_factor=?"); args.append(scale_factor)
    if unit is not None:
        sets.append("unit=?"); args.append(unit)
    if measured_qty is not None:
        sets.append("measured_qty=?"); args.append(measured_qty)
    if not sets:
        return
    args.append(item_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE boq_item SET {', '.join(sets)} WHERE id=?", args)


# ---------- 映射 ----------
def add_mapping(boq_item_id: int, sheet_id: int, mode: str,
                entity_id: int = None, layer_name: str = "", block_name: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO mapping(boq_item_id, sheet_id, mode, entity_id, layer_name, block_name, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (boq_item_id, sheet_id, mode, entity_id, layer_name, block_name, _now()))
        return cur.lastrowid


def entity_mapped(sheet_id: int, entity_id: int) -> bool:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT 1 FROM mapping WHERE sheet_id=? AND entity_id=? LIMIT 1", (sheet_id, entity_id)).fetchone()
    return r is not None


def get_mappings(boq_item_id: int = None, sheet_id: int = None) -> list:
    sql = "SELECT * FROM mapping"
    args = []
    conds = []
    if boq_item_id is not None:
        conds.append("boq_item_id=?"); args.append(boq_item_id)
    if sheet_id is not None:
        conds.append("sheet_id=?"); args.append(sheet_id)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [Mapping(**dict(r)) for r in rows]


def delete_mapping(mid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mapping WHERE id=?", (mid,))


def summarize_layers(project_id: int) -> list:
    """汇总该项目所有图层：实体数/块种类数/块名样本。

    Returns:
        [{'layer_name', 'entity_count', 'block_count', 'block_samples': [...]}]
        按 entity_count 降序。

    v3 任务二十九后续：e zdwg ANSI_1254 DWG 读出的乱码 layer 走
    fix_garbled_layer_name 归一化为 `__garbled_<hash>__`，便于聚合（相同
    乱码字符串在不同图纸会被 hash 到同一 key，候选生成也能去重）。
    """
    # 延迟 import 避免循环依赖（cad.reader 依赖 models）
    from .cad.reader import fix_garbled_layer_name
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT layer, dxf_type, block_name
            FROM entity
            WHERE sheet_id IN (SELECT id FROM sheet WHERE project_id=?)
            """,
            (project_id,)).fetchall()
    agg: dict = {}
    for r in rows:
        raw_layer = r["layer"] or ""
        layer = fix_garbled_layer_name(raw_layer)   # 乱码归一化
        agg.setdefault(layer, {"entity_count": 0, "blocks": set()})
        agg[layer]["entity_count"] += 1
        if r["block_name"]:
            agg[layer]["blocks"].add(r["block_name"])
    out = []
    for layer, v in agg.items():
        samples = sorted(v["blocks"])[:3] if v["blocks"] else []
        out.append({
            "layer_name": layer,
            "entity_count": v["entity_count"],
            "block_count": len(v["blocks"]),
            "block_samples": samples,
        })
    out.sort(key=lambda x: -x["entity_count"])
    return out


def clear_mappings_for_item(boq_item_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mapping WHERE boq_item_id=?", (boq_item_id,))


# ---------- 主要材料表统计（项目级） ----------
# 线性实体类型（与工程/classifier.LINEAR_TYPES 对齐，聚合 SQL 复用）
_LINEAR_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE")
# 导线层关键词（layer 名含任一即视为导线层；大小写不敏感）
WIRE_LAYER_KEYWORDS = ("LINE", "WIRE", "CABLE", "CONDUIT", "KABLO", "TRAY", "线", "导线")


def summarize_materials(project_id: int,
                        wire_keywords: tuple = WIRE_LAYER_KEYWORDS) -> dict:
    """项目级材料汇总：设备（按块计数）+ 导线（按图层长度）。

    统计口径（方案 A 定稿）：
    - 范围：项目内全部图纸（跨图累加），长度已 × sheet.scale（图纸比例）
    - 设备：只按 INSERT 块名计数（用户口径：设备只按块计数）
    - 导线：图层 = linear 桶（项目配置）∪ 图层名含关键词（默认 "line" 等）
      → Σ entity.length × scale；**按实际长度显示，不自动换算单位**，
        换算由 UI/报表的人工换算率提醒承担

    Args:
        project_id: 项目 id
        wire_keywords: 导线层名关键词元组/列表
    Returns:
        {
          "devices": [ {block_name, qty, sheet_count, layer} ... ]  按 qty 降序
          "wires":   [ {layer, entity_count, length, sheet_count} ... ] 按 length 降序
        }
    """
    sheet_ids = [s.id for s in get_sheets(project_id)]
    if not sheet_ids:
        return {"devices": [], "wires": []}
    marks = ",".join("?" for _ in sheet_ids)
    args = list(sheet_ids)

    # ---- 设备：按块名计数（INSERT 实体） ----
    devices = []
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT block_name,
                   COUNT(*) AS qty,
                   COUNT(DISTINCT sheet_id) AS sheet_count,
                   MIN(layer) AS layer
            FROM entity
            WHERE sheet_id IN ({marks}) AND dxf_type='INSERT' AND block_name<>''
            GROUP BY block_name
            ORDER BY qty DESC, block_name
            """,
            args).fetchall()
    for r in rows:
        devices.append({
            "block_name": r["block_name"],
            "qty": r["qty"],
            "sheet_count": r["sheet_count"],
            "layer": r["layer"] or "",
            "spec": "",          # 由调用方补全（block_legend / 规格推断）
        })

    # ---- 导线：linear 桶 ∪ 层名关键词，Σ length×scale ----
    cfg = get_project_config(project_id)
    linear_layers = [l for l in cfg.get("layer_rules", {}).get("linear", []) if l]
    kw_upper = tuple(str(k).upper() for k in (wire_keywords or ()))
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT e.layer,
                   COUNT(*) AS entity_count,
                   COUNT(DISTINCT e.sheet_id) AS sheet_count,
                   SUM(ROUND(e.length * s.scale, 4)) AS length_raw
            FROM entity e
            JOIN sheet s ON s.id = e.sheet_id
            WHERE e.sheet_id IN ({marks})
              AND e.dxf_type IN ('LINE','LWPOLYLINE','POLYLINE','ARC','SPLINE')
            GROUP BY e.layer
            """,
            args).fetchall()
    linear_upper = {str(l).upper() for l in linear_layers}
    wires = []
    seen_layers = set()
    for r in rows:
        layer = r["layer"] or ""
        upper = layer.upper()
        in_bucket = upper in linear_upper
        in_kw = any(k and k in upper for k in kw_upper)
        if not (in_bucket or in_kw):
            continue
        if layer in seen_layers:
            continue
        seen_layers.add(layer)
        wires.append({
            "layer_name": layer,
            "entity_count": r["entity_count"],
            "sheet_count": r["sheet_count"],
            "length_raw": round(r["length_raw"] or 0.0, 4),
        })
    wires.sort(key=lambda x: -x["length_raw"])
    return {"devices": devices, "wires": wires}


# ---------- 块图例标定（按项目） ----------
def collect_blocks(project_id: int, sheet_id: int | None = None) -> list:
    """聚合块引用，返回 [(block_name, total_count, sheet_count)]。

    - sheet_id=None：聚合该项目下所有图纸（跨图纸按块名求和）
    - sheet_id 给定：只聚合该单张图纸实际出现的块（sheet_count 恒为 1）
    """
    if sheet_id is not None:
        rows = distinct_blocks(sheet_id)
        out = [(b, c, 1) for b, c in rows]
        return sorted(out, key=lambda x: (x[0].lower(), x[0]))
    sheets = get_sheets(project_id)
    agg: dict = {}
    sheet_hit: dict = {}
    for s in sheets:
        rows = distinct_blocks(s.id)
        for bname, cnt in rows:
            agg[bname] = agg.get(bname, 0) + cnt
            sheet_hit[bname] = sheet_hit.get(bname, 0) + 1
    out = [(b, agg[b], sheet_hit[b]) for b in agg]
    return sorted(out, key=lambda x: (x[0].lower(), x[0]))


def get_block_legend(project_id: int) -> list:
    """返回该项目的图例标定列表（list[dict]）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM block_legend WHERE project_id=? ORDER BY block_name",
            (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_block_legend_map(project_id: int) -> dict:
    """返回 {block_name: dict} 便捷映射（接管算量用）"""
    return {r["block_name"]: r for r in get_block_legend(project_id)}


def save_block_legend(row: dict) -> None:
    """整行保存一条图例（INSERT OR REPLACE，靠唯一索引去重）"""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO block_legend"
            "(project_id, block_name, category, device_type, spec, unit, count_rule, "
            " confirmed, source, note, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (row["project_id"], row["block_name"],
             row.get("category", ""), row.get("device_type", ""),
             row.get("spec", ""), row.get("unit", "个"),
             row.get("count_rule", "count"),
             int(bool(row.get("confirmed", 0))),
             row.get("source", "manual"), row.get("note", ""),
             row.get("created_at") or _now()))


def set_block_confirmed(project_id: int, block_name: str, confirmed: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE block_legend SET confirmed=? WHERE project_id=? AND block_name=?",
            (int(bool(confirmed)), project_id, block_name))


def delete_block_legend(project_id: int, block_name: str = None) -> None:
    with get_conn() as conn:
        if block_name is None:
            conn.execute("DELETE FROM block_legend WHERE project_id=?", (project_id,))
        else:
            conn.execute(
                "DELETE FROM block_legend WHERE project_id=? AND block_name=?",
                (project_id, block_name))


# ===========================================================================
# V2：工程对象（engineering_object）
# ===========================================================================
def create_engineering_object(project_id: int, sheet_id: int = 0, object_type: str = "",
                              discipline: str = "", system: str = "", subsystem: str = "",
                              block_name: str = "", layer_name: str = "", tag: str = "",
                              specification: str = "", material: str = "", unit: str = "",
                              quantity_rule: str = "count", confidence: float = 0.0,
                              source: str = "", entity_ids: list = None) -> int:
    """新建工程对象，返回 id。entity_ids 为溯源锚点（实体 id 列表，JSON 存储）"""
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO engineering_object"
            "(project_id, sheet_id, object_type, discipline, system, subsystem, block_name, "
            " layer_name, tag, specification, material, unit, quantity_rule, confidence, "
            " source, entity_ids, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_id, sheet_id, object_type, discipline, system, subsystem, block_name,
             layer_name, tag, specification, material, unit, quantity_rule, confidence,
             source, json.dumps(entity_ids or []), now, now))
        return cur.lastrowid


def _eo_from_row(r) -> EngineeringObject:
    e = EngineeringObject(**{k: r[k] for k in r.keys() if k != "entity_ids"})
    try:
        e.entity_ids = json.loads(r["entity_ids"]) if r["entity_ids"] else []
    except Exception:
        e.entity_ids = []
    return e


def get_engineering_objects(project_id: int, object_type: str = None,
                            block_name: str = None, layer_name: str = None) -> list:
    sql = "SELECT * FROM engineering_object WHERE project_id=?"
    args = [project_id]
    if object_type:
        sql += " AND object_type=?"; args.append(object_type)
    if block_name:
        sql += " AND block_name=?"; args.append(block_name)
    if layer_name:
        sql += " AND layer_name=?"; args.append(layer_name)
    sql += " ORDER BY COALESCE(NULLIF(block_name,''), NULLIF(layer_name,'')) COLLATE NOCASE ASC, id"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_eo_from_row(r) for r in rows]


def get_engineering_object(eoid: int) -> EngineeringObject | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM engineering_object WHERE id=?", (eoid,)).fetchone()
    return _eo_from_row(r) if r else None


def update_engineering_object(eoid: int, **fields) -> None:
    """白名单字段更新；entity_ids 传 list 自动 JSON 序列化"""
    allowed = {"object_type", "discipline", "system", "subsystem", "block_name", "layer_name",
               "tag", "specification", "material", "unit", "quantity_rule",
               "confidence", "source"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=?")
        args.append(v)
    if not sets:
        return
    sets.append("updated_at=?")
    args.append(_now())
    args.append(eoid)
    with get_conn() as conn:
        conn.execute(f"UPDATE engineering_object SET {', '.join(sets)} WHERE id=?", args)


def set_eo_entity_ids(eoid: int, entity_ids: list) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE engineering_object SET entity_ids=?, updated_at=? WHERE id=?",
                     (json.dumps(entity_ids or []), _now(), eoid))


def delete_engineering_object(eoid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM engineering_object WHERE id=?", (eoid,))


def delete_eo_for_sheet(sheet_id: int) -> None:
    """删除某图纸的全部工程对象（提取前调用，保证幂等重建）"""
    with get_conn() as conn:
        conn.execute("DELETE FROM engineering_object WHERE sheet_id=?", (sheet_id,))


# ===========================================================================
# 图例符号知识库 symbol_library（T3/T6：人工标定沉淀 + 语义分类复用）
# ===========================================================================
def _symbol_from_row(r) -> SymbolLibrary | None:
    if not r:
        return None
    return SymbolLibrary(
        id=r[0], project_id=r[1], block_name=r[2], layer_name=r[3],
        discipline=r[4], system=r[5], spec=r[6], unit=r[7],
        quantity_rule=r[8], source=r[9], confirmed_by=r[10],
        confirmed_at=r[11], updated_at=r[12],
    )


def get_symbol(project_id: int, block_name: str = "", layer_name: str = "") -> SymbolLibrary | None:
    """按 (project_id, block_name, layer_name) 精确查知识库条目"""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM symbol_library WHERE project_id=? AND block_name=? AND layer_name=?",
            (project_id, block_name or "", layer_name or "")).fetchone()
    return _symbol_from_row(r)


def get_symbols(project_id: int, discipline: str = "", system: str = "") -> list:
    """列出某项目符号库；可按 discipline/system 过滤"""
    sql = "SELECT * FROM symbol_library WHERE project_id=?"
    args = [project_id]
    if discipline:
        sql += " AND discipline=?"
        args.append(discipline)
    if system:
        sql += " AND system=?"
        args.append(system)
    sql += " ORDER BY updated_at DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_symbol_from_row(r) for r in rows]


def upsert_symbol(project_id: int, block_name: str = "", layer_name: str = "",
                  discipline: str = "", system: str = "", spec: str = "",
                  unit: str = "", quantity_rule: str = "", source: str = "manual",
                  confirmed_by: str = "") -> int:
    """写入/更新符号库条目（键=project_id+block_name+layer_name）。

    已存在则合并更新非空字段；返回条目 id。
    """
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO symbol_library
               (project_id, block_name, layer_name, discipline, system, spec,
                unit, quantity_rule, source, confirmed_by, confirmed_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id, block_name, layer_name) DO UPDATE SET
                 discipline=COALESCE(NULLIF(excluded.discipline,''), symbol_library.discipline),
                 system=COALESCE(NULLIF(excluded.system,''), symbol_library.system),
                 spec=COALESCE(NULLIF(excluded.spec,''), symbol_library.spec),
                 unit=COALESCE(NULLIF(excluded.unit,''), symbol_library.unit),
                 quantity_rule=COALESCE(NULLIF(excluded.quantity_rule,''), symbol_library.quantity_rule),
                 source=excluded.source,
                 confirmed_by=COALESCE(NULLIF(excluded.confirmed_by,''), symbol_library.confirmed_by),
                 confirmed_at=COALESCE(excluded.confirmed_at, symbol_library.confirmed_at),
                 updated_at=excluded.updated_at
            """,
            (project_id, block_name or "", layer_name or "", discipline or "", system or "",
             spec or "", unit or "", quantity_rule or "", source, confirmed_by or "",
             now if confirmed_by else None, now))
        return cur.lastrowid


def delete_symbol(symbol_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM symbol_library WHERE id=?", (symbol_id,))


# ===========================================================================
# V2：绑定候选（binding_candidate）—— AI/规则只写这里，人工确认才进 mapping
# ===========================================================================
def create_binding_candidate(project_id: int, engineering_object_id: int, boq_item_id: int,
                             method: str = "LLM", score: float = 0.0, confidence: float = 0.0,
                             reason: str = "", model: str = "", model_version: str = "",
                             prompt_version: str = "", llm_run_id: int = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO binding_candidate"
            "(project_id, engineering_object_id, boq_item_id, method, score, confidence, "
            " reason, model, model_version, prompt_version, llm_run_id, status, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_id, engineering_object_id, boq_item_id, method, score, confidence,
             reason, model, model_version, prompt_version, llm_run_id, "PENDING", _now()))
        return cur.lastrowid


def get_candidate(cid: int) -> BindingCandidate | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM binding_candidate WHERE id=?", (cid,)).fetchone()
    return BindingCandidate(**dict(r)) if r else None


def get_candidates(project_id: int, status: str = None,
                   engineering_object_id: int = None) -> list:
    sql = "SELECT * FROM binding_candidate WHERE project_id=?"
    args = [project_id]
    if status:
        sql += " AND status=?"; args.append(status)
    if engineering_object_id is not None:
        sql += " AND engineering_object_id=?"; args.append(engineering_object_id)
    sql += " ORDER BY confidence DESC, score DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [BindingCandidate(**dict(r)) for r in rows]


def get_pending_candidates(project_id: int, limit: int = 200) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM binding_candidate WHERE project_id=? AND status='PENDING' "
            "ORDER BY confidence DESC, score DESC LIMIT ?", (project_id, limit)).fetchall()
    return [BindingCandidate(**dict(r)) for r in rows]


def candidate_status_summary(project_id: int) -> dict:
    """批量预取候选状态节点：返回 {(engineering_object_id, status): count}。

    供 UI 一次性查询所有工程对象的绑定状态，替代 N+1 循环（性能优化 P0-b）。
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT engineering_object_id, status, count(*) AS n "
            "FROM binding_candidate WHERE project_id=? "
            "GROUP BY engineering_object_id, status",
            (project_id,)).fetchall()
    return {(r["engineering_object_id"], r["status"]): r["n"] for r in rows}


def count_candidates(project_id: int, status: str = None) -> int:
    """候选计数（轻量，不取行数据；替代全量拉取后 len()）。"""
    sql = "SELECT count(*) FROM binding_candidate WHERE project_id=?"
    args = [project_id]
    if status:
        sql += " AND status=?"
        args.append(status)
    with get_conn() as conn:
        return conn.execute(sql, args).fetchone()[0]


def sheet_candidate_stats(project_id: int) -> dict:
    """图纸级 AI 进度统计（图纸列表状态徽标用）。

    Returns:
        {sheet_id: {"objects": n, "pending": n, "accepted": n}}
        无工程对象的图纸不出现在结果里。
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT eo.sheet_id AS sid,"
            "       count(DISTINCT eo.id) AS objects,"
            "       sum(CASE WHEN c.status='PENDING' THEN 1 ELSE 0 END)  AS pending,"
            "       sum(CASE WHEN c.status='ACCEPTED' THEN 1 ELSE 0 END) AS accepted "
            "FROM engineering_object eo "
            "LEFT JOIN binding_candidate c ON c.engineering_object_id = eo.id "
            "WHERE eo.project_id=? GROUP BY eo.sheet_id",
            (project_id,)).fetchall()
    return {r["sid"]: {"objects": r["objects"] or 0,
                       "pending": r["pending"] or 0,
                       "accepted": r["accepted"] or 0} for r in rows}


def update_candidate_status(cid: int, status: str) -> None:
    """status ∈ PENDING / ACCEPTED / REJECTED / SUPERSEDED"""
    with get_conn() as conn:
        conn.execute("UPDATE binding_candidate SET status=? WHERE id=?", (status, cid))


def supersede_candidates(engineering_object_id: int, exclude_cid: int = None) -> None:
    """同一工程对象的旧 PENDING 候选置 SUPERSEDED（新候选生成时调用）"""
    with get_conn() as conn:
        if exclude_cid is None:
            conn.execute(
                "UPDATE binding_candidate SET status='SUPERSEDED' "
                "WHERE engineering_object_id=? AND status='PENDING'",
                (engineering_object_id,))
        else:
            conn.execute(
                "UPDATE binding_candidate SET status='SUPERSEDED' "
                "WHERE engineering_object_id=? AND status='PENDING' AND id<>?",
                (engineering_object_id, exclude_cid))


def supersede_candidates_by_anchor(project_id: int, block_name: str = "",
                                   layer_name: str = "", exclude_cid: int = None) -> int:
    """跨图纸 supersede（2026-08-28 绑定增强 2.3.1）：同名块/同图层全部 EO 的 PENDING
    候选一次性置 SUPERSEDED。

    确认某块绑定到 BOQ 后，同一 block_name 出现在其他图纸的 EO 候选也该消失——
    一图块对应一个 BOQ 子项（跨图纸同名的也要消失）。
    若同时给 block_name 与 layer_name，命中任一即 supersede（并集）。

    Returns:
        受影响候选数
    """
    conds, args = [], []
    if block_name:
        conds.append("block_name=?"); args.append(block_name)
    if layer_name:
        conds.append("layer_name=?"); args.append(layer_name)
    if not conds:
        return 0
    where = " OR ".join(conds)
    sql = (
        "UPDATE binding_candidate SET status='SUPERSEDED' "
        "WHERE project_id=? AND status='PENDING' "
        "AND engineering_object_id IN ("
        "  SELECT id FROM engineering_object WHERE project_id=? AND (" + where + "))"
    )
    params = [project_id, project_id] + args
    if exclude_cid is not None:
        sql += " AND id<>?"
        params.append(exclude_cid)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


def delete_candidates_for_item(boq_item_id: int) -> None:
    """BOQ 条目被替换时清掉其候选"""
    with get_conn() as conn:
        conn.execute("DELETE FROM binding_candidate WHERE boq_item_id=?", (boq_item_id,))


# ===========================================================================
# V2：LLM 审计（llm_run）
# ===========================================================================
def create_llm_run(project_id: int, task_type: str, model: str = "", model_version: str = "",
                   prompt_version: str = "", temperature: float = 0.0, input_hash: str = "",
                   output_hash: str = "", duration_ms: int = 0, token_input: int = 0,
                   token_output: int = 0, status: str = "ok", error: str = "",
                   input_text: str = "", output_text: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO llm_run"
            "(project_id, task_type, model, model_version, prompt_version, temperature, "
            " input_hash, output_hash, duration_ms, token_input, token_output, status, "
            " error, created_at, input_text, output_text) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_id, task_type, model, model_version, prompt_version, temperature,
             input_hash, output_hash, duration_ms, token_input, token_output, status,
             error, _now(), input_text, output_text))
        return cur.lastrowid


def update_llm_run(run_id: int, **fields) -> None:
    allowed = {"output_hash", "duration_ms", "token_input", "token_output", "status", "error"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=?"); args.append(v)
    if not sets:
        return
    args.append(run_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE llm_run SET {', '.join(sets)} WHERE id=?", args)


def get_llm_run(run_id: int) -> LlmRun | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM llm_run WHERE id=?", (run_id,)).fetchone()
    return LlmRun(**dict(r)) if r else None


def list_llm_runs(project_id: int, limit: int = 50) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_run WHERE project_id=? ORDER BY id DESC LIMIT ?",
            (project_id, limit)).fetchall()
    return [LlmRun(**dict(r)) for r in rows]


def list_recent_llm_runs(limit: int = 500) -> list:
    """跨全部项目取最近 limit 次 LLM 调用（按时间倒序）。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_run ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [LlmRun(**dict(r)) for r in rows]


def get_llm_run_stats(limit: int = 500) -> dict:
    """跨全部项目统计最近 limit 次 LLM 调用的 token 用量。

    Returns:
        {"count": int, "token_input": int, "token_output": int,
         "ok": int, "error": int, "retried": int}
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT token_input, token_output, status FROM llm_run "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    count = len(rows)
    token_input = sum(r["token_input"] or 0 for r in rows)
    token_output = sum(r["token_output"] or 0 for r in rows)
    status_count = {"ok": 0, "error": 0, "retried": 0}
    for r in rows:
        st = (r["status"] or "ok").lower()
        status_count[st] = status_count.get(st, 0) + 1
    return {"count": count, "token_input": token_input, "token_output": token_output,
            "ok": status_count["ok"], "error": status_count["error"],
            "retried": status_count["retried"]}
