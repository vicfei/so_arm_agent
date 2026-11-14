"""HSV 色块检测器（三态输出）。

参数与判定阈值全部来自 2026-11-14 真机实战标定（CreateBlock 腕装 640x480
暗光场景）。核心纪律：弱候选报 UNCERTAIN/NONE，绝不"矮子里拔将军"——
当日用户判卷 2/3 的教训固化于此。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np


class DetectionStatus(str, Enum):
    FOUND = "FOUND"
    UNCERTAIN = "UNCERTAIN"
    NONE = "NONE"


@dataclass(frozen=True)
class ColorSpec:
    """一种目标的 HSV/几何判定参数。"""

    name: str
    hue_ranges: tuple  # ((lo, hi), ...) 空区间为全色相
    s_max: int
    v_min: int
    area_min: int
    area_max: int
    aspect_min: float
    aspect_max: float
    fill_min: float
    found_score: int  # >= 此分判 FOUND，之下判 UNCERTAIN

    def mask(self, img_bgr: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        m = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in self.hue_ranges:
            m |= cv2.inRange(hsv, (lo, 0, self.v_min), (hi, self.s_max, 255))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        return m


# 白色充电插头（11-14 实战参数：暗光暖调、贴边眩光剔除、紧凑度优先）
WHITE_PLUG = ColorSpec(
    name="white_plug",
    hue_ranges=((0, 180),),
    s_max=90, v_min=130,
    area_min=350, area_max=9000,
    aspect_min=0.3, aspect_max=4.5,
    fill_min=0.35,
    found_score=2500,
)

# 红色方块（11-08 实战参数：双 H 区间 + 长宽比过滤反光条）
RED_BLOCK = ColorSpec(
    name="red_block",
    hue_ranges=((0, 12), (168, 180)),
    s_max=255, v_min=50,
    area_min=900, area_max=12000,
    aspect_min=0.5, aspect_max=2.0,
    fill_min=0.40,
    found_score=2500,
)


@dataclass(frozen=True)
class Detection:
    status: DetectionStatus
    center: tuple | None  # (cx, cy) 像素
    bbox: tuple | None    # (x, y, w, h)
    area: int = 0
    score: int = 0
    aspect: float = 0.0
    fill: float = 0.0


def detect(img_bgr: np.ndarray, spec: ColorSpec, border: int = 5) -> Detection:
    """单帧检测。三态：FOUND / UNCERTAIN（有候选但分数不足）/ NONE。"""
    if img_bgr is None:
        return Detection(DetectionStatus.NONE, None, None)
    h_img, w_img = img_bgr.shape[:2]
    mask = spec.mask(img_bgr)
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask)
    best = None
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (spec.area_min <= area <= spec.area_max):
            continue
        if x < border or y < border or x + w > w_img - border:
            continue  # 贴边（眩光/边缘）剔除；底边允许（桌面物常贴底）
        aspect = w / float(h)
        if not (spec.aspect_min <= aspect <= spec.aspect_max):
            continue
        fill = area / float(w * h)
        if fill < spec.fill_min:
            continue
        score = int(area * fill)
        if best is None or score > best[0]:
            best = (score, x, y, w, h, area, aspect, fill,
                    int(cents[i][0]), int(cents[i][1]))
    if best is None:
        return Detection(DetectionStatus.NONE, None, None)
    score, x, y, w, h, area, aspect, fill, cx, cy = best
    status = DetectionStatus.FOUND if score >= spec.found_score else DetectionStatus.UNCERTAIN
    return Detection(status, (cx, cy), (int(x), int(y), int(w), int(h)),
                     area=area, score=score, aspect=round(aspect, 2), fill=round(fill, 2))
