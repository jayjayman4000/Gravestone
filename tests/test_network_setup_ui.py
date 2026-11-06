"""Production setup controller tested without opening host programs/networking."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NetworkSetupUITests(unittest.TestCase):
    def test_discoverable_connect_download_return_import_offline_flow(self):
        html = (ROOT / 'app/static/index.html').read_text()
        self.assertIn('id="nav-network-setup"', html)
        self.assertIn('Network &amp; downloads', html)
        self.assertIn('/home/user/Downloads', html)
        self.assertIn('Ctrl+L', html)
        script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const nodes={};
for(const id of fs.readFileSync(process.argv[1]+'/app/static/index.html','utf8').matchAll(/id="([^"]+)"/g)) {
 nodes[id[1]]={handlers:{},disabled:false,files:[],checked:false,value:'',textContent:'',
 addEventListener(k,f){this.handlers[k]=f;},focus(){},showModal(){this.open=true;},
 close(){this.open=false;},click(){return this.handlers.click?.();}};
}
const calls=[]; let fail=false;
const api=async(path,options)=>{calls.push({path,options});if(fail)throw Error('Fixture unavailable');return path==='/api/desktop/status'?{network_state:'disconnected'}:{accepted:true};};
const window={addEventListener(){}};
vm.runInNewContext(fs.readFileSync(process.argv[1]+'/app/static/setup.js','utf8'),{$:id=>nodes[id],api,window,loadLibrary:async()=>({documents:[]})});
(async()=>{
 assert.equal(calls.length,0,'No desktop action at boot');
 await nodes['nav-network-setup'].click();
 assert.equal(nodes['online-setup'].open,true);
 await nodes['setup-network-connect'].click();
 assert.deepEqual(calls.filter(x=>x.options?.method==='POST').map(x=>x.path),['/api/desktop/network-online','/api/desktop/network-settings']);
 await nodes['setup-browser'].click();
 assert.equal(calls.filter(x=>x.options?.method==='POST').at(-1).path,'/api/desktop/browser');
 assert.match(nodes['setup-network-status'].textContent,/close|return/i);
 await nodes['setup-network-offline'].click();
 assert.equal(calls.filter(x=>x.options?.method==='POST').at(-1).path,'/api/desktop/network-offline');
 assert.equal(nodes['setup-network-offline'].disabled,false);
 for(const call of calls.filter(x=>x.options?.method==='POST')) assert.equal(call.options.body,'{}');
 fail=true;await nodes['setup-network-connect'].click();
 assert.match(nodes['setup-network-status'].textContent,/not confirmed|unavailable/i);
 assert.equal(nodes['setup-network-connect'].disabled,false);
 assert.equal(nodes['setup-submit'].disabled,false,'Offline PDF import stays usable');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', script, str(ROOT)], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
