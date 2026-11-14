"""CreateBlock 原语编排：scan / center / grasp / release。

全部逻辑与常数来自 2026-11-14 真机闭环抓取的实测管线（docs/08 §10.2），
无未验证假设。确定性代码，零训练。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..executor.createblock import (ArmState, CreateBlockExecutor, UnsafeStateError,
                                    HELD_MIN_GRIP_RAD)
from ..perception.framesource import FrameSource
from ..perception.hsv_detector import (ColorSpec, Detection, DetectionStatus, detect)

# ---- 实测常数（11-14）----
ANCHOR = (320, 352)        # 对中锚点：近景下"夹爪嘴正下方"
CENTER_TOL = (26, 30)      # dx/dy 收敛容差(px)
YAW_PROBE_RAD = 0.105      # yaw 符号探针步
J2_PROBE_RAD = 0.09        # j2 符号探针步
CORR_YAW_STEP = 0.05       # yaw 每步修正量(rad) ≈ 10-15px
CORR_J2_STEP = 0.06        # j2 每步修正量(rad)
GRIPPER_OPEN_RAD = 1.0     # 张爪（跨 30mm 物体实测）
DESCENT_STEP = 0.06        # j3 缓降步进
DESCENT_MAX_STEPS = 5
LIFT_J2_DELTA = -0.35      # 抬起：j2 后仰量

# 扫描位姿阶梯（j2, j3, j4）——11-14 jointscan 六站实测
SCAN_LADDER = [(-1.30, 0.60, 1.30), (-1.20, 0.80, 1.10), (-1.10, 0.95, 0.90),
               (-1.00, 1.05, 0.70), (-0.90, 1.15, 0.50), (-0.80, 1.25, 0.30)]
SCAN_YAWS = [0.0, 0.175, -0.175, 0.35, -0.35]  # 0,±10°,±20°


@dataclass
class ScanResult:
    found: bool
    joints: tuple | None = None       # (j1, j2, j3, j4) 命中时构型
    detection: Detection | None = None
    visited: int = 0


@dataclass
class GraspResult:
    held: bool
    grip_angle: float = 0.0
    evidence: dict = field(default_factory=dict)


def correction_step(offset: int, sign: int, step: float, tol: int) -> float:
    """实测符号修正步：目标移动方向 M=-sign(offset)，执行方向 = M*sign。纯函数可单测。"""
    if abs(offset) <= tol or sign == 0:
        return 0.0
    return -step * (1 if offset > 0 else -1) * sign


def _det(frame_src: FrameSource, spec: ColorSpec) -> Detection:
    frame = frame_src.read_warmed(1)
    return detect(frame, spec) if frame is not None else Detection(DetectionStatus.NONE, None, None)


def scan_for(executor: CreateBlockExecutor, frame_src: FrameSource, spec: ColorSpec) -> ScanResult:
    """多站位扫描：关节阶梯 × yaw 序列，命中即停（确定性遍历）。"""
    visited = 0
    for yaw in SCAN_YAWS:
        for (j2, j3, j4) in SCAN_LADDER:
            executor.set_joint("joint1", yaw, interval_ms=800)
            executor.set_joint("joint2", j2, interval_ms=1100)
            executor.set_joint("joint3", j3, interval_ms=1100)
            executor.set_joint("joint4", j4, interval_ms=1100)
            visited += 1
            det = _det(frame_src, spec)
            if det.status == DetectionStatus.FOUND:
                return ScanResult(True, joints=(yaw, j2, j3, j4), detection=det, visited=visited)
    executor.set_joint("joint1", 0.0, interval_ms=900)
    return ScanResult(False, visited=visited)


def center_on(executor: CreateBlockExecutor, frame_src: FrameSource, spec: ColorSpec,
              joints: tuple, max_iter: int = 7) -> Detection | None:
    """锚点对中：实测符号探针（yaw/j2 各一次）+ 迭代收敛（11-14 实测两步收敛）。"""
    j1, j2, j3, j4 = joints
    executor.set_joint("joint1", j1, interval_ms=900)
    executor.set_joint("joint2", j2, interval_ms=1100)
    executor.set_joint("joint3", j3, interval_ms=1100)
    executor.set_joint("joint4", j4, interval_ms=1100)

    base = _det(frame_src, spec)
    if base.status == DetectionStatus.NONE or base.center is None:
        return None

    # 符号探针：yaw+
    executor.set_joint("joint1", round(j1 + YAW_PROBE_RAD, 3), interval_ms=900)
    p1 = _det(frame_src, spec)
    yaw_sign = 0
    if p1.center is not None:
        yaw_sign = 1 if p1.center[0] > base.center[0] else -1
    executor.set_joint("joint1", j1, interval_ms=900)

    # 符号探针：j2-（j2 减小使 y 增 → j2_sign=+1 语义）
    executor.set_joint("joint2", round(j2 - J2_PROBE_RAD, 3), interval_ms=900)
    p2 = _det(frame_src, spec)
    j2_sign = 0
    if p2.center is not None:
        j2_sign = 1 if p2.center[1] > base.center[1] else -1
    executor.set_joint("joint2", j2, interval_ms=900)

    for _ in range(max_iter):
        det = _det(frame_src, spec)
        if det.center is None:
            return None
        dx = det.center[0] - ANCHOR[0]
        dy = det.center[1] - ANCHOR[1]
        if abs(dx) <= CENTER_TOL[0] and abs(dy) <= CENTER_TOL[1]:
            return det
        dyaw = correction_step(dx, yaw_sign, CORR_YAW_STEP, CENTER_TOL[0])
        if dyaw:
            j1 = round(j1 + dyaw, 3)
            executor.set_joint("joint1", j1, interval_ms=900)
            continue
        dj2 = correction_step(dy, j2_sign, CORR_J2_STEP, CENTER_TOL[1])
        if dj2:
            j2 = round(j2 + dj2, 3)
            executor.set_joint("joint2", j2, interval_ms=900)
    return None  # 未收敛


def grasp(executor: CreateBlockExecutor, frame_src: FrameSource, spec: ColorSpec) -> GraspResult:
    """张爪→缓降（遮挡/电流双门）→闭爪→四重验证→抬起（11-14 实测序列）。"""
    executor.set_gripper(GRIPPER_OPEN_RAD)
    state = executor.read_state()
    j3 = state.joints[2]
    reached = False
    for _ in range(DESCENT_MAX_STEPS):
        j3 = round(j3 + DESCENT_STEP, 3)
        state = executor.set_joint("joint3", j3, interval_ms=1000)
        executor.check_currents(state)
        det = _det(frame_src, spec)
        if det.status != DetectionStatus.FOUND:  # 白物被爪指遮挡 = 捕获高度
            reached = True
            break
    if not reached:  # 走满步数也尝试闭合（与当日实战一致）
        pass
    closed = executor.set_gripper(0.0)
    held = closed.held
    result = GraspResult(held=held, grip_angle=closed.grip_angle,
                         evidence={"currents_on_close": closed.currents,
                                   "grip_angle": closed.grip_angle,
                                   "descent_end_j3": j3})
    # 抬起撤离
    j2 = closed.joints[1]
    executor.set_joint("joint2", round(j2 + LIFT_J2_DELTA, 3), interval_ms=1200)
    return result


def release(executor: CreateBlockExecutor, place_j2: float = -0.95) -> ArmState:
    """缓降至放置高度→张爪→抬起回位（11-14 收工序列）。"""
    executor.set_joint("joint2", place_j2, interval_ms=1200)
    state = executor.set_gripper(GRIPPER_OPEN_RAD)
    executor.set_joint("joint2", round(place_j2 + LIFT_J2_DELTA, 3), interval_ms=1200)
    executor.home()
    return state


def store_locked(executor: CreateBlockExecutor) -> ArmState:
    """收纳：折叠至自稳零位并保持锁位（禁止 damping —— 塌臂教训）。"""
    for name, rad in (("joint1", 0.0), ("joint2", -1.5708), ("joint3", 1.5708),
                      ("joint4", 0.0), ("joint5", 0.0)):
        executor.set_joint(name, rad, interval_ms=1200)
    return executor.set_gripper(0.3)
