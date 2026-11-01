"""Civilian kiosk structure; JavaScript behavior is in test_command_ui."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Shell(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node = {'tag': tag, 'attrs': attrs, 'ancestors': list(self.stack)}
        if 'id' in attrs:
            self.nodes[attrs['id']] = node
        if tag not in {'input', 'meta', 'link', 'br', 'hr', 'img'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break


class ConsoleLayoutTests(unittest.TestCase):
    def test_overview_has_bounded_scrolling_without_consuming_pdf_viewport(self):
        # Companion browser regression populates maximum-size synthetic bullets
        # and measures actual mobile/landscape geometry; this pins the CSS seam.
        css = (ROOT / 'app/static/style.css').read_text()
        self.assertRegex(css, r'\.reader-overview\s*\{[^}]*max-height:\s*30dvh')
        self.assertRegex(css, r'\.reader-overview\s*\{[^}]*overflow:\s*auto')
        self.assertRegex(css, r'\.reader-overview\s*\{[^}]*flex:\s*0 1 auto')

    def test_dashboard_has_no_fixed_desktop_width_cap(self):
        # Structural contract; actual computed geometry is checked in browser QA.
        css = (ROOT / 'app/static/style.css').read_text()
        self.assertIn('--page-gutter: clamp(16px, 2vw, 48px)', css)
        self.assertIn('main { width: 100%;', css)
        self.assertIn('.topbar { width: 100%; max-width: none;', css)
        self.assertNotIn('width: min(1320px, 100%)', css)
        self.assertIn('padding: 2rem var(--page-gutter)', css)
        self.assertIn('font-size: 18px', css)
        self.assertIn('flex: 0 0 190px; white-space: nowrap;', css)

    def test_search_first_home_has_six_topics_and_secondary_map(self):
        html = (ROOT / 'app/static/index.html').read_text()
        shell = Shell()
        shell.feed(html)
        nodes = shell.nodes
        self.assertEqual(nodes['main']['tag'], 'main')
        self.assertIn(nodes['main'], nodes['command-form']['ancestors'])
        self.assertIn('map-view', nodes, 'Map belongs in a secondary controlled view')
        self.assertEqual(nodes['map-view']['tag'], 'dialog')
        self.assertIn(nodes['map-view'], nodes['world-map']['ancestors'])
        self.assertNotIn(nodes['main'], nodes['world-map']['ancestors'])
        for name in ['library', 'notebook', 'map-tools', 'start-here', 'display-menu']:
            self.assertEqual(nodes[name]['tag'], 'dialog')
            self.assertIn(name + '-back', nodes)
        topics = [n for n in nodes.values() if 'data-topic' in n['attrs']]
        self.assertEqual(len(topics), 6)
        self.assertIn(nodes['map-tools'], nodes['map-pack-manager']['ancestors'])
        self.assertLess(html.index('id="command-form"'), html.index('id="topic-tiles"'))
        self.assertLess(html.index('/static/map.js'), html.index('/static/maps.js'))
        self.assertLess(html.index('/static/app.js'), html.index('/static/reader.js'))
        self.assertIn('GRAVESTONE — Offline Civil Survival Archive', html)
        self.assertIn('Source Documents', html)
        self.assertNotIn('Ready for Use', html)
        self.assertNotIn('COMMAND CONSOLE', html)
        self.assertNotIn('AI-authored', html)
        self.assertNotIn('requested-coverage', nodes)


if __name__ == '__main__':
    unittest.main()
