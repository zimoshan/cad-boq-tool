"""webapi/auth: RuoYi 风格 RBAC + Casbin

Phase 0 默认 AUTH_MODE=no_login（current_user 直接返回 sysadmin stub）
未来切 login 时：
  1. 启用 JWT 登录接口
  2. current_user 改为 token 解析 + DB 查 user
  3. 装饰器 @requires 不变
"""
from webapi.auth.decorators import requires
from webapi.auth.current_user import CurrentUser, get_current_user

__all__ = ["requires", "CurrentUser", "get_current_user"]
