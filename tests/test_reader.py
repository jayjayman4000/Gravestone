"""Dependency-free regression for actual dashboard JavaScript reader actions."""
import shutil
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReaderTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for reader behavior verification')
    def test_library_and_search_open_same_page_reader_and_restore_unsaved_workspace(self):
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
// Minimal DOM adapter only; execute the unmodified production app and handlers.
class Node {
  constructor(tag, id) { this.tagName = tag; this.id = id; this.children = []; this.handlers = {}; this.attributes = {}; this.value = ''; this.open = false; this.isConnected = true; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(k,v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k] ?? null; }
  removeAttribute(k) { delete this.attributes[k]; delete this[k]; }
  addEventListener(k,fn) { (this.handlers[k] ??= []).push(fn); }
  async fire(k, extra = {}) { const e = {preventDefault() { this.defaultPrevented = true; }, ...extra}; for (const fn of this.handlers[k] || []) await fn(e); return e; }
  focus() { document.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; for (const fn of this.handlers.close || []) fn({}); }
}
const html = fs.readFileSync(process.argv[1] + '/app/static/index.html', 'utf8');
const nodes = {};
for (const match of html.matchAll(/<([\w-]+)[^>]*\bid="([^"]+)"[^>]*>/g)) nodes[match[2]] = new Node(match[1], match[2]);
const document = {getElementById: id => nodes[id] || null, createElement: tag => new Node(tag), activeElement: null};
const window = new Node('window');
const doc = {id:'cdc-fixture', file:'originals/test.pdf', title:'Original <title>', publisher:'Centers for Disease Control and Prevention (CDC)', url:'https://www.cdc.gov/example.pdf', rights:'Fixture rights retained', retrieved_at:'test', sha256:'fixture'};
const requests = [];
let pdfMode = 'pdf';
let finishPreflight;
const fetch = async (url, options) => {
  requests.push([url, options]);
  if (options?.method === 'HEAD') {
    if (pdfMode === 'offline') throw new Error('offline');
    if (pdfMode === 'pending') return new Promise(resolve => { finishPreflight = resolve; });
    return {ok:pdfMode !== 'missing', headers:{get:() => pdfMode === 'html' ? 'text/html' : 'application/pdf'}};
  }
  const data = url === '/api/library' ? {documents:[doc],map:{}} : url === '/api/notes' ? {text:'saved text'} : url.startsWith('/api/search?') ? {results:[{id:doc.id,file:doc.file,title:doc.title,excerpt:'needle'}]} : {status:'prototype'};
  return {ok:true, json:async()=>data};
};
const context = vm.createContext({document,window,fetch,URL,TextEncoder,console});
vm.runInContext(fs.readFileSync(process.argv[1] + '/app/static/app.js','utf8'), context);
const walk = node => [node, ...node.children.flatMap(walk)];
const text = node => [node.textContent || '', ...node.children.map(text)].join(' ');
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await settle();
  const libraryButton = walk(nodes['document-list']).find(n => /Open original/.test(n.textContent));
  assert.ok(libraryButton, 'Library original action exists');
  assert.ok(nodes['reader'], 'Originals need an app-owned reader, not a bare new tab');
  assert.equal(nodes['reader'].tagName, 'dialog');
  assert.match(html, /id="reader-back"[^>]*>[^<]*Back to library/);
  nodes['note-text'].value = 'UNSAVED <private> draft';
  await nodes['note-text'].fire('input');
  libraryButton.focus();
  await libraryButton.fire('click');
  assert.equal(libraryButton.target, undefined, 'Original must not open a new tab');
  assert.equal(nodes['reader'].open, true);
  assert.equal(nodes['reader-title'].textContent, doc.title);
  assert.equal(nodes['reader-back'], document.activeElement, 'Return action initially focused');
  assert.match(text(nodes['reader-source']), /Centers for Disease Control/);
  assert.match(text(nodes['reader-source']), /Fixture rights retained/);
  assert.match(text(nodes['reader-source']), /free/i);
  assert.match(text(nodes['reader-source']), /endorse/i);
  let frame = walk(nodes['reader-body']).find(n => n.tagName === 'iframe');
  assert.equal(frame.src, '/content/originals/test.pdf');
  assert.equal(frame.title, doc.title);
  await frame.fire('error');
  assert.match(nodes['reader-status'].textContent, /could not display/i);
  assert.equal(nodes['reader'].open, true, 'Viewer error retains return action');
  await nodes['reader-back'].fire('click');
  assert.equal(nodes['reader'].open, false);
  assert.equal(document.activeElement, libraryButton);
  assert.equal(nodes['note-text'].value, 'UNSAVED <private> draft');
  assert.equal(walk(nodes['reader-body']).some(n => n.tagName === 'iframe'), false);
  assert.equal((await window.fire('beforeunload')).defaultPrevented, true, 'Dirty guard survives reading');
  const source = walk(nodes['document-list']).find(n => n.textContent === 'Publisher source (requires network)');
  assert.equal(source.href, doc.url);
  assert.equal(source.target, '_blank', 'Remote publisher pages are never embedded');
  nodes['search-query'].value = 'needle';
  await nodes['search-form'].fire('submit');
  const searchButton = walk(nodes['search-results']).find(n => /Read original in full/.test(n.textContent));
  searchButton.focus();
  await searchButton.fire('click');
  assert.equal(nodes['reader'].open, true);
  assert.match(text(nodes['reader-source']), /Centers for Disease Control/);
  assert.equal(walk(nodes['reader-body']).find(n => n.tagName === 'iframe').src, '/content/originals/test.pdf');
  await nodes['reader-back'].fire('click');
  assert.equal(document.activeElement, searchButton);
  assert.equal(nodes['note-text'].value, 'UNSAVED <private> draft');
  assert.equal(requests.filter(([url]) => url === '/api/notes').length, 1, 'Reader must not reload notes');
  assert.ok(nodes['reader-status'], 'Reader needs a visible failure/fallback status');
  assert.match(nodes['reader-status'].textContent, /blank|display/i, 'Always explain viewer fallback, not a false rendered claim');
  assert.equal(nodes['reader-download'].href, '/content/originals/test.pdf');
  assert.equal(nodes['reader-download'].download, 'test.pdf');
  assert.equal(nodes['reader-download'].target, undefined);
  for (const mode of ['missing', 'html', 'offline']) {
    pdfMode = mode;
    await libraryButton.fire('click');
    assert.equal(nodes['reader'].open, true, 'Failure must retain visible return control');
    assert.match(nodes['reader-status'].textContent, /unavailable|could not|cannot/i);
    assert.equal(walk(nodes['reader-body']).some(n => n.tagName === 'iframe'), false, 'Never embed HTML or an error response');
    await nodes['reader-back'].fire('click');
  }
  pdfMode = 'pending';
  const opening = libraryButton.fire('click');
  assert.equal(nodes['reader'].open, true, 'Return remains available while loading');
  await nodes['reader-back'].fire('click');
  finishPreflight({ok:true,headers:{get:()=>'application/pdf'}});
  await opening;
  assert.equal(nodes['reader'].open, false);
  assert.equal(walk(nodes['reader-body']).some(n => n.tagName === 'iframe'), false, 'Late response cannot reopen closed reader');
  for (const file of ['../outside.pdf', '/etc/private.pdf', 'https://evil.invalid/a.pdf', 'https:evil.pdf', 'originals/a.html', 'a\\b.pdf', 'a\0.pdf']) {
    const action = vm.runInContext('localLink', context)({...doc,file}, 'Open unsafe');
    assert.equal(action.disabled, true, 'Reject unsafe or non-PDF original: ' + file);
  }
  assert.ok(requests.some(([,options]) => options?.method === 'HEAD'), 'Validate local status/MIME before embedding');
  console.log('Reader library/search, provenance, return/focus/drafts, failures, unsafe paths, late response: OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(['node', '-e', script, str(ROOT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
