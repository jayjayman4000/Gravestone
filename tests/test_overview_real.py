"""Opt-in actual packaged inference; never substitutes synthetic completions."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import unittest
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('GRAVESTONE_OVERVIEW_REAL_ROOT'),
                     'set GRAVESTONE_OVERVIEW_REAL_ROOT to the installed /opt/gravestone tree')
class RealOverviewTests(unittest.TestCase):
    def test_packaged_epa_boiling_overview(self):
        self.assert_packaged_overview('epa-boil-water', 'epa-emergency-disinfection', 'boil water', 1)

    def test_packaged_historical_pump_overview(self):
        self.assert_packaged_overview('tm-water-pump', 'war-department-tm9-1803a-1944', 'water pump', 29)

    def assert_packaged_overview(self, label, source_id, query, page):
        from app.overview import generate_overview
        installed = Path(os.environ['GRAVESTONE_OVERVIEW_REAL_ROOT'])
        evidence = Path(os.environ['GRAVESTONE_OVERVIEW_EVIDENCE']) / label
        evidence.mkdir(parents=True, exist_ok=True)
        document = next(doc for doc in json.loads((ROOT / 'content/manifest.json').read_text())['documents']
                        if doc['id'] == source_id)
        source_hashes = {}
        for name in (document['file'], document['text_file']):
            with (ROOT / 'content' / name).open('rb') as stream:
                source_hashes[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        resources = {command: subprocess.check_output(command.split(), text=True)
                     for command in ('uptime', 'free -m')}
        (evidence / 'resources.json').write_text(json.dumps(resources, indent=2))
        available = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))
        self.assertGreater(available, 2 * 1024 * 1024, 'protect shared host RAM')
        self.assertLess(os.getloadavg()[0], 2, 'protect shared host CPU')
        package = json.loads((ROOT / 'ai/package.json').read_text())
        model = installed / 'models' / package['model']['filename']
        runtime = installed / 'ai/runtime/llama-server'
        with model.open('rb') as stream:
            model_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        self.assertEqual(model_hash, package['model']['sha256'])
        with runtime.open('rb') as stream:
            runtime_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        provenance = json.loads((installed / 'ai/BUILD_PROVENANCE.json').read_text())
        self.assertEqual(runtime_hash, provenance['runtime_sha256'])
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        cpu = min(os.sched_getaffinity(0))
        command = ['taskset', '-c', str(cpu), str(runtime), '--model', str(model),
                   '--host', '127.0.0.1', '--port', str(port), '--threads', '1',
                   '--threads-batch', '1', '--ctx-size', '2048', '--parallel', '1',
                   '--n-predict', '128', '--no-webui', '--offline', '--n-gpu-layers', '0']
        opener = build_opener(ProxyHandler({}))
        with (evidence / 'runtime.log').open('w') as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), 'owned runtime exited; see runtime.log')
                    try:
                        with opener.open(url + '/health', timeout=0.5) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail('owned runtime not ready within 30 seconds')
                from unittest.mock import patch
                from app import overview
                complete = overview._complete
                payloads = []
                def trace_complete(payload, model_url, timeout):
                    payloads.append(payload)
                    (evidence / 'request.json').write_text(json.dumps(payload, indent=2))
                    completion, status = complete(payload, model_url, timeout)
                    (evidence / 'completion.json').write_text(json.dumps(
                        {'status': status, 'completion': completion}, indent=2))
                    return completion, status
                started = time.monotonic()
                with patch.object(overview, '_complete', side_effect=trace_complete):
                    result = generate_overview(ROOT / 'content', source_id, query=query, page=page, model_url=url)
                elapsed = time.monotonic() - started
                for name, digest in source_hashes.items():
                    with (ROOT / 'content' / name).open('rb') as stream:
                        self.assertEqual(hashlib.file_digest(stream, 'sha256').hexdigest(), digest)
                record = {'kind': 'actual packaged model, not a transport fixture',
                          'source_id': source_id, 'query': query, 'requested_physical_page': page,
                          'source_hashes_unchanged': source_hashes,
                          'command': command, 'cpu_affinity': [cpu],
                          'model_sha256': model_hash, 'runtime_sha256': runtime_hash,
                          'seconds': elapsed, 'result': result,
                          'limitation': 'Exact quote/page support does not verify paraphrase accuracy, '
                                        'warning completeness, or source transcription.'}
                (evidence / 'result.json').write_text(json.dumps(record, indent=2))
                self.assertEqual(result['status'], 'available', result)
                self.assertTrue(result['bullets'])
                self.assertEqual(result['file'], document['file'])
                self.assertLessEqual(len(result['selected_pages']), 2)
                self.assertIn('unverified', result['warning'])
                pages = (ROOT / 'content' / document['text_file']).read_text().split('\f')
                candidates = {}
                from app.overview import PAGE_CHARS
                for fragment in json.loads(payloads[0]['messages'][1]['content'])['physical_page_fragments']:
                    self.assertEqual(''.join(part['text'] for part in fragment['parts']),
                                     pages[fragment['page'] - 1][:PAGE_CHARS])
                    for part in fragment['parts']:
                        if 'evidence_id' in part:
                            candidates[part['evidence_id']] = {'page': fragment['page'], 'quote': part['text']}
                self.assertLessEqual(payloads[0]['max_tokens'], 96)
                for bullet in result['bullets']:
                    self.assertIn(bullet['page'], result['selected_pages'])
                    self.assertIn(bullet['quote'], pages[bullet['page'] - 1][:PAGE_CHARS])
                    self.assertEqual({'page': bullet['page'], 'quote': bullet['quote']},
                                     candidates[bullet['evidence_id']])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                (evidence / 'cleanup.json').write_text(json.dumps(
                    {'owned_pid': process.pid, 'returncode': process.returncode, 'stopped': process.poll() is not None,
                     'proc_absent': not Path(f'/proc/{process.pid}').exists(),
                     'owned_port_closed': self.port_closed(port)}))
                self.assertFalse(Path(f'/proc/{process.pid}').exists())
                self.assertTrue(self.port_closed(port))

    @staticmethod
    def port_closed(port):
        with socket.socket() as probe:
            probe.settimeout(0.5)
            return probe.connect_ex(('127.0.0.1', port)) != 0
