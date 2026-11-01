"""Deployment wiring contracts: a real model/runtime must be staged in the ISO."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class AIImageIntegrationTests(unittest.TestCase):
    def test_image_prepares_model_and_service_without_blocking_dashboard(self):
        build = (ROOT / 'scripts/build-live.sh').read_text()
        self.assertIn('scripts/prepare-ai.sh', build)
        self.assertLess(build.index('scripts/prepare-live.sh'), build.index('scripts/prepare-ai.sh'))
        self.assertLess(build.index('scripts/prepare-ai.sh'), build.index('lb config\n'))
        self.assertIn('GRAVESTONE_AI_PACKAGE_ROOT=', build)
        self.assertIn('GRAVESTONE_AI_SERVER=', build)
        self.assertIn('GRAVESTONE_AI_MODEL=', build)
        self.assertIn('test_ai_package.py', build)
        self.assertIn('GRAVESTONE_AI_EVIDENCE=', build)
        self.assertIn('$build/config/includes.chroot/opt/gravestone', build)
        hook = (ROOT / 'live/config/hooks/live/0100-gravestone.hook.chroot').read_text()
        self.assertIn('gravestone-ai.service', hook)
        backend = (ROOT / 'live/config/includes.chroot/etc/systemd/system/gravestone.service').read_text()
        self.assertNotIn('Requires=gravestone-ai.service', backend)
        workflow = (ROOT / '.github/workflows/build-live.yml').read_text()
        for dependency in ('build-essential', 'cmake', 'pkg-config', 'curl', 'python3'):
            self.assertIn(dependency, workflow)
        for text in (build, workflow):
            self.assertIn('gravestone-0.4.2-amd64', text)

if __name__ == '__main__':
    unittest.main()
