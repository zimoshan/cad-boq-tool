"""webapi 全局配置（Pydantic Settings 读取 env.example）"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic Settings 读取环境变量 + env.example"""

    model_config = SettingsConfigDict(
        env_file="env.example" if Path("env.example").exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 应用 ----------
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8521
    app_base_url: str = "http://localhost:8521"
    log_dir: str = "/var/log/cad-boq"
    log_level: str = "INFO"

    # ---------- 数据库（PG + PostGIS） ----------
    database_url: str = Field(
        default="postgresql+asyncpg://cadboq:cadboq_dev@localhost:5432/cadboq",
        description="async 驱动，运行时用",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://cadboq:cadboq_dev@localhost:5432/cadboq",
        description="sync 驱动，alembic/sqlite_to_pg.py 用",
    )
    sqlite_backup_path: str = ""

    # ---------- 鉴权 ----------
    auth_mode: str = "no_login"  # no_login / login
    secret_key: str = "change-me-in-production-please-32bytes-min"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    # ---------- ODA ----------
    oda_file_converter: str = "/usr/local/bin/ODAFileConverter"
    oda_install_hints: str = "/usr/local/ODA,/opt/ODA"
    oda_timeout: int = 300
    accoreconsole_path: str = ""

    # ---------- LLM ----------
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-vl-max-0809"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""
    custom_embedding_model: str = ""
    llm_fallback_enabled: bool = False
    llm_fallback_backend: str = ""
    llm_quality_threshold: float = 0.7
    llm_temperature: float = 0.1
    llm_timeout: int = 120
    llm_max_tokens: int = 4000

    # ---------- 存储 ----------
    drawing_cache_dir: str = "/var/lib/cad-boq/drawing_cache"
    embedding_cache_dir: str = "/var/lib/cad-boq/embedding_cache"
    block_geometry_dir: str = "/var/lib/cad-boq/block_geometry"

    # ---------- 文件上传 ----------
    max_upload_size: int = 209715200  # 200MB
    allowed_extensions: str = ".dwg,.dxf,.xlsx,.xls,.json,.csv"

    # ---------- CORS ----------
    cors_allow_origins: str = "http://localhost:5173,http://localhost:8521,http://127.0.0.1:5173"
    cors_allow_credentials: bool = True

    # ---------- 测试数据通路（P0-22 占位） ----------
    test_data_registry_path: str = "/var/lib/cad-boq/test_data_registry.json"

    @property
    def allowed_extension_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例 Settings 缓存"""
    return Settings()
