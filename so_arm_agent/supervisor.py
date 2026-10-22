"""Supervisor：原语否决权（ORA 借鉴）。planner 可以是任何模型，这里必须是纯代码。"""

from __future__ import annotations

from .primitives import describe
from .primitives.library import POSE_LIBRARY
from .types import MoveTo, Primitive, PushToward, Verdict
from .workspace import in_bounds


class Supervisor:
    """执行前审查：工作区边界 / 行程上限 / 位姿库存在 / 任务相关性。否决必须给理由。"""

    MAX_STROKE_MM = 150.0

    def approve(self, primitive: Primitive, task) -> Verdict:
        if isinstance(primitive, MoveTo):
            if primitive.pose_name not in POSE_LIBRARY:
                return Verdict(False, f"位姿 {primitive.pose_name} 不在位姿库")
            return Verdict(True, "ok")

        if isinstance(primitive, PushToward):
            if not in_bounds(primitive.goal, margin=5.0):
                return Verdict(
                    False,
                    f"目标 ({primitive.goal.x:.0f},{primitive.goal.y:.0f}) 越出工作区边界（含 5mm 安全边）",
                )
            if primitive.stroke_mm > self.MAX_STROKE_MM:
                return Verdict(False, f"行程 {primitive.stroke_mm:.0f}mm 超上限 {self.MAX_STROKE_MM}mm")
            if primitive.object_color != task.object_color:
                return Verdict(False, f"推送对象 {primitive.object_color} 与任务对象 {task.object_color} 不符")
            return Verdict(True, "ok")

        # SetGripper 等无几何风险原语直接放行
        return Verdict(True, "ok")


def describe_prim(p: Primitive) -> str:
    return describe(p)
