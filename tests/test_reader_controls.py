"""Execute production reader controls, without a browser or third-party packages."""
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
  constructor(tag, id) { this.tagName=tag; this.id=id; this.children=[]; this.handlers={}; this.attributes={}; this.value=''; this.open=false; this.isConnected=true; }
  append(...nodes) { for(const n of nodes) n.parentElement=this; this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=[]; this.append(...nodes); }
  setAttribute(k,v) { this.attributes[k]=v; }
  getAttribute(k) { return this.attributes[k] ?? null; }
  removeAttribute(k) { delete this.attributes[k]; delete this[k]; }
  addEventListener(k,fn) { (this.handlers[k] ??=[]).push(fn); }
  async fire(k,extra={}) { if(this.disabled && k==='click') return; const e={preventDefault(){this.defaultPrevented=true;},...extra}; for(const fn of this.handlers[k]||[]) await fn(e); return e; }
  focus() { document.activeElement=this; }
  select() { this.selected=true; }
  showModal() { this.open=true; }
  close() { this.open=false; for(const fn of this.handlers.close||[]) fn({}); }
}
const walk=n=>[n,...n.children.flatMap(walk)];
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
const html=fs.readFileSync(process.argv[1]+'/app/static/index.html','utf8');
const nodes={};
for(const match of html.matchAll(/<([\w-]+)[^>]*\bid="([^"]+)"[^>]*>/g)) nodes[match[2]]=new Node(match[1],match[2]);
const document={head:new Node('head'),getElementById:id=>nodes[id]||Object.values(nodes).flatMap(walk).find(n=>n.id===id)||null,createElement:tag=>new Node(tag),activeElement:null};
const window=new Node('window');
const doc={id:'fixture',file:'originals/test.pdf',title:'Source <title>',pages:3,text_file:'search/test.txt',publisher:'CDC',rights:'Fixture rights',url:'https://www.cdc.gov/fixture'};
let hits=[{...doc,page:2,excerpt:'UNTRUSTED preview must not be copied'}];
let indexText='ORIGINAL FIRST\fORIGINAL SECOND <not HTML>\fORIGINAL THIRD';
let indexMode='ok';
let finishText;
const requests=[];
let headMode='ok',finishHead;
const fetch=async(url,options)=>{
 requests.push([url,options]);
 if(options?.method==='HEAD') {
   if(headMode==='offline') throw Error('offline');
   if(headMode==='pending') return new Promise(resolve=>{finishHead=resolve;});
   return {ok:headMode!=='missing',headers:{get:()=>headMode==='html'?'text/html':'application/pdf'}};
 }
 if(url.startsWith('/content/search/')) {
   if(indexMode==='pending') return new Promise(resolve=>{finishText=resolve;});
   return {ok:indexMode!=='missing',headers:{get:()=>indexMode==='html'?'text/html':'text/plain; charset=utf-8'},text:async()=>indexText};
 }
 const data=url==='/api/library'?{documents:[doc]}:url==='/api/notes'?{text:'saved'}:url.startsWith('/api/search?')?{results:hits}:{status:'prototype'};
 return {ok:true,json:async()=>data};
};
const context=vm.createContext({document,window,fetch,URL,TextEncoder,console,navigator:{}});
vm.runInContext(fs.readFileSync(process.argv[1]+'/app/static/app.js','utf8'),context);
vm.runInContext(fs.readFileSync(process.argv[1]+'/app/static/reader.js','utf8'),context);
let actualPages=3, renderMode='ok', loadMode='ok', finishRender;
const renders=[]; const viewers=[];
window.loadControlledPDFViewer=async container=>{
 const viewer={destroyed:false,async load(){if(loadMode==='error')throw Error('bad PDF');return actualPages;},
 async render(page,zoom){renders.push([page,zoom]);
   if(renderMode==='error')throw Error('paint failed');
   if(renderMode==='pending') await new Promise(resolve=>{finishRender=resolve;});
   if(this.destroyed)return null;
   const canvas=new Node('canvas');canvas.page=page;canvas.zoom=zoom;container.replaceChildren(canvas);return {page,zoom};},
 destroy(){this.destroyed=true;container.replaceChildren();}};
 viewers.push(viewer);return viewer;
};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const get=id=>document.getElementById(id);
const frame=()=>walk(nodes['reader-body']).find(n=>n.tagName==='iframe');
const canvas=()=>walk(nodes['reader-body']).find(n=>n.tagName==='canvas');
const link=(source=doc)=>vm.runInContext('localLink',context)(source,'Open fixture');
(async()=>{await settle();
"""


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class ReaderControlsTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(['node', '-e', HARNESS + body + "\n})().catch(e=>{console.error(e);process.exitCode=1;});", str(ROOT)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_preflight_failures_unsafe_paths_and_late_head_never_create_a_viewer(self):
        self.run_js(r"""
for(const mode of ['missing','html','offline']) {
 headMode=mode;await link(doc).fire('click');
 assert.equal(nodes.reader.open,true);
 assert.equal(viewers.length,0);
 assert.equal(canvas(),undefined);
 assert.equal(frame(),undefined);
 assert.equal(get('reader-copy').disabled,true);
 assert.match(nodes['reader-status'].textContent,/unavailable|could not display/);
 await nodes['reader-back'].fire('click');
}
headMode='pending';const opening=link(doc).fire('click');
assert.equal(nodes.reader.open,true);
await nodes['reader-back'].fire('click');
finishHead({ok:true,headers:{get:()=> 'application/pdf'}});await opening;
assert.equal(nodes.reader.open,false);
assert.equal(viewers.length,0);
for(const file of ['../outside.pdf','/etc/private.pdf','https://evil.invalid/a.pdf','https:evil.pdf','originals/a.html','a\\b.pdf','a\0.pdf']) {
 assert.equal(link({...doc,file}).disabled,true,file);
}
""")

    def test_loading_copy_guard_actual_count_and_render_failures_keep_return_and_export(self):
        self.run_js(r"""
renderMode='pending';
const opening=link({...doc,page:2}).fire('click');
await settle();
assert.match(get('reader-page').textContent,/Requested physical PDF page 2.*not yet displayed/);
assert.equal(get('reader-copy').disabled,true);
await get('reader-copy').fire('click');
assert.equal(requests.some(([url])=>url.startsWith('/content/search/')),false);
finishRender();await opening;
assert.equal(get('reader-copy').disabled,false);
renderMode='error';await get('reader-next').fire('click');
assert.equal(get('reader-copy').disabled,true);
assert.match(get('reader-page').textContent,/not yet displayed/);
assert.match(nodes['reader-status'].textContent,/could not display/);
assert.equal(nodes['reader-download'].hidden,false);
assert.equal(nodes.reader.open,true);
assert.equal(frame(),undefined);
renderMode='ok';actualPages=2;
await link({...doc,page:999}).fire('click');
assert.equal(canvas().page,2);
assert.match(get('reader-page').textContent,/Physical PDF page 2 of 2/);
assert.equal(get('reader-next').disabled,true);
assert.equal(get('reader-copy').disabled,true,'Manifest count mismatch must never select the wrong derivative page');
assert.match(nodes['reader-status'].textContent,/does not match/);
loadMode='error';await link(doc).fire('click');
assert.equal(frame(),undefined);
assert.equal(nodes['reader-download'].hidden,false);
assert.equal(get('reader-copy').disabled,true);
assert.equal(nodes.reader.open,true);
""")

    def test_late_viewer_import_cannot_clear_new_documents_canvas(self):
        self.run_js(r"""
const factory=window.loadControlledPDFViewer;
let finishImport;
window.loadControlledPDFViewer=container=>new Promise(resolve=>{finishImport=async()=>resolve(await factory(container));});
const first=link({...doc,page:1}).fire('click');await settle();
window.loadControlledPDFViewer=factory;
await link({...doc,page:3}).fire('click');
const displayed=canvas();assert.equal(displayed.page,3);
await finishImport();await first;
assert.equal(canvas(),displayed,'Old factory cleanup must never erase a newer document canvas');
""")

    def test_close_during_render_destroys_viewer_and_prevents_late_ui(self):
        self.run_js(r"""
renderMode='pending';const opening=link({...doc,page:2}).fire('click');await settle();
await nodes['reader-back'].fire('click');
assert.equal(viewers[0].destroyed,true);
finishRender();await opening;
assert.equal(nodes.reader.open,false);
assert.equal(canvas(),undefined);
assert.equal(get('reader-page').textContent,'');
""")

    def test_app_page_copy_zoom_are_bound_to_completed_canvas_not_native_viewer(self):
        self.run_js(r"""
await link({...doc,page:2}).fire('click');
assert.equal(frame(),undefined,'Native PDF viewer would expose independently navigable pages');
const canvas=()=>walk(nodes['reader-body']).find(n=>n.tagName==='canvas');
assert.equal(canvas().page,2);
assert.equal(canvas().zoom,100);
assert.match(get('reader-page').textContent,/Physical PDF page 2 of 3/);
await get('reader-next').fire('click');
assert.equal(canvas().page,3);
await get('reader-zoom-in').fire('click');
assert.equal(canvas().page,3);
assert.equal(canvas().zoom,125);
await get('reader-copy').fire('click');
assert.ok(get('reader-copy-text').value.endsWith('ORIGINAL THIRD'));
assert.match(get('reader-copy-text').value,/Physical PDF page 3 of 3/);
""")

    def test_failed_repeat_copy_clears_previously_visible_text_and_close_clears_indicator(self):
        self.run_js(r"""
await link({...doc,page:2}).fire('click');
await get('reader-copy').fire('click');
assert.equal(get('reader-copy-panel').hidden,false);
indexMode='missing';
await get('reader-copy').fire('click');
assert.equal(get('reader-copy-panel').hidden,true);
assert.equal(get('reader-copy-text').value,'');
await nodes['reader-back'].fire('click');
assert.equal(get('reader-page').textContent,'');
""")

    def test_missing_text_never_substitutes_preview_and_export_stays_available(self):
        self.run_js(r"""
for(const mode of ['missing','html']) {
 indexMode=mode;
 await link({...doc,page:2}).fire('click');
 await get('reader-copy').fire('click');
 assert.match(nodes['reader-status'].textContent,/Extracted text unavailable/);
 assert.equal(get('reader-copy-panel').hidden,true);
 assert.equal(nodes['reader-download'].hidden,false);
 assert.equal(get('reader-copy-text').value,'');
}
indexMode='ok';
for(const value of ['wrong page count','FIRST\f\fTHIRD']) {
 indexText=value;
 await link({...doc,page:2}).fire('click');
 await get('reader-copy').fire('click');
 assert.match(nodes['reader-status'].textContent,/Extracted text unavailable/);
 assert.equal(get('reader-copy-panel').hidden,true);
}
for(const path of ['../private.txt','https://evil.invalid/a.txt','originals/a.txt','search/%2e%2e/private.txt','search/a.txt#evil']) {
 doc.text_file=path;
 const before=requests.length;
 await link({...doc,page:2}).fire('click');
 await get('reader-copy').fire('click');
 assert.equal(requests.slice(before).some(([,opts])=>opts?.method!=='HEAD'),false,'Unsafe text path fetched: '+path);
}
""")

    def test_nested_library_close_preserves_draft_queries_results_and_resets_document(self):
        self.run_js(r"""
nodes.library.showModal();
nodes['note-text'].value='Private UNSAVED draft';
await nodes['note-text'].fire('input');
nodes['search-query'].value='source phrase';
nodes['command-query'].value='command phrase';
nodes['command-results'].append(new Node('article'));
const results=nodes['command-results'].children[0];
const opener=link({...doc,page:3});
await opener.fire('click');
await get('reader-zoom-in').fire('click');
await nodes['reader-back'].fire('click');
assert.equal(nodes.library.open,true);
assert.equal(document.activeElement,opener);
assert.equal(frame(),undefined);
assert.equal(nodes['note-text'].value,'Private UNSAVED draft');
assert.equal(nodes['search-query'].value,'source phrase');
assert.equal(nodes['command-query'].value,'command phrase');
assert.equal(nodes['command-results'].children[0],results);
assert.equal((await window.fire('beforeunload')).defaultPrevented,true);
actualPages=1;
await link({file:'originals/other.pdf',title:'Other',pages:1}).fire('click');
assert.equal(canvas().page,1);
assert.equal(canvas().zoom,100);
assert.equal(get('reader-next').disabled,true);
assert.equal(get('reader-copy-text').value,'');
""")

    def test_stale_copy_fetch_cannot_replace_new_page_or_closed_reader(self):
        self.run_js(r"""
indexMode='pending';
await link({...doc,page:2}).fire('click');
const copying=get('reader-copy').fire('click');
await get('reader-next').fire('click');
finishText({ok:true,headers:{get:()=> 'text/plain'},text:async()=>indexText});
await copying;
assert.equal(get('reader-copy-panel').hidden,true);
assert.equal(get('reader-copy-text').value,'');
const later=get('reader-copy').fire('click');
await nodes['reader-back'].fire('click');
finishText({ok:true,headers:{get:()=> 'text/plain'},text:async()=>indexText});
await later;
assert.equal(nodes.reader.open,false);
assert.equal(get('reader-copy-panel').hidden,true);
""")

    def test_invalid_fragments_page_bounds_export_and_source_information(self):
        self.run_js(r"""
for(const file of ['originals/a.pdf#page=9','originals/a.pdf?x=1','originals/%2e%2e/a.pdf','originals/%252e%252e/a.pdf','search/fake.pdf','//evil/a.pdf','originals/a\u0009.pdf']) {
 assert.equal(link({...doc,file}).disabled,true,file);
}
for(const [page,expected] of [[999,3],[-1,1],[1.5,1],['2&zoom=300',1],['2',2],[NaN,1],[Infinity,1]]) {
 await link({...doc,page}).fire('click');
 assert.equal(canvas().page,expected);
 assert.equal(canvas().zoom,100);
 await nodes['reader-back'].fire('click');
}
await link(doc).fire('click');
assert.equal(nodes['reader-download'].href,'/content/originals/test.pdf');
assert.equal(nodes['reader-download'].download,'test.pdf');
assert.match(nodes['reader-download'].textContent,/Export original.*complete PDF/);
assert.equal(nodes['reader-download'].target,undefined);
assert.equal(walk(nodes['reader-source']).some(n=>n.tagName==='details'),true);
assert.match(text(nodes['reader-source']),/Fixture rights/);
assert.match(text(nodes['reader-source']),/endorse/);
""")

    def test_copy_is_exact_source_page_with_selectable_clipboard_fallback(self):
        self.run_js(r"""
await link({...doc,page:2}).fire('click');
await get('reader-copy').fire('click');
const fallback=get('reader-copy-panel');
assert.equal(fallback.hidden,false);
const box=get('reader-copy-text');
assert.match(box.value,/Source: Source <title> · CDC/);
assert.match(box.value,/Physical PDF page 2 of 3 · Unverified machine-extracted text/);
assert.ok(box.value.endsWith('ORIGINAL SECOND <not HTML>'));
assert.ok(!box.value.includes('ORIGINAL FIRST'));
assert.ok(!box.value.includes('UNTRUSTED preview'));
assert.equal(box.selected,true);
let copied;
context.navigator.clipboard={writeText:async value=>{copied=value;}};
await get('reader-copy').fire('click');
assert.equal(copied,box.value);
assert.match(get('reader-status').textContent,/Copied extracted text/);
await get('reader-next').fire('click');
assert.equal(fallback.hidden,true,'Old page text must disappear on navigation');
""")

    def test_search_target_and_bounded_navigation(self):
        self.run_js(r"""
assert.equal(Object.values(nodes).flatMap(walk).filter(n=>n.id==='reader-controls').length,1,'Reader initialization must be idempotent');
nodes['search-query'].value='second';
await nodes['search-form'].fire('submit');
const button=walk(nodes['search-results']).find(n=>n.tagName==='button');
await button.fire('click');
assert.equal(canvas().page,2);
assert.equal(canvas().zoom,100);
assert.match(get('reader-page').textContent,/Physical PDF page 2 of 3/);
await get('reader-next').fire('click');
assert.equal(canvas().page,3);
assert.equal(canvas().zoom,100);
assert.equal(get('reader-next').disabled,true);
await get('reader-prev').fire('click');
await get('reader-prev').fire('click');
assert.equal(get('reader-prev').disabled,true);
for(let i=0;i<30;i++) await get('reader-zoom-in').fire('click');
assert.equal(canvas().page,1);
assert.equal(canvas().zoom,300);
for(let i=0;i<30;i++) await get('reader-zoom-out').fire('click');
assert.equal(canvas().page,1);
assert.equal(canvas().zoom,50);
assert.equal(get('reader-zoom-out').disabled,true);
""")


if __name__ == '__main__':
    unittest.main()
