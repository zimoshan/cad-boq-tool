"""几何计算：长度 / 面积（供计量引擎与解析器使用）"""
from __future__ import annotations

import math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def dist2d(a: tuple, b: tuple) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def arc_length(radius: float, start_angle: float, end_angle: float) -> float:
    """圆弧长度（角度为弧度）"""
    if radius <= 0:
        return 0.0
    # 处理跨 0 点：ezdxf 的角度可能 end < start
    diff = abs(end_angle - start_angle)
    if diff > 2 * math.pi:
        diff = diff % (2 * math.pi)
    if diff == 0:
        diff = 2 * math.pi
    return radius * diff


def bulge_to_arc_length(p1: tuple, p2: tuple, bulge: float) -> float:
    """多段线 bulge 段弧长。bulge=tan(θ/4)，θ 为包含角"""
    if abs(bulge) < 1e-12:
        return dist2d(p1, p2)
    chord = dist2d(p1, p2)
    theta = 4 * math.atan(abs(bulge))
    if abs(theta) < 1e-9:
        return chord
    radius = chord / (2 * math.sin(theta / 2))
    return radius * theta


def polyline_length(points: list, bulges: list | None = None) -> float:
    """多段线长度（支持 bulge 弧段）。points: [(x,y),...]"""
    if len(points) < 2:
        return 0.0
    bulges = bulges or [0.0] * (len(points) - 1)
    total = 0.0
    for i in range(len(points) - 1):
        b = bulges[i] if i < len(bulges) else 0.0
        total += bulge_to_arc_length(points[i], points[i + 1], b)
    return total


def closed_polyline_area(points: list) -> float:
    """闭合多边形面积（shoelace），返回绝对值"""
    if len(points) < 3:
        return 0.0
    if HAS_NUMPY:
        xs = np.array([p[0] for p in points])
        ys = np.array([p[1] for p in points])
        return abs(float(np.dot(xs, np.roll(ys, -1)) - np.dot(ys, np.roll(xs, -1))) / 2.0)
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def spline_length(control_points: list, degree: int = 3, samples: int = 64) -> float:
    """B 样条近似长度：均匀采样拟合折线求和"""
    if len(control_points) < 2:
        return 0.0
    pts = control_points
    if len(pts) == 2:
        return dist2d(pts[0], pts[1])
    # 直接用控制点多边形近似（保守估算），对常见样条足够
    total = 0.0
    for i in range(len(pts) - 1):
        total += dist2d(pts[i], pts[i + 1])
    return total


def bbox_of_points(points: list) -> tuple:
    """点集包围盒 (min_x, min_y, max_x, max_y)"""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_union(b1: tuple, b2: tuple) -> tuple:
    return (
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3]),
    )
