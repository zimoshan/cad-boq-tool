"""llm_run 全文落库回归：prompt 分析优化依赖完整输入/输出文本。

- audit.log_llm_call 必须把 input_text/output_text 全文存进 llm_run
- hash 仍保留（去重/关联指纹）
- 旧库缺列时 _migrate 自动补 input_text/output_text
- run_llm_with_retry 的全文经 _audit_run 自动透传（含重试附错误提示后的 user）
"""
from __future__ import annotations

import pytest

from app.models import LlmRun


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    import app.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db._thread_local.conn = None
    db.init_db()
    yield db
    db._thread_local.conn = None


def test_log_llm_call_stores_full_texts(temp_db):
    from app.llm import audit
    pid = temp_db.create_project("t")   # llm_run.project_id 有外键约束
    rid = audit.log_llm_call(
        pid, "binding", "qwen2.5:7b", "binding-v3", 0.1,
        input_text="SYSTEM\nUSER 候选 BOQ...",
        output_text='{"selected_boq_id":"EL-L01","confidence":0.9}',
        duration_ms=1234, token_input=321, token_output=45)
    runs = temp_db.list_llm_runs(pid)
    assert len(runs) == 1
    r: LlmRun = runs[0]
    assert r.id == rid
    assert r.input_text.endswith("候选 BOQ...")
    assert r.output_text.startswith('{"selected_boq_id"')
    # hash 是全文 sha256 前 16 位，仍在
    assert r.input_hash and r.output_hash
    assert r.prompt_version == "binding-v3"


def test_migrate_adds_text_columns_on_old_db(temp_db, tmp_path):
    """旧库（无 input_text/output_text 列）连库后自动补列并可写入。"""
    import sqlite3
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.executescript("""
        CREATE TABLE llm_run (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            task_type TEXT DEFAULT '', model TEXT DEFAULT '', model_version TEXT DEFAULT '',
            prompt_version TEXT DEFAULT '', temperature REAL DEFAULT 0,
            input_hash TEXT DEFAULT '', output_hash TEXT DEFAULT '',
            duration_ms INTEGER DEFAULT 0, token_input INTEGER DEFAULT 0,
            token_output INTEGER DEFAULT 0, status TEXT DEFAULT 'ok',
            error TEXT DEFAULT '', created_at TEXT DEFAULT '');
    """)
    con.commit()
    con.close()

    import app.db as db
    # 新连接走 init_db → _migrate 补列
    db._thread_local.conn = None
    real_db_path = db.DB_PATH
    db.DB_PATH = old
    try:
        db._thread_local.conn = None
        db.init_db()
        cols = {r[1] for r in db.get_conn().execute("PRAGMA table_info(llm_run)").fetchall()}
        assert {"input_text", "output_text"} <= cols
        rid = db.create_llm_run(1, "binding", input_text="in", output_text="out")
        row = dict(next(iter(db.get_conn().execute(
            "SELECT * FROM llm_run WHERE id=?", (rid,)).fetchall())))
        assert row["input_text"] == "in" and row["output_text"] == "out"
    finally:
        db._thread_local.conn = None
        db.DB_PATH = real_db_path


def test_retry_passes_full_prompt_through(monkeypatch, tmp_path):
    """runner 重试路径：附错误提示后的 user 全文进入下一轮审计。"""
    from app.llm import runner as R

    calls = []

    class FakeBackend:
        model = "fake"

        def chat(self, system, user):
            calls.append(user)
            return {"content": "不是JSON", "tokens_in": 1, "tokens_out": 1}

    monkeypatch.setattr(R, "_resolve_runtime",
                        lambda t="binding": (type("C", (), {
                            "primary_backend": "custom", "primary_model": "fake",
                            "auto_fallback": False, "quality_threshold": 0.7,
                            "api_keys": {}, "custom_endpoints": {},
                            "ollama_host": "",
                        })(), None, 0.7))
    monkeypatch.setattr(R, "_resolve_backend", lambda *a, **k: FakeBackend())
    monkeypatch.setattr(R.audit, "log_llm_call", (
        lambda project_id, task_type, model, prompt_version, temperature,
        input_text, output_text, duration_ms, token_input, token_output,
        status="ok", error="":
        calls.append(("audit", status, input_text)) or len(calls)))

    res = R.run_llm_with_retry(1, "binding", "S", "U",
                               validator=lambda c: (_ for _ in ()).throw(
                                   ValueError("bad json")),
                               prompt_version="v-test", retries=1)
    assert not res["ok"] and len(calls) >= 2
    audited = [c for c in calls if isinstance(c, tuple)]
    # 每轮审计的 input 都带 system+user；重试轮 user 含上轮错误提示
    assert all("S" in c[2] for c in audited)
    assert any("上次输出未通过校验" in c[2] for c in audited[1:])
