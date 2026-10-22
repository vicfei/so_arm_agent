"""公共数据类：全部分层只经由这些类型交互。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def dist_to(self, other: "Point2") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass(frozen=True)
class Pixel:
    x: int
    y: int


@dataclass(frozen=True)
class ObjectDetection:
    name: str
    color: str
    center: Point2
    pixel: Pixel
    radius_mm: float


@dataclass(frozen=True)
class Task:
    object_color: str
    target: Point2
    tolerance_mm: float = 25.0


# ---- 原语三件套（deterministic, zero-training）----


@dataclass(frozen=True)
class MoveTo:
    pose_name: str  # 位姿库键：HOME / PRE_PUSH / DESCEND / ...


@dataclass(frozen=True)
class SetGripper:
    open: bool


@dataclass(frozen=True)
class PushToward:
    object_color: str
    goal: Point2
    stroke_mm: float = 80.0


Primitive = MoveTo | SetGripper | PushToward


# ---- 裁决 / 反馈 / 证据 ----


@dataclass(frozen=True)
class Verdict:
    approved: bool
    reason: str


@dataclass(frozen=True)
class VerifierFeedback:
    ok: bool
    distance_mm: float
    hint: str = ""


@dataclass
class EvidenceRecord:
    kind: str  # plan | veto | execute | verify
    payload: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
