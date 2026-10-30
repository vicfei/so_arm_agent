"""真感知闭环测试: 渲染->CV 检测精度 + 完整 mock 任务（真感知件）。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from so_arm_agent.agent import Agent
from so_arm_agent.evidence import Evidence
from so_arm_agent.executor.mock import MockExecutor
from so_arm_agent.perception.mock import MockScene
from so_arm_agent.perception.opencv_camera import OpenCVDetector, RenderedCamera, Renderer
from so_arm_agent.planner.scripted import ScriptedPlanner
from so_arm_agent.types import Point2, Task


class TestPerceptionPrecision(unittest.TestCase):
    def test_roundtrip_accuracy(self):
        scene = MockScene(objects={"红": (220.0, 100.0), "蓝": (120.0, 160.0)})
        cam = RenderedCamera(scene)
        p = cam.observe()
        self.assertEqual(len(p), 2)
        for det in p:
            tx, ty = scene.objects[det.color]
            err = ((det.center.x - tx) ** 2 + (det.center.y - ty) ** 2) ** 0.5
            self.assertLess(err, 3.0, f"{det.color} 检测误差 {err:.2f}mm 超标")

    def test_missing_color_not_detected(self):
        scene = MockScene(objects={"红": (50.0, 50.0)})
        cam = RenderedCamera(scene)
        p = cam.observe()
        colors = {d.color for d in p}
        self.assertEqual(colors, {"红"})


class TestRealPerceptionLoop(unittest.TestCase):
    def test_full_task_with_real_perception(self):
        scene = MockScene(objects={"红": (220.0, 100.0), "蓝": (120.0, 160.0)})
        task = Task(object_color="红", target=Point2(30.0, 100.0), tolerance_mm=25.0)
        agent = Agent(planner=ScriptedPlanner(), camera=RenderedCamera(scene),
                      executor=MockExecutor(scene), evidence=Evidence(), max_replans=5)
        result = agent.run(task)
        self.assertTrue(result.success)
        self.assertGreaterEqual(result["attempts"], 2)  # 首轮否决后收敛


if __name__ == "__main__":
    unittest.main()
