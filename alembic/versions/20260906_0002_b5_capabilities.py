"""B5 6 段能力 alembic 迁移（v2.0 §2.5 / §5.3，2026-09-06）

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06

新增：
- entity.units（VARCHAR(16)）— B5 S3 单位标定
- sheet.drawing_type（VARCHAR(32)）— B5 S4 图纸类型
- sheet.units（VARCHAR(16)）— B5 S3 同上
- cross_sheet_dedup 表 — B5 S5 跨图去重
- writeback_audit 表 — B5 S7 保真回写审计
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # B5 S3 entity.units（per-entity 单位覆盖；缺省 NULL 用 sheet.units）
    op.add_column("entity", sa.Column("units", sa.String(16), nullable=True))
    op.create_index("idx_entity_units", "entity", ["units"])

    # B5 S3 sheet.units + S4 drawing_type
    op.add_column("sheet", sa.Column("units", sa.String(16), server_default="", nullable=False))
    op.add_column("sheet", sa.Column("drawing_type", sa.String(32), server_default="plan", nullable=False))
    op.create_index("idx_sheet_drawing_type", "sheet", ["drawing_type"])

    # B5 S5 cross_sheet_dedup 表
    op.create_table(
        "cross_sheet_dedup",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_name", sa.Text, nullable=False),
        sa.Column("sheet_ids", sa.Text, server_default="[]", nullable=False),  # JSON list
        sa.Column("merged_entity_ids", sa.Text, server_default="[]", nullable=False),  # JSON list
        sa.Column("merged_eo_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("canonical_eo_id", sa.Integer),
        sa.Column("dedup_method", sa.Text, server_default="bbox_overlap", nullable=False),
        sa.Column("confidence", sa.Float, server_default="0", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_csd_project", "cross_sheet_dedup", ["project_id"])
    op.create_index("idx_csd_block", "cross_sheet_dedup", ["project_id", "block_name"])

    # B5 S7 writeback_audit 表
    op.create_table(
        "writeback_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("boq_item_id", sa.Integer, sa.ForeignKey("boq_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_qty", sa.Float, server_default="0", nullable=False),
        sa.Column("measured_qty", sa.Float, server_default="0", nullable=False),
        sa.Column("takability", sa.Text, server_default="MEASURABLE", nullable=False),
        sa.Column("file_sha256", sa.Text, server_default="", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_wa_project", "writeback_audit", ["project_id"])
    op.create_index("idx_wa_item", "writeback_audit", ["boq_item_id"])
    op.create_index("idx_wa_takability", "writeback_audit", ["project_id", "takability"])


def downgrade() -> None:
    op.drop_index("idx_wa_takability", "writeback_audit")
    op.drop_index("idx_wa_item", "writeback_audit")
    op.drop_index("idx_wa_project", "writeback_audit")
    op.drop_table("writeback_audit")
    op.drop_index("idx_csd_block", "cross_sheet_dedup")
    op.drop_index("idx_csd_project", "cross_sheet_dedup")
    op.drop_table("cross_sheet_dedup")
    op.drop_index("idx_sheet_drawing_type", "sheet")
    op.drop_column("sheet", "drawing_type")
    op.drop_column("sheet", "units")
    op.drop_index("idx_entity_units", "entity")
    op.drop_column("entity", "units")
