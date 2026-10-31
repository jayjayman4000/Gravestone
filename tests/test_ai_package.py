"""Packaging contract tests; real inference is an explicit opt-in integration test."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class AIPackageTests(unittest.TestCase):
    def test_pinned_official_inputs_have_integrity_metadata(self):
        path = ROOT / "ai/package.json"
        self.assertTrue(path.is_file(), "missing pinned AI package metadata")
        package = json.loads(path.read_text())
        model = package["model"]
        self.assertEqual(model["revision"], "23749fefcc72300e3a2ad315e1317431b06b590a")
        self.assertEqual(model["filename"], "Qwen3-0.6B-Q8_0.gguf")
        self.assertEqual(model["bytes"], 639446688)
        self.assertEqual(model["sha256"], "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031")
        self.assertTrue(model["url"].startswith("https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/" + model["revision"]))
        runtime = package["runtime"]
        self.assertEqual(runtime["release"], "b12001")
        self.assertRegex(runtime["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(runtime["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(runtime["commit"], runtime["url"])
        for artifact in (model, runtime, *package["documents"]):
            self.assertGreater(artifact["bytes"], 0)
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual({d["path"] for d in package["documents"]}, {
            "licenses/Qwen-LICENSE", "licenses/llama.cpp-LICENSE", "upstream/Qwen-README.md"})

    def test_verifier_rejects_wrong_size_and_wrong_digest(self):
        implementation = ROOT / "ai/package.py"
        self.assertTrue(implementation.is_file(), "missing package integrity verifier")
        spec = importlib.util.spec_from_file_location("ai_package", implementation)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            artifact.write_bytes(b"verified")
            expected = {"bytes": 8, "sha256": hashlib.sha256(b"verified").hexdigest()}
            module.verify_file(artifact, expected)
            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.verify_file(artifact, expected)
            artifact.write_bytes(b"short")
            with self.assertRaisesRegex(ValueError, "size"):
                module.verify_file(artifact, expected)

    def test_build_contract_is_baseline_cpu_only_and_install_is_fresh(self):
        implementation = ROOT / "ai/package.py"
        spec = importlib.util.spec_from_file_location("ai_package", implementation)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, "CMAKE_FLAGS"), "missing portable source build")
        flags = module.CMAKE_FLAGS
        for flag in ("BUILD_SHARED_LIBS=OFF", "GGML_NATIVE=OFF", "GGML_AVX=OFF",
                     "GGML_AVX2=OFF", "GGML_FMA=OFF", "GGML_F16C=OFF",
                     "GGML_SSE42=OFF", "GGML_BMI2=OFF", "GGML_OPENMP=OFF",
                     "GGML_CUDA=OFF", "GGML_VULKAN=OFF", "GGML_BLAS=OFF",
                     "LLAMA_CURL=OFF", "LLAMA_OPENSSL=OFF", "LLAMA_BUILD_UI=OFF",
                     "LLAMA_USE_PREBUILT_UI=OFF", "LLAMA_CONNECT=OFF",
                     "LLAMA_BUILD_NUMBER=12001", "LLAMA_BUILD_COMMIT=eb4e244be77a906a183cd4a00fd51d9ad3200955"):
            self.assertIn("-D" + flag, flags)
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            artifact.write_bytes(b"cached")
            expected = {"bytes": 6, "sha256": hashlib.sha256(b"cached").hexdigest(),
                        "url": "https://unused.invalid/"}
            self.assertEqual(module.fetch(expected, artifact), artifact)
            artifact.write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.fetch(expected, artifact)
            with self.assertRaisesRegex(ValueError, "outside.*repository"):
                module.validate_target(ROOT / "ai/staging")
            target = Path(directory) / "target"
            target.mkdir()
            (target / "models").mkdir()
            (target / "models" / "keep").write_text("existing")
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.validate_target(target)
        script = ROOT / "scripts/prepare-ai.sh"
        self.assertTrue(script.is_file(), "missing builder entry point")
        result = subprocess.run([str(script)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APP_ROOT", result.stderr)

    def test_service_is_independent_loopback_and_hardened(self):
        path = ROOT / "live/config/includes.chroot/etc/systemd/system/gravestone-ai.service"
        self.assertTrue(path.is_file(), "missing offline model service")
        unit = path.read_text()
        for setting in ("User=user", "After=live-config.service", "ConditionFileIsExecutable=/opt/gravestone/ai/runtime/llama-server", "NoNewPrivileges=true",
                        "ProtectSystem=strict", "PrivateTmp=true", "IPAddressDeny=any",
                        "IPAddressAllow=localhost", "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX"):
            self.assertIn(setting, unit)
        command = next(line.split("=", 1)[1] for line in unit.splitlines() if line.startswith("ExecStart="))
        for argument in ("/opt/gravestone/ai/runtime/llama-server", "--host 127.0.0.1", "--port 8767",
                         "--model /opt/gravestone/models/Qwen3-0.6B-Q8_0.gguf", "--ctx-size 2048",
                         "--threads 2", "--threads-batch 2", "--parallel 1", "--n-predict 128",
                         "--no-webui", "--offline"):
            self.assertIn(argument, command)
        self.assertNotIn("Requires=gravestone.service", unit)
        self.assertNotIn("Before=gravestone.service", unit)


@unittest.skipUnless(os.environ.get("GRAVESTONE_AI_PACKAGE_ROOT"), "set GRAVESTONE_AI_PACKAGE_ROOT to validate installed artifacts")
class InstalledPackageTests(unittest.TestCase):
    def test_installed_outputs_are_verified_and_include_build_source(self):
        target = Path(os.environ["GRAVESTONE_AI_PACKAGE_ROOT"])
        self.assertTrue((target / "ai/BUILD_PROVENANCE.json").is_file(), "package has not been built")
        package = json.loads((ROOT / "ai/package.json").read_text())
        artifacts = [(target / "models" / package["model"]["filename"], package["model"]),
                     (target / "ai/sources/llama.cpp.tar.gz", package["runtime"])]
        artifacts.extend((target / "ai" / doc["path"], doc) for doc in package["documents"])
        for path, expected in artifacts:
            self.assertEqual(path.stat().st_size, expected["bytes"])
            with path.open("rb") as stream:
                self.assertEqual(hashlib.file_digest(stream, "sha256").hexdigest(), expected["sha256"])
        binary = target / "ai/runtime/llama-server"
        self.assertTrue(os.access(binary, os.X_OK))
        provenance = json.loads((target / "ai/BUILD_PROVENANCE.json").read_text())
        with binary.open("rb") as stream:
            self.assertEqual(hashlib.file_digest(stream, "sha256").hexdigest(), provenance["runtime_sha256"])
        self.assertEqual(provenance["inputs"], package)
        self.assertEqual(provenance["build_jobs"], 2)
        self.assertIn("-DGGML_NATIVE=OFF", provenance["cmake_flags"])
        self.assertIn("12001", provenance["runtime_version"])
        self.assertIn("eb4e244be", provenance["runtime_version"])
        self.assertNotIn("libggml", provenance["runtime_dependencies"])
        self.assertNotIn("libllama", provenance["runtime_dependencies"])
        cache = (target / "ai/sources/CMakeCache.txt").read_text()
        for name in ("BUILD_SHARED_LIBS", "GGML_NATIVE", "GGML_AVX", "GGML_AVX2", "GGML_FMA",
                     "GGML_F16C", "GGML_OPENMP", "LLAMA_OPENSSL", "LLAMA_USE_PREBUILT_UI"):
            self.assertIn(name + ":BOOL=OFF", cache)


@unittest.skipUnless(os.environ.get("GRAVESTONE_AI_SERVER") and os.environ.get("GRAVESTONE_AI_MODEL"),
                     "real inference requires GRAVESTONE_AI_SERVER and GRAVESTONE_AI_MODEL")
class RealInferenceTests(unittest.TestCase):
    def test_real_official_model_returns_term_expansion_json(self):
        # This test launches an actual llama-server and verifies actual model bytes.
        model = Path(os.environ["GRAVESTONE_AI_MODEL"])
        expected = json.loads((ROOT / "ai/package.json").read_text())["model"]
        self.assertEqual(model.stat().st_size, expected["bytes"])
        with model.open("rb") as stream:
            self.assertEqual(hashlib.file_digest(stream, "sha256").hexdigest(), expected["sha256"])
        mem_available = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                             if line.startswith("MemAvailable:"))
        self.assertGreater(mem_available, 2 * 1024 * 1024, "protect shared host: need 2 GiB available")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "server.log"
            with log_path.open("w+") as log:
                process = subprocess.Popen([
                    os.environ["GRAVESTONE_AI_SERVER"], "--model", str(model), "--host", "127.0.0.1",
                    "--port", str(port), "--ctx-size", "2048", "--threads", "2", "--threads-batch", "2",
                    "--parallel", "1", "--n-predict", "128", "--no-webui", "--offline", "--n-gpu-layers", "0"],
                    stdout=log, stderr=log)
                started = time.monotonic()
                try:
                    deadline = started + 120
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            self.fail("real server exited: " + log_path.read_text()[-6000:])
                        try:
                            with opener.open(url + "/health", timeout=2) as response:
                                if response.status == 200:
                                    break
                        except (OSError, urllib.error.URLError):
                            pass
                        time.sleep(0.25)
                    else:
                        self.fail("real model startup timed out: " + log_path.read_text()[-6000:])
                    payload = {
                        "messages": [
                            {"role": "system", "content": "Expand a library search query into related search terms only. Return a JSON object with a terms array of at most 5 short strings. Do not provide instructions or answer the query."},
                            {"role": "user", "content": "safe drinking water"}],
                        "response_format": {"type": "json_object"},
                        "chat_template_kwargs": {"enable_thinking": False},
                        "max_tokens": 96, "temperature": 0,
                    }
                    request = urllib.request.Request(url + "/v1/chat/completions",
                        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                    query_started = time.monotonic()
                    with opener.open(request, timeout=180) as response:
                        output = json.load(response)
                    content = output["choices"][0]["message"]["content"]
                    terms = json.loads(content)["terms"]
                    self.assertIsInstance(terms, list)
                    self.assertTrue(terms)
                    self.assertLessEqual(len(terms), 5)
                    self.assertTrue(all(isinstance(term, str) and term for term in terms))
                    # Exercise production parsing, ranking and source-only output against
                    # this actual server, within the application's real 20-second budget.
                    from app.retrieval import command_search
                    retrieval_started = time.monotonic()
                    retrieval = command_search(ROOT / 'content', 'safe drinking water', model_url=url)
                    retrieval_elapsed = time.monotonic() - retrieval_started
                    # A real round-trip is required, but accepted new terms are
                    # not guaranteed. Do not mislabel a duplicate-only completion
                    # as useful AI assistance or weaken the availability check.
                    self.assertEqual(retrieval['model_status'], 'available', retrieval)
                    self.assertIsInstance(retrieval['expansion_terms'], list)
                    self.assertEqual(retrieval['mode'],
                                     'ai-assisted' if retrieval['expansion_terms'] else 'keyword-only', retrieval)
                    self.assertEqual(retrieval['terms'],
                                     ['safe', 'drinking', 'water'] + retrieval['expansion_terms'])
                    self.assertTrue(retrieval['results'], retrieval)
                    manifest = json.loads((ROOT / 'content/manifest.json').read_text())
                    by_file = {doc['file']: doc for doc in manifest['documents']}
                    for hit in retrieval['results']:
                        text = (ROOT / 'content' / by_file[hit['file']]['text_file']).read_text()
                        self.assertIn(hit['excerpt'], text.split('\f')[hit['page'] - 1])
                    evidence = {"server": os.environ["GRAVESTONE_AI_SERVER"], "model": str(model),
                                "model_sha256": expected["sha256"], "request": payload, "response": output,
                                "retrieval": retrieval,
                                "retrieval_elapsed_seconds": round(retrieval_elapsed, 3),
                                "query_elapsed_seconds": round(time.monotonic() - query_started, 3),
                                "total_elapsed_seconds": round(time.monotonic() - started, 3)}
                    if os.environ.get("GRAVESTONE_AI_EVIDENCE"):
                        evidence_path = Path(os.environ["GRAVESTONE_AI_EVIDENCE"])
                        self.assertNotIn(ROOT, evidence_path.resolve().parents)
                        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
                    print("REAL_INFERENCE " + json.dumps(evidence), flush=True)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
