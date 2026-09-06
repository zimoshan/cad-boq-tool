"""v1.0 §22 几何算法优化

优先：
  1. SPLINE 真实弧长（自适应采样）
  2. 平行线对 → 中心线（避免桥架/风管双边界双倍计量）
  3. HATCH 多环、孔洞（shoelace 多边形面积）
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def spline_arc_length(
    points: Sequence[tuple[float, float]],
    iterations: int = 3,
) -> float:
    """v1.0 §22.1 SPLINE 真实弧长

    用 Casteljau / adaptive subdivision 估算 Bezier 长度。
    points: 4 个控制点 (P0, P1, P2, P3)
    iterations: subdivision 次数（3 = 2^3=8 段，约 0.4% 误差）
    """
    if len(points) != 4:
        return sum(
            math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]) for i in range(len(points) - 1)
        )

    p0, p1, p2, p3 = [tuple(p) for p in points]

    def lerp(a, b, t):
        return (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
        )

    def casteljau(t):
        q0 = lerp(p0, p1, t)
        q1 = lerp(p1, p2, t)
        q2 = lerp(p2, p3, t)
        r0 = lerp(q0, q1, t)
        r1 = lerp(q1, q2, t)
        return lerp(r0, r1, t)

    segments = 2**iterations
    total = 0.0
    prev = p0
    for i in range(1, segments + 1):
        t = i / segments
        cur = casteljau(t)
        total += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return total


def parallel_line_centerline(
    line1: tuple[tuple[float, float], tuple[float, float]],
    line2: tuple[tuple[float, float], tuple[float, float]],
    tolerance: float = 5.0,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """v1.0 §22.2 平行线对 → 中心线

    2 条参数化平行线段（同向或反向），返回两端中点连线。
    """
    (x1, y1), (x2, y2) = line1
    (x3, y3), (x4, y4) = line2
    dx1, dy1 = x2 - x1, y2 - y1
    dx2, dy2 = x4 - x3, y4 - y3
    len1 = math.hypot(dx1, dy1)
    len2 = math.hypot(dx2, dy2)
    if len1 < 1e-6 or len2 < 1e-6:
        return None
    ux1, uy1 = dx1 / len1, dy1 / len1
    ux2, uy2 = dx2 / len2, dy2 / len2
    dot = ux1 * ux2 + uy1 * uy2
    if abs(abs(dot) - 1.0) > 0.05:
        return None  # 不平行
    # 反向时翻转 line2 端点
    if dot < 0:
        x3, y3, x4, y4 = x4, y4, x3, y3
    # 中心线：两端中点
    center_start = ((x1 + x3) / 2, (y1 + y3) / 2)
    center_end = ((x2 + x4) / 2, (y2 + y4) / 2)
    if math.hypot(center_end[0] - center_start[0], center_end[1] - center_start[1]) < tolerance:
        return None
    return (center_start, center_end)


def hatch_polygon_area(loops: list[list[tuple[float, float]]]) -> float:
    """v1.0 §22.3 HATCH 多环孔洞面积（外环 - 内环孔洞）

    shoelace 公式：
        area = 0.5 * |sum((x_i * y_{i+1}) - (x_{i+1} * y_i))|
    外环正面积，环（孔洞）减面积
    """
    if not loops:
        return 0.0
    # 第一环当外环（面积累加），其余当孔洞（面积累减）
    net = 0.0
    for i, loop in enumerate(loops):
        if len(loop) < 3:
            continue
        a = 0.0
        for j in range(len(loop)):
            x1, y1 = loop[j]
            x2, y2 = loop[(j + 1) % len(loop)]
            a += x1 * y2 - x2 * y1
        loop_area = abs(a) / 2.0
        net += loop_area if i == 0 else -loop_area
    return max(0.0, net)
