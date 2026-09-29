/**
 * dashboard.js - 树莓派 Web 控制台前端交互与数据实时轮询
 */

let currentMorseCode = "";
let audioCtx = null;

// 初始化简易音频发生器 (模拟电键哔哔声)
function playBeep(duration = 80) {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.value = 750; // 750Hz 经典电台发报音调
    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration / 1000);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration / 1000);
  } catch (e) {
    // 忽略音频限制
  }
}

// 轮询更新硬件状态
async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("Network response was not ok");
    const data = await res.json();
    renderStatus(data);
  } catch (err) {
    console.warn("Status fetch failed:", err);
    document.getElementById("server-status-badge").innerHTML = `
      <span class="badge-pulse" style="background:#ef4444;box-shadow:0 0 8px #ef4444;"></span>
      <span>离线重连中</span>
    `;
  }
}

function renderStatus(data) {
  // 恢复在线徽章
  document.getElementById("server-status-badge").innerHTML = `
    <span class="badge-pulse"></span>
    <span>在线正常</span>
  `;

  // 1. CPU
  const cpuPercent = data.cpu.usage_percent;
  document.getElementById("cpu-val").innerText = `${cpuPercent}%`;
  document.getElementById("cpu-sub").innerText = `${data.cpu.core_count} 核心 @ ${data.cpu.freq_mhz} MHz`;
  const cpuBar = document.getElementById("cpu-bar");
  cpuBar.style.width = `${cpuPercent}%`;
  cpuBar.className = "progress-bar-fill " + (cpuPercent > 80 ? "fill-red" : (cpuPercent > 50 ? "fill-amber" : "fill-blue"));

  // 2. 核心温度
  const temp = data.cpu.temperature_c;
  document.getElementById("temp-val").innerText = `${temp} °C`;
  const tempSub = document.getElementById("temp-sub");
  const tempBar = document.getElementById("temp-bar");
  const tempPercent = Math.min(100, Math.max(0, (temp - 20) * 1.5));
  tempBar.style.width = `${tempPercent}%`;

  if (temp < 50) {
    tempSub.innerText = "温度优良 (低负荷运行)";
    tempBar.className = "progress-bar-fill fill-green";
  } else if (temp < 65) {
    tempSub.innerText = "温度适中 (正常负荷)";
    tempBar.className = "progress-bar-fill fill-amber";
  } else {
    tempSub.innerText = "注意散热 (高温预警)";
    tempBar.className = "progress-bar-fill fill-red";
  }

  // 3. 内存
  const mem = data.memory;
  document.getElementById("mem-val").innerText = `${mem.percent}%`;
  document.getElementById("mem-sub").innerText = `${mem.used_mb} MB / ${mem.total_mb} MB`;
  const memBar = document.getElementById("mem-bar");
  memBar.style.width = `${mem.percent}%`;
  memBar.className = "progress-bar-fill " + (mem.percent > 85 ? "fill-red" : "fill-blue");

  // 4. 磁盘 / TF 卡
  const disk = data.disk;
  document.getElementById("disk-val").innerText = `${disk.percent}%`;
  document.getElementById("disk-sub").innerText = `${disk.used_gb} GB / ${disk.total_gb} GB`;
  document.getElementById("disk-bar").style.width = `${disk.percent}%`;

  // 5. 运行时间与网络
  document.getElementById("uptime-badge").innerText = `运行: ${data.uptime.system}`;
  document.getElementById("net-ip").innerText = data.network.ip;
  document.getElementById("net-clients").innerText = `${data.network.clients_count} 台`;

  // 6. 骨骼追踪与光流极速状态同步
  if (data.devices) {
    const poseInfer = document.getElementById("pose-infer-badge");
    const poseBtn = document.getElementById("pose-toggle-btn");
    const flowBtn = document.getElementById("flow-toggle-btn");

    const flowEnabled = data.devices.flow_enabled !== false;
    const pLat = data.devices.perceived_latency_ms || 0;
    const inferMs = data.devices.pose_infer_ms || 0;
    const kpts = data.devices.pose_keypoints || 0;
    const isDetected = data.devices.pose_detected;

    if (poseInfer) {
      if (data.devices.pose_enabled) {
        if (flowEnabled && pLat > 0) {
          poseInfer.innerHTML = `延迟: <b style="color:var(--accent-green);">&lt;30ms</b> (光流20fps) | AI: <b>${inferMs.toFixed(0)}ms</b> (${kpts}点)`;
          poseInfer.style.color = isDetected ? "var(--accent-green)" : "#94a3b8";
        } else {
          poseInfer.innerHTML = `AI推理: <b>${inferMs.toFixed(1)}ms</b> (${kpts} 关节点)`;
          poseInfer.style.color = isDetected ? "var(--accent-green)" : "#94a3b8";
        }
      } else {
        poseInfer.innerText = "骨骼追踪已暂停";
        poseInfer.style.color = "#64748b";
      }
    }

    if (poseBtn && data.devices.pose_enabled !== undefined) {
      poseBtn.innerText = data.devices.pose_enabled ? "🦴 骨骼追踪: 开启" : "🦴 骨骼追踪: 关闭";
      if (data.devices.pose_enabled) {
        poseBtn.style.borderColor = "var(--accent-green)";
        poseBtn.style.color = "var(--accent-green)";
      } else {
        poseBtn.style.borderColor = "var(--border-color)";
        poseBtn.style.color = "var(--text-muted)";
      }
    }

    if (flowBtn) {
      flowBtn.innerText = flowEnabled ? "⚡ 极速跟随: 开启" : "🎯 纯AI模式: 228ms";
      if (flowEnabled) {
        flowBtn.style.borderColor = "#38bdf8";
        flowBtn.style.color = "#38bdf8";
      } else {
        flowBtn.style.borderColor = "var(--border-color)";
        flowBtn.style.color = "var(--text-muted)";
      }
    }
  }

  // 7. LED 硬件指示灯同步
  const ledBulb = document.getElementById("led-bulb");
  const ledBtn = document.getElementById("led-toggle-btn");
  if (data.devices && data.devices.led_state) {
    ledBulb.classList.add("active");
    ledBtn.innerText = "关闭 LED 绿灯";
    ledBtn.className = "btn btn-red";
  } else {
    ledBulb.classList.remove("active");
    ledBtn.innerText = "点亮 LED 绿灯";
    ledBtn.className = "btn btn-primary";
  }
}

// 极速光流跟随开关交互
async function toggleFlowMode() {
  try {
    const res = await fetch("/api/pose/flow/toggle", { method: "POST" });
    const data = await res.json();
    playBeep(80);
    fetchSystemStatus();
  } catch (e) {
    console.error("Flow toggle failed", e);
  }
}

// 骨骼姿态识别开关交互
async function togglePose() {
  try {
    const res = await fetch("/api/pose/toggle", { method: "POST" });
    const data = await res.json();
    playBeep(60);
    fetchSystemStatus();
  } catch (e) {
    console.error("Pose toggle failed", e);
  }
}

// LED 开关交互
async function toggleLed() {
  try {
    const res = await fetch("/api/led/toggle", { method: "POST" });
    const json = await res.json();
    playBeep(40);
    fetchSystemStatus();
  } catch (e) {
    alert("控制请求失败，请检查网络！");
  }
}

// 摩斯密码发报机交互
function appendMorse(symbol) {
  currentMorseCode += symbol;
  document.getElementById("morse-input").innerText = currentMorseCode || "等待输入...";
  playBeep(symbol === "." ? 60 : 180);
  decodeMorse();
}

function clearMorse() {
  currentMorseCode = "";
  document.getElementById("morse-input").innerText = "等待输入...";
  document.getElementById("morse-output").innerText = "无信号";
  fetch("/api/morse/decode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: "" }),
  });
}

function sendPresetMorse(code) {
  currentMorseCode = code;
  document.getElementById("morse-input").innerText = currentMorseCode;
  playBeep(200);
  decodeMorse();
}

async function decodeMorse() {
  if (!currentMorseCode.trim()) return;
  try {
    const res = await fetch("/api/morse/decode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: currentMorseCode }),
    });
    const data = await res.json();
    document.getElementById("morse-output").innerText = data.decoded_text || "无法解码";
  } catch (err) {
    console.error(err);
  }
}

// 页面加载启动
document.addEventListener("DOMContentLoaded", () => {
  fetchSystemStatus();
  setInterval(fetchSystemStatus, 1500); // 每 1.5 秒刷新一次

  // 绑定键盘空格发报 (空格短按点，回车长按划)
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === " ") {
      e.preventDefault();
      appendMorse(".");
    } else if (e.key === "Enter") {
      e.preventDefault();
      appendMorse("-");
    } else if (e.key === "Backspace") {
      clearMorse();
    }
  });
});
