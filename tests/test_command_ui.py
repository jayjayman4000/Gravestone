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
  append(...children) { for (const child of children) { child.parentElement=this; this.children.push(child); if(child.id) nodes[child.id]=child; } }
  replaceChildren(...children) { this.children=[]; this.append(...children); }
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
for(const m of html.matchAll(/id="([^"]+)"[^>]*>([^<]*)</g)) if(nodes[m[1]]) nodes[m[1]].textContent=m[2];
const document={getElementById:id=>nodes[id]||null,createElement:tag=>new Node(tag),activeElement:null};
const window=new Node('window');
// Legacy controls let behavior regressions run while the old shell is replaced.
for(const id of ['example-water','example-power']) if(!nodes[id]) nodes[id]=new Node('button',id);
const doc={id:'fixture',title:'Test <title>',publisher:'Test publisher',file:'originals/test.pdf',page:99,rights:'Retain fixture rights',url:'https://example.invalid/original.pdf'};
const hit={id:doc.id,title:doc.title,publisher:doc.publisher,file:doc.file,page:3,excerpt:'Exact <script> text\nwith original line breaks.',score:2,matched_terms:['water']};
const response={query:'Find water',mode:'keyword-only',model_status:'Local model unavailable',terms:['water'],results:[hit],warning:'Machine-extracted search preview — not verified; open the original document and read full context.',message:'Source matches only.'};
const requests=[];
let commandHandler=async()=>response;
const fetch=async(url,options={})=>{
 requests.push([url,options]);
 if(options.method==='HEAD') return {ok:true,headers:{get:()=> 'application/pdf'}};
 if(url==='/content/coverage.json') return new Promise(()=>{}); // Acquisition metadata must never gate retrieval.
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

    def test_source_cards_preserve_exact_excerpt_and_hit_page_over_manifest(self):
        self.run_js(r"""
context.readerCapture=[];
vm.runInContext('openReader = async (doc, opener) => readerCapture.push(doc)',context);
nodes['note-text'].value='UNSAVED private draft';
await nodes['note-text'].fire('input');
await submit('Find water');
assert.ok(requests.some(([url])=>url==='/api/command?q=Find%20water'));
const output=text(nodes['command-results']);
for(const expected of [hit.excerpt,doc.title,doc.publisher,'PDF page 3']) assert.ok(output.includes(expected),expected);
assert.match(nodes['model-state'].textContent,/Keyword search/);
const original=walk(nodes['command-results']).find(n=>n.className==='source-open');
assert.ok(original,'Entire source card opens the original page');
await original.fire('click');
assert.equal(context.readerCapture[0].page,3,'Hit page must not be replaced by manifest page');
assert.equal(context.readerCapture[0].rights,doc.rights);
assert.equal(context.readerCapture[0].url,doc.url);
assert.equal(nodes['note-text'].value,'UNSAVED private draft');
assert.equal(requests.filter(([url])=>url==='/api/notes').length,1);
assert.equal(requests.some(([,opts])=>opts.method==='POST'),false);
assert.doesNotMatch(fs.readFileSync(root+'/app/static/command.js','utf8'),/innerHTML|insertAdjacentHTML|window\.open|localStorage|sessionStorage/);
assert.equal(walk(nodes['command-results']).filter(n=>n.className==='warning').length,0,'Do not repeat warning boxes on every card');
""")

    def test_source_edition_from_manifest_is_visible_once_per_card_when_present(self):
        self.run_js(r"""
const edition='Fixture edition · historical test publication';
doc.edition=edition;
doc.source_caveat='Long fixture caveat that belongs in source details, not each card.';
commandHandler=async()=>({...response,
 results:[{...hit,edition:'Untrusted hit edition'}],
 related_results:[{...hit,title:'Related edition fixture',page:4}]});
await submit('fixture edition');
const cards=walk(nodes['command-results']).filter(n=>n.className==='search-hit');
assert.equal(cards.length,2);
for (const card of cards) {
 const editionLines=card.children.filter(n=>n.className==='source-meta'&&n.textContent===edition);
 assert.equal(editionLines.length,1,'Show one edition metadata line from the manifest per source card');
 assert.ok(card.children.indexOf(editionLines[0])<card.children.findIndex(n=>n.className==='snippet'));
 assert.ok(text(card).includes(hit.excerpt),'Never rewrite publisher excerpts');
 assert.ok(!text(card).includes(doc.source_caveat),'Do not repeat the full source caveat');
 assert.ok(!text(card).includes('Untrusted hit edition'),'Manifest edition takes precedence');
}
assert.ok(text(cards[0]).includes(hit.title),'Preserve the publisher title');
delete doc.edition;
commandHandler=async()=>({...response});
await submit('fixture without edition');
const card=walk(nodes['command-results']).find(n=>n.className==='search-hit');
assert.equal(card.children.filter(n=>n.className==='source-meta').length,1,'No empty edition line without an edition');
assert.ok(!text(card).includes(edition));
""")

    def test_one_shared_extraction_notice_precedes_primary_or_related_only_results(self):
        self.run_js(r"""
for (const relatedOnly of [false, true]) {
 const hits=[hit,{...hit,page:4}];
 commandHandler=async()=>({...response,
  results:relatedOnly?[]:hits,related_results:relatedOnly?hits:[]});
 await submit('fixture search');
 const output=nodes['command-results'];
 const notices=walk(output).filter(n=>n.textContent===response.warning);
 assert.equal(notices.length,1,'Show the exact machine-extraction warning once per response');
 const notice=notices[0];
 assert.equal(notice.tagName,'p','Use a shared small notice, not a warning box');
 assert.equal(notice.className,'coverage-note');
 assert.equal(notice.parentElement,output,'Notice must stay outside cards and collapsed related matches');
 assert.notEqual(notice.hidden,true);
 assert.ok(output.children.indexOf(notice)<output.children.findIndex(n=>n.className==='search-hit'||n.tagName==='details'),
  'Disclose unverified extraction before any result or related-match disclosure');
 assert.equal(walk(output).filter(n=>n.className==='search-hit').length,2);
 assert.equal(walk(output).filter(n=>n.className==='warning').length,0);
}
commandHandler=async()=>({...response,results:[],related_results:[]});
await submit('empty fixture');
assert.ok(!text(nodes['command-results']).includes(response.warning),'No extraction notice without excerpts');
""")

    def test_primary_partial_match_discloses_missing_query_words(self):
        self.run_js(r"""
commandHandler=async()=>({...response,
 coverage:{status:'local-coverage',required_terms:['infant','formula','unsafe','water']},
 message:'Keyword overlap is not proof of topic coverage or relevance.',
 results:[{...hit,matched_terms:['infant','formula','water'],missing_terms:['unsafe']}]});
await submit('infant formula unsafe water');
const output=text(nodes['command-results']);
assert.match(output,/Missing query words: unsafe/);
assert.match(output,/Partial keyword match/);
assert.match(output,/Keyword overlap is not proof/);
assert.ok(output.includes(hit.excerpt),'Raw excerpt is unchanged');
""")

    def test_related_matches_stay_collapsed_separate_and_labeled_when_no_primary(self):
        self.run_js(r"""
commandHandler=async()=>({...response,results:[],
 coverage:{status:'no-local-coverage',required_terms:['engine','repair']},
 related_results:[{...hit,title:'Related only',missing_terms:['engine']}],
 message:'No local coverage for this query. Partial keywords may be unrelated.'});
await submit('engine repair');
assert.match(nodes['command-status'].textContent,/No matching installed source/);
const details=walk(nodes['command-results']).find(n=>n.tagName==='details');
assert.ok(details,'Related matches need a separate disclosure');
assert.notEqual(details.open,true,'Do not promote unrelated matches into primary results');
assert.match(text(details),/Partial keyword matches.*may be unrelated/);
assert.match(text(details),/Missing query words: engine/);
assert.ok(text(details).includes(hit.excerpt));
assert.equal(walk(nodes['command-results']).filter(n=>n.className==='search-hit').length,1);
""")

    def test_primary_and_related_buckets_render_together_without_promoting_related(self):
        self.run_js(r"""
const primary={...hit,title:'Primary fixture',page:2};
const relatedHit={...hit,title:'Related fixture',page:4,missing_terms:['fixture']};
commandHandler=async()=>({...response,results:[primary],related_results:[relatedHit]});
await submit('fixture search');
const output=nodes['command-results'];
const primaryCards=output.children.filter(n=>n.className==='search-hit');
assert.equal(primaryCards.length,1,'Only primary matches belong at the top level');
assert.ok(text(primaryCards[0]).includes(primary.title));
assert.ok(text(primaryCards[0]).includes(primary.excerpt));
const disclosures=output.children.filter(n=>n.tagName==='details');
assert.equal(disclosures.length,1);
const related=disclosures[0];
assert.notEqual(related.open,true,'Related matches stay collapsed even alongside primary matches');
assert.match(text(related.children[0]),/Partial keyword matches.*may be unrelated \(1\)/);
assert.match(text(related),/not evidence that this topic is covered/);
const relatedCards=walk(related).filter(n=>n.className==='search-hit');
assert.equal(relatedCards.length,1);
assert.ok(text(relatedCards[0]).includes(relatedHit.title));
assert.ok(text(relatedCards[0]).includes(relatedHit.excerpt));
assert.match(text(relatedCards[0]),/Missing query words: fixture/);
assert.equal(walk(output).filter(n=>n.className==='search-hit').length,2);
assert.equal(walk(output).filter(n=>n.textContent===response.warning).length,1);
assert.ok(output.children.findIndex(n=>n.textContent===response.warning)<output.children.indexOf(primaryCards[0]));
assert.ok(output.children.indexOf(primaryCards[0])<output.children.indexOf(related));
assert.match(nodes['command-status'].textContent,/^1 source excerpts/,'Do not count related matches as primary');
""")

    def test_missing_negation_is_disclosed_exactly_in_both_result_buckets(self):
        self.run_js(r"""
// Deliberately artificial fixture labels, not safety-source instructions.
const primary={...hit,title:'Primary fixture',excerpt:'Fixture label blue.',matched_terms:['fixture','blue'],missing_terms:['not']};
const relatedHit={...primary,title:'Related fixture',page:4,missing_terms:['not','violet']};
commandHandler=async()=>({...response,results:[primary],related_results:[relatedHit]});
await submit('fixture not blue violet');
const output=nodes['command-results'];
const primaryCard=output.children.find(n=>n.className==='search-hit');
const related=output.children.find(n=>n.tagName==='details');
const relatedCard=walk(related).find(n=>n.className==='search-hit');
for (const [card,expected] of [[primaryCard,'Partial keyword match · Missing query words: not'],
 [relatedCard,'Partial keyword match · Missing query words: not, violet']]) {
 const disclosure=card.children.find(n=>n.textContent===expected);
 assert.ok(disclosure,'Preserve backend missing terms, including negation, verbatim and in order');
 const excerpt=card.children.find(n=>n.className==='snippet');
 assert.equal(excerpt.textContent,primary.excerpt);
 assert.ok(card.children.indexOf(disclosure)<card.children.indexOf(excerpt));
}
assert.notEqual(related.open,true);
""")

    def test_response_modes_missing_sources_and_errors_do_not_invent_answers(self):
        self.run_js(r"""
commandHandler=async()=>({...response,mode:'ai-assisted',model_status:'available'});
await submit('water');
assert.match(nodes['model-state'].textContent,/Keyword assistance/);
commandHandler=async()=>({...response,results:[],model_status:'timeout'});
await submit('uncovered topic');
assert.match(nodes['model-state'].textContent,/Keyword search/);
assert.match(nodes['command-status'].textContent,/No matching installed source/);
assert.doesNotMatch(text(nodes['command-results']),/Test <title>|No answer is generated/);
commandHandler=async()=>{throw new Error('test service unavailable');};
await submit('water');
assert.match(nodes['command-status'].textContent,/Search failed.*test service unavailable/);
assert.match(nodes['model-state'].textContent,/Search unavailable/);
assert.doesNotMatch(text(nodes['command-results']),/Test <title>/);
""")

    def test_validation_cancellation_and_late_response_isolation(self):
        self.run_js(r"""
const count=()=>requests.filter(([url])=>url.startsWith('/api/command?')).length;
await submit('   ');
assert.equal(count(),0);
assert.match(nodes['command-status'].textContent,/Enter a search/);
await submit('x'.repeat(201));
assert.equal(count(),0);
assert.match(nodes['command-status'].textContent,/200/);
let finishOld;
commandHandler=()=>new Promise(resolve=>{finishOld=resolve;});
const old=submit('old');
assert.equal(nodes['command-cancel'].hidden,false);
const oldSignal=requests.at(-1)[1].signal;
commandHandler=async()=>({...response,query:'latest'});
await submit('latest');
assert.equal(oldSignal.aborted,true);
finishOld({...response,query:'stale',results:[{...hit,title:'STALE RESULT'}]}); await old;
assert.match(nodes['command-status'].textContent,/latest/);
assert.doesNotMatch(text(nodes['command-results']),/STALE RESULT/);
let finishCancelled;
commandHandler=()=>new Promise(resolve=>{finishCancelled=resolve;});
const pending=submit('cancelled'); await settle();
const signal=requests.at(-1)[1].signal;
await nodes['command-cancel'].fire('click');
assert.equal(signal.aborted,true);
assert.match(nodes['command-status'].textContent,/cancelled/i);
assert.equal(nodes['command-cancel'].hidden,true);
finishCancelled({...response,query:'cancelled result'}); await pending;
assert.doesNotMatch(text(nodes['command-results']),/cancelled result/);
""")

    def test_modal_navigation_retains_draft_search_focus_and_source_links(self):
        self.run_js(r"""
vm.runInContext(fs.readFileSync(root+'/app/static/console.js','utf8'),context);
await settle();
await submit('water');
const output=text(nodes['command-results']);
nodes['note-text'].value='Unsaved navigation draft';
await nodes['note-text'].fire('input');
for(const [name,openerID] of [['library','nav-library'],['notebook','nav-notebook'],['map-view','nav-map'],['start-here','nav-start-here'],['display-menu','nav-display-menu']]) {
 const opener=nodes[openerID]; opener.focus(); await opener.fire('click');
 assert.equal(nodes[name].open,true,name);
 assert.equal(document.activeElement,nodes[name+'-back']);
 if(name==='map-view') {
  await nodes['nav-map-tools'].fire('click');
  assert.equal(nodes['map-tools'].open,true);
  await nodes['map-tools-back'].fire('click');
  assert.equal(nodes[name].open,true,'Nested Map tools returns to map');
 }
 await nodes[name+'-back'].fire('click');
 assert.equal(nodes[name].open,false);
 assert.equal(document.activeElement,opener);
 assert.equal(nodes['command-query'].value,'water');
 assert.equal(text(nodes['command-results']),output);
 assert.equal(nodes['note-text'].value,'Unsaved navigation draft');
}
assert.ok(text(nodes['start-source-links']).includes(doc.title),'Start here links only to installed originals');
await nodes['topic-maps'].fire('click');
assert.equal(nodes['map-view'].open,true);
await nodes['map-view-back'].fire('click');
await nodes['topic-repair'].fire('click'); await settle();
assert.ok(requests.some(([url])=>url.includes('/api/command?q=engine%20repair')));
assert.match(nodes['coverage-repair'].textContent,/Not installed/i);
assert.equal(requests.filter(([url])=>url==='/api/system').length,1,'Read system information once; no expensive polling');
assert.equal(nodes['system-battery'].textContent,'Unavailable');
assert.equal(nodes['system-storage'].textContent,'Unavailable');
assert.equal(requests.some(([,opts])=>opts.method==='POST'),false);
assert.equal(requests.some(([url])=>url==='/content/coverage.json'),false);
""")


if __name__ == '__main__':
    unittest.main()
