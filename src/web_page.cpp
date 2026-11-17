#include <Arduino.h>
#include "web_page.h"

const char webpage[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ESP32 Robot</title>
<style>
  :root { color-scheme: dark; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #0b1118; color: #eef5fa; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; background: radial-gradient(circle at 50% -20%, #1b3d47, #0b1118 55%); }
  button { font: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
  button:disabled { opacity: .45; cursor: default; }
  [hidden] { display: none !important; }
  .shell { width: min(100% - 32px, 760px); margin: 0 auto; padding: 28px 0 48px; }
  .eyebrow { color: #78d9bd; font-size: 12px; font-weight: 750; letter-spacing: .18em; text-transform: uppercase; }
  h1 { font-size: clamp(26px, 5vw, 38px); margin: 7px 0 5px; }
  .subtitle { color: #a9bdca; margin: 0 0 24px; }
  .summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 17px 20px; border: 1px solid #314752; border-radius: 18px; background: #14232c; }
  .summary small, .section-label { display: block; color: #99afbc; font-size: 12px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; }
  .summary strong { display: block; margin-top: 4px; font-size: 22px; }
  .connection { flex: none; border-radius: 99px; padding: 7px 11px; color: #102319; background: #79e1aa; font-size: 12px; font-weight: 800; }
  .connection.offline { background: #eaa273; color: #29150e; }
  .section-label { margin: 27px 0 12px; }
  .modes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  input { width: 100%; margin: 12px 0; padding: 12px; border: 1px solid #49606b; border-radius: 9px; background: #09131b; color: white; font: inherit; }
  .action { display: inline-block; margin-top: 12px; padding: 12px; border: 1px solid #72dcb7; border-radius: 9px; color: white; background: #1c493f; font: inherit; text-decoration: none; }
  .emergency { display: block; width: 100%; margin-top: 18px; padding: 12px; border: 1px solid #d4777b; border-radius: 12px; background: #8b3038; color: white; }
  .mode-btn { text-align: left; padding: 17px; border: 1px solid #334954; border-radius: 16px; color: #c4d5de; background: #14232c; }
  .mode-btn.active { border-color: #72dcb7; color: white; background: #1c493f; box-shadow: inset 0 0 0 1px #72dcb7; }
  .mode-btn strong, .mode-btn span { display: block; }
  .mode-btn strong { font-size: 15px; }
  .mode-btn span { margin-top: 4px; font-size: 12px; opacity: .8; }
  .card { margin-top: 18px; padding: 21px; border: 1px solid #2d424d; border-radius: 20px; background: #111e27; }
  .card h2 { font-size: 20px; margin: 0 0 6px; }
  .card p { margin: 0; color: #a9bdca; line-height: 1.5; font-size: 14px; }
  .auto-visual { margin-top: 23px; display: flex; align-items: center; gap: 13px; border-radius: 14px; background: #19342f; padding: 15px; color: #a8f2cf; }
  .auto-visual .icon { font-size: 26px; }
  .auto-visual b, .auto-visual small { display: block; }
  .auto-visual small { margin-top: 3px; color: #b3c9c1; }
  .controller { display: grid; grid-template-columns: repeat(3, 76px); justify-content: center; gap: 9px; margin: 22px auto 10px; touch-action: none; }
  .control-btn { width: 76px; height: 68px; border: 1px solid #46606b; border-radius: 15px; color: white; background: #263b48; font-size: 29px; font-weight: bold; touch-action: none; user-select: none; }
  .control-btn.active { background: #198467; border-color: #8bffcd; transform: scale(.95); }
  .control-btn.stop { background: #8b3038; border-color: #d4777b; font-size: 22px; }
  #forward { grid-column: 2; }
  #left { grid-column: 1; grid-row: 2; }
  #stop { grid-column: 2; grid-row: 2; }
  #right { grid-column: 3; grid-row: 2; }
  #backward { grid-column: 2; grid-row: 3; }
  .hint { text-align: center; }
  .log-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .log-head h2 { margin: 0; }
  .log-head button { border: 1px solid #49606b; border-radius: 9px; padding: 7px 10px; color: #d5e5eb; background: #263b48; font-size: 12px; }
  .log { margin: 0; min-height: 110px; max-height: 240px; overflow-y: auto; padding: 13px; border-radius: 12px; background: #09131b; color: #bed2dd; font: 12px/1.7 ui-monospace, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
  @media (max-width: 480px) { .shell { width: min(100% - 24px, 760px); padding-top: 20px; } .mode-btn { padding: 13px; } .mode-btn strong { font-size: 13px; } .card { padding: 17px; } }
</style>
</head>
<body>
<main class="shell">
  <div class="eyebrow">ESP32 · Robot controller</div>
  <h1>Điều khiển xe</h1>
  <p class="subtitle">Chọn chế độ lái và theo dõi hoạt động của xe.</p>
  <div class="summary" aria-live="polite">
    <div><small>Trạng thái xe</small><strong id="status">Đang kết nối…</strong></div>
    <span class="connection offline" id="connection">Đang kết nối</span>
  </div>
  <div class="section-label">Chế độ lái</div>
  <nav class="modes" aria-label="Chế độ lái">
    <button class="mode-btn" id="driveAutoMode" type="button" aria-pressed="false"><strong>OBSTACLE AUTO</strong><span>Tự tránh vật cản</span></button>
    <button class="mode-btn" id="driveManualMode" type="button" aria-pressed="false"><strong>WI-FI MANUAL</strong><span>Điều khiển trực tiếp</span></button>
    <button class="mode-btn" id="driveAIMode" type="button" aria-pressed="false"><strong>AUTO + AI / AI</strong><span>Camera, tự chạy và bám mục tiêu</span></button>
  </nav>
  <section class="card" id="autoPanel" hidden>
    <h2>Xe đang tự lái</h2>
    <p>Xe dùng cảm biến để kiểm tra phía trước, lùi và chọn hướng đi khi gặp vật cản.</p>
    <div class="auto-visual"><span class="icon" aria-hidden="true">◉</span><div><b>Chế độ tự động</b><small>Chuyển sang Wi-Fi Manual để điều khiển xe.</small></div></div>
  </section>
  <section class="card" id="manualPanel" hidden>
    <h2>Điều khiển thủ công</h2>
    <p>Giữ nút mũi tên để xe di chuyển; thả nút để dừng.</p>
    <div class="controller" aria-label="Điều khiển hướng">
      <button class="control-btn" id="forward" type="button" aria-label="Tiến">↑</button>
      <button class="control-btn" id="left" type="button" aria-label="Trái">←</button>
      <button class="control-btn stop" id="stop" type="button" aria-label="Dừng">■</button>
      <button class="control-btn" id="right" type="button" aria-label="Phải">→</button>
      <button class="control-btn" id="backward" type="button" aria-label="Lùi">↓</button>
    </div>
    <p class="hint">Có thể dùng phím mũi tên · Space hoặc Esc để dừng</p>
  </section>
  <section class="card" id="aiPanel" hidden>
    <h2>Auto + AI · YOLOv8n</h2>
    <p>Mở bảng AI trên laptop để ghép nối iPhone. Chọn Bắt đầu Auto + AI để xe tự né vật cản khi chưa thấy mục tiêu và chuyển sang bám khi phát hiện mục tiêu. Mở bảng này chưa kích hoạt xe.</p>
    <label for="aiServer">Địa chỉ bảng AI trên laptop</label>
    <input id="aiServer" type="url" placeholder="https://IP-laptop:8090" value="https://localhost:8090">
    <button class="action" id="openAI" type="button">Mở camera, QR và log AI</button>
    <p id="aiHint">Trên laptop đang chạy AI, dùng https://localhost:8090. Đổi Wi-Fi thì chạy lại ai/run.ps1 để cập nhật QR cho iPhone.</p>
  </section>
  <button class="emergency" id="emergencyStop" type="button">DỪNG KHẨN CẤP · MỌI MODE</button>
  <section class="card" aria-label="Nhật ký hoạt động">
    <div class="log-head"><h2 id="logTitle">Nhật ký xe</h2><button id="clearLog" type="button">Xóa hiển thị</button></div>
    <pre class="log" id="log" aria-live="polite">Đang tải trạng thái…</pre>
  </section>
</main>
<script>
(() => {
  const byId = id => document.getElementById(id);
  const directions = ['forward', 'backward', 'left', 'right'];
  const labels = {STOPPED: 'Đã dừng', FORWARD: 'Đang tiến', BACKWARD: 'Đang lùi', LEFT: 'Đang rẽ trái', RIGHT: 'Đang rẽ phải'};
  let mode = null, held = null, heartbeat = null, pending = null, sending = false, switching = false;
  let latestId = 0, lastUptime = null, modeRevision = 0;
  let modeEpoch = null, bootId = null, viewingAI = false;
  const logs = {AUTO: [], MANUAL: [], AI: [], HYBRID: []};
  const hiddenIds = {AUTO: 0, MANUAL: 0, AI: 0, HYBRID: 0};
  const logMode = () => mode === 'HYBRID' ? 'HYBRID' : viewingAI ? 'AI' : (mode || 'MANUAL');

  function showMode(value) {
    mode = value;
    const auto = value === 'AUTO';
    const ai = viewingAI || value === 'AI' || value === 'HYBRID';
    byId('autoPanel').hidden = ai || !auto;
    byId('manualPanel').hidden = ai || value !== 'MANUAL';
    byId('aiPanel').hidden = !ai;
    for (const [id, selected] of [['driveAutoMode', !ai && auto], ['driveManualMode', !ai && value === 'MANUAL'], ['driveAIMode', ai]]) {
      byId(id).classList.toggle('active', selected);
      byId(id).setAttribute('aria-pressed', String(selected));
      byId(id).disabled = id !== 'driveAIMode' && !['AUTO', 'MANUAL', 'AI', 'HYBRID'].includes(value);
    }
    renderLog();
  }

  function clearHold() {
    if (heartbeat !== null) clearInterval(heartbeat);
    heartbeat = null;
    held = null;
    directions.forEach(id => byId(id).classList.remove('active'));
  }

  function request(path) {
    pending = {path, created: Date.now(), epoch: modeEpoch, revision: modeRevision};
    pump();
  }

  async function pump() {
    if (sending) return;
    sending = true;
    try {
      while (pending) {
        const command = pending;
        pending = null;
        const isMotion = directions.some(id => command.path === '/' + id);
        if (isMotion && (mode !== 'MANUAL' || switching || Date.now() - command.created > 400)) continue;
        if (command.path === '/stop' && (mode !== 'MANUAL' || switching)) continue;
        try {
          const response = await fetch(command.path, {cache: 'no-store', signal: AbortSignal.timeout(1200), headers: command.epoch === null ? {} : {'X-Mode-Epoch': String(command.epoch)}});
          if (!response.ok) throw new Error('HTTP ' + response.status);
          if (command.path === '/driveauto' || command.path === '/drivemanual') {
            const confirmed = await response.json();
            if (command.revision !== modeRevision) continue;
            if (confirmed.mode_epoch !== undefined) modeEpoch = confirmed.mode_epoch;
            modeRevision++;
            viewingAI = false;
            showMode(command.path === '/driveauto' ? 'AUTO' : 'MANUAL');
            switching = false;
          }
        } catch (_) {
          if (command.revision !== modeRevision) continue;
          clearHold();
          switching = false;
          pending = null;
          byId('connection').textContent = 'Mất kết nối';
          byId('connection').classList.add('offline');
          byId('status').textContent = 'Không rõ trạng thái';
        }
      }
    } finally { sending = false; }
  }

  function stopMove(force = false) {
    const wasHeld = held !== null;
    clearHold();
    if ((wasHeld || force) && mode === 'MANUAL' && !switching) request('/stop');
  }

  function startMove(direction) {
    if (mode !== 'MANUAL' || viewingAI || switching || held === direction) return;
    clearHold();
    held = direction;
    byId(direction).classList.add('active');
    request('/' + direction);
    heartbeat = setInterval(() => request('/' + direction), 250);
  }

  directions.forEach(direction => {
    const button = byId(direction);
    button.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      startMove(direction);
    });
    const release = () => { if (held === direction) stopMove(); };
    button.addEventListener('pointerup', release);
    button.addEventListener('pointercancel', release);
    button.addEventListener('lostpointercapture', release);
  });
  byId('stop').addEventListener('click', () => stopMove(true));

  function switchMode(path) {
    if (viewingAI && ((path === '/driveauto' && mode === 'AUTO') || (path === '/drivemanual' && mode === 'MANUAL'))) {
      viewingAI = false; showMode(mode); return;
    }
    if (switching || (path === '/driveauto' && mode === 'AUTO') || (path === '/drivemanual' && mode === 'MANUAL')) return;
    clearHold();
    switching = true;
    pending = {path, created: Date.now(), epoch: modeEpoch, revision: modeRevision};
    pump();
  }
  byId('driveAutoMode').addEventListener('click', () => switchMode('/driveauto'));
  byId('driveManualMode').addEventListener('click', () => switchMode('/drivemanual'));
  byId('driveAIMode').addEventListener('click', () => {
    stopMove(); viewingAI = true; showMode(mode);
  });
  byId('openAI').addEventListener('click', () => {
    try {
      const url = new URL(byId('aiServer').value);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error();
      url.searchParams.set('robot', window.location.origin);
      window.location.href = url.href;
    } catch (_) { byId('aiHint').textContent = 'Nhập địa chỉ https://IP-laptop:8090 hợp lệ.'; }
  });
  byId('emergencyStop').addEventListener('click', async () => {
    clearHold(); pending = null; modeRevision++; switching = false;
    modeEpoch = null; showMode(null);
    try {
      const response = await fetch('/estop', {method: 'POST', signal: AbortSignal.timeout(1200)});
      if (!response.ok) throw new Error();
      byId('status').textContent = 'Đã gửi dừng khẩn cấp';
    } catch (_) { byId('status').textContent = 'Chưa xác nhận dừng; kiểm tra kết nối xe'; }
  });

  const keys = {ArrowUp: 'forward', ArrowDown: 'backward', ArrowLeft: 'left', ArrowRight: 'right'};
  document.addEventListener('keydown', event => {
    if (event.repeat) return;
    if (keys[event.key]) { event.preventDefault(); startMove(keys[event.key]); }
    else if (event.key === 'Escape' || event.code === 'Space') { event.preventDefault(); stopMove(true); }
  });
  document.addEventListener('keyup', event => {
    if (keys[event.key] && held === keys[event.key]) { event.preventDefault(); stopMove(); }
  });
  window.addEventListener('blur', () => { if (held !== null) stopMove(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && held !== null) stopMove(); });

  function renderLog() {
    const lines = logs[logMode()] || [];
    byId('logTitle').textContent = 'Nhật ký ' + logMode();
    byId('log').textContent = lines.length ? lines.join('\n') : 'Chưa có sự kiện.';
    byId('log').scrollTop = byId('log').scrollHeight;
  }
  byId('clearLog').addEventListener('click', () => {
    hiddenIds[logMode()] = latestId;
    (logs[logMode()] || []).length = 0;
    renderLog();
  });

  async function poll() {
    try {
      const revision = modeRevision;
      const response = await fetch('/status', {cache: 'no-store', signal: AbortSignal.timeout(2000)});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const state = await response.json();
      if (state.uptime_ms !== undefined) {
        if ((lastUptime !== null && state.uptime_ms < lastUptime) || (bootId !== null && state.boot_id !== bootId)) {
          latestId = 0;
          Object.values(logs).forEach(lines => { lines.length = 0; });
          Object.keys(hiddenIds).forEach(key => { hiddenIds[key] = 0; });
        }
        lastUptime = state.uptime_ms;
        bootId = state.boot_id;
      }
      if (!switching && revision === modeRevision) {
        if (modeEpoch !== state.mode_epoch) { clearHold(); pending = null; }
        modeEpoch = state.mode_epoch;
        if (state.drive_mode !== 'MANUAL') clearHold();
        showMode(state.drive_mode);
      }
      byId('status').textContent = labels[state.movement] || state.movement;
      byId('connection').textContent = 'Đã kết nối';
      byId('connection').classList.remove('offline');
      for (const event of state.events || []) {
        if (event.id > latestId) {
          latestId = event.id;
          if (logs[event.mode] && event.id > hiddenIds[event.mode]) {
            const seconds = Math.floor((event.ms || 0) / 1000);
            const stamp = String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
            logs[event.mode].push('[' + stamp + '] [' + event.mode + '] ' + event.message);
          }
        }
      }
      Object.values(logs).forEach(lines => { if (lines.length > 60) lines.splice(0, lines.length - 60); });
      renderLog();
    } catch (_) {
      byId('connection').textContent = 'Mất kết nối';
      byId('connection').classList.add('offline');
      byId('status').textContent = 'Không rõ trạng thái';
    }
    setTimeout(poll, 750);
  }
  poll();
})();
</script>
</body>
</html>
)rawliteral";
