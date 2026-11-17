// Run the actual dashboard script with a minimal browser surface and API fixtures.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'ai/web/index.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

async function dashboard(state) {
  const nodes = new Map();
  for (const match of source.matchAll(/\bid="([^"]+)"/g)) {
    const listeners = {};
    nodes.set(match[1], {textContent:'', value:'', disabled:false, hidden:false, listeners,
      addEventListener(type, callback) { listeners[type] = callback; },
      replaceChildren() {}, appendChild() {}});
  }
  const requests = [];
  const context = {document:{getElementById:id=>nodes.get(id)}, location:{search:''},
    URLSearchParams, URL, AbortSignal, AbortController, performance,
    setTimeout(){return 1;}, clearTimeout(){}, setInterval(){return 1;},
    fetch:async (url, options={}) => {
      requests.push({url, options});
      return {ok:true, status:200, json:async()=>url.startsWith('/api/state')?state:{message:'Đã thực hiện'}};
    }};
  vm.runInNewContext(script, context);
  await flush();
  return {nodes, requests};
}

function ready(overrides={}) {
  return {active:false, model_ready:true, inference_ready:true, camera_ready:true,
    robot_online:true, camera_connected:false, config:{robot_url:'http://127.0.0.1:8081',public_url:''},
    robot:{drive_mode:'MANUAL',hybrid_supported:true,movement:'STOPPED'},
    decision:{state:'IDLE',reason:''}, events:[],event_id:0, pair_remaining:600,
    https:{setup_url:'https://localhost:8090/setup'}, ...overrides};
}

(async()=>{
  let page = await dashboard(ready());
  assert.equal(page.nodes.get('startHybrid').disabled, false);
  await page.nodes.get('startHybrid').listeners.click();
  assert.deepEqual(JSON.parse(page.requests.at(-1).options.body), {mode:'HYBRID'});
  assert.equal(page.requests.at(-1).url, '/api/start');

  page = await dashboard(ready({robot:{drive_mode:'AI',movement:'STOPPED'}}));
  assert.equal(page.nodes.get('startHybrid').disabled, true);
  assert.equal(page.nodes.get('start').disabled, false);

  page = await dashboard(ready({active:true, control_mode:'HYBRID',
    robot:{drive_mode:'HYBRID',hybrid_supported:true,hybrid_state:'SEARCH',movement:'FORWARD'},
    decision:{state:'SEARCH',reason:'Đang tìm mục tiêu'}}));
  assert.equal(page.nodes.get('startHybrid').disabled, true);
  assert.equal(page.nodes.get('start').disabled, true);
  assert.equal(page.nodes.get('stop').disabled, false);
  assert.match(page.nodes.get('behavior').textContent, /Auto/);
  assert.match(page.nodes.get('modeHealth').textContent, /Auto \+ AI/);
  await page.nodes.get('stop').listeners.click();
  assert.equal(page.requests.at(-1).url, '/api/stop');

  page = await dashboard(ready({camera_ready:false}));
  assert.equal(page.nodes.get('startHybrid').disabled, true);

  page = await dashboard(ready());
  page.nodes.get('configForm').listeners.input();
  assert.equal(page.nodes.get('startHybrid').disabled, true);
  console.log('Dashboard: 5 scenarios passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
