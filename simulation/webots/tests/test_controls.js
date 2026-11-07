const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, '../../../src/web_page.cpp'), 'utf8');
const source = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const calls = [], elements = new Map(), intervals = new Map();
  let timerId = 0;
  function element(id) {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, {
        hidden: id === 'manualPanel' || id === 'autoPanel',
        textContent: '', scrollTop: 0, scrollHeight: 0,
        listeners: {}, attributes: {},
        setPointerCapture() {},
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(name, handler) { this.listeners[name] = handler; },
        fire(name, extra = {}) {
          this.listeners[name]?.({button: 0, pointerId: 1, preventDefault() {}, ...extra});
        },
        classList: {
          add(name) { classes.add(name); },
          remove(name) { classes.delete(name); },
          toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
          contains(name) { return classes.has(name); }
        }
      });
    }
    return elements.get(id);
  }
  const document = element('document');
  document.getElementById = element;
  const window = element('window');
  vm.runInNewContext(source, {
    document, window, Date, AbortSignal,
    setInterval(fn) { intervals.set(++timerId, fn); return timerId; },
    clearInterval(id) { intervals.delete(id); },
    setTimeout() {},
    fetch(url) {
      return new Promise((resolve, reject) => calls.push({
        url,
        resolve(data = {}) { resolve({ok: true, json: async () => data}); },
        reject
      }));
    }
  });
  const status = (mode, movement = 'STOPPED', events = []) => ({
    drive_mode: mode, movement, events
  });
  return {calls, element, document, window, intervals, status};
}

test('state selects the visible panel and renders robot events', async () => {
  const h = harness();
  assert.equal(h.calls[0].url, '/status');
  assert.equal(h.element('manualPanel').hidden, true);
  h.calls[0].resolve(h.status('AUTO', 'FORWARD', [
    {id: 1, ms: 1234, mode: 'AUTO', message: 'Obstacle Auto selected'}
  ]));
  await flush();
  assert.equal(h.element('autoPanel').hidden, false);
  assert.equal(h.element('manualPanel').hidden, true);
  assert.match(h.element('log').textContent, /Obstacle Auto selected/);
  h.element('forward').fire('pointerdown');
  h.element('stop').fire('click');
  assert.deepEqual(h.calls.map(call => call.url), ['/status']);
});

test('held manual command is serialized before switching to auto', async () => {
  const h = harness();
  h.calls[0].resolve(h.status('MANUAL'));
  await flush();
  assert.equal(h.element('manualPanel').hidden, false);
  h.element('forward').fire('pointerdown');
  assert.equal(h.calls[1].url, '/forward');
  h.element('driveAutoMode').fire('click');
  h.element('forward').fire('pointerup');
  assert.equal(h.intervals.size, 0);
  h.calls[1].resolve();
  await flush();
  assert.deepEqual(h.calls.map(call => call.url), ['/status', '/forward', '/driveauto']);
  h.calls[2].resolve();
  await flush();
  assert.equal(h.element('manualPanel').hidden, true);
  h.window.fire('blur');
  h.element('right').fire('pointerdown');
  assert.equal(h.calls.length, 3);
});

test('manual release replaces queued heartbeats with stop', async () => {
  const h = harness();
  h.calls[0].resolve(h.status('MANUAL'));
  await flush();
  h.element('left').fire('pointerdown');
  for (const heartbeat of h.intervals.values()) heartbeat();
  h.element('left').fire('pointerup');
  h.calls[1].resolve();
  await flush();
  assert.deepEqual(h.calls.map(call => call.url), ['/status', '/left', '/stop']);
  assert.equal(h.intervals.size, 0);
});

test('auto to manual enables controls after mode response', async () => {
  const h = harness();
  h.calls[0].resolve(h.status('AUTO'));
  await flush();
  h.element('driveManualMode').fire('click');
  assert.equal(h.calls[1].url, '/drivemanual');
  h.element('forward').fire('pointerdown');
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve();
  await flush();
  assert.equal(h.element('manualPanel').hidden, false);
  h.element('forward').fire('pointerdown');
  assert.equal(h.calls[2].url, '/forward');
});
