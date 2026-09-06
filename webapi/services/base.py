"""Service 层公共基础（异常 + 通用工具）"""
from __future__ import annotations

from fastapi import HTTPException, status


class ServiceError(HTTPException):
    """业务异常（Service 层抛出，FastAPI 自动转 JSON 响应）"""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, code: str = "service_error") -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message},
        )


class NotFoundError(ServiceError):
    def __init__(self, resource: str, id_: int | str) -> None:
        super().__init__(
            message=f"{resource} #{id_} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
        )


class PermissionDeniedError(ServiceError):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="permission_denied",
        )
