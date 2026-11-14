"""CreateBlockExecutor：真机执行器 + 安全层（docs/08 §10.3 六条铁律的代码化）。

通道（11-08~14 验证）：SSH(paramiko) → Nano → Arm5DoFUServo(/dev/ttyTHS1)。
M1 用 SSHCodeRunner（今日实战模式：上传任务码→远端执行→解析 STATE 行）；
harness 迁上 Nano 后换 LocalCodeRunner，其余零改动。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .base import Executor
from ..types import Primitive


class UnsafeStateError(RuntimeError):
    """安全层熔断（驱动保护/趴伏/电流尖峰）——上层必须停任务并叫人。"""


# ---- 关节限位（厂商 arm5dof_kinematic 实测值，rad）----
JOINT_LIMITS = {
    "joint1": (-1.5708, 1.5708),
    "joint2": (-2.65, -0.2269),
    "joint3": (-0.7854, 2.18166),
    "joint4": (-2.0944, 2.0944),
    "joint5": (-1.5708, 1.5708),
    "left_gripper_joint": (0.0, 1.5708),
}
JOINT_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "left_gripper_joint"]

# 安全层常数（11-14 实战标定）
CURRENT_SPIKE_A = 1.2        # 任一关节电流超此值 → 立即回退
DRIVER_DEAD_A = 0.005        # 电流低于此值（带载关节）→ 驱动保护判定
ANGLE_TRACK_TOL = 0.25       # 关节回读与命令差超此值 → 跟踪失败
STARTUP_MIN_TOOL_Z_MM = 30.0 # 启动自检：工具低于此高度 = 趴伏构型拒任务
HELD_MIN_GRIP_RAD = 0.12     # 夹爪角高于此值 = 持物（空抓约 0.03）


@dataclass
class ArmState:
    joints: list = field(default_factory=list)            # 6 关节 rad
    currents: dict = field(default_factory=dict)          # {servo_id: A}
    tool_z_mm: float | None = None

    @property
    def grip_angle(self) -> float:
        return self.joints[5] if len(self.joints) > 5 else 0.0

    @property
    def held(self) -> bool:
        return self.grip_angle > HELD_MIN_GRIP_RAD


# ---- 远端执行的任务码模板（在 Nano 的 nvdli-data SDK 环境里运行）----
ARM_CODE = r'''
import os, sys, time
os.chdir("/home/jetson/nvdli-data")
sys.path.insert(0, os.getcwd())
import numpy as np
from arm5dof_uservo import Arm5DoFUServo

def main():
    arm = Arm5DoFUServo(config_folder="config", is_init_pose=False)
    arm.set_servo_velocity({velocity})
    mgr = arm.uservo
    for sid in range(6):
        mgr.ping(sid)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "read"
    if cmd == "set":
        name, t = sys.argv[2], float(sys.argv[3])
        iv = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
        arm.set_joint_angle(name, t, interval=iv, is_wait=True)
        time.sleep(0.3)
    elif cmd == "grip":
        arm.set_gripper_angle(angle=float(sys.argv[2]), T=1.0)
        time.sleep(0.4)
    elif cmd == "home":
        arm.home()
        time.sleep(0.4)
    j = np.round(arm.get_joint_angle_list(), 3).tolist()
    cur = {{}}
    for s in (2, 3, 5):
        try:
            cur[s] = round(mgr.query_current(s), 2)
        except Exception:
            cur[s] = -1.0
    z = None
    try:
        z = arm.get_tool_pose()[2]
    except Exception:
        pass
    print("STATE %s CUR %s Z %s" % (j, cur, z))

main()
'''


class CodeRunner(Protocol):
    def run(self, code: str, args: list) -> str: ...


class SSHCodeRunner:
    """paramiko 上传任务码到 Nano 执行（11-14 当日全链路验证的模式）。"""

    def __init__(self, host: str, key_path: str, user: str = "jetson", timeout: int = 90):
        self.host, self.key_path, self.user, self.timeout = host, key_path, user, timeout

    def run(self, code: str, args: list) -> str:
        import paramiko  # 延迟导入：WSL 侧测试不需要

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = paramiko.Ed25519Key.from_private_key_file(self.key_path)
        client.connect(self.host, username=self.user, pkey=key, timeout=8,
                       look_for_keys=False, allow_agent=False)
        try:
            sftp = client.open_sftp()
            with sftp.open("/tmp/saa_job.py", "w") as f:
                f.write(code)
            sftp.close()
            _, stdout, _ = client.exec_command(
                "cd /home/jetson/nvdli-data && timeout %d python3 -u /tmp/saa_job.py %s 2>&1"
                % (self.timeout, " ".join(args)), timeout=self.timeout + 10)
            return stdout.read().decode("utf-8", "replace")
        finally:
            client.close()


class LocalCodeRunner:
    """本地子进程执行（harness 迁上 Nano 后使用）。"""

    def __init__(self, workdir: str = "/home/jetson/nvdli-data"):
        self.workdir = workdir

    def run(self, code: str, args: list) -> str:
        import subprocess

        r = subprocess.run(["python3", "-u", "-", *args], input=code, cwd=self.workdir,
                           capture_output=True, text=True, timeout=90)
        return r.stdout + r.stderr


def parse_state(out: str) -> ArmState:
    """从任务码输出解析 STATE 行（解析器独立，便于单测）。"""
    for line in out.splitlines():
        if line.startswith("STATE"):
            try:
                body = line.split("STATE ", 1)[1]
                jpart, rest = body.split(" CUR ", 1)
                cpart, zpart = (rest.split(" Z ", 1) + [""])[:2]
                joints = [float(v) for v in jpart.strip("[]").split(",")]
                currents = {}
                for kv in cpart.strip("{}").split(", "):
                    if ":" in kv:
                        k, v = kv.split(":")
                        currents[int(k)] = float(v)
                z = float(zpart) if zpart not in ("", "None") else None
                return ArmState(joints=joints, currents=currents, tool_z_mm=z)
            except (ValueError, IndexError):
                continue
    raise UnsafeStateError("STATE 解析失败（臂无响应或驱动异常）: %r" % out[-120:])


class CreateBlockExecutor(Executor):
    """安全层内置：双反馈门 / 电流熔断 / 启动自检 / 限位校验。"""

    def __init__(self, runner: CodeRunner, velocity: int = 50):
        self.runner = runner
        self.velocity = velocity
        self._code = ARM_CODE.format(velocity=velocity)
        self._startup_ok = False

    # -- 基础指令 --
    def _exec(self, args: list) -> ArmState:
        return parse_state(self.runner.run(self._code, args))

    def read_state(self) -> ArmState:
        return self._exec([])

    def set_joint(self, name: str, rad: float, interval_ms: int = 1000) -> ArmState:
        if name not in JOINT_LIMITS:
            raise ValueError("未知关节 %s" % name)
        lo, hi = JOINT_LIMITS[name]
        if not (lo - 1e-6 <= rad <= hi + 1e-6):
            raise UnsafeStateError("关节 %s 目标 %.3f 超限位 [%.3f, %.3f]" % (name, rad, lo, hi))
        idx = JOINT_ORDER.index(name)
        state = self._exec(["set", name, "%.4f" % rad, str(interval_ms)])
        # 双反馈门：角度跟踪
        err = abs(state.joints[idx] - rad)
        if err >= ANGLE_TRACK_TOL:
            raise UnsafeStateError(
                "关节 %s 跟踪失败: 命令 %.3f 回读 %.3f（差 %.3f）——疑似卡阻/驱动保护"
                % (name, rad, state.joints[idx], err))
        return state

    def check_currents(self, state: ArmState) -> None:
        loaded = [state.currents.get(s, 0.0) for s in (2, 3)]  # 肘/腕承载关节
        if any(c > CURRENT_SPIKE_A for c in loaded):
            raise UnsafeStateError("电流尖峰 %s —— 立即回退" % state.currents)
        # 注：带载关节 0A 在两种状态出现（驱动保护/完全卸载），由角度跟踪门兜底

    def set_gripper(self, rad: float) -> ArmState:
        return self._exec(["grip", "%.4f" % rad])

    def home(self) -> ArmState:
        return self._exec(["home"])

    # -- 启动自检（docs/09 安全层：z<30mm 判趴伏拒任务）--
    def startup_check(self) -> ArmState:
        state = self.read_state()
        if len(state.joints) != 6:
            raise UnsafeStateError("启动自检失败：关节读数不全 %s" % state.joints)
        if state.tool_z_mm is not None and state.tool_z_mm < STARTUP_MIN_TOOL_Z_MM:
            raise UnsafeStateError(
                "启动自检失败：工具 z=%.1fmm 低于 %.0fmm —— 趴伏构型，"
                "先执行关节反序解卡（docs/08 §10.1），禁用 home()"
                % (state.tool_z_mm, STARTUP_MIN_TOOL_Z_MM))
        self._startup_ok = True
        return state

    # -- Executor 接口（接五层骨架的通用原语）--
    def execute(self, primitive: Primitive) -> dict:
        if not self._startup_ok:
            self.startup_check()
        from ..primitives.library import MoveTo, SetGripper  # 局部导入避环
        if isinstance(primitive, MoveTo):
            state = self.home() if primitive.pose_name.upper() == "HOME" else self.read_state()
        elif isinstance(primitive, SetGripper):
            state = self.set_gripper(1.0 if primitive.open else 0.0)
        else:
            raise NotImplementedError("CreateBlock 原语走 primitives.createblock 编排函数")
        return {"joints": state.joints, "currents": state.currents,
                "held": state.held}
