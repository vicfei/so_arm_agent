#!/usr/bin/env python3
"""MVP mock 演示：推 X 到 Y（"把红块推到左侧标记处"）。

含一次 supervisor 否决（首次提案越界）与多轮推送收敛（行程 80mm < 初始距离），
全程证据落盘 evidence/。零外部依赖。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from so_arm_agent.agent import Agent
from so_arm_agent.evidence import Evidence
from so_arm_agent.executor.mock import MockExecutor
from so_arm_agent.perception.mock import MockCamera, MockScene
from so_arm_agent.planner.scripted import ScriptedPlanner
from so_arm_agent.types import Point2, Task


def main() -> int:
    scene = MockScene(objects={"红": (220.0, 100.0), "蓝": (120.0, 160.0)})
    task = Task(object_color="红", target=Point2(30.0, 100.0), tolerance_mm=25.0)

    agent = Agent(
        planner=ScriptedPlanner(),
        camera=MockCamera(scene),
        executor=MockExecutor(scene),
        evidence=Evidence(),
        max_replans=5,
    )
    result = agent.run(task)

    print("场景：红块@ (220,100)，蓝块@ (120,160)；任务：把红块推到 (30,100) 邻域 25mm")
    print(f"结果：{'PASS' if result.success else 'FAIL'}  尝试轮数 {result['attempts']}")
    print(f"证据：{result['total']} 条（否决 {result['vetoes']} / 执行 {result['executes']} / 复核 {result['verifies']}）→ {result['path']}")
    print(f"终态：{ {k: (round(v[0]), round(v[1])) for k, v in scene.objects.items()} }")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
