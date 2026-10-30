#!/usr/bin/env python3
"""任务套件：N 个布局 × M 次重复，统计成功率与平均轮数（scripted 感知真实测）。

用法: python3 scripts/run_suite.py [--runs 5] [--out suite_results.md]
依赖: numpy opencv-python-headless（感知走真渲染+真CV）
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from so_arm_agent.agent import Agent
from so_arm_agent.evidence import Evidence
from so_arm_agent.executor.mock import MockExecutor
from so_arm_agent.perception.mock import MockScene
from so_arm_agent.perception.opencv_camera import RenderedCamera
from so_arm_agent.planner.scripted import ScriptedPlanner
from so_arm_agent.types import Point2, Task

# 5 个任务: 不同色块/布局/目标（含近距/远距/对角线/多物体干扰布局）
TASKS = [
    ("T1-推红左近", {"objects": {"红": (220.0, 100.0), "蓝": (120.0, 160.0)},
      "task": Task("红", Point2(30.0, 100.0))}),
    ("T2-推蓝右远", {"objects": {"红": (60.0, 40.0), "蓝": (40.0, 170.0)},
      "task": Task("蓝", Point2(270.0, 60.0))}),
    ("T3-对角线", {"objects": {"红": (260.0, 30.0), "蓝": (260.0, 170.0)},
      "task": Task("红", Point2(40.0, 170.0))}),
    ("T4-三物干扰", {"objects": {"红": (150.0, 100.0), "蓝": (140.0, 90.0), "绿": (200.0, 150.0)},
      "task": Task("绿", Point2(60.0, 40.0))}),
    ("T5-贴边目标", {"objects": {"红": (30.0, 180.0), "蓝": (250.0, 30.0)},
      "task": Task("红", Point2(270.0, 25.0))}),
]


def run_once(objects, task) -> tuple[bool, int]:
    scene = MockScene(objects=dict(objects))
    agent = Agent(planner=ScriptedPlanner(), camera=RenderedCamera(scene),
                  executor=MockExecutor(scene), evidence=Evidence(), max_replans=6)
    result = agent.run(task)
    return result.success, result["attempts"]


def main() -> int:
    runs = 5
    if "--runs" in sys.argv:
        runs = int(sys.argv[sys.argv.index("--runs") + 1])
    out = Path("suite_results.md")
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])

    rows = []
    t0 = time.time()
    for name, spec in TASKS:
        oks, atts = [], []
        for _ in range(runs):
            ok, att = run_once(spec["objects"], spec["task"])
            oks.append(ok)
            atts.append(att)
        rows.append((name, sum(oks) / len(oks) * 100, statistics.mean(atts)))
        print(f"  {name}: {sum(oks)}/{len(oks)}  平均轮数 {statistics.mean(atts):.1f}", flush=True)

    total = sum(r[1] for r in rows) / len(rows)
    lines = [
        "# 任务套件结果（scripted planner + 真渲染 + 真 CV 感知 + mock 执行）",
        "",
        f"- 每任务 {runs} 次 | 总平均成功率 **{total:.0f}%** | 生成于 {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 任务 | 成功率 | 平均轮数 |", "|---|---|---|",
    ]
    lines += [f"| {n} | {sr:.0f}% | {a:.1f} |" for n, sr, a in rows]
    lines += ["", "说明: 感知链（渲染→OpenCV 色块检测）为真实算法实测; 执行为 mock"
             "（臂重装后换真机 TCP executor 重跑本表）。"]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n平均成功率 {total:.0f}% | 明细 -> {out} | 耗时 {time.time()-t0:.1f}s")
    return 0 if total == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
