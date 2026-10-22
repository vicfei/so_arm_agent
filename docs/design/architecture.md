# 分层契约（骨架 v0）

每层只依赖 `types.py` 的数据类与下一层的接口类；真机实现逐层替换 mock，其余不动。

## types.py（公共数据）

- `Point2(x, y)`：工作区坐标，毫米，原点=桌面左上（俯视），x 向右 y 向下。
- `Pixel(x, y)`：相机像素坐标（标定前与工作区 1:1，标定后走 `workspace.py` 映射）。
- `ObjectDetection(name, color, center: Point2, pixel: Pixel, radius_mm)`：符号化感知输出。
- `Task(object_color, target: Point2, tolerance_mm)`：MVP 任务 = 把某色块推到目标点邻域。
- 原语三件套：`MoveTo(pose_name)`、`SetGripper(open: bool)`、`PushToward(object_color, goal: Point2, stroke_mm)`。
- `EvidenceRecord(ts, kind, payload: dict)`：planner 咨询/原语裁决/执行回执/verifier 判定全记。
- `VerifierFeedback(ok, distance_mm, hint)`：重规划的反馈通道。

## Planner（planner/）

- `consult(perception, task, feedback=None) -> list[原语]`——低频：每个任务步只调一次，
  不做逐帧控制（实验 1b 教训）。
- `ScriptedPlanner`：零 API 依赖的规则规划器（mock 演示与测试用）；首次提案故意含越界
  目标以演示否决权。`DeepSeekPlanner` 留接口（真机阶段接 API，key 走环境变量，不落盘）。

## Perception（perception/）

- `observe() -> list[ObjectDetection]`——符号化输出，不输出原始帧（OpenCV 实现在真机阶段补）。
- `MockCamera`：读 MockScene 的真实状态模拟一次"拍照识别"。

## Primitives + Supervisor（primitives/, supervisor.py）

- 原语库 = 确定性代码，零训练。前置条件与几何约束集中在 supervisor 审查：
  工作区边界、行程上限、目标可达性、任务相关性（颜色匹配）。**否决必须给理由**，
  理由进证据流并回传 planner 下一轮 consult。
- 设计取向：planner 可以是任何模型，supervisor 必须是可审计的纯代码（ORA 结论）。

## Executor（executor/）

- `execute(原语) -> 回执 dict`。`MockExecutor` 持有桌面物理：push 把物体沿射线推进
  `stroke_mm`（不足则到目标），move/gripper 只改机械臂状态。
- `TCPBridgeExecutor`（真机）：接 SO-101 TCP 桥（05 号资产，度数级控制），接口同 mock。

## Verifier（verifier/）

- `verify(task, perception) -> VerifierFeedback`：复核 = 再 observe 一次（"复拍一帧"的
  符号化形态），判目标邻域；不 ok 则反馈距离与方向提示给 planner。
- 真机阶段升级为 VLM 判完成度（DeepSeek-Vision 同一 API 位），接口不变。

## Agent 主循环（agent.py）

```
for attempt in range(max_replans):
    perception = perceive()
    plan = planner.consult(perception, task, feedback)
    for primitive in plan:
        verdict = supervisor.approve(primitive, world_state)
        if verdict.vetoed: 记证据, 把理由并入 feedback, break
        receipt = executor.execute(primitive)
        记证据
    feedback = verifier.verify(task, perceive())
    if feedback.ok: return SUCCESS(证据摘要)
return FAILED(全部证据归档)
```
