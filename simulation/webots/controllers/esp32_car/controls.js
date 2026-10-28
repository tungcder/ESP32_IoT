// Controls for the Webots page; firmware HTML and GPIO code are unchanged.
(() => {
  const directions = ['forward', 'backward', 'left', 'right'];
  let held = null, heartbeat = null, pending = null, sending = false;
  let ledMode = 'AUTO', allLedsOn = false;
  const button = id => document.getElementById(id);

  function clearHold() {
    if (heartbeat !== null) clearInterval(heartbeat);
    heartbeat = null;
    held = null;
    directions.forEach(id => button(id).classList.remove('active'));
  }

  async function pump() {
    if (sending) return;
    sending = true;
    try {
      while (pending) {
        const command = pending;
        pending = null;
        // Never replay queued motion or mode changes after a stalled connection.
        if (command.path !== '/stop' && Date.now() - command.created > 400) continue;
        try {
          const response = await fetch(command.path, {
            cache: 'no-store', signal: AbortSignal.timeout(800)
          });
          if (!response.ok) throw new Error('HTTP ' + response.status);
        } catch (_) {
          clearHold();
          pending = command.path === '/stop' ? null : {path: '/stop', created: Date.now()};
          button('status').textContent = 'MẤT KẾT NỐI';
        }
      }
    } finally { sending = false; }
  }

  function drive(path) {
    // Only one request in flight and the latest waiting drive command is kept.
    pending = {path, created: Date.now()};
    return pump();
  }

  function stopMove() {
    clearHold();
    button('status').textContent = 'STOPPED';
    return drive('/stop');
  }

  function startMove(direction) {
    if (held === direction) return;
    clearHold();
    held = direction;
    button(direction).classList.add('active');
    drive('/' + direction);
    heartbeat = setInterval(() => drive('/' + direction), 250);
  }

  directions.forEach(direction => {
    const control = button(direction);
    control.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault();
      control.setPointerCapture(event.pointerId);
      startMove(direction);
    });
    const release = () => { if (held === direction) stopMove(); };
    control.addEventListener('pointerup', release);
    control.addEventListener('pointercancel', release);
    control.addEventListener('lostpointercapture', release);
  });

  button('stop').addEventListener('click', stopMove);
  for (const [id, path] of [['driveAutoMode', '/driveauto'], ['driveManualMode', '/drivemanual']]) {
    button(id).addEventListener('click', () => {
      clearHold();
      // Each mode endpoint already stops the car; no competing /stop request.
      drive(path);
    });
  }

  async function ledCommand(path) {
    try {
      const response = await fetch(path, {cache: 'no-store', signal: AbortSignal.timeout(800)});
      if (!response.ok) throw new Error('HTTP ' + response.status);
    } catch (_) { button('status').textContent = 'MẤT KẾT NỐI'; }
  }
  button('autoMode').addEventListener('click', () => ledCommand('/ledauto'));
  button('manualMode').addEventListener('click', () => ledCommand('/ledmanual'));
  button('allLed').addEventListener('click', () => {
    if (ledMode === 'MANUAL') ledCommand(allLedsOn ? '/ledoff' : '/ledon');
  });
  const keys = {ArrowUp: 'forward', ArrowDown: 'backward', ArrowLeft: 'left', ArrowRight: 'right'};
  document.addEventListener('keydown', event => {
    if (event.repeat) return;
    if (keys[event.key]) { event.preventDefault(); startMove(keys[event.key]); }
    else if (event.key === 'Escape' || event.code === 'Space') { event.preventDefault(); stopMove(); }
  });
  document.addEventListener('keyup', event => {
    if (keys[event.key] && held === keys[event.key]) { event.preventDefault(); stopMove(); }
  });
  window.addEventListener('blur', stopMove);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopMove(); });
  window.stopMove = stopMove;
  window.webotsControl = {
    testTimeout() { clearHold(); drive('/forward'); },
    updateState(state) {
      ledMode = state.led_mode;
      allLedsOn = state.leds.every(Boolean);
      button('autoMode').classList.toggle('active', ledMode === 'AUTO');
      button('manualMode').classList.toggle('active', ledMode === 'MANUAL');
      button('allLed').classList.toggle('on', allLedsOn);
      button('allLed').textContent = allLedsOn ? 'ALL LEDs ON' : 'ALL LEDs OFF';
    }
  };
})();
