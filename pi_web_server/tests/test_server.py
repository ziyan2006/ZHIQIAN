"""
test_server.py - 自动化单元与集成测试
验证底层状态采集逻辑与 Flask RESTful API 端点
"""

import sys
import os
import unittest
import cv2

# 将上级目录加入导入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from system_monitor import (
    get_cpu_temperature,
    get_ip_address,
    format_uptime,
    get_full_system_status,
)
from app import app


class TestSystemMonitor(unittest.TestCase):

    def test_temperature_range(self):
        """验证温度在合理范围 (0 ~ 100 摄氏度)"""
        temp = get_cpu_temperature()
        self.assertIsInstance(temp, float)
        self.assertGreater(temp, 10.0)
        self.assertLess(temp, 95.0)

    def test_format_uptime(self):
        """验证运行时间字符串转换"""
        self.assertEqual(format_uptime(45), "0分 45秒")
        self.assertEqual(format_uptime(3665), "1时 1分 5秒")
        self.assertEqual(format_uptime(90000), "1天 1时 0分")

    def test_full_status_structure(self):
        """验证系统全量指标结构完整性"""
        status = get_full_system_status()
        self.assertEqual(status["status"], "online")
        self.assertIn("cpu", status)
        self.assertIn("memory", status)
        self.assertIn("disk", status)
        self.assertIn("network", status)
        self.assertIn("temperature_c", status["cpu"])
        self.assertGreaterEqual(status["memory"]["percent"], 0)
        self.assertLessEqual(status["memory"]["percent"], 100)


class TestFlaskEndpoints(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_status_endpoint(self):
        """验证 /api/status 返回 200 与结构"""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "online")
        self.assertIn("cpu", data)
        self.assertIn("devices", data)

    def test_index_page(self):
        """验证首页 HTML 正常渲染并包含关键标签"""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("智能嵌入式系统控制台", html)
        self.assertIn("无间道发报机", html)

    def test_static_css(self):
        """验证静态 CSS 样式文件正常加载"""
        res = self.client.get("/static/css/dashboard.css")
        self.assertEqual(res.status_code, 200)
        css = res.get_data(as_text=True)
        self.assertIn("--bg-primary", css)

    def test_led_toggle_endpoint(self):
        """验证 /api/led/toggle 开关状态切换"""
        res1 = self.client.post("/api/led/toggle")
        self.assertEqual(res1.status_code, 200)
        s1 = res1.get_json()["led_state"]

        res2 = self.client.post("/api/led/toggle")
        self.assertEqual(res2.status_code, 200)
        s2 = res2.get_json()["led_state"]

        self.assertNotEqual(s1, s2)

    def test_morse_decode_endpoint(self):
        """验证无间道发报机摩斯码解码功能"""
        # 测试 SOS: ... --- ...
        payload = {"code": "... --- ..."}
        res = self.client.post("/api/morse/decode", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["decoded_text"], "SOS")

        # 测试 UESTC: ..- . ... - -.-.
        payload2 = {"code": "..- . ... - -.-."}
        res2 = self.client.post("/api/morse/decode", json=payload2)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["decoded_text"], "UESTC")

    def test_pose_toggle_endpoint(self):
        """验证 /api/pose/toggle 骨骼追踪开关接口"""
        res1 = self.client.post("/api/pose/toggle")
        self.assertEqual(res1.status_code, 200)
        s1 = res1.get_json()["pose_enabled"]

        res2 = self.client.post("/api/pose/toggle")
        self.assertEqual(res2.status_code, 200)
        s2 = res2.get_json()["pose_enabled"]

        self.assertNotEqual(s1, s2)

    def test_pose_mode_endpoints(self):
        """验证 /api/pose/mode 与 /api/pose/flow/toggle 性能模式切换接口"""
        # 测试 GET /api/pose/mode
        res_get = self.client.get("/api/pose/mode")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertIn("mode", data_get)
        self.assertIn("modes_available", data_get)

        # 测试 POST 切换模式
        for mode in ["fast", "accurate", "eco"]:
            res = self.client.post("/api/pose/mode", json={"mode": mode})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["mode"], mode)

        # 测试 /api/pose/flow/toggle
        res_toggle = self.client.post("/api/pose/flow/toggle")
        self.assertEqual(res_toggle.status_code, 200)
        self.assertIn("flow_enabled", res_toggle.get_json())

    def test_optical_flow_tracking_engine(self):
        """验证 Pose 引擎的光流跟随与感知延迟指标"""
        from pose_detector import MoveNetPoseDetector
        import numpy as np

        engine = MoveNetPoseDetector()
        self.assertTrue(engine.is_ready())

        # 构造两帧图像（黑底上画一个白色矩形模拟局部特征）
        f1 = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(f1, (160, 120), 20, (255, 255, 255), -1)

        # 手动注入一个追踪点
        with engine.lock:
            engine.last_poses = [{0: (160, 120, 0.9)}]
            engine.last_detected = True
            engine.is_inferring = True

        engine.prev_gray = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)

        # 第二帧：向右下偏移 4 像素
        f2 = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(f2, (164, 124), 20, (255, 255, 255), -1)

        _, stats = engine.detect_and_draw(f2)
        # 光流应跟随移动，且感知延迟在 30ms 以内
        self.assertIn("perceived_latency_ms", stats)
        self.assertLess(stats["perceived_latency_ms"], 30.0)


if __name__ == "__main__":
    unittest.main()

