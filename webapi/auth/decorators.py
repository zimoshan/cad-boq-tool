"""权限装饰器 @requires("perm:code")

Phase 0（AUTH_MODE=no_login）：装饰器直接放行（no_login 模式无鉴权）
未来切 AUTH_MODE=login：通过 Casbin 校验 perm_code
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException, status

from webapi.auth.casbin_rbac import rbac
from webapi.auth.current_user import CurrentUser, get_current_user
from webapi.config import get_settings


def requires(perm_code: str) -> Callable:
    """权限装饰器：@requires("cad:upload")

    装饰后：
      - 解析当前用户（Depends get_current_user）
      - no_login 模式：直接放行
      - login 模式：Casbin 校验 perm_code
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            settings = get_settings()
            current_user: CurrentUser = kwargs.get("current_user") or get_current_user()

            if settings.auth_mode == "no_login":
                # 免登录模式：放行
                return await func(*args, **kwargs)

            # login 模式：Casbin 校验
            role_codes = current_user.role_codes or ["anonymous"]
            allowed = any(rbac.check(role, "*", perm_code) for role in role_codes) or current_user.is_admin
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {perm_code}",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
