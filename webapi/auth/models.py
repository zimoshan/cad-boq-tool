"""RuoYi 风格 RBAC 4 张表 + 关联表

参照 RuoYi-Vue 数据模型：
- sys_user (用户)
- sys_role (角色)
- sys_menu (菜单/权限)
- sys_dict (字典)
- sys_user_role (用户-角色 N:N)
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from webapi.db.base import Base


class SysUser(Base):
    """用户表"""

    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    avatar: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # 关系
    roles: Mapped[list[SysRole]] = relationship(
        "SysRole",
        secondary="sys_user_role",
        back_populates="users",
        lazy="selectin",
    )


class SysRole(Base):
    """角色表"""

    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)  # admin/user/guest
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 关系
    users: Mapped[list[SysUser]] = relationship("SysUser", secondary="sys_user_role", back_populates="roles")


class SysUserRole(Base):
    """用户-角色 N:N 关联表"""

    __tablename__ = "sys_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sys_role.id", ondelete="CASCADE"), index=True, nullable=False
    )


class SysMenu(Base):
    """菜单/权限表（type: M=目录 C=菜单 F=按钮）"""

    __tablename__ = "sys_menu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(1), default="C", nullable=False)  # M/C/F
    perm_code: Mapped[str] = mapped_column(String(128), default="", index=True, nullable=False)  # e.g. cad:upload
    path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    component: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SysDict(Base):
    """字典表（type+key → value）"""

    __tablename__ = "sys_dict"
    __table_args__ = (UniqueConstraint("dict_type", "dict_key", name="uq_dict_type_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    dict_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dict_value: Mapped[str] = mapped_column(String(255), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remark: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
