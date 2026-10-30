# 07 · 生态扫描：四仓画像与借鉴清单（2026-10-22）

对 RUA/harness 赛道四个代表性仓库的代码前走读（元数据 + README 级），结论先行的对照表：

| 仓库 | ★ | 核心主张 | 训练 | 硬件 | 许可 | 对本仓价值 |
|---|---|---|---|---|---|---|
| hao-ai-lab/ORA | 72 | 开源权重 LLM（DeepSeek-V4.1-Flash）零样本控机器人，无 VLA 无示教 | 零训练 | 仅仿真，需 ≥32GB 显存 | Apache-2.0 | ★★★ supervisor + evidence 模式 |
| Darwin-Agent/HarnessPAI | 37 | 进化式线束：运行时冻结程序，跨 rollout 由编码智能体修订并蒸馏轨迹反哺 π0.5 | 轨迹→微调 | 仅仿真，重基建 | 无许可 | ★★ 两时间尺度设计 |
| terminalworld/OpenRUA | 10 | Claude Code/Codex 经 ROS 2 控任意机器人，感知控制由运行时写码涌现 | 零训练 | Panda/WidowX/Cobot Magic + YAML 桥接 | Apache-2.0 | ★★★ workspace-as-harness、ZCode 插件位 |
| WindyLab/GenSwarm | 31 | LLM 生码控集群（西湖 IUSL） | 零训练 | 自研集群+Vicon，不可复现 | 无许可 | ★ 跳过 |

## 关键判断

1. **06 号设计与赛道主流同频**：原语层否决权 = ORA supervisor；OpenCV 符号化感知 = OpenRUA
   "perception as file I/O"；verifier 重规划 = HarnessPAI outcome check；DeepSeek 当 planner =
   ORA 的模型选型。设计不用改，放心建。
2. **生态位空着**：四家全部仿真优先/大算力/特殊硬件。**真机 SO-101 + 8GB 消费卡 + lerobot 生态**
   无人占据；OpenRUA 文档把若干 agent 运行时列为"未验证的插件智能体"。
3. **可借件**（落进骨架）：
   - ORA evidence recording：请求/工具调用/动作/回执全落盘可回放 → `evidence.py`
   - ORA supervisor：模型不可绕过的执行前审查 → `supervisor.py`（否决权）
   - OpenRUA workspace-as-harness：机器人文档+工具契约进工作区让 planner 自读（真机阶段做）
   - HarnessPAI 两时间尺度：rollout 内冻结计划不在线决策、跨 rollout 才改程序——正是
     "低频咨询"的理论包装；其轨迹蒸馏管线留作训练线重开时的接口

## 来源

- 元数据 2026-10-22 实测（GitHub API）；README 走读同日。
- 9 仓老画像见旅程仓 `references-robot-harness-landscape.md`（2026-10-20，含 SO-ARM 生态）。
