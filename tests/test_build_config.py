"""Live-image contract checks; no root, Docker, or network required."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildConfigTests(unittest.TestCase):
    def test_prepare_stages_application_without_git_or_bytecode(self):
        script = ROOT / "scripts/prepare-live.sh"
        self.assertTrue(script.is_file(), "missing live staging script")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "source"
            for name in ("scripts", "live"):
                shutil.copytree(ROOT / name, repo / name)
            for name in ("app", "content", ".git", "app/__pycache__"):
                (repo / name).mkdir(parents=True, exist_ok=True)
            (repo / "app/__main__.py").write_text("print('fixture')\n")
            (repo / "content/index.json").write_text("{}\n")
            (repo / "app/__pycache__/stale.pyc").write_bytes(b"stale")
            (repo / ".local").mkdir()
            (repo / ".local/private-notes.txt").write_text("private fixture")
            build = base / "build"
            subprocess.run(["bash", str(repo / "scripts/prepare-live.sh"), str(build)], check=True)
            target = build / "config/includes.chroot/opt/gravestone"
            self.assertTrue((target / "app/__main__.py").is_file())
            self.assertTrue((target / "content/index.json").is_file())
            self.assertFalse(list(target.rglob(".git")))
            self.assertFalse(list(target.rglob("*.pyc")))
            self.assertFalse((target / ".local").exists(), 'Private runtime data must not enter an image')
            self.assertTrue((build / "auto/config").is_file())
            result = subprocess.run(["bash", str(repo / "scripts/prepare-live.sh"), str(build)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "must refuse nonempty build directory")
            self.assertIn("empty", result.stderr)
            unsafe = subprocess.run(["bash", str(repo / "scripts/prepare-live.sh"), str(repo)], capture_output=True, text=True)
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("outside", unsafe.stderr)
            self.assertTrue((build / "config/hooks/live/0100-gravestone.hook.chroot").stat().st_mode & 0o111)

    def test_readiness_requires_successful_http_response(self):
        import http.server
        import threading
        script = ROOT / "live/config/includes.chroot/usr/local/bin/gravestone-wait-ready"
        self.assertTrue(script.is_file(), "missing readiness probe")
        self.assertIn("http://127.0.0.1:8766/api/status", script.read_text())

        class Handler(http.server.BaseHTTPRequestHandler):
            status = 503

            def do_GET(self):
                self.send_response(self.status)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/health"
            failed = subprocess.run(["sh", str(script), url, "1", "0"], capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            Handler.status = 200
            subprocess.run(["sh", str(script), url, "1", "0"], check=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_kiosk_and_smoke_are_wired_to_user_service(self):
        include = ROOT / "live/config/includes.chroot"
        backend = include / "etc/systemd/system/gravestone.service"
        self.assertTrue(backend.is_file(), "missing backend unit")
        unit = backend.read_text()
        for token in ("User=user", "After=live-config.service", "WorkingDirectory=/opt/gravestone", "--data-dir /home/user/.local/share/gravestone", "--host 127.0.0.1 --port 8766"):
            self.assertIn(token, unit)
        self.assertIn("ExecStartPost=/usr/local/bin/gravestone-wait-ready", unit)
        self.assertIn("ExecStartPost=/usr/bin/echo GRAVESTONE_SERVICE_READY", unit)
        self.assertIn("StandardOutput=journal+console", unit)
        lightdm = (include / "etc/lightdm/lightdm.conf.d/90-gravestone.conf").read_text()
        for token in ("autologin-user=user", "autologin-session=gravestone", "user-session=gravestone"):
            self.assertIn(token, lightdm)
        session = (include / "usr/local/bin/gravestone-session").read_text()
        self.assertLess(session.index("gravestone-wait-ready"), session.index("firefox-esr"))
        self.assertIn("openbox", session)
        smoke_unit = (include / "etc/systemd/system/gravestone-smoke.service").read_text()
        self.assertIn("ConditionKernelCommandLine=gravestone.smoke=1", smoke_unit)
        smoke = include / "usr/local/sbin/gravestone-boot-smoke"
        smoke_text = smoke.read_text()
        self.assertLess(smoke_text.index("gravestone-wait-ready"), smoke_text.index("GRAVESTONE_BOOT_OK"))
        self.assertIn("/dev/ttyS0", smoke_text)
        self.assertIn("systemctl poweroff", smoke_text)
        # On the host without the opt-in kernel flag this must do nothing.
        result = subprocess.run(["sh", str(smoke)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_image_and_ci_enforce_boot_and_artifact_contract(self):
        config = (ROOT / "live/auto/config").read_text()
        for token in ("--distribution bookworm", "--architectures amd64", "--binary-image iso-hybrid", "syslinux grub-efi", "--uefi-secure-boot disable", "--debian-installer none", "--apt-secure true", "--chroot-squashfs-compression-type xz", "persistence-media=removable-usb", "persistence-storage=filesystem", "live-media=removable", "swap=false", "noswap", "ip=frommedia"):
            self.assertIn(token, config)
        packages = (ROOT / "live/config/package-lists/kiosk.list.chroot").read_text().split()
        for package in ("xorg", "openbox", "lightdm", "firefox-esr", "python3", "live-boot", "live-config-systemd"):
            self.assertIn(package, packages)
        bios = ROOT / "live/config/bootloaders/isolinux/isolinux.cfg"
        uefi = ROOT / "live/config/bootloaders/grub-pc/config.cfg"
        self.assertTrue(bios.is_file(), "BIOS menu needs an unattended boot timeout")
        self.assertTrue(uefi.is_file(), "UEFI menu needs an unattended boot timeout")
        self.assertIn("timeout 30", bios.read_text())
        self.assertIn("set timeout=3", uefi.read_text())
        workflow = ROOT / ".github/workflows/build-live.yml"
        self.assertTrue(workflow.is_file(), "missing manual build workflow")
        workflow_text = workflow.read_text()
        for token in ("workflow_dispatch:", "--privileged", "debian:bookworm", "if: always()", "actions/upload-artifact@", "scripts/smoke-iso.sh"):
            self.assertIn(token, workflow_text)
        self.assertNotIn("gh release create", workflow_text)
        build = (ROOT / "scripts/build-live.sh").read_text()
        for token in ("lb config", "lb build", "gravestone-0.4.2-amd64.iso", "14000000000", "sha256sum"):
            self.assertIn(token, build)
        smoke = (ROOT / "scripts/smoke-iso.sh").read_text()
        for token in ("qemu-system-x86_64", "240", "-accel tcg", "-m 2048", "-smp 2", "-kernel", "-initrd", "-cdrom", "gravestone.smoke=1", "GRAVESTONE_BOOT_OK", "-nic none"):
            self.assertIn(token, smoke)
        self.assertIn("BIOS", smoke)
        self.assertIn("UEFI", smoke)

    def test_measured_cooldown_precedes_real_overview_gate(self):
        build = (ROOT / 'scripts/build-live.sh').read_text()
        cooldown = 'python3 -u "$repo/scripts/wait-for-host-load.py"'
        self.assertIn(cooldown, build)
        self.assertIn('set -euo pipefail', build)
        self.assertLess(build.index('-p test_ai_package.py'), build.index(cooldown))
        self.assertLess(build.index(cooldown), build.index('GRAVESTONE_OVERVIEW_REAL_ROOT='))
        # A failed cooldown must not be made optional by a shell conditional.
        self.assertEqual(build.split(cooldown)[1].splitlines()[0], '')

    def test_real_overview_gate_runs_before_image_build(self):
        build = (ROOT / "scripts/build-live.sh").read_text()
        for token in ('GRAVESTONE_OVERVIEW_REAL_ROOT="$app_root"',
                      'GRAVESTONE_OVERVIEW_EVIDENCE="$out/overview-inference"',
                      'python3 -m unittest discover -s tests -p test_overview_real.py -v'):
            self.assertIn(token, build)
        self.assertLess(build.index('-p test_overview_real.py'), build.index('\nlb build'))


if __name__ == "__main__":
    unittest.main()
