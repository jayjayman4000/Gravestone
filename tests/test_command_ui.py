"""Command UI behavior: real production scripts with a dependency-free DOM adapter.

Fixtures below are test-only data, never survival content. Browser QA separately
exercises native form submission, layout, dialogs, and the local HTTP service.
"""
import shutil
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag, id) { this.tagName=tag; this.id=id; this.children=[]; this.handlers={}; this.attributes={}; this.value=''; this.isConnected=true; this.open=false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  setAttribute(k,v) { this.attributes[k]=v; }
  removeAttribute(k) { delete this.attributes[k]; delete this[k]; }
  addEventListener(k,fn) { (this.handlers[k] ??= []).push(fn); }
  async fire(k, extra={}) { const event={preventDefault(){},...extra}; for(const fn of this.handlers[k]||[]) await fn(event); }
  focus() { document.activeElement=this; }
  showModal() { this.open=true; }
  close() { this.open=false; for(const fn of this.handlers.close||[]) fn({}); }
}
const root=process.argv[1];
const html=fs.readFileSync(root+'/app/static/index.html','utf8');
const nodes={};
for(const m of html.matchAll(/<([\w-]+)[^>]*\bid="([^"]+)"[^>]*>/g)) nodes[m[2]]=new Node(m[1],m[2]);
const document={getElementById:id=>nodes[id]||null,createElement:tag=>new Node(tag),activeElement:null};
const window=new Node('window');
const doc={id:'fixture',title:'Test <title>',publisher:'Test publisher',file:'originals/test.pdf',rights:'Retain fixture rights',url:'https://example.invalid/original.pdf'};
const hit={id:doc.id,title:doc.title,publisher:doc.publisher,file:doc.file,page:3,excerpt:'Exact <script> text\nwith original line breaks.',score:2,matched_terms:['water']};
const response={query:'Find water',mode:'keyword-only',model_status:'Local model unavailable',terms:['water'],results:[hit],warning:'Machine-extracted search preview — not verified; open the original document and read full context.',message:'Source matches only.'};
const requests=[];
let commandHandler=async()=>response;
const fetch=async(url,options={})=>{
 requests.push([url,options]);
 if(options.method==='HEAD') return {ok:true,headers:{get:()=> 'application/pdf'}};
 if(url.startsWith('/api/command?')) { const handler=commandHandler; return {ok:true,json:async()=>await handler(url,options)}; }
 return {ok:true,json:async()=>url==='/api/library'?{documents:[doc]}:url==='/api/notes'?{text:'saved'}:url==='/content/coverage.json'?{description:'Requested coverage only',topics:[{id:'fixture-topic',title:'Test requested topic',status:'source-acquisition-pending'}]}:{status:'prototype'}};
};
const context=vm.createContext({document,window,fetch,URL,TextEncoder,AbortController,console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(root+'/app/static/app.js','utf8'),context);
assert.ok(nodes['command-form'], 'Initial viewport needs the command form, not a marketing hero');
assert.match(html,/\/static\/command.js/);
vm.runInContext(fs.readFileSync(root+'/app/static/command.js','utf8'),context);
const walk=node=>[node,...node.children.flatMap(walk)];
const text=node=>[node.textContent||'',...node.children.map(text)].join(' ');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const submit=async(query)=>{nodes['command-query'].value=query; await nodes['command-form'].fire('submit');};
(async()=>{await settle();
"""


@unittest.skipUnless(shutil.which('node'), 'Node.js required for command behavior verification')
class CommandUITests(unittest.TestCase):
    def run_js(self, body):
        script = HARNESS + body + "\n})().catch(e=>{console.error(e);process.exitCode=1;});"
        result = subprocess.run(['node', '-e', script, str(ROOT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_question_returns_exact_sources_and_controlled_reader_preserves_draft(self):
        self.run_js(r"""
assert.match(html,/Gravestone \/ Command/);
assert.match(html,/Sources only \/ no generated survival answers/);
assert.match(html,/maxlength="200"/);
assert.match(html,/Find safe drinking water guidance/);
assert.match(html,/Find power outage guidance/);
assert.match(nodes['model-state'].textContent,/Model status shown after search/);
nodes['note-text'].value='UNSAVED private draft';
await nodes['note-text'].fire('input');
await submit('Find water');
assert.ok(requests.some(([url])=>url==='/api/command?q=Find%20water'));
const output=text(nodes['command-results']);
for(const expected of [hit.excerpt,doc.title,doc.publisher,'Page 3','water',response.warning]) assert.ok(output.includes(expected),expected);
assert.match(nodes['model-state'].textContent,/Keyword search/);
assert.doesNotMatch(nodes['model-state'].textContent,/powered by Qwen/i);
const original=walk(nodes['command-results']).find(n=>n.textContent==='Read original in full');
assert.ok(original);
original.focus(); await original.fire('click');
assert.equal(nodes.reader.open,true);
assert.ok(text(nodes['reader-source']).includes(doc.rights));
assert.ok(text(nodes['reader-source']).includes(doc.url));
assert.equal(walk(nodes['reader-body']).find(n=>n.tagName==='iframe').src,'/content/originals/test.pdf');
assert.equal(original.target,undefined);
await nodes['reader-back'].fire('click');
assert.equal(nodes.reader.open,false);
assert.equal(document.activeElement,original);
assert.equal(nodes['note-text'].value,'UNSAVED private draft');
assert.equal(requests.filter(([url])=>url==='/api/notes').length,1);
assert.equal(requests.some(([,opts])=>opts.method==='POST'),false,'Command never autosaves notes or history');
assert.doesNotMatch(fs.readFileSync(root+'/app/static/command.js','utf8'),/innerHTML|insertAdjacentHTML|window\.open|localStorage|sessionStorage/);
""")

    def test_mode_is_per_response_no_sources_reports_gap_and_errors_do_not_invent_answers(self):
        self.run_js(r"""
commandHandler=async()=>({...response,mode:'ai-assisted',model_status:'available'});
await submit('water');
assert.match(nodes['model-state'].textContent,/Locally powered by Qwen/);
commandHandler=async()=>({...response,results:[],model_status:'timeout'});
await submit('uncovered topic');
assert.match(nodes['model-state'].textContent,/Keyword search.*timeout/);
assert.doesNotMatch(nodes['model-state'].textContent,/Qwen/);
assert.match(text(nodes['command-results']),/Collection gap/i);
assert.match(text(nodes['command-results']),/incomplete/i);
assert.match(text(nodes['command-results']),/not verified/i);
commandHandler=async()=>{throw new Error('test service unavailable');};
await submit('water');
assert.match(nodes['command-status'].textContent,/Search failed.*test service unavailable/);
assert.match(nodes['model-state'].textContent,/Search unavailable/);
assert.doesNotMatch(text(nodes['command-results']),/Test <title>/,'Stale source cards removed on failure');
""")

    def test_input_validation_examples_cancellation_and_late_response_isolation(self):
        self.run_js(r"""
const count=()=>requests.filter(([url])=>url.startsWith('/api/command?')).length;
await submit('   ');
assert.equal(count(),0);
assert.match(nodes['command-status'].textContent,/Enter a question/);
await submit('x'.repeat(201));
assert.equal(count(),0);
assert.match(nodes['command-status'].textContent,/200/);
await nodes['example-water'].fire('click');
await settle();
assert.ok(requests.some(([url])=>url==='/api/command?q=Find%20safe%20drinking%20water%20guidance'));
await nodes['example-power'].fire('click');
await settle();
assert.ok(requests.some(([url])=>url==='/api/command?q=Find%20power%20outage%20guidance'));
let finishOld;
commandHandler=()=>new Promise(resolve=>{finishOld=resolve;});
const old=submit('old');
assert.equal(nodes['command-cancel'].hidden,false);
const oldSignal=requests.at(-1)[1].signal;
commandHandler=async()=>({...response,query:'latest'});
await submit('latest');
assert.equal(oldSignal.aborted,true,'Superseded request is aborted');
finishOld({...response,query:'stale'}); await old;
assert.match(text(nodes['command-results']),/latest/);
assert.doesNotMatch(text(nodes['command-results']),/stale/);
let finishCancelled;
commandHandler=()=>new Promise(resolve=>{finishCancelled=resolve;});
const pending=submit('cancelled');
await settle();
const signal=requests.at(-1)[1].signal;
await nodes['command-cancel'].fire('click');
assert.equal(signal.aborted,true);
assert.match(nodes['command-status'].textContent,/cancelled/i);
assert.equal(nodes['command-cancel'].hidden,true);
finishCancelled({...response,query:'cancelled result'}); await pending;
assert.doesNotMatch(text(nodes['command-results']),/cancelled result/);
""")

    def test_command_first_shell_and_optional_requested_coverage_are_not_installed_content(self):
        self.run_js(r"""
assert.ok(html.indexOf('id="command-form"') < html.indexOf('id="library"'));
assert.doesNotMatch(html, /class="hero"/);
const css=fs.readFileSync(root+'/app/static/style.css','utf8');
assert.match(css,/\.command-panel/,'Command workstation has its own compact layout');
assert.match(css,/\[hidden\]/,'Hidden cancel and reader download must stay hidden despite button styles');
assert.ok(nodes['requested-coverage'],'Requested coverage stays a separate collapsed panel');
assert.equal(nodes['requested-coverage'].tagName,'details');
assert.match(html,/Requested coverage — not installed/);
assert.ok(requests.some(([url])=>url==='/content/coverage.json'));
assert.match(text(nodes['coverage-topics']),/Test requested topic/);
assert.match(text(nodes['coverage-topics']),/not installed/i);
assert.doesNotMatch(text(nodes['document-list']),/Test requested topic/);
""")


if __name__ == '__main__':
    unittest.main()
