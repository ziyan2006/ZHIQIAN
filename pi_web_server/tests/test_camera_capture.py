"""Camera selection, failure recovery and hardware resource ownership."""

import sys
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camera_capture


class TestCameraCapture(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((480, 640, 3), [10, 20, 30], dtype=np.uint8)

    def test_csi_frames_keep_bgr_order_and_release(self):
        hardware = Mock()
        hardware.wait.return_value = self.frame
        with patch.dict(sys.modules, {"picamera2": SimpleNamespace(Picamera2=Mock(return_value=hardware))}):
            camera = camera_capture.Picamera2Capture()
            ok, frame = camera.read()
            self.assertTrue(ok)
            np.testing.assert_array_equal(frame[0, 0], [10, 20, 30])
            hardware.wait.assert_called_once_with(hardware.capture_array.return_value, timeout=5)
            camera.release()
            camera.release()
            hardware.close.assert_called_once()
            self.assertFalse(camera.isOpened())
            self.assertEqual(camera.read(), (False, None))

    def test_failed_csi_start_releases_hardware(self):
        hardware = Mock()
        hardware.start.side_effect = RuntimeError("sensor unavailable")
        with patch.dict(sys.modules, {"picamera2": SimpleNamespace(Picamera2=Mock(return_value=hardware))}):
            with self.assertRaises(RuntimeError):
                camera_capture.Picamera2Capture()
        hardware.close.assert_called_once()

    def test_auto_prefers_csi(self):
        csi = Mock()
        with patch.object(camera_capture, "_open_csi", return_value=csi), patch.object(camera_capture, "_open_usb") as usb:
            self.assertIs(camera_capture.open_camera(), csi)
            usb.assert_not_called()

    def test_auto_falls_back_to_usb_without_picamera2(self):
        usb = Mock()
        with patch.object(camera_capture, "_open_csi", side_effect=ImportError), patch.object(camera_capture, "_open_usb", return_value=usb):
            self.assertIs(camera_capture.open_camera(), usb)

    def test_explicit_usb_skips_csi(self):
        with patch.object(camera_capture, "_open_csi") as csi, patch.object(camera_capture, "_open_usb", return_value=None):
            self.assertIsNone(camera_capture.open_camera("usb"))
            csi.assert_not_called()

    def test_failed_probe_releases_csi(self):
        factory = Mock()
        factory.global_camera_info.return_value = [{"Id": "/base/sensor", "Num": 0, "Model": "imx219"}]
        capture = Mock()
        capture.read.side_effect = TimeoutError("no frame")
        with patch.dict(sys.modules, {"picamera2": SimpleNamespace(Picamera2=factory)}), patch.object(camera_capture, "Picamera2Capture", return_value=capture):
            with self.assertRaises(TimeoutError):
                camera_capture._open_csi()
        capture.release.assert_called_once()

    def test_capture_failure_does_not_kill_service(self):
        import app

        with patch.object(app.threading, "Thread"):
            service = app.CameraStreamService()
        hardware = Mock()
        hardware.read.side_effect = TimeoutError("no frame")
        service.cap = hardware
        service.has_real_camera = True
        service.backend = "csi"
        with patch.object(app.time, "sleep", side_effect=lambda _: setattr(service, "running", False)):
            service._capture_loop()
        hardware.release.assert_called_once()
        self.assertIsNone(service.cap)
        self.assertFalse(service.has_real_camera)
        self.assertEqual(service.backend, "simulation")

    def test_upside_down_mount_rotates_before_pose_and_jpeg(self):
        import app
        import cv2

        frame = np.zeros((100, 160, 3), dtype=np.uint8)
        frame[:30, :30] = [10, 20, 230]
        frame[-30:, -30:] = [220, 30, 10]
        original = frame.copy()
        with patch.dict(os.environ, {"CAMERA_ROTATION": "180"}), patch.object(app.threading, "Thread"):
            service = app.CameraStreamService()
        hardware = Mock(backend="usb")
        hardware.read.return_value = (True, frame)
        service.cap = hardware
        pose = Mock(enabled=True)
        pose.detect_and_draw.side_effect = lambda image: (image, {
            "pose_detected": False, "keypoints_count": 0, "inference_ms": 0,
        })
        with patch.object(app, "pose_engine", pose), patch.object(app.time, "sleep", side_effect=lambda _: setattr(service, "running", False)):
            service._capture_loop()
        np.testing.assert_array_equal(pose.detect_and_draw.call_args.args[0], original[::-1, ::-1])
        jpeg = cv2.imdecode(np.frombuffer(service.get_frame(), dtype=np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_allclose(jpeg[10, 10], original[-11, -11], atol=8)
        np.testing.assert_allclose(jpeg[-11, -11], original[10, 10], atol=8)


if __name__ == "__main__":
    unittest.main()
