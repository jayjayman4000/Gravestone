"""Library/search integration uses the same controlled reader and workspace."""
import shutil
import subprocess
import unittest
from test_reader_controls import HARNESS, ROOT


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class ReaderIntegrationTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(['node', '-e', HARNESS + body + "\n})().catch(e=>{console.error(e);process.exitCode=1;});", str(ROOT)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    # Reuse the DOM/PDF.js boundary adapter, not an alternate reader implementation.
    def test_library_and_search_return_preserve_unsaved_workspace(self):
        self.run_js(r"""
const original=walk(nodes['document-list']).find(n=>/Open original/.test(n.textContent));
assert.ok(original);
nodes['note-text'].value='UNSAVED <private> draft';
await nodes['note-text'].fire('input');
await original.fire('click');
assert.equal(nodes.reader.open,true);
assert.equal(document.activeElement,nodes['reader-back']);
assert.equal(frame(),undefined);
assert.equal(canvas().page,1);
assert.match(text(nodes['reader-source']),/Fixture rights/);
assert.equal(original.target,undefined);
await nodes['reader-back'].fire('click');
assert.equal(document.activeElement,original);
assert.equal(canvas(),undefined);
assert.equal(nodes['note-text'].value,'UNSAVED <private> draft');
assert.equal((await window.fire('beforeunload')).defaultPrevented,true);
const source=walk(nodes['document-list']).find(n=>n.textContent==='Publisher source (requires network)');
assert.equal(source.href,doc.url);
assert.equal(source.target,'_blank');
nodes['search-query'].value='needle';
await nodes['search-form'].fire('submit');
const action=walk(nodes['search-results']).find(n=>n.className==='source-open');
await action.fire('click');
assert.equal(canvas().page,2);
await nodes['reader-back'].fire('click');
assert.equal(document.activeElement,action);
assert.equal(nodes['note-text'].value,'UNSAVED <private> draft');
assert.equal(requests.filter(([url])=>url==='/api/notes').length,1);
""")


if __name__ == '__main__':
    unittest.main()
