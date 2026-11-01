"""Execute real overview JS against the reader's deterministic DOM fixture."""
from pathlib import Path
import shutil
import subprocess
import unittest
from test_reader_controls import HARNESS, ROOT


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class OverviewUITests(unittest.TestCase):
    def run_js(self, body):
        self.assertTrue((ROOT / 'app/static/overview.js').is_file(), 'Optional overview UI must exist')
        harness = HARNESS.replace(" requests.push([url,options]);", " requests.push([url,options]);\n if(url==='/api/overview') return context.overviewFetch(url,options);")
        setup = """
context.AbortController=AbortController;
vm.runInContext(fs.readFileSync(process.argv[1]+'/app/static/overview.js','utf8'),context);
let payload;
context.overviewFetch=async(url,options)=>{payload=JSON.parse(options.body);return {ok:true,json:async()=>({status:'available',file:doc.file,
 selected_pages:[2],warning:'AI-generated overview — unverified',scope:'Selected fragments, not the complete PDF.',
 bullets:[{text:'Synthetic <script> point',page:2,quote:'ORIGINAL SECOND <not HTML>'}]})};};
"""
        result = subprocess.run(['node', '-e', harness + setup + body + "\n})().catch(e=>{console.error(e);process.exitCode=1;});", str(ROOT)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_citation_collapses_overview_before_navigation_without_stale_side_effects(self):
        self.run_js(r"""
await link(doc).fire('click');
let navigated=0;
window.readerOverview.reset(doc,()=>1,page=>{
 assert.equal(get('reader-overview').open,false,'Reveal the original before navigating');
 navigated=page;
});
window.readerOverview.availability(true);
get('reader-overview').open=true;
await get('overview-generate').fire('click');
const citation=walk(get('overview-results')).find(n=>n.tagName==='button');
await citation.fire('click');
assert.equal(navigated,2);
assert.equal(get('reader-overview').open,false);
await link({...doc,id:'other',file:'originals/other.pdf',page:3}).fire('click');
get('reader-overview').open=true;
await citation.fire('click');
assert.equal(get('reader-overview').open,true,'Stale citation must not collapse a different document panel');
assert.equal(canvas().page,3);
assert.equal(navigated,2);
""")

    def test_superseded_citation_cannot_collapse_or_navigate_same_document(self):
        self.run_js(r"""
await link(doc).fire('click');
await get('overview-generate').fire('click');
const stale=walk(get('overview-results')).find(n=>n.tagName==='button');
await get('overview-generate').fire('click');
get('reader-overview').open=true;
await stale.fire('click');
assert.equal(get('reader-overview').open,true);
assert.equal(canvas().page,1);
await nodes['reader-back'].fire('click');
await stale.fire('click');
assert.equal(nodes.reader.open,false);
""")

    def test_pending_overview_discloses_wait_and_cancel_does_not_claim_inference_stopped(self):
        self.run_js(r"""
let finish;
context.overviewFetch=()=>new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({status:'timeout'})});});
await link(doc).fire('click');
const pending=get('overview-generate').fire('click');
assert.match(get('overview-status').textContent,/2 minutes/);
await get('overview-cancel').fire('click');
assert.match(get('overview-status').textContent,/may still finish locally/);
finish();await pending;
assert.equal(get('overview-results').children.length,0);
""")

    def test_disabled_overview_explains_quality_gate_and_keeps_original_usable(self):
        self.run_js(r"""
context.overviewFetch=async()=>({ok:true,json:async()=>({status:'disabled',bullets:[],selected_pages:[],
 message:'Experimental overview withheld pending substantive quality validation. Read the original PDF.'})});
await link(doc).fire('click');
await get('overview-generate').fire('click');
assert.match(get('overview-status').textContent,/withheld pending substantive quality validation/);
assert.equal(get('overview-results').children.length,0);
assert.equal(get('overview-cancel').hidden,true);
await get('reader-copy').fire('click');
assert.ok(get('reader-copy-text').value.endsWith('ORIGINAL FIRST'));
await nodes['reader-back'].fire('click');
assert.equal(nodes.reader.open,false);
""")

    def test_late_generation_is_aborted_and_cannot_cross_documents_or_close(self):
        self.run_js(r"""
let finish, signal;
context.overviewFetch=async(u,o)=>{signal=o.signal;return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({status:'available',file:doc.file,selected_pages:[1],warning:'AI-generated unverified',scope:'Fragments only',bullets:[{text:'LATE STALE RESULT',page:1,quote:'ORIGINAL FIRST'}]})});});};
await link(doc).fire('click');
const first=get('overview-generate').fire('click');
await link({...doc,file:'originals/other.pdf',id:'other',title:'Other'}).fire('click');
assert.equal(signal.aborted,true);finish();await first;
assert.equal(get('overview-results').children.length,0);
await link(doc).fire('click');
const second=get('overview-generate').fire('click');
await nodes['reader-back'].fire('click');
assert.equal(signal.aborted,true);finish();await second;
assert.equal(get('overview-results').children.length,0);
assert.equal(nodes.reader.open,false);
await link(doc).fire('click');
const third=get('overview-generate').fire('click');
await get('overview-cancel').fire('click');
assert.equal(signal.aborted,true);finish();await third;
assert.equal(get('overview-results').children.length,0);
assert.match(get('overview-status').textContent,/cancelled/);
""")

    def test_opt_in_cited_panel_preserves_reader_copy_zoom_and_private_draft(self):
        self.run_js(r"""
nodes['command-query'].value='current topic';nodes['note-text'].value='PRIVATE DRAFT';
await link({...doc,page:1}).fire('click');
assert.equal(requests.some(([u])=>u==='/api/overview'),false);
assert.equal(get('overview-query').value,'current topic');
await get('reader-zoom-in').fire('click');
await get('overview-generate').fire('click');
assert.deepEqual(payload,{id:'fixture',query:'current topic',page:1});
assert.ok(!JSON.stringify(payload).includes('PRIVATE'));
assert.match(text(get('overview-results')),/AI-generated.*unverified/);
assert.match(text(get('overview-results')),/not the complete PDF/);
assert.equal(walk(get('overview-results')).some(n=>n.tagName==='script'),false);
const citation=walk(get('overview-results')).find(n=>n.tagName==='button');
await citation.fire('click');
assert.equal(canvas().page,2);assert.equal(canvas().zoom,125);
assert.match(text(get('overview-results')),/Synthetic <script> point/);
await get('reader-copy').fire('click');
assert.ok(get('reader-copy-text').value.endsWith('ORIGINAL SECOND <not HTML>'));
assert.ok(!get('reader-copy-text').value.includes('Synthetic'));
assert.equal(nodes['note-text'].value,'PRIVATE DRAFT');
await nodes['reader-back'].fire('click');
assert.equal(get('overview-results').children.length,0);
""")
