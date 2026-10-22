# 06 · 路线转向：Robot Use Agent（SO-ARM101 × Agent Harness × 开源模型）

> 2026-10-20 定稿。本文件取代原"实验 4 第二档（带视觉 smolvla 微调）"的规划——
> 训练线正式挂起，全部真机精力转向 **Agent Harness 路线**：不训练模型，
> 用 LLM/VLM（API）驱动 SO-ARM101 的确定性原语完成任务。

## 为什么转向（决策依据，全部来自本仓库实测）

1. **训练线三连负结果**：02 号（跨域蒸馏方向可白嫖/绝对坐标死穴）、实验 1（三路对照瓶颈终判在小脑——base 5% > oracle 2.5% > vlm 0%）、实验 4 一档（MLP 开环 0.41° 闭环崩,goal 通道被数据结构淹没）
2. **生态判断**：RoboHarness 公开宣战"harness 打败 VLA"；ORA 用同款 DeepSeek 零样本在 RoboTwin/LIBERO-Pro 拿到 69%/81%——模型够了,缺的是 harness 工程
3. **硬件约束天然排除训练**：8GB 消费卡 + WSL2 无 sudo,而 harness 路线的算力在云端 API,本地零负担
4. 一句话：**模仿学习的成败在数据分布而非网络（01/02/4 三部曲验证）,而 harness 把"数据从哪来"的问题直接消掉了**

## 架构（四块现成资产重组）

```
任务（自然语言, 如"把橡皮推到左边标记处"）
    ▼
Planner: DeepSeek-Vision 看相机帧 → 原语序列 + 目标坐标
    │      （已验证: 读图准/JSON 输出干净/13s 每次→低频决策设计）
    ▼
原语层（确定性代码, 零训练）:
    move_to(位姿库) / gripper(open/close) / push_toward(像素目标)
    ▼
Executor: TCP 桥 → 度数级舵机控制
    │      （05 号: 桥 v3.2 + SDK 四层 patch + 校准, 全部闭环）
    ▼
Verifier: 复拍一帧 → VLM 判完成度 → 超阈值带反馈重规划
          （03 号遛狗的 planner/executor/verifier 三件套整体平移）
```

## 三个待建技术件（各 ~半小时现场工作）

1. **像素→工作区标定**：爪子放桌面 4-5 个已知点,记录相机像素,拟合映射
2. **预设位姿库**：HOME / 预抓取 / 下探 / 推送姿态,手动示教存档
3. **平面任务优先**：5DOF 无深度信息——推/拨/铲先做,抓取用固定桌面高度假设后置

## 任务阶梯

| 级 | 任务 | 新增能力 |
|---|---|---|
| MVP | 推 X 到 Y（VLM 定位→映射→推→复核重试） | 闭环全通 |
| L2 | 按颜色/类别分拣（"红色都推到左边"） | 多物体+序列规划 |
| L3 | 固定高度抓放 | 抓取原语 |
| L4 | 长程组合（叠积木/清空桌面） | 子任务链+记忆层 |

## 建仓目标

SO-ARM 生态调研（05 号 + 9 仓画像）确认: VLM-agent 驱动的 Python 仓接近空白
（唯一近缘 jixinyan/Embodied-DeepSeek-Harness 为 TypeScript 5⭐）。**so-arm-agent**
与 cheetah-llm-driver 共享架构（planner 插槽+原语+verifier）,双仓互相引用。

## 生态参照系（9 仓画像摘要, 2026-10-20）

- 执行参照: TheRobotStudio/SO-ARM100（鼻祖 7.8k⭐）、ros-physical-ai/ros2_so_arm（ROS 2/MoveIt 现成包 102⭐）
- 硬件升级: roboninecom 平行夹爪（193⭐, 3D 打印, 兼容 STS3215）——抓取能力质变,重装时考虑
- 同路线样本: jixinyan/Embodied-DSH（插件化 agent×机器人）; 弃用的对标: squint（视觉 RL, 训练线遗产）

## 与已有实验的关系

- 03 号遛狗 = 本路线在 Cheetah 上的最小验证（四要素闭环全通）
- 实验 1b 教训直接生效: 大脑干预要低频+原语级, 不做逐帧控制
- 02/4 号训练线冻结, 数据与模型留存（reach_dataset.npz / reach_mlp*.pt）,
  若未来重开训练线可从当日状态恢复
