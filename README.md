# so_arm_agent

[![CI](https://github.com/vicfei/so_arm_agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vicfei/so_arm_agent/actions/workflows/ci.yml)

Robot Use Agent for SO-ARM101：不训练模型，用 LLM/VLM（API，低频咨询）驱动确定性原语完成桌面任务。

> 设计定稿见 [docs/06-robot-use-agent-roadmap.md](docs/06-robot-use-agent-roadmap.md)（2026-10-20，自
> robot-learning-journey 迁入，本仓即该路线的设计文档+代码仓）。生态扫描与借鉴清单见
> [docs/07-landscape-2026-10.md](docs/07-landscape-2026-10.md)（ORA / OpenRUA / HarnessPAI / GenSwarm）。

## 架构（四件套，06 号定稿）

```
任务（自然语言）
    ▼
Planner: DeepSeek-Vision 低频看图 → 原语序列 + 目标坐标   [planner/]
    ▼
原语层（确定性代码, 零训练）:
    move_to(位姿库) / gripper(open/close) / push_toward  [primitives/]
    ▼
Supervisor: 原语否决权 + 证据落盘（ORA 借鉴）            [supervisor.py, evidence.py]
    ▼
Executor: TCP 桥 → 度数级舵机控制（mock 先行）           [executor/]
    ▼
Verifier: 复拍一帧 → 判完成度 → 带反馈重规划             [verifier/]
```

分层契约见 [docs/design/architecture.md](docs/design/architecture.md)。

## 90% 真闭环（mock 执行外的全真链路）

感知与规划不走任何假件——渲染器把模拟桌面画成真实 BGR 帧，OpenCV 做 HSV 色块检测
（实测往返误差 0.00mm），LLM 规划器看渲染帧低频出原语（DeepSeek-Vision，约 13s/次）。
**唯一的模拟件是电机转动**（mock executor 直接更新场景状态）——臂重装后换真机 TCP
executor，其余代码零改动。

```bash
python3 scripts/run_real_perception_demo.py              # scripted（零网络）
DEEPSEEK_API_KEY=... python3 scripts/run_real_perception_demo.py --llm   # 真 LLM 规划
python3 scripts/run_suite.py                             # 5 任务成功率表
```

两种模式均已实测 PASS（scripted 4 轮 / LLM 3 轮完成推送）；任务套件 5 任务全绿
（见 [suite_results.md](suite_results.md)）。

## 状态

- **2026-10-22**: 建仓；mock 闭环骨架。
- **2026-10-29**: 90% 真闭环——真渲染+真 CV 感知（0.00mm 精度）+ LLM 规划插槽 + 任务套件 5/5；CI 上线。
- 真机件待臂重装：像素→工作区标定、预设位姿库、TCP 桥接入（照 SO101_QUICKSTART）。

## 跑 mock 演示

```bash
python3 scripts/run_mock_demo.py          # 零依赖，任何 Python 3.10+
python3 -m unittest discover -s tests     # 闭环测试
```

演示内容：模拟桌面 + 色块 + 假相机，agent 把红块推到左侧目标区——包含一次**越界否决**
（supervisor 拦截 planner 的非法提案）与**多轮推送收敛**（verifier 反馈驱动重规划），
全程证据落盘 `evidence/evidence-*.jsonl`。

## 约定

- mock 路径零外部依赖；真机路径依赖 SO-101 TCP 桥（`~/services/robotics`，勿在本仓复制）。
- 与 cheetah-llm-driver（遛狗线）共享 planner 插槽 + 原语 + verifier 架构，双仓互引。
- 训练线冻结（02/04 号负结果定案）；若重开见旅程仓归档。
