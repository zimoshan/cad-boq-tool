"""v1.0 §17 negative_samples 表（alembic 0005，2026-09-06）

rejected_bindings 自动写为负样本（v1.0 §17 人工确认数据必须形成正负样本）
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "negative_sample",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engineering_object_id", sa.Integer, nullable=False),
        sa.Column("boq_item_id", sa.Integer, sa.ForeignKey("boq_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_name", sa.Text, server_default="", nullable=False),
        sa.Column("layer_name", sa.Text, server_default="", nullable=False),
        sa.Column("reason", sa.Text, server_default="", nullable=False),
        sa.Column("confidence_at_reject", sa.Float, server_default="0", nullable=False),
        sa.Column("method", sa.String(16), server_default="LLM", nullable=False),
        sa.Column("rejected_by", sa.String(64), server_default="sysadmin", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_neg_project", "negative_sample", ["project_id"])
    op.create_index("idx_neg_eo_boq", "negative_sample", ["engineering_object_id", "boq_item_id"])
    op.create_index("idx_neg_block", "negative_sample", ["block_name"])


def downgrade() -> None:
    op.drop_index("idx_neg_block", "negative_sample")
    op.drop_index("idx_neg_eo_boq", "negative_sample")
    op.drop_index("idx_neg_project", "negative_sample")
    op.drop_table("negative_sample")
