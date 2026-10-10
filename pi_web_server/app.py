"""
app.py - 树莓派智能嵌入式控制台主服务 (Flask)
提供响应式前端页面渲染、硬件系统监控 API、
GPIO/虚拟硬件交互接口以及摄像头实时推流桩。
"""

import os
import time
import threading
import atexit
import logging
from flask import Flask, render_template, jsonify, request, Response
from system_monitor import get_full_system_status
from camera_capture import open_camera

logging.basicConfig(level=logging.INFO)

# 导入 MoveNet 轻量人体骨骼识别检测器
try:
    from pose_detector import MoveNetPoseDetector
    pose_engine = MoveNetPoseDetector()
    print("[*] MoveNet Pose Engine initialized successfully.")
except Exception as e:
    print(f"[*] Warning: Pose detector could not be loaded: {e}")
    pose_engine = None

app = Flask(__name__)

# 全局虚拟外设状态（用于无硬件时的交互演示与状态同步）
virtual_devices = {
    "led_state": False,
    "buzzer_state": False,
    "last_morse_input": "",
    "morse_decoded_text": "WAITING_SIGNAL",
    "pose_enabled": True,
    "pose_mode": "fast",
    "flow_enabled": True,
    "pose_detected": False,
    "pose_keypoints": 0,
    "pose_infer_ms": 0.0,
    "perceived_latency_ms": 0.0,
    "motion_detected": True,
}

# 摩斯电码映射字典（支持无间道发报机功能）
MORSE_CODE_DICT = {
    ".-": "A",
    "-...": "B",
    "-.-.": "C",
    "-..": "D",
    ".": "E",
    "..-.": "F",
    "--.": "G",
    "....": "H",
    "..": "I",
    ".---": "J",
    "-.-": "K",
    ".-..": "L",
    "--": "M",
    "-.": "N",
    "---": "O",
    ".--.": "P",
    "--.-": "Q",
    ".-.": "R",
    "...": "S",
    "-": "T",
    "..-": "U",
    "...-": "V",
    ".--": "W",
    "-..-": "X",
    "-.--": "Y",
    "--..": "Z",
    "-----": "0",
    ".----": "1",
    "..---": "2",
    "...--": "3",
    "....-": "4",
    ".....": "5",
    "-....": "6",
    "--...": "7",
    "---..": "8",
    "----.": "9",
    "/": " ",
}


@app.route("/")
def index():
    """渲染主仪表盘控制台页面"""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """获取系统底层实时指标 (CPU、内存、核心温度、网络、运行时间)"""
    data = get_full_system_status()
    data["devices"] = virtual_devices
    data["camera"] = {
        "connected": camera_service.has_real_camera,
        "backend": camera_service.backend,
        "rotation": camera_service.rotation,
    }
    return jsonify(data)


@app.route("/api/led/toggle", methods=["POST"])
def toggle_led():
    """控制 LED 开关：同时控制树莓派板载绿色 ACT 贴片灯与 40-Pin 扩展引脚 GPIO 18"""
    virtual_devices["led_state"] = not virtual_devices["led_state"]
    state_val = "1" if virtual_devices["led_state"] else "0"

    # 1. 优先控制板载物理绿色 ACT 贴片 LED (通过 Linux sysfs)
    act_path = "/sys/class/leds/ACT"
    if os.path.exists(act_path):
        try:
            with open(f"{act_path}/trigger", "w") as f:
                f.write("none")
            with open(f"{act_path}/brightness", "w") as f:
                f.write("255" if virtual_devices["led_state"] else "0")
        except Exception:
            import subprocess
            subprocess.run(
                f"echo raspberry | sudo -S sh -c 'echo none > {act_path}/trigger; echo {state_val} > {act_path}/brightness'",
                shell=True,
                capture_output=True,
            )

    # 2. 同时控制外接 40-Pin GPIO 18 扩展引脚 (支持外接面包板/发光二极管)
    try:
        from gpiozero import LED
        led = LED(18)
        if virtual_devices["led_state"]:
            led.on()
        else:
            led.off()
    except Exception:
        try:
            import RPi.GPIO as GPIO
            PIN = 18
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN, GPIO.OUT)
            GPIO.output(PIN, GPIO.HIGH if virtual_devices["led_state"] else GPIO.LOW)
        except Exception:
            pass

    return jsonify({"success": True, "led_state": virtual_devices["led_state"]})


@app.route("/api/morse/decode", methods=["POST"])
def decode_morse():
    """
    无间道发报机接口：接收输入的摩斯密码串（点.与划-），返回译文
    """
    req = request.get_json(silent=True) or {}
    code_raw = req.get("code", "").strip()
    virtual_devices["last_morse_input"] = code_raw

    # 简单分词解析（空格分隔字符，/ 分隔单词）
    words = code_raw.split(" / ")
    decoded_words = []
    for word in words:
        letters = word.split(" ")
        decoded_letters = [MORSE_CODE_DICT.get(letter.strip(), "?") for letter in letters if letter.strip()]
        decoded_words.append("".join(decoded_letters))

    result_text = " ".join(decoded_words) if decoded_words else "无信号"
    virtual_devices["morse_decoded_text"] = result_text
    return jsonify({
        "success": True,
        "input_code": code_raw,
        "decoded_text": result_text
    })


@app.route("/api/pose/toggle", methods=["POST"])
def toggle_pose():
    """切换人体骨架追踪开关"""
    virtual_devices["pose_enabled"] = not virtual_devices["pose_enabled"]
    if pose_engine:
        pose_engine.enabled = virtual_devices["pose_enabled"]
    return jsonify({
        "success": True,
        "pose_enabled": virtual_devices["pose_enabled"]
    })


@app.route("/api/pose/mode", methods=["GET", "POST"])
def pose_mode():
    """获取或设置姿态识别性能模式 (fast: 光流极速 20fps, accurate: 纯 AI 228ms, eco: 节能温控)"""
    if request.method == "POST":
        req = request.get_json(silent=True) or {}
        mode = req.get("mode", "fast")
        if mode in ("fast", "accurate", "eco"):
            virtual_devices["pose_mode"] = mode
            if pose_engine:
                pose_engine.set_mode(mode)
            virtual_devices["flow_enabled"] = (mode != "accurate")
            return jsonify({
                "success": True,
                "mode": mode,
                "flow_enabled": virtual_devices["flow_enabled"]
            })
        return jsonify({"success": False, "error": f"Invalid mode: {mode}"}), 400

    return jsonify({
        "success": True,
        "mode": virtual_devices.get("pose_mode", "fast"),
        "modes_available": ["fast", "accurate", "eco"],
        "flow_enabled": virtual_devices.get("flow_enabled", True),
        "perceived_latency_ms": virtual_devices.get("perceived_latency_ms", 0.0)
    })


@app.route("/api/pose/flow/toggle", methods=["POST"])
def toggle_pose_flow():
    """快捷切换光流极速跟随模式"""
    curr = virtual_devices.get("pose_mode", "fast")
    new_mode = "accurate" if curr == "fast" else "fast"
    virtual_devices["pose_mode"] = new_mode
    if pose_engine:
        pose_engine.set_mode(new_mode)
    virtual_devices["flow_enabled"] = (new_mode == "fast")
    return jsonify({
        "success": True,
        "mode": new_mode,
        "flow_enabled": virtual_devices["flow_enabled"]
    })


def get_simulated_frame(frame_idx: int) -> bytes:
    """生成带雷达扫描与动态仿真骨骼的轻量级测试 JPEG 帧"""
    try:
        import cv2
        import numpy as np
        import math

        img = np.zeros((360, 640, 3), dtype=np.uint8)
        img[:] = (20, 24, 33)  # 深蓝灰底色

        # 网格线
        for x in range(0, 640, 40):
            cv2.line(img, (x, 0), (x, 360), (35, 42, 56), 1)
        for y in range(0, 360, 40):
            cv2.line(img, (0, y), (640, y), (35, 42, 56), 1)

        # 扫描中心雷达圈
        center = (320, 180)
        cv2.circle(img, center, 100, (45, 60, 80), 2)
        cv2.circle(img, center, 50, (45, 60, 80), 1)

        # 旋转扫描线
        angle = (frame_idx * 6) % 360
        rad = math.radians(angle)
        end_x = int(center[0] + 100 * math.cos(rad))
        end_y = int(center[1] + 100 * math.sin(rad))
        cv2.line(img, center, (end_x, end_y), (0, 215, 120), 2)

        # 若开启了骨骼追踪，绘制动态仿真人形骨骼 (展示效果)
        if virtual_devices.get("pose_enabled", True):
            t = frame_idx * 0.15
            bx = 320 + int(30 * math.sin(t * 0.5))
            by = 130
            # 头
            cv2.circle(img, (bx, by), 12, (0, 215, 255), 2)
            cv2.circle(img, (bx, by), 4, (255, 255, 255), -1)
            # 躯干
            cv2.line(img, (bx, by + 12), (bx, by + 70), (50, 100, 255), 3)
            # 双臂摆动
            arm_swing = math.sin(t) * 20
            cv2.line(img, (bx, by + 25), (int(bx - 30), int(by + 45 + arm_swing)), (100, 255, 50), 3)
            cv2.line(img, (bx, by + 25), (int(bx + 30), int(by + 45 - arm_swing)), (255, 200, 0), 3)
            # 双腿迈步
            leg_swing = math.sin(t) * 25
            cv2.line(img, (bx, by + 70), (int(bx - 20), int(by + 120 + leg_swing)), (80, 240, 150), 3)
            cv2.line(img, (bx, by + 70), (int(bx + 20), int(by + 120 - leg_swing)), (255, 220, 100), 3)
            # 关节圆点
            for pt in [(bx, by + 25), (int(bx - 30), int(by + 45 + arm_swing)), (int(bx + 30), int(by + 45 - arm_swing)),
                       (bx, by + 70), (int(bx - 20), int(by + 120 + leg_swing)), (int(bx + 20), int(by + 120 - leg_swing))]:
                cv2.circle(img, pt, 4, (255, 255, 255), -1)

            cv2.putText(img, "AI Pose: Active (17 Keypoints Animated)", (20, 310),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 120), 2)

        # 文字提示
        cv2.putText(img, "Raspberry Pi 3B+ MoveNet Engine Ready", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 230, 240), 2)
        cv2.putText(img, f"FPS: ~20  |  Frame: #{frame_idx}  |  {time.strftime('%H:%M:%S')}", (20, 335),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 220, 160), 1)

        ret, buffer = cv2.imencode(".jpg", img)
        return buffer.tobytes()
    except Exception:
        return b""


class CameraStreamService:
    """
    单例摄像头管理服务 (硬件独占保护 + 自动热插拔重连 + 多客户端并发广播)
    由于 Linux V4L2 摄像头设备节点在硬件层是排他的，
    本服务以单例后台守护线程持续采集物理摄像头，
    并将处理好 AI 骨骼的 JPEG 广播给所有连接的客户端。
    支持 CSI/Picamera2 与 USB/OpenCV，采集失败时自动重试并回退仿真画面。
    """
    def __init__(self):
        self.cap = None
        self.latest_jpeg = None
        self.lock = threading.Lock()
        self.running = True
        self.has_real_camera = False
        self.backend = "simulation"
        self.requested_backend = os.environ.get("CAMERA_BACKEND", "auto").lower()
        if self.requested_backend not in {"auto", "csi", "usb"}:
            raise ValueError("CAMERA_BACKEND must be auto, csi, or usb")
        self.rotation = int(os.environ.get("CAMERA_ROTATION", "0"))
        if self.rotation not in {0, 180}:
            raise ValueError("CAMERA_ROTATION must be 0 or 180")
        self.prev_small_gray = None
        self.static_frame_count = 0
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _open_camera(self):
        try:
            return open_camera(self.requested_backend)
        except Exception:
            logging.exception("Could not open camera; retrying")
            return None

    def _release_camera(self):
        camera, self.cap = self.cap, None
        if camera is not None:
            try:
                camera.release()
            except Exception:
                logging.exception("Could not release camera")
        self.has_real_camera = False
        self.backend = "simulation"
        self.prev_small_gray = None

    def stop(self):
        self.running = False
        self.thread.join(timeout=7)
        if not self.thread.is_alive():
            self._release_camera()

    def _capture_loop(self):
        import cv2
        import numpy as np
        frame_idx = 0
        while self.running:
            frame_idx += 1
            if self.cap is None or not self.cap.isOpened():
                self._release_camera()
                self.cap = self._open_camera()
                if self.cap is None:
                    # 未检测到物理摄像头，输出雷达仿真帧并等待重试
                    sim_bytes = get_simulated_frame(frame_idx)
                    with self.lock:
                        self.latest_jpeg = sim_bytes
                        self.has_real_camera = False
                    time.sleep(0.5)
                    continue

            try:
                ret, frame = self.cap.read()
            except Exception:
                logging.exception("Camera capture failed; retrying")
                ret, frame = False, None
            if not ret or frame is None or frame.size == 0:
                print("[CameraService] Camera read returned empty, releasing for reconnect...")
                self._release_camera()
                time.sleep(0.5)
                continue

            self.has_real_camera = True
            self.backend = self.cap.backend

            # Orient the image before motion detection, pose coordinates and labels.
            if self.rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)

            # 动态帧间差分运动门控 (Motion Gating: 降低画面静止时的 CPU 负荷与温升)
            try:
                small_g = cv2.cvtColor(cv2.resize(frame, (120, 90)), cv2.COLOR_BGR2GRAY)
                if self.prev_small_gray is not None:
                    diff = cv2.absdiff(small_g, self.prev_small_gray)
                    motion_val = float(np.mean(diff))
                else:
                    motion_val = 10.0
                self.prev_small_gray = small_g
                has_motion = motion_val > 1.8
                virtual_devices["motion_detected"] = has_motion
            except Exception:
                has_motion = True

            # 执行 AI 骨骼姿态识别与绘制
            if pose_engine and pose_engine.enabled and pose_engine.is_ready():
                # 节能温控模式或画面完全静止且无人时，避免持续死循环跑 AI 前向推理
                if virtual_devices.get("pose_mode") == "eco" and not has_motion and not virtual_devices.get("pose_detected", False):
                    self.static_frame_count += 1
                    if self.static_frame_count % 15 != 0:
                        pose_engine.enabled = False
                    else:
                        pose_engine.enabled = True
                else:
                    pose_engine.enabled = True
                    self.static_frame_count = 0

                frame, stats = pose_engine.detect_and_draw(frame)
                virtual_devices["pose_detected"] = stats["pose_detected"]
                virtual_devices["pose_keypoints"] = stats["keypoints_count"]
                virtual_devices["pose_infer_ms"] = stats["inference_ms"]
                virtual_devices["perceived_latency_ms"] = stats.get("perceived_latency_ms", stats["inference_ms"])
                virtual_devices["flow_enabled"] = stats.get("flow_enabled", True)
                virtual_devices["pose_mode"] = stats.get("mode", "fast")
            else:
                cv2.putText(frame, f"Pi-Cam Live | {time.strftime('%H:%M:%S')}", (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret_enc, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ret_enc:
                with self.lock:
                    self.latest_jpeg = buffer.tobytes()

            # CSI capture already waits for the next frame at the configured 30 FPS.
            if self.backend == "usb":
                time.sleep(0.035)
        self._release_camera()

    def get_frame(self):
        with self.lock:
            return self.latest_jpeg


camera_service = CameraStreamService()
atexit.register(camera_service.stop)


def generate_camera_frames():
    """
    客户端推流生成器：直接从全局 CameraStreamService 获取最新广播帧。
    无论有多少个手机、电脑同时看，永不发生底层摄像头占用冲突！
    支持热插拔，插上摄像头瞬间自动切换到真实画面！
    """
    frame_idx = 0
    while True:
        frame_idx += 1
        frame_bytes = camera_service.get_frame()
        if not frame_bytes:
            frame_bytes = get_simulated_frame(frame_idx)

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.04)


@app.route("/api/camera/stream")
def camera_stream():
    """实时视频流输出接口 (MJPEG 格式，浏览器 <img> 标签直接播放)"""
    return Response(generate_camera_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    # 0.0.0.0 允许局域网内任意手机、电脑通过热点访问
    print("============================================================")
    print("[*] Raspberry Pi Web Dashboard Started!")
    print("[*] Local URL:   http://127.0.0.1:5000")
    print("[*] Hotspot URL: http://192.168.4.1:5000 or http://pi.local:5000")
    print("============================================================")
    app.run(host=os.environ.get("WEB_HOST", "0.0.0.0"), port=5000, debug=False)
