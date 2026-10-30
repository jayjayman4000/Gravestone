"""Controlled renderer contract; PDF.js is injected only at its async boundary."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'app/static/pdfjs/controlled-viewer.mjs'
HARNESS = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {ControlledPDFViewer} = await import(pathToFileURL(process.argv[1]));
const requested=[]; const rendered=[]; const canvases=[];
let destroyed=0; let cancelled=0; let actualPages=10;
const page = n => ({getViewport:({scale})=>({width:600*scale,height:800*scale}),
  render:({canvasContext,viewport})=> { rendered.push([n,canvasContext.canvas,viewport]); return {promise:Promise.resolve(),cancel(){cancelled++;}}; }});
const pdf={numPages:actualPages,getPage:async n=>{requested.push(n);return page(n);},destroy(){destroyed++;}};
let options;
const pdfjs={GlobalWorkerOptions:{},getDocument:o=>{options=o;return {promise:Promise.resolve(pdf),destroy(){destroyed++;}};}};
const container={children:[],replaceChildren(...children){this.children=children;}};
const createCanvas=()=>{const canvas={setAttribute(){},getContext(){return {canvas};}};canvases.push(canvas);return canvas;};
const viewer=new ControlledPDFViewer(container,{pdfjs,createCanvas});
"""


class PDFVendorTests(unittest.TestCase):
    def test_pinned_official_runtime_resources_and_licenses_are_unmodified(self):
        metadata = json.loads((ROOT / 'docs/vendor/pdfjs-dist-5.4.624.json').read_text())
        self.assertEqual(metadata['package'], 'pdfjs-dist')
        self.assertEqual(metadata['version'], '5.4.624')
        self.assertEqual(metadata['source_url'], 'https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-5.4.624.tgz')
        self.assertEqual(metadata['upstream_commit'], '384c6208b257e81fa7bcd4e59dc100e3c99d9528')
        self.assertEqual(metadata['license'], 'Apache-2.0')
        self.assertEqual(metadata['license_sha256'], '0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594')
        root = ROOT / 'app/static/pdfjs'
        recorded = set()
        for entry in metadata['files']:
            self.assertNotIn('..', Path(entry['path']).parts)
            data = (root / entry['path']).read_bytes()
            self.assertEqual(len(data), entry['bytes'], entry['path'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'], entry['path'])
            recorded.add(entry['path'])
        shipped = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(shipped - {'controlled-viewer.mjs', 'controlled-viewer.css'}, recorded)
        for required in ['LICENSE', 'cmaps/LICENSE', 'standard_fonts/LICENSE_FOXIT', 'standard_fonts/LICENSE_LIBERATION', 'wasm/LICENSE_OPENJPEG', 'wasm/LICENSE_PDFJS_OPENJPEG', 'pdf.min.mjs', 'pdf.worker.min.mjs']:
            self.assertIn(required, recorded)


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class ControlledPDFViewerTests(unittest.TestCase):
    def run_js(self, body):
        self.assertTrue(MODULE.is_file(), 'Missing controlled single-page renderer; native PDF navigation can drift')
        result = subprocess.run(['node', '--input-type=module', '-e', HARNESS + body, str(MODULE)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_only_requested_physical_page_is_rendered_on_owned_canvas(self):
        self.run_js(r"""
assert.equal(await viewer.load('/content/originals/fema.pdf'),10);
assert.equal(container.children.length,0);
const result=await viewer.render(7,100);
assert.equal(result.page,7);
assert.equal(result.zoom,100);
assert.deepEqual(requested,[7]);
assert.deepEqual(rendered.map(r=>r[0]),[7]);
assert.equal(container.children.length,1);
assert.equal(container.children[0],rendered[0][1]);
assert.equal(container.children[0].width,600);
assert.equal(container.children[0].height,800);
assert.equal(options.url,'/content/originals/fema.pdf');
assert.equal(options.isEvalSupported,false);
assert.equal(options.useWasm,false);
assert.equal(options.enableXfa,false);
assert.ok(options.cMapUrl.endsWith('/cmaps/'));
assert.ok(options.standardFontDataUrl.endsWith('/standard_fonts/'));
await viewer.render(8,125);
assert.equal(container.children.length,1);
assert.equal(container.children[0].width,750);
assert.deepEqual(rendered.map(r=>r[0]),[7,8]);
""")

    def test_close_during_document_load_never_revives_document_or_paints(self):
        self.run_js(r"""
let finish;
pdfjs.getDocument=o=>({promise:new Promise(resolve=>finish=resolve),destroy(){destroyed++;}});
const loading=viewer.load('/content/originals/fema.pdf');
viewer.destroy();finish(pdf);
assert.equal(await loading,null);
assert.equal(viewer.pdf,undefined);
assert.equal(container.children.length,0);
assert.ok(destroyed>=1);
""")

    def test_rapid_navigation_never_commits_stale_render_and_close_cancels_work(self):
        self.run_js(r"""
await viewer.load('/content/originals/fema.pdf');
const pending=new Map();
pdf.getPage=async n=>({getViewport:()=>({width:n,height:10}),render:()=>{
  let done;const promise=new Promise(resolve=>done=resolve);pending.set(n,done);
  return {promise,cancel(){cancelled++;}};
}});
const first=viewer.render(7,100); await new Promise(setImmediate);
const second=viewer.render(8,125); await new Promise(setImmediate);
assert.equal(container.children.length,0,'Old canvas must not remain while a new target is pending');
pending.get(8)(); assert.deepEqual(await second,{page:8,zoom:125});
const current=container.children[0];
pending.get(7)(); assert.equal(await first,null);
assert.equal(container.children[0],current,'Late page 7 cannot replace page 8');
assert.ok(cancelled>=1);
const third=viewer.render(9,100);await new Promise(setImmediate);
viewer.destroy();pending.get(9)();assert.equal(await third,null);
assert.equal(container.children.length,0);
assert.ok(destroyed>=1);
assert.ok(cancelled>=2);
""")


if __name__ == '__main__':
    unittest.main()
