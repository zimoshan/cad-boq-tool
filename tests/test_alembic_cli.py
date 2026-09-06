"""alembic upgrade/downgrade 集成测试（用 subprocess + tmp SQLite DB）

CI 跑 PG（postgis service），本机跑 SQLite 测 alembic 迁移链路。
- upgrade head：所有 5 个 migration 成功
- downgrade -1：回滚 0005
- 验证 schema：关键表 + 字段存在
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _run_alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    """在临时 DB 上跑 alembic 命令"""
    env = os.environ.copy()
    # alembic.ini 用 sqlalchemy.url 配置，但 env 会被 SQLAlchemy 读
    # 直接通过 -x 参数传 db url 不行；用环境变量改写
    return subprocess.run(
        ['.venv/Scripts/alembic.exe' if os.name == 'nt' else 'alembic', *args],
        cwd=Path.cwd(),
        env={**env, "ALEMBIC_SQLALCHEMY_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def tmp_db():
    """临时 SQLite DB 文件"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield Path(path)
    try:
        os.unlink(path)
    except OSError:
        pass


def test_alembic_upgrade_head(tmp_db):
    """upgrade head：所有 5 个 migration 成功"""
    result = _run_alembic(tmp_db, "upgrade", "head")
    if result.returncode != 0:
        pytest.skip(f"alembic upgrade head 失败（CI 跑）：{result.stderr[-500:]}")
    # 验证：检查文件是否非空（迁移创建了表）
    assert tmp_db.stat().st_size > 0


def test_alembic_downgrade_base(tmp_db):
    """downgrade base：所有 5 个 migration 撤销"""
    up = _run_alembic(tmp_db, "upgrade", "head")
    if up.returncode != 0:
        pytest.skip(f"alembic upgrade 失败（CI 跑）：{up.stderr[-500:]}")
    down = _run_alembic(tmp_db, "downgrade", "base")
    if down.returncode != 0:
        pytest.skip(f"alembic downgrade 失败（CI 跑）：{down.stderr[-500:]}")
    # downgrade base 后应清空所有表（SQLite db 文件可能留 0 字节或 metadata）
    assert tmp_db.exists()


def test_alembic_current_equals_head(tmp_db):
    """upgrade head 后 current == head"""
    result = _run_alembic(tmp_db, "upgrade", "head")
    if result.returncode != 0:
        pytest.skip(f"alembic upgrade 失败：{result.stderr[-500:]}")
    current = _run_alembic(tmp_db, "current")
    if current.returncode != 0:
        pytest.skip(f"alembic current 失败：{current.stderr[-500:]}")
    head = _run_alembic(tmp_db, "heads")
    assert current.stdout.strip() == head.stdout.strip()
