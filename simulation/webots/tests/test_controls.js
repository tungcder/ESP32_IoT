const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../controllers/esp32_car/controls.js'), 'utf8');

function harness() {
  const calls = [], intervals = new Map(), elements = new Map();
  let now = 0, timerId = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      listeners: {}, classes: new Set(), textContent: '',
      setPointerCapture() {},
      addEventListener(name, handler) { this.listeners[name] = handler; },
      fire(name, extra = {}) {
        this.listeners[name]?.({button: 0, pointerId: 1, preventDefault() {}, ...extra});
      },
      classList: {
        add(name) { elements.get(id).classes.add(name); },
        remove(name) { elements.get(id).classes.delete(name); },
        toggle(name, enabled) {
          if (enabled) this.add(name); else this.remove(name);
        }
      }
    });
    return elements.get(id);
  }
  const document = element('document');
  document.getElementById = element;
  const window = element('window');
  vm.runInNewContext(source, {
    document, window, Date: {now: () => now}, AbortSignal,
    setInterval(callback) { intervals.set(++timerId, callback); return timerId; },
    clearInterval(id) { intervals.delete(id); },
    fetch(url) { return new Promise((resolve, reject) => calls.push({
      url, resolve: () => resolve({ok: true}), reject
    })); }
  });
  return {calls, element, window, document,
    heartbeat: () => [...intervals.values()].forEach(callback => callback()),
    advance: ms => { now += ms; }, intervals};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('mode button sends AUTO once without a competing stop', async () => {
  const h = harness();
  h.element('driveAutoMode').fire('click');
  assert.deepEqual(h.calls.map(c => c.url), ['/driveauto']);
  h.calls[0].resolve();
  await flush();
  assert.equal(h.calls.length, 1);
});

test('AUTO is not cancelled when switching tabs, explicit stop still works', async () => {
  const h = harness();
  h.element('driveAutoMode').fire('click');
  h.calls[0].resolve();
  await flush();
  h.window.fire('blur');
  h.document.hidden = true;
  h.document.fire('visibilitychange');
  assert.deepEqual(h.calls.map(c => c.url), ['/driveauto']);
  h.element('stop').fire('click');
  assert.equal(h.calls[1].url, '/stop');
  h.calls[1].resolve();
  await flush();
});

test('releasing replaces queued heartbeats with stop', async () => {
  const h = harness();
  h.element('forward').fire('pointerdown');
  h.heartbeat(); h.heartbeat(); h.heartbeat();
  assert.equal(h.calls.length, 1);
  h.element('forward').fire('pointerup');
  h.calls[0].resolve();
  await flush();
  assert.deepEqual(h.calls.map(c => c.url), ['/forward', '/stop']);
  assert.equal(h.intervals.size, 0);
  h.calls[1].resolve();
  await flush();
  assert.equal(h.calls.length, 2);
});

test('stale waiting motion is discarded after a slow request', async () => {
  const h = harness();
  h.element('forward').fire('pointerdown');
  h.element('right').fire('pointerdown');
  h.advance(500);
  h.calls[0].resolve();
  await flush();
  assert.deepEqual(h.calls.map(c => c.url), ['/forward']);
});

test('network failure cancels heartbeat and requests stop', async () => {
  const h = harness();
  h.document.fire('keydown', {key: 'ArrowUp'});
  h.calls[0].reject(new Error('offline'));
  await flush();
  assert.equal(h.intervals.size, 0);
  assert.equal(h.calls[1].url, '/stop');
  h.calls[1].resolve();
  await flush();
  h.document.fire('keydown', {key: 'ArrowUp', repeat: true});
  assert.equal(h.calls.length, 2);
});

test('LED controls follow actual server state', () => {
  const h = harness();
  h.window.webotsControl.updateState({led_mode: 'MANUAL', leds: [true, true, true, true]});
  assert.equal(h.element('allLed').textContent, 'ALL LEDs ON');
  h.element('allLed').fire('click');
  assert.equal(h.calls[0].url, '/ledoff');
});
