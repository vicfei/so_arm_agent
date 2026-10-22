"""Planner 接口：低频咨询协议（每任务步一次，不逐帧——实验 1b 教训）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Primitive, Task, VerifierFeedback


class Perception(list):  # list[ObjectDetection] 的语义别名
    pass


class Planner(ABC):
    @abstractmethod
    def consult(
        self,
        perception: Perception,
        task: Task,
        feedback: VerifierFeedback | None = None,
    ) -> list[Primitive]:
        """看一次符号化感知 + 上一轮 verifier 反馈 → 原语序列。"""


class DeepSeekPlanner(Planner):
    """真机阶段实现：DeepSeek-Vision 看相机帧 → JSON 原语序列（06 号已验证读图准/输出干净）。
    key 走环境变量 DEEPSEEK_API_KEY，不落盘不进日志。骨架期留桩。"""

    def consult(
        self,
        perception: Perception,
        task: Task,
        feedback: VerifierFeedback | None = None,
    ) -> list[Primitive]:
        raise NotImplementedError("真机阶段接入；mock 闭环请用 ScriptedPlanner")
