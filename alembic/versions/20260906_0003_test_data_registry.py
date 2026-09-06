"""P1-2 test_data_registry 表（alembic 0003，2026-09-06）

替代 Phase 0 JSON 文件存储（webapi/services/dataset.py）。

#3 决策：DWG/数据资产不自动入库，用户手动标记为测试数据后存此表。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_data_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("project_id", sa.Integer, nullable=False, index=True),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("data_type", sa.String(16), nullable=False),  # drawing / boq / json
        sa.Column("note", sa.Text, server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.String(64), server_default="sysadmin", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_tdr_project", "test_data_registry", ["project_id"])
    op.create_index("idx_tdr_active", "test_data_registry", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_tdr_active", "test_data_registry")
    op.drop_index("idx_tdr_project", "test_data_registry")
    op.drop_table("test_data_registry")
