"""Verifier：复核 = 再 observe 一次，判目标邻域；不 ok 给重规划反馈。
真机阶段升级为 VLM 判完成度（同 DeepSeek API 位），接口不变。"""

from __future__ import annotations

from ..types import Task, VerifierFeedback


class Verifier:
    def verify(self, task: Task, perception) -> VerifierFeedback:
        for det in perception:
            if det.color == task.object_color:
                dist = det.center.dist_to(task.target)
                if dist <= task.tolerance_mm:
                    return VerifierFeedback(True, round(dist, 1), "已在目标邻域")
                return VerifierFeedback(
                    False,
                    round(dist, 1),
                    f"距目标 {dist:.0f}mm（容差 {task.tolerance_mm:.0f}），继续从当前位推送",
                )
        return VerifierFeedback(False, -1.0, "目标物体不在视野")
