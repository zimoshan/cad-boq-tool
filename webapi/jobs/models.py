"""Job 数据模型（Phase 2 JobManager）"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    """5 状态"""

    PENDING = "PENDING"  # 已入队未启动
    RUNNING = "RUNNING"  # 正在执行
    COMPLETED = "COMPLETED"  # 成功完成
    FAILED = "FAILED"  # 异常失败
    CANCELLED = "CANCELLED"  # 用户取消


@dataclass
class JobProgress:
    """进度（task_type + done/total + 消息）"""

    task_type: str = ""  # phase / subtask 名称
    done: int = 0
    total: int | None = None
    message: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "done": self.done,
            "total": self.total,
            "message": self.message,
            "extra": self.extra,
        }


@dataclass
class Job:
    """Job 完整状态"""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""  # 任务名（如 'parse_dwg_xxx'）
    status: JobStatus = JobStatus.PENDING
    progress: JobProgress = field(default_factory=JobProgress)
    payload: dict = field(default_factory=dict)  # 入参
    result: Any = None  # 完成结果
    error: str = ""  # 失败错误
    created_by: str = "sysadmin"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict:
        """序列化（排除内部 `__func__` 函数对象，避免 JSON 序列化失败）"""
        payload = {k: v for k, v in self.payload.items() if not k.startswith("__")}
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "payload": payload,
            "result": self.result,
            "error": self.error,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
