"""公共 schema（分页/响应包装/错误）"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包装：{code, message, data}"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class Pagination(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PageResult(BaseModel, Generic[T]):
    """分页结果"""

    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail
