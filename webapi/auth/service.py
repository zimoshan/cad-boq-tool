"""RBAC CRUD service（当前仅 stub，P0-4 骨架）

Phase 0 占位：仅建表 + Casbin 策略就绪
Phase 1+ 业务期：补齐 CRUD
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.models import SysRole, SysUser, SysUserRole
from webapi.auth.schemas import UserCreate


async def get_user_by_username(db: AsyncSession, username: str) -> SysUser | None:
    """按用户名查用户（含 roles）"""
    result = await db.execute(select(SysUser).where(SysUser.username == username))
    return result.scalar_one_or_none()


async def get_or_create_admin(db: AsyncSession) -> SysUser:
    """Phase 0 启动时确保 sysadmin 用户存在（no_login 模式下用）"""
    admin = await get_user_by_username(db, "sysadmin")
    if admin:
        return admin
    admin_role_result = await db.execute(select(SysRole).where(SysRole.code == "admin"))
    admin_role = admin_role_result.scalar_one_or_none()
    if not admin_role:
        admin_role = SysRole(name="超级管理员", code="admin", description="内置", is_active=True)
        db.add(admin_role)
        await db.flush()
    user_create = UserCreate(
        username="sysadmin",
        password="sysadmin_no_login",  # no_login 模式不校验密码
        nickname="系统管理员",
        email="",
        phone="",
        role_codes=["admin"],
    )
    user = SysUser(
        username=user_create.username,
        password_hash="",  # no_login 占位
        nickname=user_create.nickname,
        email=user_create.email,
        phone=user_create.phone,
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    await db.flush()
    db.add(SysUserRole(user_id=user.id, role_id=admin_role.id))
    await db.commit()
    await db.refresh(user)
    return user
