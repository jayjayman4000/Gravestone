"""Pinned offline AI packaging. Called by scripts/prepare-ai.sh; stdlib only."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

AI_DIR = Path(__file__).resolve().parent
REPO = AI_DIR.parent
CMAKE_FLAGS = [
    "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF",
    "-DLLAMA_BUILD_NUMBER=12001", "-DLLAMA_BUILD_COMMIT=eb4e244be77a906a183cd4a00fd51d9ad3200955",
    "-DCMAKE_C_FLAGS=-march=x86-64 -mtune=generic",
    "-DCMAKE_CXX_FLAGS=-march=x86-64 -mtune=generic",
    "-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc",
    "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_TOOLS=ON", "-DLLAMA_BUILD_SERVER=ON", "-DLLAMA_BUILD_APP=OFF",
    "-DLLAMA_BUILD_UI=OFF", "-DLLAMA_USE_PREBUILT_UI=OFF", "-DLLAMA_CONNECT=OFF",
    "-DLLAMA_OPENSSL=OFF", "-DLLAMA_CURL=OFF", "-DLLAMA_SUBPROCESS=OFF",
    "-DLLAMA_LLGUIDANCE=OFF", "-DGGML_CPU=ON", "-DGGML_NATIVE=OFF",
    "-DGGML_BACKEND_DL=OFF", "-DGGML_CPU_ALL_VARIANTS=OFF", "-DGGML_CCACHE=OFF",
    "-DGGML_SSE42=OFF", "-DGGML_AVX=OFF", "-DGGML_AVX2=OFF",
    "-DGGML_AVX_VNNI=OFF", "-DGGML_BMI2=OFF", "-DGGML_FMA=OFF", "-DGGML_F16C=OFF",
    "-DGGML_AVX512=OFF", "-DGGML_AVX512_VBMI=OFF", "-DGGML_AVX512_VNNI=OFF",
    "-DGGML_AVX512_BF16=OFF", "-DGGML_AMX_TILE=OFF", "-DGGML_AMX_INT8=OFF",
    "-DGGML_AMX_BF16=OFF", "-DGGML_OPENMP=OFF", "-DGGML_OPENMP_FETCH=OFF",
    "-DGGML_BLAS=OFF", "-DGGML_ACCELERATE=OFF", "-DGGML_LLAMAFILE=OFF",
    "-DGGML_CUDA=OFF", "-DGGML_HIP=OFF", "-DGGML_MUSA=OFF", "-DGGML_VULKAN=OFF",
    "-DGGML_METAL=OFF", "-DGGML_SYCL=OFF", "-DGGML_OPENCL=OFF", "-DGGML_WEBGPU=OFF",
    "-DGGML_RPC=OFF", "-DGGML_HEXAGON=OFF", "-DGGML_ZDNN=OFF",
    "-DGGML_VIRTGPU=OFF", "-DGGML_VIRTGPU_BACKEND=OFF",
]


def validate_target(target):
    target = Path(target).resolve()
    if target == REPO or REPO in target.parents:
        raise ValueError("APP_ROOT must be outside the source repository")
    for path in (target / "models", target / "ai/runtime", target / "ai/sources"):
        if path.exists() or path.is_symlink():
            raise ValueError(f"AI output already exists: {path}; use a fresh staging tree")
    return target


def fetch(artifact, path):
    path = Path(path)
    if path.exists():
        verify_file(path, artifact)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    try:
        subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--connect-timeout", "30",
                        "--proto", "=https", "--proto-redir", "=https",
                        "--output", str(partial), artifact["url"]], check=True)
        verify_file(partial, artifact)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def prepare(target):
    target = validate_target(target)
    if platform.machine() not in ("x86_64", "amd64") or sys.platform != "linux":
        raise ValueError("AI packaging currently supports Linux amd64 builders only")
    for tool in ("curl", "cmake", "c++", "make", "ldd"):
        if not shutil.which(tool):
            raise ValueError(f"missing builder dependency: {tool}; install build-essential cmake curl ca-certificates python3")
    package = json.loads((AI_DIR / "package.json").read_text())
    # Downloads/build tree are ephemeral and never created in the Git checkout.
    with tempfile.TemporaryDirectory(prefix="gravestone-ai-") as temporary:
        work = Path(temporary)
        model = fetch(package["model"], work / package["model"]["filename"])
        archive = fetch(package["runtime"], work / "llama.cpp.tar.gz")
        for document in package["documents"]:
            fetch(document, work / document["path"])
        source = work / ("llama.cpp-" + package["runtime"]["commit"])
        with tarfile.open(archive, "r:gz") as tar:
            # data filter rejects traversal and unsafe links on Python 3.11+.
            tar.extractall(work, filter="data")
        build = work / "build"
        configure = ["cmake", "-S", str(source), "-B", str(build), *CMAKE_FLAGS]
        # Do not inherit host ISA overrides or a surprise compiler/cache wrapper.
        env = os.environ.copy()
        for name in ("CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CC", "CXX", "CMAKE_TOOLCHAIN_FILE"):
            env.pop(name, None)
        subprocess.run(configure, env=env, check=True)
        subprocess.run(["cmake", "--build", str(build), "--target", "llama-server", "--parallel", "2"],
                       env=env, check=True)
        binary = build / "bin/llama-server"
        version = subprocess.check_output([str(binary), "--version"], text=True, stderr=subprocess.STDOUT)
        help_text = subprocess.check_output([str(binary), "--help"], text=True, stderr=subprocess.STDOUT)
        if "--no-webui" not in help_text or "--offline" not in help_text:
            raise ValueError("compiled server does not support required offline/no-webui flags")
        dependencies = subprocess.check_output(["ldd", str(binary)], text=True)
        if any(name in dependencies for name in ("libllama", "libggml", "libgomp", "libssl", "libcurl")):
            raise ValueError("unexpected shared AI/OpenMP/network dependency: " + dependencies)
        ai = target / "ai"
        (ai / "runtime").mkdir(parents=True)
        (ai / "sources").mkdir()
        (target / "models").mkdir()
        shutil.copy2(binary, ai / "runtime/llama-server")
        shutil.copy2(model, target / "models" / model.name)
        shutil.copy2(archive, ai / "sources/llama.cpp.tar.gz")
        shutil.copy2(build / "CMakeCache.txt", ai / "sources/CMakeCache.txt")
        for document in package["documents"]:
            destination = ai / document["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(work / document["path"], destination)
        shutil.copy2(AI_DIR / "package.json", ai / "package.json")
        if (AI_DIR / "README.md").exists():
            shutil.copy2(AI_DIR / "README.md", ai / "README.md")
        provenance = dict(schema_version=1, built_utc=datetime.now(timezone.utc).isoformat(),
                          inputs=package, cmake_flags=CMAKE_FLAGS, build_jobs=2,
                          compiler=subprocess.check_output(["c++", "--version"], text=True),
                          libc=subprocess.check_output(["ldd", "--version"], text=True),
                          runtime_version=version, runtime_dependencies=dependencies,
                          runtime_sha256=hashlib.file_digest(binary.open("rb"), "sha256").hexdigest())
        (ai / "BUILD_PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")
        verify_file(target / "models" / model.name, package["model"])
        print(f"Installed verified offline AI package into {target}")


def main():
    if len(sys.argv) != 2:
        print("Usage: scripts/prepare-ai.sh APP_ROOT (fresh staging root outside repository)", file=sys.stderr)
        return 2
    try:
        prepare(Path(sys.argv[1]))
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"AI packaging failed: {error}", file=sys.stderr)
        return 1
    return 0


def verify_file(path, artifact):
    """Reject truncation or altered bytes before extraction or installation."""
    path = Path(path)
    if path.stat().st_size != artifact["bytes"]:
        raise ValueError(f"size mismatch: {path}")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != artifact["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path}")


if __name__ == "__main__":
    sys.exit(main())
