#!/usr/bin/env python3
"""90% 真闭环演示：真渲染帧 + 真 OpenCV 感知 + mock 执行（唯一模拟件=电机转动）。

用法:
  python3 scripts/run_real_perception_demo.py              # scripted planner（零网络）
  DEEPSEEK_API_KEY=... python3 scripts/run_real_perception_demo.py --llm
依赖: numpy opencv-python-headless（LLM 模式另需网络与 key）
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from so_arm_agent.agent import Agent
from so_arm_agent.evidence import Evidence
from so_arm_agent.executor.mock import MockExecutor
from so_arm_agent.perception.mock import MockScene
from so_arm_agent.perception.opencv_camera import RenderedCamera, Renderer
from so_arm_agent.planner.scripted import ScriptedPlanner
from so_arm_agent.types import Point2, Task
from so_arm_agent.perception.base import Perception


class ReportingCamera(RenderedCamera):
    """在 Perception 上附带帧的 base64（供 LLM 视觉通道）。"""

    def observe(self):

        p = super().observe()
        import cv2
        ok, buf = cv2.imencode(".jpg", self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            p.frame_b64 = base64.b64encode(buf).decode()  # 动态属性, LLMPlanner 读取
        return p


def main() -> int:
    scene = MockScene(objects={"红": (220.0, 100.0), "蓝": (120.0, 160.0)})
    task = Task(object_color="红", target=Point2(30.0, 100.0), tolerance_mm=25.0)

    planner = ScriptedPlanner()
    if "--llm" in sys.argv:
        from so_arm_agent.planner.llm_planner import LLMPlanner
        planner = LLMPlanner()

    # 感知精度自检: 渲染->检测 与 场景真值对比
    cam = ReportingCamera(scene)
    p0 = cam.observe()
    print("== 感知精度自检（渲染->CV检测 vs 真值）==")
    for det in p0:
        tx, ty = scene.objects[det.color]
        err = ((det.center.x - tx) ** 2 + (det.center.y - ty) ** 2) ** 0.5
        print(f"  {det.color}块: 检测({det.center.x:.1f},{det.center.y:.1f}) 真值({tx:.0f},{ty:.0f}) 误差 {err:.2f}mm")

    agent = Agent(planner=planner, camera=cam,
                  executor=MockExecutor(scene), evidence=Evidence(), max_replans=5)
    result = agent.run(task)

    print(f"\n== 闭环结果 ==")
    print(f"模式: {'LLM(DeepSeek-Vision)' if '--llm' in sys.argv else 'scripted'} | 感知: 真渲染+真CV | 执行: mock")
    print(f"{'PASS' if result.success else 'FAIL'}  轮数 {result['attempts']} | 证据 {result['total']} 条 -> {result['path']}")
    print(f"终态: { {k: (round(v[0]), round(v[1])) for k, v in scene.objects.items()} }")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
