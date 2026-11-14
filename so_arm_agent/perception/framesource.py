"""FrameSource：双模式相机抽象（docs/09 D6）。

铁律 1（11-14）：相机按设备名寻址，绝不信任 index——DSHOW 枚举跨进程漂移。
- FFmpegDeviceSource：Windows 侧按设备名经 ffmpeg 抓帧（当日验证的主路径）
- OpenCVDeviceSource：Nano 本地直读 /dev/videoN（11-08 验证）
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod

import cv2
import numpy as np


class FrameSource(ABC):
    @abstractmethod
    def read(self) -> np.ndarray | None:
        """抓一帧 BGR；失败返回 None。"""

    def read_warmed(self, n: int = 2) -> np.ndarray | None:
        """连读 n+1 帧取末帧（AE 稳定），全部失败返回 None。"""
        frame = None
        for _ in range(n + 1):
            frame = self.read()
        return frame


class FFmpegDeviceSource(FrameSource):
    """按 DirectShow 设备名抓帧（如 "USB 2.0 Camera" / "Integrated Webcam"）。"""

    def __init__(self, device_name: str, ffmpeg_exe: str | None = None):
        self.device_name = device_name
        self.ffmpeg_exe = ffmpeg_exe or self._find_ffmpeg()
        self._tmp = os.path.join(tempfile.gettempdir(), "fs_frame.jpg")

    @staticmethod
    def _find_ffmpeg() -> str:
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("需要 imageio-ffmpeg（pip install imageio-ffmpeg）") from e

    def read(self) -> np.ndarray | None:
        try:
            subprocess.run(
                [self.ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "dshow", "-i", "video=" + self.device_name,
                 "-frames:v", "1", "-q:v", "2", self._tmp],
                capture_output=True, timeout=30)
            img = cv2.imread(self._tmp)
            return img if img is not None and img.size else None
        except Exception:
            return None


class OpenCVDeviceSource(FrameSource):
    """index 或设备路径直读（Nano 本地模式 / 回放视频文件）。"""

    def __init__(self, src, warmup: int = 3):
        self.src = src
        self.warmup = warmup
        self._cap = None

    def read(self) -> np.ndarray | None:
        try:
            if self._cap is None or not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.src)
            for _ in range(self.warmup):
                self._cap.read()
            ok, frame = self._cap.read()
            return frame if ok else None
        except Exception:
            return None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
