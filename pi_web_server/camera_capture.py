"""CSI/Picamera2 and USB/OpenCV capture with the same BGR frame interface."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Picamera2Capture:
    backend = "csi"

    def __init__(self, camera_num=0):
        from picamera2 import Picamera2

        self.camera = Picamera2(camera_num)
        self.opened = False
        try:
            # IMX219's 640x480 sensor mode reads only the centre of the image.
            # Use its full-view binned mode, then let the ISP scale to 640x480.
            raw = (
                {"size": (1640, 1232)}
                if self.camera.camera_properties.get("Model") == "imx219"
                else {}
            )
            # libcamera RGB888 arrays are BGR, matching OpenCV and the pose engine.
            config = self.camera.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                raw=raw,
                controls={"FrameRate": 30},
                buffer_count=4,
            )
            self.camera.configure(config)
            self.camera.start()
            self.opened = True
        except Exception:
            self.release()
            raise

    def isOpened(self):
        return self.opened

    def read(self):
        if not self.opened:
            return False, None
        job = self.camera.capture_array("main", wait=False)
        frame = self.camera.wait(job, timeout=5)
        return frame is not None and frame.size > 0, frame

    def release(self):
        self.opened = False
        camera, self.camera = self.camera, None
        if camera is not None:
            camera.close()


class USBCapture:
    backend = "usb"

    def __init__(self, camera):
        self.camera = camera

    def isOpened(self):
        return self.camera.isOpened()

    def read(self):
        return self.camera.read()

    def release(self):
        self.camera.release()


def _open_csi():
    from picamera2 import Picamera2

    for info in Picamera2.global_camera_info():
        # Picamera2 also lists USB devices; those belong to the OpenCV path.
        if info.get("Id", "").startswith("/base/"):
            camera = Picamera2Capture(info["Num"])
            try:
                ok, frame = camera.read()
                if ok:
                    logger.info("Opened CSI camera %s (%s)", info["Model"], frame.shape)
                    return camera
            except Exception:
                camera.release()
                raise
            camera.release()
    return None


def _usb_devices():
    video_class = Path("/sys/class/video4linux")
    if video_class.is_dir():
        # Scan every USB video node, skipping the Pi's raw CSI and codec nodes.
        return [
            str(Path("/dev") / node.name)
            for node in sorted(video_class.glob("video*"))
            if any(part.startswith("usb") for part in (node / "device").resolve().parts)
        ]
    return [0, 1, 2]  # Desktop development, including Windows.


def _open_usb():
    import cv2

    apis = [cv2.CAP_V4L2] if os.name == "posix" else [cv2.CAP_ANY]
    for device in _usb_devices():
        for api in apis:
            camera = cv2.VideoCapture(device, api)
            try:
                if camera.isOpened():
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    ok, frame = camera.read()
                    if ok and frame is not None and frame.size > 0:
                        logger.info("Opened USB camera %s (%s)", device, frame.shape)
                        return USBCapture(camera)
            except Exception:
                logger.exception("Could not read USB camera %s", device)
            camera.release()
    return None


def open_camera(backend="auto"):
    """Prefer CSI in auto mode; return None when no camera can supply frames."""
    if backend not in {"auto", "csi", "usb"}:
        raise ValueError("CAMERA_BACKEND must be auto, csi, or usb")
    if backend in {"auto", "csi"}:
        try:
            camera = _open_csi()
            if camera is not None:
                return camera
        except ImportError:
            if backend == "csi":
                logger.exception("Picamera2 is unavailable")
        except Exception:
            logger.exception("Could not open CSI camera")
    if backend in {"auto", "usb"}:
        return _open_usb()
    return None
