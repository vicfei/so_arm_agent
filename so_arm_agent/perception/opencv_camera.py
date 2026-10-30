"""渲染相机 + OpenCV 色块检测：真图像、真算法的感知闭环（90% 真闭环件）。

MockScene -> Renderer 渲染成真 BGR 帧 -> OpenCVDetector 做 HSV 色块检测
-> 组装 Perception。与 MockCamera 可互换（同为 Camera 插槽），Agent 零改动。
依赖: numpy, opencv-python-headless。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # 避免循环导入
    from .mock import MockScene

from ..types import ObjectDetection, Pixel, Point2
from .base import Perception
from ..workspace import Calibration, in_bounds
from .base import Camera

# 渲染配色（BGR）：桌面浅灰、目标区描边绿、夹爪标记深灰
TABLE_BGR = (235, 235, 228)
COLOR_BGR = {"红": (60, 60, 205), "蓝": (200, 120, 40), "绿": (70, 170, 70)}
GRIP_BGR = (70, 70, 70)

# HSV 检测阈值（OpenCV H: 0-179）
HSV_RANGES = {
    "红": ((0, 120, 90), (10, 255, 255)),
    "蓝": ((100, 110, 90), (130, 255, 255)),
    "绿": ((45, 90, 90), (85, 255, 255)),
}

OBJECT_R_MM = 12.0  # 色块半径（渲染与检测共用）


class Renderer:
    """把 MockScene 渲染成真实 BGR 帧。scale=像素/毫米。"""

    def __init__(self, scene: "MockScene", scale: float = 2.0, width_mm: float = 300.0,
                 height_mm: float = 200.0) -> None:
        self.scene = scene
        self.scale = scale
        self.w = int(width_mm * scale)
        self.h = int(height_mm * scale)

    def render(self) -> np.ndarray:
        import cv2
        img = np.full((self.h, self.w, 3), TABLE_BGR, dtype=np.uint8)
        r = int(OBJECT_R_MM * self.scale)
        for color, (x, y) in self.scene.objects.items():
            bgr = COLOR_BGR.get(color, (128, 128, 128))
            cx, cy = int(x * self.scale), int(y * self.scale)
            cv2.circle(img, (cx, cy), r, bgr, -1)
        # 夹爪标记（左上角小方块，示意位姿存在）
        cv2.rectangle(img, (4, 4), (24, 24), GRIP_BGR, -1)
        return img


class OpenCVDetector:
    """HSV 阈值 + 连通域检测色块，输出工作区坐标（经 Calibration 逆映射）。"""

    def __init__(self, calibration: Calibration | None = None, scale: float = 2.0,
                 min_area_px: int = 30) -> None:
        self.cal = calibration or Calibration()
        self.scale = scale
        self.min_area = min_area_px

    def detect(self, frame: np.ndarray) -> list[ObjectDetection]:
        import cv2
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
        out: list[ObjectDetection] = []
        h, w = frame.shape[:2]
        for color, (lo, hi) in HSV_RANGES.items():
            mask = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask[:28, :28] = 0  # 挖掉夹爪标记区
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) < self.min_area:
                continue
            m = cv2.moments(c)
            px = int(m["m10"] / m["m00"])
            py = int(m["m01"] / m["m00"])
            point = self.cal.pixel_to_workspace(Pixel(px, py))
            point = Point2(point.x / self.scale, point.y / self.scale)
            if not in_bounds(point, margin=-20):  # 容忍渲染边缘
                continue
            out.append(ObjectDetection(
                name=f"{color}块", color=color, center=point,
                pixel=Pixel(px, py), radius_mm=OBJECT_R_MM))
        return out


class RenderedCamera(Camera):
    """Camera 插槽的真感知实现：渲染帧 + CV 检测。与 MockCamera 可互换。"""

    def __init__(self, scene: "MockScene", calibration: Calibration | None = None,
                 scale: float = 2.0) -> None:
        self.renderer = Renderer(scene, scale=scale)
        self.detector = OpenCVDetector(calibration, scale=scale)
        self.frames = 0
        self.last_frame: np.ndarray | None = None

    def observe(self) -> Perception:
        self.frames += 1
        frame = self.renderer.render()
        self.last_frame = frame
        return Perception(self.detector.detect(frame))
