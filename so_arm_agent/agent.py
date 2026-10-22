"""主循环：任务 → plan → supervisor 审查 → execute → verify → 重规划。"""

from __future__ import annotations

from .evidence import Evidence
from .executor.base import Executor
from .perception.base import Camera
from .planner.base import Planner
from .primitives import describe
from .supervisor import Supervisor
from .types import Task, VerifierFeedback
from .verifier import Verifier


class AgentResult(dict):
    @property
    def success(self) -> bool:
        return bool(self.get("success"))


class Agent:
    def __init__(
        self,
        planner: Planner,
        camera: Camera,
        executor: Executor,
        supervisor: Supervisor | None = None,
        verifier: Verifier | None = None,
        evidence: Evidence | None = None,
        max_replans: int = 5,
    ) -> None:
        self.planner = planner
        self.camera = camera
        self.executor = executor
        self.supervisor = supervisor or Supervisor()
        self.verifier = verifier or Verifier()
        self.evidence = evidence or Evidence()
        self.max_replans = max_replans

    def run(self, task: Task) -> AgentResult:
        feedback: VerifierFeedback | None = None
        for attempt in range(1, self.max_replans + 1):
            perception = self.camera.observe()
            plan = self.planner.consult(perception, task, feedback)
            self.evidence.log(
                "plan",
                {"attempt": attempt, "steps": [describe(p) for p in plan]},
            )

            aborted = False
            for primitive in plan:
                verdict = self.supervisor.approve(primitive, task)
                if not verdict.approved:
                    self.evidence.log(
                        "veto",
                        {"attempt": attempt, "primitive": describe(primitive), "reason": verdict.reason},
                    )
                    feedback = VerifierFeedback(False, -1.0, f"supervisor 否决：{verdict.reason}")
                    aborted = True
                    break
                receipt = self.executor.execute(primitive)
                self.evidence.log("execute", {"attempt": attempt, **receipt})

            if aborted:
                continue  # 带否决理由重规划

            feedback = self.verifier.verify(task, self.camera.observe())
            self.evidence.log(
                "verify",
                {"attempt": attempt, "ok": feedback.ok, "distance_mm": feedback.distance_mm},
            )
            if feedback.ok:
                return AgentResult(success=True, attempts=attempt, **self.evidence.summary())

        return AgentResult(success=False, attempts=self.max_replans, **self.evidence.summary())
