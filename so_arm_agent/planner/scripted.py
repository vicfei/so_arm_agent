"""规则规划器：零 API 依赖。首次提案故意含越界目标，演示 supervisor 否决权。"""

from __future__ import annotations

from ..types import (
    MoveTo,
    Point2,
    Primitive,
    PushToward,
    SetGripper,
    Task,
    VerifierFeedback,
)
from .base import Perception, Planner


class ScriptedPlanner(Planner):
    def __init__(self) -> None:
        self.calls = 0

    def consult(
        self,
        perception: Perception,
        task: Task,
        feedback: VerifierFeedback | None = None,
    ) -> list[Primitive]:
        self.calls += 1
        if self.calls == 1:
            # 演示用"失误"：目标越出工作区左界，应被 supervisor 否决并附理由
            return [MoveTo("PRE_PUSH"), PushToward(task.object_color, Point2(-50, task.target.y))]
        # 重规划也走同一目标：executor 从物体当前位置推进固定行程，重复推送自然收敛
        return [MoveTo("PRE_PUSH"), SetGripper(open=False), PushToward(task.object_color, task.target)]
