"""initial schema: 12 业务表 + 4 RBAC 表 + PostGIS + v2.0 修正

Revision ID: 0001
Revises:
Create Date: 2026-09-06

v2.0 修正（来自 docs/CAD_BOQ_Web化_架构设计_v2.0.md §2）：
- B2: boq_item 加 section + bill_qty + installed_qty + qty_remaining + item_key
- B3: sheet.blocks_json 仍保留（外置实现在 Phase 0 P0-8，schema 暂不变）
- B4: entity 加 min_x/max_x/min_y/max_y + 几何索引（geometry PostGIS）

业务表（来自 app/db.py _SCHEMA，1:1 翻译 SQLite → PG）：
- project / sheet / entity / boq_item / mapping / block_legend
- engineering_object / llm_run / project_config / binding_candidate
- llm_settings / symbol_library

RBAC 表（来自 webapi/auth/models.py）：
- sys_user / sys_role / sys_user_role / sys_menu / sys_dict
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================================
    # 0. PostGIS 扩展（B4 空间查询基础）
    # =====================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # =====================================================================
    # 1. 业务表
    # =====================================================================

    # project
    op.create_table(
        "project",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
        sa.Column("boq_path", sa.Text, server_default="", nullable=False),
    )

    # sheet
    op.create_table(
        "sheet",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("src_path", sa.Text, server_default="", nullable=False),
        sa.Column("dxf_path", sa.Text, server_default="", nullable=False),
        sa.Column("status", sa.Text, server_default="ready", nullable=False),
        sa.Column("scale", sa.Float, server_default="1.0", nullable=False),
        sa.Column("entity_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("layer_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("blocks_json", sa.Text, server_default="", nullable=False),  # B3 暂保留，Phase 0 P0-8 外置
        sa.Column("is_base", sa.Integer, server_default="0", nullable=False),
    )
    op.create_index("idx_sheet_project", "sheet", ["project_id"])

    # entity（B4 加 min_x/max_x/min_y/max_y + 几何字段）
    op.create_table(
        "entity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sheet_id", sa.Integer, sa.ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False),
        sa.Column("handle", sa.Text, nullable=False),
        sa.Column("dxf_type", sa.Text, server_default="", nullable=False),
        sa.Column("layer", sa.Text, server_default="", nullable=False),
        sa.Column("block_name", sa.Text, server_default="", nullable=False),
        # 原 SQLite bbox TEXT(JSON)；PG 改为 4 列 + PostGIS geometry
        sa.Column("min_x", sa.Float),
        sa.Column("min_y", sa.Float),
        sa.Column("max_x", sa.Float),
        sa.Column("max_y", sa.Float),
        sa.Column("geometry", Geometry(geometry_type="POLYGON", srid=0, spatial_index=False), nullable=True),
        sa.Column("geom_json", sa.Text, server_default="", nullable=False),
        sa.Column("length", sa.Float, server_default="0", nullable=False),
        sa.Column("area", sa.Float, server_default="0", nullable=False),
        sa.Column("color", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_entity_sheet", "entity", ["sheet_id"])
    op.create_index("idx_entity_layer", "entity", ["sheet_id", "layer"])
    op.create_index("idx_entity_block", "entity", ["sheet_id", "block_name"])
    # B4 空间索引
    op.execute("CREATE INDEX idx_entity_bbox ON entity USING gist (geometry)")

    # boq_item（B2 加 section + bill_qty + installed_qty + qty_remaining + item_key）
    op.create_table(
        "boq_item",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_index", sa.Integer, server_default="0", nullable=False),
        sa.Column("section", sa.Text, server_default="", nullable=False),  # B2 新增
        sa.Column("item_key", sa.Text, server_default="", nullable=False),  # B2 新增（如 rNNN）
        sa.Column("code", sa.Text, server_default="", nullable=False),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("brand", sa.Text, server_default="", nullable=False),  # B2 新增
        sa.Column("unit", sa.Text, server_default="", nullable=False),
        sa.Column("bill_qty", sa.Float, server_default="0", nullable=False),  # B2 新增
        sa.Column("installed_qty", sa.Float, server_default="0", nullable=False),  # B2 新增
        sa.Column("qty_remaining", sa.Float, server_default="0", nullable=False),  # B2 新增
        sa.Column("original_qty", sa.Float, server_default="0", nullable=False),  # 兼容旧
        sa.Column("rule_type", sa.Text, server_default="length", nullable=False),
        sa.Column("scale_factor", sa.Float, server_default="1.0", nullable=False),
        sa.Column("mapped_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("measured_qty", sa.Float, server_default="0", nullable=False),
    )
    op.create_index("idx_boq_project", "boq_item", ["project_id"])
    op.create_index("idx_boq_item_key", "boq_item", ["project_id", "item_key"])

    # mapping
    op.create_table(
        "mapping",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("boq_item_id", sa.Integer, sa.ForeignKey("boq_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_id", sa.Integer, sa.ForeignKey("sheet.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.Text, server_default="entity", nullable=False),
        sa.Column("entity_id", sa.Integer),
        sa.Column("layer_name", sa.Text, server_default="", nullable=False),
        sa.Column("block_name", sa.Text, server_default="", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_mapping_item", "mapping", ["boq_item_id"])
    op.create_index("idx_mapping_entity", "mapping", ["entity_id"])

    # block_legend
    op.create_table(
        "block_legend",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_name", sa.Text, nullable=False),
        sa.Column("category", sa.Text, server_default="", nullable=False),
        sa.Column("device_type", sa.Text, server_default="", nullable=False),
        sa.Column("spec", sa.Text, server_default="", nullable=False),
        sa.Column("unit", sa.Text, server_default="个", nullable=False),
        sa.Column("count_rule", sa.Text, server_default="count", nullable=False),
        sa.Column("confirmed", sa.Integer, server_default="0", nullable=False),
        sa.Column("source", sa.Text, server_default="manual", nullable=False),
        sa.Column("note", sa.Text, server_default="", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_unique_constraint("uq_legend_proj_block", "block_legend", ["project_id", "block_name"])

    # engineering_object
    op.create_table(
        "engineering_object",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_id", sa.Integer, sa.ForeignKey("sheet.id", ondelete="CASCADE")),
        sa.Column("object_type", sa.Text, server_default="", nullable=False),
        sa.Column("discipline", sa.Text, server_default="", nullable=False),
        sa.Column("system", sa.Text, server_default="", nullable=False),
        sa.Column("subsystem", sa.Text, server_default="", nullable=False),
        sa.Column("block_name", sa.Text, server_default="", nullable=False),
        sa.Column("layer_name", sa.Text, server_default="", nullable=False),
        sa.Column("tag", sa.Text, server_default="", nullable=False),
        sa.Column("specification", sa.Text, server_default="", nullable=False),
        sa.Column("material", sa.Text, server_default="", nullable=False),
        sa.Column("unit", sa.Text, server_default="", nullable=False),
        sa.Column("quantity_rule", sa.Text, server_default="count", nullable=False),
        sa.Column("confidence", sa.Float, server_default="0", nullable=False),
        sa.Column("source", sa.Text, server_default="", nullable=False),
        sa.Column("entity_ids", sa.Text, server_default="", nullable=False),  # JSON list
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
        sa.Column("updated_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_eo_project", "engineering_object", ["project_id"])
    op.create_index("idx_eo_block", "engineering_object", ["project_id", "block_name"])
    op.create_index("idx_eo_layer", "engineering_object", ["project_id", "layer_name"])

    # llm_run
    op.create_table(
        "llm_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE")),
        sa.Column("task_type", sa.Text, server_default="", nullable=False),
        sa.Column("model", sa.Text, server_default="", nullable=False),
        sa.Column("model_version", sa.Text, server_default="", nullable=False),
        sa.Column("prompt_version", sa.Text, server_default="", nullable=False),
        sa.Column("temperature", sa.Float, server_default="0", nullable=False),
        sa.Column("input_hash", sa.Text, server_default="", nullable=False),
        sa.Column("output_hash", sa.Text, server_default="", nullable=False),
        sa.Column("input_text", sa.Text, server_default="", nullable=False),  # v2.0 加
        sa.Column("output_text", sa.Text, server_default="", nullable=False),  # v2.0 加
        sa.Column("duration_ms", sa.Integer, server_default="0", nullable=False),
        sa.Column("token_input", sa.Integer, server_default="0", nullable=False),
        sa.Column("token_output", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.Text, server_default="ok", nullable=False),
        sa.Column("error", sa.Text, server_default="", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_lr_project", "llm_run", ["project_id"])

    # project_config
    op.create_table(
        "project_config",
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("layer_rules", sa.Text, server_default="{}", nullable=False),
        sa.Column("block_rules", sa.Text, server_default="{}", nullable=False),
        sa.Column("meta", sa.Text, server_default="{}", nullable=False),
        sa.Column("updated_at", sa.Text, server_default="", nullable=False),
    )

    # binding_candidate
    op.create_table(
        "binding_candidate",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engineering_object_id", sa.Integer, sa.ForeignKey("engineering_object.id", ondelete="CASCADE"), nullable=False),
        sa.Column("boq_item_id", sa.Integer, sa.ForeignKey("boq_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.Text, server_default="LLM", nullable=False),
        sa.Column("score", sa.Float, server_default="0", nullable=False),
        sa.Column("confidence", sa.Float, server_default="0", nullable=False),
        sa.Column("reason", sa.Text, server_default="", nullable=False),
        sa.Column("model", sa.Text, server_default="", nullable=False),
        sa.Column("model_version", sa.Text, server_default="", nullable=False),
        sa.Column("prompt_version", sa.Text, server_default="", nullable=False),
        sa.Column("llm_run_id", sa.Integer, sa.ForeignKey("llm_run.id", ondelete="SET NULL")),
        sa.Column("status", sa.Text, server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.Text, server_default="", nullable=False),
    )
    op.create_index("idx_bc_eo", "binding_candidate", ["engineering_object_id"])
    op.create_index("idx_bc_boq", "binding_candidate", ["boq_item_id"])
    op.create_index("idx_bc_status", "binding_candidate", ["project_id", "status"])
    op.create_index("idx_bc_proj_eo", "binding_candidate", ["project_id", "engineering_object_id"])
    op.create_index("idx_bc_proj_eo_status", "binding_candidate", ["project_id", "engineering_object_id", "status"])

    # llm_settings（单例表）
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer, primary_key=True, server_default="1"),
        sa.CheckConstraint("id = 1", name="ck_llm_settings_singleton"),
        sa.Column("active_backend", sa.Text, server_default="ollama", nullable=False),
        sa.Column("ollama_host", sa.Text, server_default="http://127.0.0.1:11434", nullable=False),
        sa.Column("ollama_model", sa.Text, server_default="qwen2.5:7b", nullable=False),
        sa.Column("dashscope_api_key", sa.Text, server_default="", nullable=False),
        sa.Column("dashscope_model", sa.Text, server_default="qwen-vl-max-0809", nullable=False),
        sa.Column("openai_api_key", sa.Text, server_default="", nullable=False),
        sa.Column("openai_model", sa.Text, server_default="gpt-4o-mini", nullable=False),
        sa.Column("deepseek_api_key", sa.Text, server_default="", nullable=False),
        sa.Column("deepseek_model", sa.Text, server_default="deepseek-chat", nullable=False),
        sa.Column("custom_base_url", sa.Text, server_default="", nullable=False),
        sa.Column("custom_api_key", sa.Text, server_default="", nullable=False),
        sa.Column("custom_model", sa.Text, server_default="", nullable=False),
        sa.Column("custom_embedding_model", sa.Text, server_default="", nullable=False),
        sa.Column("fallback_enabled", sa.Integer, server_default="0", nullable=False),
        sa.Column("fallback_backend", sa.Text, server_default="", nullable=False),
        sa.Column("quality_threshold", sa.Float, server_default="0.7", nullable=False),
        sa.Column("temperature", sa.Float, server_default="0.1", nullable=False),
        sa.Column("timeout", sa.Integer, server_default="120", nullable=False),
        sa.Column("max_tokens", sa.Integer, server_default="4000", nullable=False),
        sa.Column("updated_at", sa.Text, server_default="", nullable=False),
    )

    # symbol_library
    op.create_table(
        "symbol_library",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_name", sa.Text, server_default="", nullable=False),
        sa.Column("layer_name", sa.Text, server_default="", nullable=False),
        sa.Column("discipline", sa.Text, server_default="", nullable=False),
        sa.Column("system", sa.Text, server_default="", nullable=False),
        sa.Column("spec", sa.Text, server_default="", nullable=False),
        sa.Column("unit", sa.Text, server_default="", nullable=False),
        sa.Column("quantity_rule", sa.Text, server_default="", nullable=False),
        sa.Column("source", sa.Text, server_default="manual", nullable=False),
        sa.Column("confirmed_by", sa.Text, server_default="", nullable=False),
        sa.Column("confirmed_at", sa.Text, server_default="", nullable=False),
        sa.Column("updated_at", sa.Text, server_default="", nullable=False),
        sa.UniqueConstraint("project_id", "block_name", "layer_name", name="uq_symlib_key"),
    )
    op.create_index("idx_symlib_block", "symbol_library", ["block_name"])
    op.create_index("idx_symlib_layer", "symbol_library", ["layer_name"])

    # =====================================================================
    # 2. RBAC 表（来自 webapi/auth/models.py）
    # =====================================================================
    op.create_table(
        "sys_user",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("password_hash", sa.String(255), server_default="", nullable=False),
        sa.Column("nickname", sa.String(64), server_default="", nullable=False),
        sa.Column("email", sa.String(128), server_default="", nullable=False),
        sa.Column("phone", sa.String(32), server_default="", nullable=False),
        sa.Column("avatar", sa.String(255), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("is_admin", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("remark", sa.String(255), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "sys_role",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("code", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("description", sa.String(255), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "sys_user_role",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("sys_user.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("sys_role.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_table(
        "sys_menu",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("parent_id", sa.Integer, server_default="0", index=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("type", sa.String(1), server_default="C", nullable=False),
        sa.Column("perm_code", sa.String(128), server_default="", index=True, nullable=False),
        sa.Column("path", sa.String(255), server_default="", nullable=False),
        sa.Column("component", sa.String(255), server_default="", nullable=False),
        sa.Column("icon", sa.String(64), server_default="", nullable=False),
        sa.Column("sort", sa.Integer, server_default="0", nullable=False),
        sa.Column("visible", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "sys_dict",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("dict_type", sa.String(64), index=True, nullable=False),
        sa.Column("dict_key", sa.String(64), nullable=False),
        sa.Column("dict_value", sa.String(255), nullable=False),
        sa.Column("sort", sa.Integer, server_default="0", nullable=False),
        sa.Column("remark", sa.String(255), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dict_type", "dict_key", name="uq_dict_type_key"),
    )


def downgrade() -> None:
    # 逆序删除
    op.drop_table("sys_dict")
    op.drop_table("sys_menu")
    op.drop_table("sys_user_role")
    op.drop_table("sys_role")
    op.drop_table("sys_user")
    op.drop_index("idx_symlib_layer", "symbol_library")
    op.drop_index("idx_symlib_block", "symbol_library")
    op.drop_table("symbol_library")
    op.drop_table("llm_settings")
    op.drop_index("idx_bc_proj_eo_status", "binding_candidate")
    op.drop_index("idx_bc_proj_eo", "binding_candidate")
    op.drop_index("idx_bc_status", "binding_candidate")
    op.drop_index("idx_bc_boq", "binding_candidate")
    op.drop_index("idx_bc_eo", "binding_candidate")
    op.drop_table("binding_candidate")
    op.drop_table("project_config")
    op.drop_index("idx_lr_project", "llm_run")
    op.drop_table("llm_run")
    op.drop_index("idx_eo_layer", "engineering_object")
    op.drop_index("idx_eo_block", "engineering_object")
    op.drop_index("idx_eo_project", "engineering_object")
    op.drop_table("engineering_object")
    op.drop_table("block_legend")
    op.drop_index("idx_mapping_entity", "mapping")
    op.drop_index("idx_mapping_item", "mapping")
    op.drop_table("mapping")
    op.drop_index("idx_boq_item_key", "boq_item")
    op.drop_index("idx_boq_project", "boq_item")
    op.drop_table("boq_item")
    op.execute("DROP INDEX IF EXISTS idx_entity_bbox")
    op.drop_index("idx_entity_block", "entity")
    op.drop_index("idx_entity_layer", "entity")
    op.drop_index("idx_entity_sheet", "entity")
    op.drop_table("entity")
    op.drop_index("idx_sheet_project", "sheet")
    op.drop_table("sheet")
    op.drop_table("project")
