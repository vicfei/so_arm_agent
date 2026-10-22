"""假相机 + 模拟桌面：读 MockScene 真实状态模拟"拍照识别"，供闭环跑纯逻辑。"""

from __future__ import annotations

from ..workspace import Calibration
from .base import Camera, Perception


class MockScene:
    """桌面物理真值：物体位置 + 机械臂状态。MockExecutor 改它，MockCamera 读它。"""

    def __init__(self, objects: dict[str, tuple[float, float]]) -> None:
        # objects: color -> (x, y) 工作区坐标 mm
        self.objects: dict[str, tuple[float, float]] = dict(objects)
        self.arm_pose = "HOME"
        self.gripper_open = True


class MockCamera(Camera):
    def __init__(self, scene: MockScene, calibration: Calibration | None = None) -> None:
        self.scene = scene
        self.cal = calibration or Calibration()
        self.frames = 0

    def observe(self) -> Perception:
        self.frames += 1
        from ..types import ObjectDetection, Pixel, Point2

        out = Perception()
        for color, (x, y) in self.scene.objects.items():
            center = Point2(x, y)
            out.append(
                ObjectDetection(
                    name=f"{color}块",
                    color=color,
                    center=center,
                    pixel=self.cal.workspace_to_pixel(center),
                    radius_mm=12.0,
                )
            )
        return out
