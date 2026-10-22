"""闭环测试：mock 推送任务达成 + 否决发生 + 证据落盘。零依赖 unittest。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from so_arm_agent.agent import Agent
from so_arm_agent.evidence import Evidence
from so_arm_agent.executor.mock import MockExecutor
from so_arm_agent.perception.mock import MockCamera, MockScene
from so_arm_agent.planner.scripted import ScriptedPlanner
from so_arm_agent.types import Point2, Task


class TestMockLoop(unittest.TestCase):
    def test_push_task_succeeds_with_veto_and_evidence(self):
        scene = MockScene(objects={"红": (220.0, 100.0)})
        task = Task(object_color="红", target=Point2(30.0, 100.0), tolerance_mm=25.0)
        with tempfile.TemporaryDirectory() as td:
            agent = Agent(
                planner=ScriptedPlanner(),
                camera=MockCamera(scene),
                executor=MockExecutor(scene),
                evidence=Evidence(log_dir=td),
                max_replans=5,
            )
            result = agent.run(task)

            self.assertTrue(result.success)
            self.assertLessEqual(result["attempts"], 5)
            # 首轮越界提案被否决
            self.assertGreaterEqual(result["vetoes"], 1)
            # 多轮推送收敛：至少执行 2 次 push
            self.assertGreaterEqual(result["executes"], 2)
            # 红块确实进入目标邻域
            fx, fy = scene.objects["红"]
            self.assertLess(((fx - 30.0) ** 2 + (fy - 100.0) ** 2) ** 0.5, 25.0)
            # 证据文件真实存在且非空
            ev = agent.evidence
            self.assertTrue(Path(ev.path).exists())
            self.assertEqual(len(ev.records), result["total"])

    def test_object_not_in_view_fails_honestly(self):
        scene = MockScene(objects={"蓝": (100.0, 100.0)})
        task = Task(object_color="红", target=Point2(30.0, 100.0))
        agent = Agent(
            planner=ScriptedPlanner(),
            camera=MockCamera(scene),
            executor=MockExecutor(scene),
            evidence=Evidence(log_dir=tempfile.mkdtemp()),
            max_replans=2,
        )
        result = agent.run(task)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
