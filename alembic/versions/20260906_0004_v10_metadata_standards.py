"""v1.0 §25/§26 schema 扩展（alembic 0004，2026-09-06）

P0-35（v1.0 适配）：
- §25 图纸元数据 5 字段：level / zone / revision / status / design_stage
- §26 CAD Standard Profile：拆 5 规则文件
  * project_config 加 cad_standard_profile_path 字段（指向 cad_standard/ 目录）

注：cad_standard 5 规则 JSON 文件本身在 P0-35 commit 2 创建
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P0-35 §25：图纸元数据 5 字段
    op.add_column("sheet", sa.Column("level", sa.String(32), server_default="", nullable=False))
    op.add_column("sheet", sa.Column("zone", sa.String(32), server_default="", nullable=False))
    op.add_column("sheet", sa.Column("revision", sa.String(16), server_default="", nullable=False))
    op.add_column("sheet", sa.Column("status", sa.String(32), server_default="ready", nullable=False))
    op.add_column("sheet", sa.Column("design_stage", sa.String(32), server_default="", nullable=False))
    op.create_index("idx_sheet_status", "sheet", ["status"])
    op.create_index("idx_sheet_revision", "sheet", ["revision"])

    # P0-35 §26：CAD Standard Profile 路径
    op.add_column("project_config", sa.Column("cad_standard_profile_path", sa.Text, server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("project_config", "cad_standard_profile_path")
    op.drop_index("idx_sheet_revision", "sheet")
    op.drop_index("idx_sheet_status", "sheet")
    op.drop_column("sheet", "design_stage")
    op.drop_column("sheet", "status")
    op.drop_column("sheet", "revision")
    op.drop_column("sheet", "zone")
    op.drop_column("sheet", "level")
