"""Palette runtime and best-effort settings, without browser dependencies."""
import shutil
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThemeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_palettes_persist_and_storage_failure_does_not_block_ui(self):
        path = ROOT / 'app/static/themes.js'
        self.assertTrue(path.exists(), 'The display menu needs a palette controller')
        script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync(process.argv[1], 'utf8');
for(const mode of ['fresh','saved','denied','invalid']) {
 const buttons={}, events=[], writes=[];
 for(const name of ['amber','red','green','contrast']) buttons['theme-'+name]={attrs:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,fn){this[k]=fn;}};
 const document={documentElement:{dataset:{}},getElementById:id=>buttons[id],dispatchEvent:e=>events.push(e.type)};
 const localStorage={getItem(){if(mode==='denied')throw Error('denied');return mode==='saved'?'green':mode==='invalid'?'unknown':null;},setItem(k,v){if(mode==='denied')throw Error('denied');writes.push([k,v]);}};
 vm.runInNewContext(script,{document,localStorage,CustomEvent:class {constructor(type){this.type=type;}}});
 assert.equal(document.documentElement.dataset.theme, mode==='saved'?'green':'amber');
 for(const name of ['red','green','contrast','amber']) {
  buttons['theme-'+name].click();
  assert.equal(document.documentElement.dataset.theme,name);
  assert.equal(buttons['theme-'+name].attrs['aria-pressed'],'true');
  for(const other of ['red','green','contrast','amber'].filter(x=>x!==name))assert.equal(buttons['theme-'+other].attrs['aria-pressed'],'false');
 }
 assert.ok(events.includes('gravestone-theme-change'));
 if(mode!=='denied')assert.equal(writes.at(-1)[1],'amber');
}
"""
        result = subprocess.run(['node', '-e', script, str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        css = (ROOT / 'app/static/style.css').read_text()
        for color in ['#FFB000', '#FF1A1A', '#00FF66', '#FFFFFF', '#000000']:
            self.assertIn(color, css)
        for variable in ['--bg', '--text', '--surface', '--border', '--map-bg', '--map-land', '--map-line', '--map-label']:
            self.assertIn(variable, css)


if __name__ == '__main__':
    unittest.main()
