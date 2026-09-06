"""RuoYi 风格 RBAC + Casbin 基础测试（no_login 模式）"""
from __future__ import annotations

import pytest

from webapi.auth.current_user import CurrentUser, get_current_user
from webapi.auth.decorators import requires
from webapi.auth.schemas import UserCreate, UserRead


class TestCurrentUser:
    """no_login 模式 current_user 行为"""

    def test_get_current_user_returns_sysadmin(self, monkeypatch):
        """AUTH_MODE=no_login 时返回 sysadmin stub"""
        monkeypatch.setenv("AUTH_MODE", "no_login")
        # 清缓存
        from webapi.config import get_settings
        get_settings.cache_clear()
        user = get_current_user()
        assert user.id == 1
        assert user.username == "sysadmin"
        assert user.is_admin is True
        assert "admin" in user.role_codes

    def test_current_user_has_role(self):
        user = CurrentUser(id=1, username="u", nickname="n", is_admin=False, role_codes=["viewer"])
        assert user.has_role("viewer") is True
        assert user.has_role("admin") is False

    def test_admin_has_any_role(self):
        user = CurrentUser(id=1, username="u", nickname="n", is_admin=True, role_codes=[])
        assert user.has_role("anything") is True


class TestRequiresDecorator:
    """@requires(perm_code) 装饰器行为"""

    @pytest.mark.asyncio
    async def test_requires_passes_in_no_login_mode(self, monkeypatch):
        """AUTH_MODE=no_login 直接放行"""
        monkeypatch.setenv("AUTH_MODE", "no_login")
        from webapi.config import get_settings
        get_settings.cache_clear()

        @requires("cad:upload")
        async def my_endpoint():
            return "OK"

        result = await my_endpoint()
        assert result == "OK"

    @pytest.mark.asyncio
    async def test_requires_passes_in_login_mode_for_admin(self, monkeypatch):
        """AUTH_MODE=login + admin 用户：放行"""
        monkeypatch.setenv("AUTH_MODE", "login")
        from webapi.config import get_settings
        get_settings.cache_clear()

        @requires("cad:upload")
        async def my_endpoint(current_user: CurrentUser = None):
            return "OK"

        # admin 用户
        admin = CurrentUser(id=1, username="admin", nickname="admin", is_admin=True, role_codes=[])
        result = await my_endpoint(current_user=admin)
        assert result == "OK"


class TestSchemas:
    """Pydantic v2 schema 验证"""

    def test_user_create_min_length(self):
        with pytest.raises(ValueError):
            UserCreate(username="ab", password="x")  # username 至少 3 字符

    def test_user_create_ok(self):
        u = UserCreate(username="alice", password="secret123", role_codes=["admin"])
        assert u.username == "alice"
        assert u.role_codes == ["admin"]

    def test_user_read_from_attributes(self):
        # 模拟 from_attributes 模式
        class FakeUser:
            id = 1
            username = "alice"
            nickname = "Alice"
            email = ""
            phone = ""
            is_active = True
            is_admin = False
            roles = []
            created_at = "2026-09-06T10:00:00"
        u = UserRead.model_validate(FakeUser())
        assert u.username == "alice"
        assert u.is_active is True
