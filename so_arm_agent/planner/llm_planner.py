"""LLM/VLM 规划器：DeepSeek-Vision 低频看图咨询 -> 原语序列（06 号定稿架构）。

协议: 渲染帧(base64) + CV 检测摘要 + 任务 -> JSON {primitives: [...]}
- 视觉通道看整体布局，CV 通道给精确坐标（双通道互补，jev-drone 符号化定理）
- 输出严格 JSON，解析失败抛错（由 agent 的重规划循环兜底）
- 需要 DEEPSEEK_API_KEY 环境变量；模型 deepseek-v4-flash-vision-exp（13s/次，低频使用）
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request

from ..types import MoveTo, Point2, Primitive, PushToward, SetGripper, Task
from ..perception.base import Perception
from .base import Perception, Planner

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = os.environ.get("SO_ARM_AGENT_MODEL", "deepseek-v4-flash-vision-exp")

SYSTEM_PROMPT = """你是机械臂任务规划器。桌面俯视图中有一只夹爪和若干彩色圆块（毫米坐标）。
你的职责：为"把指定色块推到目标点"生成原语序列。可用原语：
- {"type": "move_to", "pose": "PRE_PUSH"}        移动到预推送位
- {"type": "gripper", "open": true|false}         开/合夹爪
- {"type": "push_toward", "color": "红|蓝|绿", "goal": [x, y]}  把色块沿直线推向 (x,y)
工作区 300x200mm（原点左上）。只输出 JSON: {"primitives": [...], "reason": "一句话"}"""


class LLMPlanner(Planner):
    def __init__(self, api_key: str | None = None) -> None:
        self.key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.calls = 0

    def consult(self, perception: Perception, task: Task,
                feedback=None) -> list[Primitive]:
        if not self.key:
            raise RuntimeError("LLMPlanner 需要 DEEPSEEK_API_KEY（低频咨询, 约 13s/次）")
        self.calls += 1
        frame = getattr(perception, "frame_b64", None)
        content: list[dict] = [{"type": "text", "text": self._user_prompt(perception, task, feedback)}]
        if frame:
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{frame}"}})
        body = json.dumps({
            "model": MODEL, "max_tokens": 8000,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": content}],
        }).encode()
        req = urllib.request.Request(API_URL, data=body, headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
        text = out["choices"][0]["message"].get("content", "").strip()
        return self._parse(text, task)

    def _user_prompt(self, p: Perception, task: Task, feedback) -> str:
        lines = [f"任务: 把{task.object_color}块推到 ({task.target.x:.0f},{task.target.y:.0f})mm 邻域 {task.tolerance_mm:.0f}mm",
                 "当前检测(CV精确坐标):"]
        for o in p:
            lines.append(f"  {o.color}块 @ ({o.center.x:.0f},{o.center.y:.0f})")
        if feedback is not None:
            lines.append(f"上一轮反馈: {getattr(feedback, 'note', feedback)}")
        lines.append("给出原语序列。")
        return "\n".join(lines)

    def _parse(self, text: str, task: Task) -> list[Primitive]:
        m = re.search(r"\{.*\}", text, re.S)
        d = json.loads(m.group(0) if m else text)
        prims: list[Primitive] = []
        for item in d.get("primitives", []):
            t = item.get("type")
            if t == "move_to":
                prims.append(MoveTo(item.get("pose", "PRE_PUSH")))
            elif t == "gripper":
                prims.append(SetGripper(open=bool(item.get("open", True))))
            elif t == "push_toward":
                gx, gy = item.get("goal", [task.target.x, task.target.y])
                prims.append(PushToward(item.get("color", task.object_color),
                                         Point2(float(gx), float(gy))))
        if not prims:
            raise ValueError(f"LLM 未给出可用原语: {text[:120]}")
        return prims
