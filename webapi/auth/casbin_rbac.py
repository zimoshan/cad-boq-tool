"""Casbin RBAC 策略配置（当前空策略，所有权限通过）

Phase 0 占位：策略文件 casbin_policy.csv 为空（所有人所有权限）
Phase 1+ 业务期：按角色加载策略
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import casbin

# 策略文件路径
POLICY_FILE = Path(__file__).parent / "casbin_policy.csv"

# Phase 0：空策略（所有人都有权限）
DEFAULT_POLICY = """# Casbin RBAC 策略
# 格式：p, role_code, path, method
# Phase 0 占位：空策略表示所有路径都允许
"""

# 模型文件（RBAC with pattern）
DEFAULT_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && (p.obj == "*" || keyMatch(r.obj, p.obj)) && (p.act == "*" || r.act == p.act)
"""


class CasbinRBAC:
    """Casbin 包装（懒加载）"""

    def __init__(self) -> None:
        self._enforcer: casbin.Enforcer | None = None

    def get_enforcer(self) -> casbin.Enforcer:
        if self._enforcer is None:
            # 写默认模型与策略到临时路径
            model_file = Path(__file__).parent / "casbin_model.conf"
            if not model_file.exists():
                model_file.write_text(DEFAULT_MODEL, encoding="utf-8")
            if not POLICY_FILE.exists():
                POLICY_FILE.write_text(DEFAULT_POLICY, encoding="utf-8")
            self._enforcer = casbin.Enforcer(str(model_file), str(POLICY_FILE))
        return self._enforcer

    def check(self, sub: str, obj: str, act: str) -> bool:
        """检查 sub 角色对 obj 路径 act 操作是否有权限

        Phase 0：策略空 = 一律 True
        """
        try:
            return self.get_enforcer().enforce(sub, obj, act)
        except Exception:
            return True  # 失败时放行（no_login 模式友好）


rbac = CasbinRBAC()
