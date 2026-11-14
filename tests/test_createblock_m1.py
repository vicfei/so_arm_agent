"""M1 单元测试：检测器三态 / 符号修正 / 执行器安全层 / 持物判定。
全部离线可跑（合成帧 + Mock 运行器），CI 与本地均执行。"""

import unittest

try:
    import cv2
    import numpy as np
    HAS_CV = True
except ImportError:  # pragma: no cover
    HAS_CV = False

from so_arm_agent.executor.createblock import (
    ArmState, CreateBlockExecutor, UnsafeStateError, parse_state)
from so_arm_agent.primitives.createblock import correction_step
from so_arm_agent.perception.hsv_detector import (
    DetectionStatus, WHITE_PLUG, detect)


def make_state(joints, currents={2: 0.02, 3: 0.03, 5: 0.0}, z=100.0):
    return "STATE %s CUR %s Z %s" % (joints, currents, z)


class TestParseState(unittest.TestCase):
    def test_ok(self):
        s = parse_state(make_state([0.0, -1.0, 1.05, 0.7, 0.0, 0.169], {2: 0.32, 3: 0.5, 5: 0.1}))
        self.assertEqual(len(s.joints), 6)
        self.assertTrue(s.held)
        self.assertEqual(s.tool_z_mm, 100.0)

    def test_garbage_raises(self):
        with self.assertRaises(UnsafeStateError):
            parse_state("random noise\nno state line")


class TestCorrectionStep(unittest.TestCase):
    """11-14 实测语义：yaw+ 使目标右移(sign=+1)时，目标偏右(dx>0)需 yaw 负步。"""

    def test_yaw_left_correction(self):
        self.assertLess(correction_step(50, sign=1, step=0.05, tol=26), 0)

    def test_yaw_right_correction(self):
        self.assertGreater(correction_step(-50, sign=1, step=0.05, tol=26), 0)

    def test_within_tolerance_zero(self):
        self.assertEqual(correction_step(20, sign=1, step=0.05, tol=26), 0.0)

    def test_sign_inverted_flips(self):
        self.assertGreater(correction_step(50, sign=-1, step=0.05, tol=26), 0)


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, code, args):
        self.calls.append(args)
        if not self.responses:
            raise AssertionError("unexpected extra call: %s" % args)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class TestExecutorSafety(unittest.TestCase):
    def _ex(self, responses):
        return CreateBlockExecutor(FakeRunner(responses))

    def test_set_joint_tracks(self):
        ex = self._ex([make_state([0.0, -1.0, 1.05, 0.7, 0.0, 0.3])])
        st = ex.set_joint("joint3", 1.05)
        self.assertAlmostEqual(st.joints[2], 1.05, places=3)

    def test_tracking_failure_aborts(self):
        ex = self._ex([make_state([0.0, -1.0, 1.45, 0.7, 0.0, 0.3])])  # 回读 1.45 ≠ 命令 1.05
        with self.assertRaises(UnsafeStateError):
            ex.set_joint("joint3", 1.05)

    def test_limit_check(self):
        ex = self._ex([])
        with self.assertRaises(UnsafeStateError):
            ex.set_joint("joint2", -0.10)  # 超 joint2 上限 -0.2269

    def test_current_spike(self):
        st = ArmState([0, -1, 1.05, 0.7, 0, 0.3], {2: 1.5, 3: 0.1})
        ex = self._ex([])
        with self.assertRaises(UnsafeStateError):
            ex.check_currents(st)

    def test_startup_rejects_collapsed(self):
        ex = self._ex([make_state([0.0, -1.9, 1.2, 1.9, 0.0, 0.5], z=10.0)])
        with self.assertRaises(UnsafeStateError):
            ex.startup_check()

    def test_startup_passes(self):
        ex = self._ex([make_state([0.0, -1.57, 1.57, 0.0, 0.0, 0.3], z=180.0)])
        st = ex.startup_check()
        self.assertTrue(st.tool_z_mm > 30)


@unittest.skipUnless(HAS_CV, "numpy/cv2 不可用")
class TestDetectorThreeState(unittest.TestCase):
    def _frame(self, blobs, size=(480, 640), bg=(45, 60, 90)):  # BGR 褐桌暗底
        img = np.full((size[0], size[1], 3), bg, np.uint8)
        for (cx, cy, w, h, color) in blobs:
            cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), color, -1)
        return img

    def test_found_strong_plug(self):
        img = self._frame([(373, 298, 90, 33, (255, 250, 245))])
        det = detect(img, WHITE_PLUG)
        self.assertEqual(det.status, DetectionStatus.FOUND)
        self.assertAlmostEqual(det.center[0], 373, delta=4)

    def test_none_empty_scene(self):
        det = detect(self._frame([]), WHITE_PLUG)
        self.assertEqual(det.status, DetectionStatus.NONE)

    def test_uncertain_weak_blob(self):
        img = self._frame([(300, 300, 34, 22, (200, 195, 190))])  # 面积小分低
        det = detect(img, WHITE_PLUG)
        self.assertEqual(det.status, DetectionStatus.UNCERTAIN)

    def test_border_glare_excluded(self):
        img = self._frame([(620, 30, 40, 40, (255, 255, 255))])  # 贴右上边
        det = detect(img, WHITE_PLUG)
        self.assertEqual(det.status, DetectionStatus.NONE)


if __name__ == "__main__":
    unittest.main()
