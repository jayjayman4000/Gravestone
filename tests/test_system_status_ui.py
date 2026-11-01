"""Real console/app scripts in a Node VM with deterministic DOM/network/clock fixtures.

These fixtures exercise UI behavior, not physical battery or browser acceptance.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor() { this.handlers={}; this.children=[]; this.textContent=''; this.value=''; this.isConnected=true; this.open=false; }
  addEventListener(k,fn) { (this.handlers[k] ??= []).push(fn); }
  fire(k) { for(const fn of this.handlers[k]||[]) fn({preventDefault(){}}); }
  append(...children) { for(const child of children) { child.parentElement=this; this.children.push(child); if(child.id) nodes[child.id]=child; } }
  replaceChildren(...children) { this.children=children; }
  setAttribute(k,v) { this[k]=v; }
  focus() { document.activeElement=this; }
  showModal() { this.open=true; }
  close() { this.open=false; this.fire('close'); }
}
const root=process.argv[1];
const html=fs.readFileSync(root+'/app/static/index.html','utf8');
const nodes={};
for(const m of html.matchAll(/\bid="([^"]+)"/g)) { nodes[m[1]]=new Node(); nodes[m[1]].parentElement=new Node(); }
for(const m of html.matchAll(/id="([^"]+)"[^>]*>([^<]*)</g)) nodes[m[1]].textContent=m[2];
const document={visibilityState:'visible',activeElement:null,getElementById:id=>nodes[id],createElement:()=>new Node()};
const window=new Node();
let now=0, nextID=0;
const timers=new Map();
const setTimeout=(fn,delay)=>{const id=++nextID;timers.set(id,{fn,due:now+delay});return id;};
const clearTimeout=id=>timers.delete(id);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function tick(ms) {
 const end=now+ms;
 while(true) {
  const next=[...timers].filter(([,t])=>t.due<=end).sort((a,b)=>a[1].due-b[1].due)[0];
  if(!next) break;
  now=next[1].due; timers.delete(next[0]); next[1].fn(); await settle();
 }
 now=end; await settle();
}
const sample=(percent=73,status='Discharging',free=4000000000)=>({
 battery:{available:true,percent,status,source:'sysfs'},
 storage:{available:true,free_bytes:free,total_bytes:8000000000}
});
let handler=async()=>sample();
const requests=[];
const fetch=async(url,options={})=>{
 if(url==='/api/system') { requests.push({options,time:now}); return await handler(options); }
 return {ok:true,json:async()=>url==='/api/library'?{documents:[]}:url==='/api/notes'?{text:'saved'}:{status:'prototype'}};
};
const respond=data=>({ok:true,json:async()=>data});
const setSample=data=>{handler=async()=>respond(data);};
setSample(sample());
const context=vm.createContext({document,window,fetch,URL,TextEncoder,AbortController,console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(root+'/app/static/app.js','utf8'),context);
vm.runInContext(fs.readFileSync(root+'/app/static/console.js','utf8'),context);
const battery=nodes['system-battery'];
const storage=nodes['system-storage'];
(async()=>{await settle();
"""


@unittest.skipUnless(shutil.which('node'), 'Node.js required for telemetry behavior verification')
class SystemStatusUITests(unittest.TestCase):
    def run_js(self, body):
        # Isolate fake-clock bindings from Node's global lexical environment:
        # undici's native fetch must retain real timers and their .unref().
        script = "(function(){\n" + HARNESS + body + "\n})().catch(e=>{console.error(e);process.exitCode=1;});\n})();"
        result = subprocess.run(['node', '-e', script, str(ROOT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_poll_reads_changed_battery_and_storage_without_touching_workspace(self):
        self.run_js(r"""
assert.match(battery.textContent,/73%/);
assert.equal(storage.textContent,'4.0 GB free');
nodes['note-text'].value='Unsaved private draft';
nodes['nav-notebook'].fire('click');
const focus=document.activeElement;
const readiness=nodes['runtime-status'].textContent;
setSample(sample(72,'Discharging',3000000000));
await tick(14999); assert.equal(requests.length,1);
await tick(1); assert.equal(requests.length,2,'Refresh real telemetry after 15 seconds');
assert.match(battery.textContent,/72%/);
assert.equal(storage.textContent,'3.0 GB free');
assert.equal(nodes['note-text'].value,'Unsaved private draft');
assert.equal(nodes.notebook.open,true);
assert.equal(document.activeElement,focus);
assert.equal(nodes['runtime-status'].textContent,readiness);
assert.equal(requests[1].options.cache,'no-store');
""")


    def test_charging_unplugged_and_full_follow_status_not_boolean(self):
        self.run_js(r"""
for(const [status,percent] of [['Charging',73],['Discharging',72],['Full',100],['Not charging',100],['Unknown',99]]) {
 const data=sample(percent,status);
 data.battery.charging=true; // A contradictory legacy boolean must not invent charging.
 setSample(data); await tick(15000);
 assert.equal(battery.textContent,percent+'% · '+status);
}
""")


    def test_failed_request_clears_live_values_and_recovers(self):
        self.run_js(r"""
handler=async()=>{throw new Error('fixture disconnected');};
await tick(15000);
assert.match(battery.textContent,/Unavailable.*stale/i);
assert.match(storage.textContent,/Unavailable.*stale/i);
assert.doesNotMatch(battery.textContent,/73%/);
assert.doesNotMatch(storage.textContent,/4.0 GB/);
assert.match(storage.title,/failed|unavailable/i);
setSample(sample(72,'Charging',2000000000)); await tick(15000);
assert.equal(battery.textContent,'72% · Charging');
assert.equal(storage.textContent,'2.0 GB free');
assert.doesNotMatch(storage.title,/failed|stale/i);
""")


    def test_absent_or_invalid_hardware_clears_previous_readings_then_recovers(self):
        self.run_js(r"""
for(const data of [
 {battery:{available:false},storage:{available:false}},
 sample(-1,'Charging',-1),
 {battery:{available:true,percent:'72'},storage:{available:true,free_bytes:9,total_bytes:8}},
 {}]) {
 setSample(data); await tick(15000);
 assert.equal(battery.textContent,'Unavailable');
 assert.equal(storage.textContent,'Unavailable');
 assert.doesNotMatch(battery.title,/failed|stale/i);
}
setSample(sample(0,'Discharging',0)); await tick(15000);
assert.equal(battery.textContent,'0% · Discharging');
assert.equal(storage.textContent,'0.0 GB free');
""")


    def test_visibility_pauses_polling_and_resume_focus_pageshow_do_not_overlap(self):
        self.run_js(r"""
document.visibilityState='hidden'; window.fire('visibilitychange');
assert.match(battery.textContent,/stale|paused/i);
assert.doesNotMatch(battery.textContent,/73%/);
await tick(60000); assert.equal(requests.length,1,'No polling while hidden');
window.fire('focus'); window.fire('pageshow'); await settle();
assert.equal(requests.length,1,'Hidden focus must not request');
let finish;
handler=async()=>new Promise(resolve=>{finish=resolve;});
document.visibilityState='visible'; window.fire('visibilitychange');
window.fire('focus'); window.fire('pageshow'); await settle();
assert.equal(requests.length,2,'Resume once despite concurrent wake events');
await tick(1000); window.fire('focus'); await settle();
assert.equal(requests.length,2,'One request in flight');
finish(respond(sample(72,'Charging'))); await settle();
assert.equal(battery.textContent,'72% · Charging');
setSample(sample(71)); await tick(15000);
assert.equal(requests.length,3,'Exactly one recurring timer');
assert.match(battery.textContent,/71%/);
window.fire('focus'); await settle(); assert.equal(requests.length,4,'Focus refreshes promptly');
window.fire('pageshow'); await settle(); assert.equal(requests.length,5,'BFCache return refreshes promptly');
""")


    def test_request_timeout_aborts_network_and_body_then_recovers_without_overlap(self):
        self.run_js(r"""
for(const phase of ['network','body']) {
 let active=0, maximum=0, aborted=false, release;
 handler=async options=>{
  active++; maximum=Math.max(maximum,active);
  const pending=new Promise((resolve,reject)=>{
   release=resolve;
   options.signal.addEventListener('abort',()=>{
    aborted=true; active--; reject(new Error('fixture abort'));
   },{once:true});
  });
  return phase==='network'?pending:{ok:true,json:()=>pending};
 };
 window.fire('focus'); await settle();
 const before=requests.length;
 assert.ok(requests.at(-1).options.signal,'A request-local abort signal is required');
 await tick(4999); window.fire('focus'); window.fire('pageshow'); await settle();
 assert.equal(requests.length,before,'Do not overlap a pending fetch or JSON body');
 assert.equal(aborted,false);
 await tick(1);
 assert.equal(aborted,true,'Abort the whole request after five seconds');
 assert.match(battery.textContent,/Unavailable.*stale/i);
 assert.equal(active,0);
 assert.equal(maximum,1);
 setSample(sample(72,'Discharging')); await tick(15000);
 assert.equal(requests.length,before+1,'Retry after a bounded failure');
 assert.equal(battery.textContent,'72% · Discharging');
 release(respond(sample(99,'Full'))); await settle();
 assert.equal(battery.textContent,'72% · Discharging','Late timed-out result cannot win');
 assert.equal(timers.size,1,'Only the next poll remains, no leaked deadline');
}
""")


    def test_hiding_aborts_inflight_and_fast_resume_waits_for_cleanup(self):
        self.run_js(r"""
let rejectOld, aborted=false, active=0, maximum=0;
handler=async options=>{
 active++; maximum=Math.max(maximum,active);
 return new Promise((resolve,reject)=>{
  rejectOld=()=>{active--; reject(new Error('fixture hidden abort settled'));};
  options.signal.addEventListener('abort',()=>{aborted=true;},{once:true});
 });
};
window.fire('focus'); await settle();
const before=requests.length;
document.visibilityState='hidden'; window.fire('visibilitychange');
assert.equal(aborted,true,'Stop hidden network work promptly');
assert.match(battery.textContent,/paused/i);
setSample(sample(71));
document.visibilityState='visible'; window.fire('visibilitychange'); window.fire('focus');
await settle(); assert.equal(requests.length,before,'Await abort cleanup before another request');
rejectOld(); await settle();
assert.equal(active,0); assert.equal(maximum,1);
assert.equal(requests.length,before+1,'Refresh immediately after cancelled request settles');
assert.equal(battery.textContent,'71% · Discharging');
assert.equal(timers.size,1);
""")


    def test_native_fetch_abort_interrupts_loopback_headers_and_json_body(self):
        """Native fetch/HTTP acceptance; fake clock advances the production deadline."""
        self.run_js(r"""
const http=require('node:http');
for(const phase of ['headers','body']) {
 let accepted;
 const seen=new Promise(resolve=>{accepted=resolve;});
 const server=http.createServer((req,res)=>{
  if(phase==='body') { res.writeHead(200,{'Content-Type':'application/json'}); res.write('{'); }
  accepted(); // Intentionally never finish this test-only response.
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try {
  const url='http://127.0.0.1:'+server.address().port+'/api/system';
  handler=options=>globalThis.fetch(url,options);
  window.fire('focus'); await seen; await settle();
  const signal=requests.at(-1).options.signal;
  await tick(5000);
  for(let i=0;i<100 && !/stale/.test(battery.textContent);i++) {
   await new Promise(resolve=>globalThis.setTimeout(resolve,10));
  }
  assert.equal(signal.aborted,true);
  assert.match(battery.textContent,/Unavailable.*stale/i,phase);
  assert.match(storage.textContent,/Unavailable.*stale/i,phase);
  setSample(sample(70)); window.fire('focus'); await settle();
  assert.equal(battery.textContent,'70% · Discharging');
 } finally {
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
 }
}
""")


if __name__ == '__main__':
    unittest.main()
