"""工作区几何：边界与像素↔工作区映射（标定件的技术位，真机阶段换实现）。"""

from __future__ import annotations

from .types import Pixel, Point2

# 模拟桌面：300 x 200 mm，原点左上（俯视），x 右 y 下。
WORKSPACE_W_MM = 300.0
WORKSPACE_H_MM = 200.0


def in_bounds(p: Point2, margin: float = 0.0) -> bool:
    return (
        margin <= p.x <= WORKSPACE_W_MM - margin
        and margin <= p.y <= WORKSPACE_H_MM - margin
    )


def clamp_into_bounds(p: Point2, margin: float = 10.0) -> Point2:
    return Point2(
        min(max(p.x, margin), WORKSPACE_W_MM - margin),
        min(max(p.y, margin), WORKSPACE_H_MM - margin),
    )


class Calibration:
    """像素↔工作区映射。v0 为 1:1 恒等映射；真机标定后替换为 4-5 点单应/仿射拟合
    （06 号技术件 1：爪子放桌面已知点记录相机像素）。"""

    def pixel_to_workspace(self, px: Pixel) -> Point2:
        return Point2(float(px.x), float(px.y))

    def workspace_to_pixel(self, p: Point2) -> Pixel:
        return Pixel(int(round(p.x)), int(round(p.y)))
