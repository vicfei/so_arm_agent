"""感知接口：符号化输出，不出原始帧。真机阶段换 OpenCV 实现（颜色/轮廓/ArUco）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import ObjectDetection


class Perception(list):
    """list[ObjectDetection] 的语义别名。"""

    __slots__ = ()


class Camera(ABC):
    @abstractmethod
    def observe(self) -> Perception:
        """拍一帧 → 符号化检测结果列表。"""
