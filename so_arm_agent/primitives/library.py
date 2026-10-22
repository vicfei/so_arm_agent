"""原语库：确定性代码，零训练。几何/前置约束审查集中在 supervisor.py。"""

from ..types import MoveTo, Primitive, PushToward, SetGripper

__all__ = ["MoveTo", "SetGripper", "PushToward", "Primitive"]

# 预设位姿库（06 号技术件 2）：真机阶段由手动示教填充角度档位，mock 期只记名。
POSE_LIBRARY: dict[str, str] = {
    "HOME": "复位安全位",
    "PRE_PUSH": "推送预备（平面推进姿，爪闭合贴桌面）",
    "DESCEND": "下探（固定桌面高度假设）",
}


def describe(p: Primitive) -> str:
    if isinstance(p, MoveTo):
        return f"move_to({p.pose_name})"
    if isinstance(p, SetGripper):
        return f"gripper({'open' if p.open else 'close'})"
    if isinstance(p, PushToward):
        return f"push_toward({p.object_color} -> ({p.goal.x:.0f},{p.goal.y:.0f}), stroke={p.stroke_mm:.0f})"
    return repr(p)
