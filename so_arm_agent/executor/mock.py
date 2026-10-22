"""模拟执行器：持有桌面物理。push 把物体沿射线推进固定行程（不足则到目标）。"""

from __future__ import annotations

import math

from ..types import MoveTo, Point2, Primitive, PushToward, SetGripper
from .base import Executor


class MockExecutor(Executor):
    def __init__(self, scene) -> None:  # scene: perception.MockScene（避免循环导入不注类型）
        self.scene = scene
        self.executed: list[str] = []

    def execute(self, primitive: Primitive) -> dict:
        if isinstance(primitive, MoveTo):
            self.scene.arm_pose = primitive.pose_name
            receipt = {"primitive": f"move_to({primitive.pose_name})", "arm_pose": primitive.pose_name}
        elif isinstance(primitive, SetGripper):
            self.scene.gripper_open = primitive.open
            receipt = {"primitive": f"gripper({'open' if primitive.open else 'close'})"}
        elif isinstance(primitive, PushToward):
            if primitive.object_color not in self.scene.objects:
                receipt = {"primitive": "push_toward", "error": f"物体 {primitive.object_color} 不在视野"}
            else:
                ox, oy = self.scene.objects[primitive.object_color]
                obj = Point2(ox, oy)
                goal = primitive.goal
                d = obj.dist_to(goal)
                if d <= primitive.stroke_mm:
                    new_pos = goal
                else:
                    new_pos = Point2(
                        ox + (goal.x - ox) / d * primitive.stroke_mm,
                        oy + (goal.y - oy) / d * primitive.stroke_mm,
                    )
                self.scene.objects[primitive.object_color] = (new_pos.x, new_pos.y)
                receipt = {
                    "primitive": "push_toward",
                    "object": primitive.object_color,
                    "from": [round(ox), round(oy)],
                    "to": [round(new_pos.x), round(new_pos.y)],
                    "moved_mm": round(obj.dist_to(new_pos)),
                }
        else:  # pragma: no cover
            receipt = {"primitive": repr(primitive), "error": "未知原语"}
        self.executed.append(receipt["primitive"])
        receipt["arm_pose"] = getattr(self.scene, "arm_pose", "?")
        return receipt


def _ray(p0: Point2, p1: Point2, t: float) -> Point2:  # 备用工具
    return Point2(p0.x + (p1.x - p0.x) * t, p0.y + (p1.y - p0.y) * t)


def _norm(dx: float, dy: float) -> float:
    return math.hypot(dx, dy)
