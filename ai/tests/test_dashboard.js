const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const source = page.match(/<script>([\s\S]*?)<\/script>/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

async function harness({fallback = false} = {}) {
  const elements = new Map(), timers = new Map(), intervals = [], frames = [];
  let now = 1000, nextTimer = 0, draws = 0, failPoll = false;
  let snapshot = {
    active: false, model_ready: true, model_error: '', inference_ready: true,
    camera_ready: true, camera_connected: true, camera_error: '', frame_age_ms: 30,
    robot_online: true, robot_error: '', robot: {drive_mode: 'MANUAL', movement: 'STOPPED'},
    config: {robot_url: 'http://172.20.10.3', public_url: 'https://172.20.10.5:8090'},
    decision: {state: 'IDLE', reason: 'Idle'}, events: [], pair_url: 'pair', pair_remaining: 600,
    https: {setup_url: 'setup', fingerprint: 'test', expires: '2027-11-10'}
  };
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      hidden: id === 'video', src: '', value: '', listeners: {},
      addEventListener(event, fn) { this.listeners[event] = fn; },
      getContext() { return {drawImage() { draws++; }}; }
    });
    return elements.get(id);
  }
  class ImageFallback {
    constructor() { this.width = 480; this.height = 640; }
    set src(value) { Promise.resolve().then(() => this.onload()); }
  }
  vm.runInNewContext(source, {
    document: {getElementById: element}, location: {search: ''}, URLSearchParams, Date,
    URL: {createObjectURL() { return 'blob:frame'; }, revokeObjectURL() {}},
    performance: {now: () => now}, AbortSignal, AbortController, Image: ImageFallback,
    createImageBitmap: fallback ? undefined : async () => ({width: 480, height: 640, close() {}}),
    setTimeout(fn, ms) { timers.set(++nextTimer, {fn, ms}); return nextTimer; },
    clearTimeout(id) { timers.delete(id); }, setInterval(fn) { intervals.push(fn); },
    fetch(url) {
      if (url.startsWith('/frame.jpg')) return new Promise(resolve => frames.push(resolve));
      if (failPoll) return Promise.reject(Error('Temporary status failure'));
      return Promise.resolve({ok: true, json: async () => structuredClone(snapshot)});
    }
  });
  await flush();
  return {
    element, timers, frames, intervals, draws: () => draws,
    setNow(value) { now = value; },
    setSnapshot(values) { snapshot = {...snapshot, ...values}; },
    failPoll() { failPoll = true; },
    async image(age) {
      assert(frames.length, 'No pending frame request');
      frames.shift()({ok: true, status: 200, blob: async () => ({}),
        headers: {get: name => name === 'X-Frame-Age-Ms' ? String(age) : '1'}});
      await flush();
    },
    async poll() {
      const entry = [...timers].find(([, timer]) => timer.ms === 500);
      assert(entry, 'Missing status poll timer');
      timers.delete(entry[0]); await entry[1].fn(); await flush();
    }
  };
}

test('valid 400 ms image is displayed with no waiting-text overlay', async () => {
  const h = await harness();
  await h.image(400);
  assert.equal(h.draws(), 1);
  assert.equal(h.element('video').hidden, false);
  assert.equal(h.element('cameraPlaceholder').hidden, true);
});

test('fallback decoder works without createImageBitmap or bitmap.close', async () => {
  const h = await harness({fallback: true});
  await h.image(100);
  assert.equal(h.draws(), 1);
  assert.equal(h.element('video').hidden, false);
});

test('one stale status sample does not reset fresh video or restart its stream', async () => {
  const h = await harness();
  await h.image(100);
  h.setSnapshot({camera_ready: false});
  await h.poll();
  assert.equal(h.element('video').hidden, false);
  assert.equal(h.element('start').disabled, true);
  assert.equal(h.frames.length, 0);
});

test('temporary status failure keeps fresh video while disabling AI start', async () => {
  const h = await harness();
  await h.image(100);
  h.failPoll(); await h.poll();
  assert.equal(h.element('video').hidden, false);
  assert.equal(h.element('start').disabled, true);
});

test('displayed video still expires after 500 ms', async () => {
  const h = await harness();
  await h.image(100);
  h.setNow(1401);
  h.intervals.forEach(fn => fn());
  assert.equal(h.element('video').hidden, true);
  assert.equal(h.element('cameraPlaceholder').hidden, false);
});

test('expired image is skipped without a tight request loop', async () => {
  const h = await harness();
  await h.image(501);
  assert.equal(h.draws(), 0);
  assert.equal(h.frames.length, 0);
  assert([...h.timers.values()].some(timer => timer.ms === 67));
});
