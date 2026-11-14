# 09 · CreateBlock Agent/Harness 设计（v1，2026-11-14）

> 继承：06 号五层路线 + 08 号真机接入与安全层规格（§10.3）+ 仓内 90% 真闭环代码。
> 本文=CreateBlock 真机 harness 的首版设计，M1-M4 落地后回填实测数据。

## 1. 定位与目标

在 CreateBlock 五自由度臂（Nano B01 + CLB 舵机 + 腕装 640×480 相机）上完成桌面任务
（抓放 / 分拣 / 推移 / 组合），形态 = **云端 LLM 低频规划 + 本地确定性原语执行 +
视觉强制闭环 + 全程证据留痕**。不训练模型（06 号定稿不变）。

## 2. 部署拓扑（三层脑）

```
┌─ 大脑（云端，低频 1-3 次/任务）─ DeepSeek-Vision / GLM-4V / Kimi
│    任务理解 → 原语序列 JSON；异常时看证据重规划
├─ 小脑（Nano 本地 harness，Python ~300MB）─ 常驻
│    任务状态机 / 原语库 / 感知 / 验证 / 安全层 / evidence
│    直连 /dev/ttyTHS1（舵机）+ FrameSource（双模式相机）
└─ 反射（确定性原语，永远本地不经 LLM）─ 关节指令+电流监护
```

- **D1 harness 跑在 Nano**：串口直连零中继、断网可继续执行已下发序列、4GB 足够
  （headless 省桌面 ~500MB）。WSL/Win11 是开发面：代码 rsync 上去，evidence 拉回来。
- **D6 FrameSource 双模式**：`cam@nano`（/dev/video0 直读）与 `cam@laptop`
  （HTTP MJPEG 从笔记本拉帧，笔记本侧跑帧服务）抽象统一——相机插哪都能跑
  （两种形态都已实测）。

## 3. 模块与接口

```
Task(自然语言) ─→ Planner ─→ Plan[{primitive, args}...] ─→ Supervisor(否决/装配)
                                                                    │
   Evidence(帧+状态+电流 JSONL) ←── Executor(真机|仿真) ←── Primitives(确定性)
                    │                                              │
                    └──────→ Verifier(三态) ──失败──→ Replan(带证据)
```

| 模块 | 设计要点 |
|---|---|
| **Planner** | 云 API 注入式（复用 DeepSeek 通道）；输入=任务文本+场景摘要（检测物体列表+坐标，不传大图省时延）；输出=原语序列 JSON schema 校验。降级链：DeepSeek→GLM→ScriptedPlanner（预置脚本，无网可用） |
| **Perception** | 今日 HSV 检测器类化：`detect(color) -> {FOUND(bbox)/NONE/UNCERTAIN}` **三态强制**；`frame()`；预留 TensorRT 检测器插拔位（DLI 迁移学习路径） |
| **Primitives** | 今日三段管线的原语化（全部实测过）：`scan_for(target)`（高位横扫+关节阶梯俯扫）· `center(target)`（锚点对中，实测符号探针）· `grasp()`（张爪→缓降→遮挡触发→闭爪→四重验证）· `release(zone)` · `push(from,to)` · `home()/pose(name)` · `read_state()` |
| **Executor** | `CreateBlockExecutor`（真机：Nano 本地 uServo / 兼容保留 SSH 模式）与 `SimExecutor`（pybullet 同构，11-08 验证）双后端，**仿真排练→真机执行**是默认路径 |
| **Verifier** | 判据三通道：夹爪角（>0.12rad=持物）+ 闭爪电流（>0.3A 对抗）+ 前后帧差比对；**VLM 只做复核提示不当法官**（11-14 两次幻觉实锤）；输出 PASS/FAIL/UNCERTAIN |
| **Supervisor** | 否决权：工作区半径 ≤150mm、速度 ≤80dps、电流 ≤1.2A、禁用位姿表（趴伏构型禁 home()）；每步装袋进 evidence |
| **Evidence** | 每原语一组：指令 JSON + 关节回读 + 电流 + 关键帧（自动落盘，今日 8 帧取证模式的自动化）；JSONL 索引；预留 LeRobot 数据集导出（示教线复用） |

## 4. 安全层（08 §10.3 六条，工程化嵌入 Executor）

1. 相机按设备名寻址（laptop 模式）；每动作后强制抓帧留证
2. 每步双反馈门（电流>0.2A 且角度跟随），0 电流=驱动保护→**任务熔断+人介入提示**（断电重启是唯一解，不自愈）
3. 缓降步进（j3 +0.06/步）+ 遮挡检测触发 + 电流>1.2A 自动回退两步
4. 近场操作走关节空间直控；IK 仅用于位姿库合法目标（显式 pitch 会被静默拒且警告在 stderr）
5. 对中循环用实测符号（±Δ 探针一次），不推算符号
6. 检测三态+NONE 出口；检测置信不足时变位姿重扫而非硬选

**启动自检**（新任务前置）：读 6 舵机电流基线+工具 z——z<30mm 或任一电流≈0
即判定趴伏/驱动关闭态，拒任务并报告。

## 5. 失败模式与对策

| 失败 | 对策 | 级别 |
|---|---|---|
| 舵机驱动保护关闭 | 熔断+人介入（断电重启） | 不可自愈 |
| 检测 NONE/UNCERTAIN | 变位姿重扫（≤3 次）→ 上报带帧 | 自愈 |
| LLM 超时/限额 | Scripted 降级 | 自愈 |
| Wi-Fi 断 | 已下发序列本地继续；新规划暂停缓存 | 自愈 |
| 抓空（四重验证失败） | 抬起→重新 scan→center→grasp（≤2 轮）→ 上报 | 自愈 |
| 相机被臂遮挡 | scan 位姿表轮换（今日多站位思路） | 自愈 |

## 6. 评估

- 任务套件（复用 run_suite 框架）：抓白块 / 抓指定色块 / 推移到区 / 放入桶 / 双物排序
- 指标：成功率、人工干预次数、原语耗时分布、重规划率、验证 UNCERTAIN 率
- 每任务 evidence 全留档（回传 WSL 归档）

## 7. 里程碑

- **M1 真机原语层**（无 LLM）：FrameSource 双模式 + 四原语类化 + 启动自检。
  **状态（11-14 深夜）：代码层已落仓**（perception/framesource+hsv_detector、
  executor/createblock 含安全层与双 CodeRunner、primitives/createblock 四原语，
  21/21 单测绿）。**待真机验收：臂通电后插头任务 3/3 复跑**。
- **M2 云脑接入**：Planner（DeepSeek）+ Supervisor/Evidence 完整化。
  验收："把桌上白色物体夹起来"自然语言一句进、evidence 全链出。
- **M3 仿真排练默认化**：动作序列先 SimExecutor 走通再上真机；任务套件 5 项跑分。
- **M4 感知升级**：TensorRT 检测器（DLI 迁移学习）替换 HSV；舵机精度体检实验
  （重复定位散布实测，验证 ±5-10mm 估计）。

## 8. 与现有仓的映射

复用：五层骨架 / supervisor / evidence / mock-sim 双后端模式 / 任务套件 / CI。
新增：`primitives/createblock.py`（四原语）、`executor/createblock.py`（真机+安全层）、
`perception/hsv_detector.py`（三态）、`perception/framesource.py`（双模式）、
`planner/cloud.py`（降级链）、`deploy/`（rsync 到 Nano + 常驻方式）。
