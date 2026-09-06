"""当前用户（FastAPI Depends）

Phase 0 AUTH_MODE=no_login：直接返回 sysadmin stub
未来切 AUTH_MODE=login：改为 JWT 解析 + DB 查 user
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends

from webapi.config import get_settings


@dataclass
class CurrentUser:
    """当前用户（webapi 视图层使用）"""
    id: int
    username: str
    nickname: str
    is_admin: bool
    role_codes: list[str] = field(default_factory=list)

    def has_role(self, code: str) -> bool:
        return self.is_admin or code in self.role_codes


def get_current_user() -> CurrentUser:
    """FastAPI Depends：返回当前用户

    Phase 0（AUTH_MODE=no_login）：返回 sysadmin stub，所有权限
    切 login 后：解析 Authorization header → JWT → DB 查 user → 返回
    """
    settings = get_settings()
    if settings.auth_mode == "no_login":
        return CurrentUser(
            id=1,
            username="sysadmin",
            nickname="系统管理员（免登录）",
            is_admin=True,
            role_codes=["admin"],
        )
    # 未来扩展：JWT 解析
    # from fastapi import Header, HTTPException
    # from jose import jwt, JWTError
    # auth_header = ...
    # token = auth_header.split(" ", 1)[1]
    # payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    # username = payload.get("sub")
    # 然后从 DB 查 user 返回
    raise NotImplementedError(f"AUTH_MODE={settings.auth_mode} not implemented yet")
