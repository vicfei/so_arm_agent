# 08 · CreateBlock Jetson 臂接入实录（2026-11-08）

> SO-101 已退役拆机。当日从开箱到"仿真全通 + 真机抓取三爪复盘"的完整记录，
> 含节点级网络发现与真机 executor 通道的重新定义。所有 IP/端口/凭据按脱敏红线以代称记录。

## 1. 摘要

- CreateBlock（创乐博 loborobot）Jetson Nano B01 五自由度视觉机械臂当日完成接入：
  **SSH 免密通道、舵机总线（6×CLB-S325）、腕装摄像头、pybullet 同构仿真**四条链路全部打通并实测。
- pybullet 仿真全序列验证通过（IK/FK 闭环误差 ~2.5mm）；真机小幅动作 + 视觉抓取首次尝试，
  三爪复盘定位到**检测器在暖光下锁错目标**的根因并已修复，待方块复位后复验。
- **真机执行通道由原计划的 SO-101 式 TCP 桥改为 SSH→Nano→uServo**（详见 §7，executor 规划随之修订）。

## 2. 硬件档案

| 部件 | 规格 |
|------|------|
| 主控 | Jetson Nano B01（4GB，L4T R32.6.1 / JetPack 4.6.1，Ubuntu 20.04） |
| 臂 | 5 自由度 + 平行夹爪（左爪主动、右爪 mimic 齿轮），全铝绿色结构件 |
| 舵机 | CLB-S325 总线舵机 ×6（关节 ID 0-4 + 夹爪 ID 5），总线电压 ~7.4V |
| 摄像头 | 640×480 定焦 UVC，**腕装**（URDF 固定挂 link4，随臂运动） |
| 底座 | 双 USB Hub：Wi-Fi dongle（Nano 无板载 Wi-Fi）+ 外设 |
| 套件软件栈 | ROS 2 Foxy、pybullet、uServo SDK、运动学/轨迹规划、九点标定视觉抓取栈、DLI 教程 |

关键路径：`~/dev_ws/src/arm5dof/`（mechanical/pybullet/uservo/ros2/visual 五包）、
`~/nvdli-data/`（完整视觉抓取栈 + config/vconfig 标定）、`~/Notebook/2.机械臂实验/`（9 个 Jupyter 教程）。

## 3. 控制拓扑与节点约束

```
WSL2 (ZCode 主控)
  │  paramiko（Windows 侧 Miniconda 中继，密钥免密）
  ▼
Jetson Nano（家庭 LAN，DHCP 地址）
  ├─ /dev/ttyTHS1 @115200 8N1（GPIO 硬件串口）→ 6×CLB 舵机
  └─ /dev/video0（腕装摄像头；OpenCV 抓帧 → SFTP 回拉）
```

**节点级发现（重要）**：本机 WSL2 互联网出站正常，但**到局域网网段被 Hyper-V 防火墙拦截**
（Windows 侧扫描可见 LAN 设备、WSL 侧同扫全空）。因此**一切 LAN 操作必须借 Windows 侧**
（PowerShell / Miniconda Python）。另：WSL 的 ICMP socket 在大量并发 ping 后会
`sendmsg: No buffer space available` 且不自愈——LAN 探测一律 TCP connect。
Windows 侧 `python.exe`（WindowsApps）是 Store 假壳（exit 49），真实运行时是 Miniconda。

USB 直连笔记本的路全部证伪：镜像关闭了 USB 设备模式（三根线零枚举）、
Nano 的 USB-A 是主机口（host-to-host 无数据）。**首次配网必须 HDMI 屏+键鼠**。

## 4. 舵机总线协议（uServo，纯 Python 可移植）

帧 = 帧头(2B) + 功能码(1B) + 参数长(1B) + 参数 + 校验和(sum mod 256)。
请求帧头 `12 4C` / 响应帧头 `05 1C`；角度单位 0.1°（int16LE），单圈限 ±180°，死区 3°。

| 功能码 | 语义 |
|--------|------|
| 1 | PING（扫描在线 ID） |
| 3 / 4 | 内存表读 / 写（电压=1 电流=2 功率=3 温度=4） |
| 7 / 9 | 轮式模式 / 阻尼模式（拖动示教入口） |
| 8 / 11 / 12 | 设角度（默认 / 指定周期 / 指定转速） |
| 10 | 查角度（13-16 为多圈变体） |

SDK（`uservo.py` + `arm5dof_uservo.py`）仅依赖 pyserial+numpy，已镜像到
`~/services/robotics/createblock-arm/`（WSL 侧），可脱离 Nano 移植。
已知 SDK 小坑：`set_tool_pose` 软移动成功时返回 None（无 return），不能当失败判据；
`query_temperature` 解码异常（读出 2000°C 级，勿信）。

## 5. pybullet 同构仿真层（已验证）

`Arm5DoFPyBullet` 与真机 `Arm5DoFUServo` **同构接口**（set_joint_angle[_list][_soft] /
set_tool_pose / gripper_* / get_tool_pose），共享同一套运动学与 config 标定。

实测（11-08 晚，GUI 模式直开在 Nano 的 HDMI 屏，Tegra X1 渲染）：
home → 夹爪开合 → joint1 ±0.55rad → object_release → 回 home，7 帧全序列正确；
home(250,0,200)mm 的 IK→FK 回读误差 ~2.5mm（z_error_polyfit 补偿在位）。

SSH 跑 pybullet 的三个要点：
① `create_world` 硬编码 GUI——借 `DISPLAY=:0` + 会话 XAUTHORITY 可把窗口开到 HDMI 屏，
   无屏则 monkeypatch `pybullet.connect`→DIRECT；
② 源码残留 `from turtle import st`——import 前向 `sys.modules` 塞 turtle stub；
③ URDF 相对路径 `../urdf/` 是坑，一律传绝对路径。

## 6. 首次视觉抓取复盘（三爪）

任务：找到桌面红块→拍照→夹取。管线 = 套件原厂流程（俯视位拍照 → HSV 检测 →
九点仿射像素→工作台 mm → IK → 抓取序列），臂先到 `capture_image` 位姿使腕装相机俯视。

| 爪次 | 检测 | 结果 | 归因 |
|------|------|------|------|
| 1 | 出厂 ColorBlockDetector | 0 检出，保险中止 | 出厂 HSV 统计在晚间暖光下失效 |
| 2 | 自研 HSV v1（最大连通域） | 下爪偏位，蹭弹方块 ~6cm，闭合落空（夹爪角 0.028rad） | 暖光下方块本体饱和度跌、旁侧红色反光条反而高饱和——检测锁了反光条 |
| 3 | HSV v2（+长宽比过滤） | 检测锁定真方块（绿框与块重合），但方块已被弹到视野贴边，边缘区仿射误差放大（两批漂移 37mm），稳定性中止 | 方块位置贴边，非检测器问题 |

**修正沉淀**（已固化进脚本）：HSV 红色双区间（H∈[0,12]∪[168,180]，S≥40，V≥50）+
连通域**长宽比 0.5~2.0 过滤**（反光条 aspect≈4.6 一滤即掉）+ 面积≥900px。
定位稳定性门限：两批均值漂移 ≤18mm 且工作区半径 ∈[15,150]mm。
**IK 预检必须用 `auto_gen_pitch`**（默认 π/2 俯仰会误报不可达）。
出厂抓取偏移 (wx-25, wy+10) 保留待净验证。**标定的像素→工作台仿射在视野边缘不可靠**，
有效工作区以中央区域为准。

证据帧：Windows 桌面 `arm_captures\`（检测帧/19 帧序列/抓后帧/四联分析图）。

## 7. so_arm_agent 对接规划（executor 通道修订）

原 06 号设计假设真机走 SO-101 式 TCP 串口桥。**现修订为**：

```
Executor(真机) = SSH(paramiko 中继) → Nano → uServo(ttyTHS1)
Executor(预演) = 同一动作脚本 → Arm5DoFPyBullet（同构接口，零改动切换）
```

- `arm_application.ArmApplication` 对两种臂后端通用（构造注入），grab/move2ws/pose 语义直接复用；
- 感知层：套件 `Image2Workspace`（九点标定）提供像素→工作台坐标，与仓内 OpenCV HSV
  检测层衔接即可得"检测→坐标"真链路（本日 HSV v2 已是可用实现）；
- Verifier：夹爪角反馈（>0.10rad 判定持物）+ 俯视复拍比对，双通道判完成度；
- 首个目标任务维持 design 定稿的 push/grasp 类，场地 = 套件工作台中央区。

## 8. 坑册（当日全集）

1. USB 设备模式被镜像关闭（micro-USB 零枚举）；USB host-to-host 无数据；充电线无枚举事件
2. Nano B01 无板载 Wi-Fi——dongle 在底座 Hub 上，勿拔
3. 首次配网需 HDMI+键鼠；OLED 屏的 IP 显示脚本在无网络时会显示 docker0 的虚拟地址（待修）
4. WSL→LAN 被拦 / ICMP 缓冲不自愈 / Windows python.exe 假壳（§3）
5. 腕装相机：视野随臂姿变化，检测前必须先到 `capture_image` 俯视位
6. 暖光 HSV 漂移 + 反光条误锁（§6 修正）
7. 标定仿射在视野贴边区不可靠
8. 该摄像头产出的 JPEG 直接送 VLM 会解析失败，需重编码一次再送
9. pybullet GUI/turtle/URDF 相对路径三坑（§5）
10. DHCP 地址可能漂移；找回 = Windows 侧扫 SSH 开放主机（10s）

## 9. 待办

- [x] 方块复位后复跑 v2 检测抓取 → 已升级为插头闭环抓取并**成功**（见 §10，2026-11-14）
- [ ] CreateBlockExecutor 落码（executor/ 新增，sim/real 双后端；安全层规格=§10 方法学）
- [ ] Nano 上 OLED IP 显示脚本修掉 docker0 误显
- [ ] 拖动示教（阻尼模式）采轨迹 → LeRobot 格式数据集（第二档路线）
- [ ] 路由器侧给 Nano 绑定固定 DHCP
- [ ] 检测管线补"无目标"出口（弱候选报 NONE，2026-11-14 判卷教训）

## 10. 2026-11-14 续：事故、解卡与首次全自动闭环抓取

### 10.1 事故与根因（两案）

**案一·摄像头身份混乱（全天主坑）**：DirectShow 的相机 index 跨进程漂移，
导致多轮抓帧用错相机（内置/臂摄互换），叠加 VLM 在低光小物体上的两次反光幻觉
（下午 (223,392)、晚 (210,395) 均为不存在的插头）。用户人眼判卷 2/3 后定案。
**根治**：ffmpeg 按设备名寻址（`-i video="USB 2.0 Camera"`），index 永不信任。
臂摄识别特征（用户提供）：褐桌面 + 头顶白炽灯白色光斑 + 贴桌俯视。

**案二·阻尼塌臂卡死**：11-08 收官惯例 `set_damping(0)`（自由模式）+ 收纳 = 重力塌臂
趴底座（死点前兆=工具 z 仅 2mm）。次日盲发关节指令方向反了，往死点里顶；
堵转触发固件过载保护关闭电机驱动（铁证：电流 0.016A、命令 20° 实动 0°、
三条软件解锁路径全部无效）。**解卡配方**：断电重启复活驱动 → **关节反序展开**
（j2 后仰卸载 → 弹起脱卡：z 24→246mm、肘电流 0.81→0.02A → 展腕 → 回家）。
厂商 `home()` 对趴伏构型的 IK 解是往压紧方向走的，**禁止用于解卡**。
预防：收纳保持上电锁位或摆自重平衡位，禁用 damping(0) 收纳。

### 10.2 闭环抓取全流程（成功，全自动）

目标：夹住桌上白色充电插头（用户移至可达区、出初始视野）。

```
① 扫描   高位 yaw ±30° 横扫(7站) 无果 → 用户提示需俯仰
         → 显式 pitch 全被 IK 拒(警告走 stderr 勿吞) → 关节空间阶梯(j2/j3/j4×6站)
         → 白色候选出现，两帧视差一致 = 真物体
② 对中   锚点(320,352)：j2 修垂直(dy -60→0 一次收敛)；yaw 符号探针实测
         (+6°→白物右移57px) 后两步收敛(dx=0)
③ 夹取   张爪 1.0rad → j3 步进 0.06 缓降 → 白块被爪指遮挡=捕获位 → 闭爪
④ 验证   四重证据：夹爪角 0.169rad(空抓0.03) / 闭爪电流 0.5A 对抗 /
         遮挡时序 / 抬起后爪间白物+线缆 —— 全部一致判 HELD
```

### 10.3 执行器安全层规格（本次实战沉淀，CreateBlockExecutor 直接采用）

1. 摄像头按设备名寻址；每次动作后抓帧留证
2. 每步双反馈：电流 >0.2A=真出力；角度跟随=真运动；电流≈0=驱动关/自由模式→禁发指令
3. 缓降步进（j3 +0.06/步）+ 遮挡检测触发捕获 + 电流 >1.2A 自动回退
4. IK 显式 pitch 易被拒且警告走 stderr——近场操作用关节空间直控，IK 只用于合法位姿库
5. 对中循环用"实测符号"而非推算符号（yaw/j2 各做一次 +Δ 探针）
6. 检测器三态输出：检出/未检出/不确定；弱候选报 NONE 不硬选
