import json
from pathlib import Path
import subprocess
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]


class SetupUITests(unittest.TestCase):
    def test_optional_setup_accessible_controls(self):
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags = {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.tags[attrs['id']] = (tag, attrs)
        html = (ROOT / 'app/static/index.html').read_text()
        parsed = Tags(); parsed.feed(html)
        self.assertIn('nav-online-setup', parsed.tags)
        self.assertEqual(parsed.tags['online-setup'][0], 'dialog')
        self.assertEqual(parsed.tags['nav-online-setup'][1]['aria-controls'], 'online-setup')
        self.assertNotIn('open', parsed.tags['online-setup'][1])
        self.assertIn('setup-skip', parsed.tags)
        self.assertIn('setup-rights', parsed.tags)
        self.assertIn('setup-file', parsed.tags)
        self.assertIn('/static/setup.js', html)

    def test_import_is_generic_local_preparation(self):
        html = (ROOT / "app/static/index.html").read_text()
        self.assertIn('>Import personal content</button>', html)
        self.assertIn('id="setup-title">Import personal content</h2>', html)
        self.assertNotIn("setup-guides", html)
        self.assertNotIn("setup-source", html)
        self.assertNotIn("Online setup", html)
        script = (ROOT / "app/static/setup.js").read_text()
        self.assertNotIn("catalog.guides", script)
        self.assertNotIn("/api/setup", script)
        self.assertIn("ordinary computer", html)

    def test_personal_reader_urls_are_allowlisted(self):
        source = (ROOT / 'app/static/app.js').read_text().split('const documentsByFile')[0]
        path = 'personal/' + 'a' * 64 + '/original.pdf'
        script = source + '\nconsole.log(JSON.stringify([originalURL(' + json.dumps(path) + '), originalURL("personal/../notes.txt"), contentURL("personal/" + "a".repeat(64) + "/search.txt")]));'
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), ['/' + path, None, '/personal/' + 'a' * 64 + '/search.txt'])

    def test_setup_checkbox_has_intrinsic_width(self):
        css = (ROOT / 'app/static/style.css').read_text()
        self.assertRegex(css, r'#setup-rights\s*\{[^}]*width:\s*auto')

    def test_build_runner_installs_parser_before_source_tests(self):
        workflow = (ROOT / '.github/workflows/build-live.yml').read_text()
        install = workflow.index('sudo apt-get install -y --no-install-recommends python3-pypdf2')
        tests = workflow.index('/usr/bin/python3 -m unittest discover -s tests -v')
        self.assertLess(install, tests)

    def test_live_parser_dependency_packaged(self):
        packages = (ROOT / 'live/config/package-lists/kiosk.list.chroot').read_text().splitlines()
        self.assertIn('python3-pypdf2', packages)
