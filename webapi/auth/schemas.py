"""Pydantic v2 schema for RuoYi 风格 RBAC"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- User ----------
class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    nickname: str = ""
    email: str = ""
    phone: str = ""


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)
    role_codes: list[str] = Field(default_factory=lambda: ["user"])


class UserUpdate(BaseModel):
    nickname: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    is_admin: bool
    roles: list[RoleRead] = Field(default_factory=list)
    created_at: datetime


# ---------- Role ----------
class RoleBase(BaseModel):
    name: str
    code: str = Field(min_length=1, max_length=64)
    description: str = ""


class RoleCreate(RoleBase):
    is_active: bool = True


class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


# ---------- Menu ----------
class MenuBase(BaseModel):
    parent_id: int = 0
    name: str
    type: str = "C"  # M/C/F
    perm_code: str = ""
    path: str = ""
    component: str = ""
    icon: str = ""
    sort: int = 0


class MenuCreate(MenuBase):
    visible: bool = True
    is_active: bool = True


class MenuRead(MenuBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    visible: bool
    is_active: bool


# ---------- Dict ----------
class DictBase(BaseModel):
    dict_type: str
    dict_key: str
    dict_value: str
    sort: int = 0
    remark: str = ""


class DictCreate(DictBase):
    is_active: bool = True


class DictRead(DictBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# 解决前向引用
UserRead.model_rebuild()
