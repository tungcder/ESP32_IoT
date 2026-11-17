// Exercise the firmware dashboard without connecting to or moving a real robot.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/web_page.cpp'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

async function dashboard(overrides = {}) {
  const nodes = new Map(), requests = [], documentListeners = {};
  for (const [, id] of source.matchAll(/\bid="([^"]+)"/g)) {
    const classes = new Set();
    nodes.set(id, {
      hidden: false, disabled: false, style: {}, listeners: {}, attributes: {},
      classList: {
        add: name => classes.add(name), remove: name => classes.delete(name),
        contains: name => classes.has(name),
        toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); }
      },
      addEventListener(type, callback) { this.listeners[type] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      setPointerCapture() {}
    });
  }
  const state = {
    drive_mode: 'MANUAL', movement: 'STOPPED', mode_epoch: 7, boot_id: 1,
    uptime_ms: 1000, events: [], manual_input: 'WEB', gamepad_age_ms: -1,
    gamepad_left: 0, gamepad_right: 0, ...overrides
  };
  vm.runInNewContext(script, {
    document: {
      getElementById: id => nodes.get(id),
      addEventListener(type, callback) { documentListeners[type] = callback; }
    },
    window: {addEventListener() {}, location: {origin: 'http://robot.local'}},
    URL, AbortSignal, setTimeout() {}, setInterval() { return 1; }, clearInterval() {},
    fetch: async (url, options = {}) => {
      requests.push({url, options});
      if (url.startsWith('/manualinput?source=')) {
        state.manual_input = url.endsWith('gamepad') ? 'GAMEPAD' : 'WEB';
        state.movement = 'STOPPED';
      }
      return {ok: true, json: async () => ({...state})};
    }
  });
  await flush();
  return {
    nodes, requests,
    key(type, key) { documentListeners[type]({key, repeat: false, preventDefault() {}}); }
  };
}

(async () => {
  // Web control must still issue motion and stop on key release.
  let page = await dashboard();
  assert.equal(page.nodes.get('webControls').hidden, false);
  assert.equal(page.nodes.get('padPanel').hidden, true);
  page.key('keydown', 'ArrowUp');
  await flush();
  assert.equal(page.requests.at(-1).url, '/forward');
  assert.equal(page.requests.at(-1).options.headers['X-Mode-Epoch'], '7');
  page.key('keyup', 'ArrowUp');
  await flush();
  assert.equal(page.requests.at(-1).url, '/stop');

  // Stop must revoke gamepad input so the next held-stick command cannot resume motion.
  page = await dashboard({manual_input: 'GAMEPAD', gamepad_age_ms: 100,
    gamepad_left: -30, gamepad_right: 60});
  assert.equal(page.nodes.get('webControls').hidden, true);
  assert.equal(page.nodes.get('padPanel').hidden, false);
  assert.equal(page.nodes.get('padValL').textContent, -30);
  assert.equal(page.nodes.get('padValR').textContent, 60);
  const requestsBeforeKey = page.requests.length;
  page.key('keydown', 'ArrowUp');
  await flush();
  assert.equal(page.requests.length, requestsBeforeKey);
  page.nodes.get('padStop').listeners.click();
  await flush();
  assert.equal(page.requests.at(-1).url, '/manualinput?source=web');
  assert.equal(page.nodes.get('webControls').hidden, false);
  assert.equal(page.nodes.get('padPanel').hidden, true);

  // Expired telemetry must not display stale motor output as live.
  page = await dashboard({manual_input: 'GAMEPAD', gamepad_age_ms: 1500,
    gamepad_left: 80, gamepad_right: 80});
  assert.equal(page.nodes.get('padDot').classList.contains('live'), false);
  assert.equal(page.nodes.get('padValL').textContent, 0);
  assert.equal(page.nodes.get('padValR').textContent, 0);

  // Switching input must use the epoch and apply the server confirmation.
  page = await dashboard();
  page.nodes.get('inputPad').listeners.click();
  await flush();
  assert.equal(page.requests.at(-1).url, '/manualinput?source=gamepad');
  assert.equal(page.requests.at(-1).options.headers['X-Mode-Epoch'], '7');
  assert.equal(page.nodes.get('padPanel').hidden, false);
  page.nodes.get('inputWeb').listeners.click();
  await flush();
  assert.equal(page.requests.at(-1).url, '/manualinput?source=web');
  assert.equal(page.nodes.get('webControls').hidden, false);

  // Auto must not accept web motion or manual-input selection from this page.
  page = await dashboard({drive_mode: 'AUTO'});
  const requestsBeforeAutoInput = page.requests.length;
  page.nodes.get('inputPad').listeners.click();
  page.key('keydown', 'ArrowUp');
  await flush();
  assert.equal(page.requests.length, requestsBeforeAutoInput);

  // Older firmware and Webots must retain web controls without an unsupported selector.
  page = await dashboard({manual_input: undefined});
  assert.equal(page.nodes.get('manualInputSelector')?.hidden, true);
  assert.equal(page.nodes.get('webControls').hidden, false);

  // Emergency Stop remains available regardless of the selected input.
  page = await dashboard({manual_input: 'GAMEPAD'});
  await page.nodes.get('emergencyStop').listeners.click();
  assert.equal(page.requests.at(-1).url, '/estop');
  assert.equal(page.requests.at(-1).options.method, 'POST');
  console.log('Manual dashboard: 7 scenarios passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
