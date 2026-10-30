# Offline search-term expansion package

This is an optional **local librarian**, not a source of survival instructions.
The model proposes search terms; the application retrieves attributed publisher
originals. Model suggestions can be wrong. Documents, maps, ordinary keyword
search and application readiness must remain usable if AI is absent, loading,
out of memory, incompatible, slow, or returns invalid JSON.

## Pinned inputs and redistribution

`package.json` records official HTTPS URLs, immutable revisions, exact byte sizes
and SHA-256 digests. Downloads fail closed on any mismatch:

- Qwen's official `Qwen/Qwen3-0.6B-GGUF`, revision
  `23749fefcc72300e3a2ad315e1317431b06b590a`, `Qwen3-0.6B-Q8_0.gguf`,
  **639446688 bytes**, SHA-256
  `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.
  Apache-2.0 license and original model card are archived in `licenses/` and
  `upstream/`. The model card contains upstream online examples; these are not
  network requirements of the shipped runtime.
- llama.cpp release **b12001**, source commit
  `eb4e244be77a906a183cd4a00fd51d9ad3200955`, official codeload source archive,
  **38818990 bytes**, SHA-256
  `bd2f111a77f617614fd58e1202bed7d0249d3ea8949ad8a1a183915d612f0aad`.
  Runtime is MIT-licensed. Its complete pinned source archive is installed in
  `ai/sources/llama.cpp.tar.gz`, retaining bundled third-party sources/notices.
  Do not remove those notices when redistributing the executable.

The Git tree holds metadata, build code, documentation and small original license
snapshots only. **Never commit model weights, compiled binaries or build trees.**
The parent `.gitignore` excludes `models/*.gguf`, `ai/runtime/`, `ai/sources/`.
The packager additionally rejects destinations inside the source checkout.

## Build integration (network at build time only)

Inside the existing Debian **bookworm amd64** build container, install:

```sh
apt-get install -y --no-install-recommends build-essential cmake curl ca-certificates python3
```

`pkg-config` is harmless but not required for this CPU-only configuration. No
CUDA, GPU driver, OpenMP, SSL development package, Node, Rust, external model
client, privileged operation, or root access is needed by the packager itself.
Python 3.11 with tar extraction filters is required (current bookworm security
updates provide them).

Run after staging the app and before `lb config`/`lb build`:

```sh
/src/scripts/prepare-ai.sh /build/work/config/includes.chroot/opt/gravestone
```

The target app root can already contain app/content/AI metadata, but `models/`,
`ai/runtime/` and `ai/sources/` must not exist. Reuse a **fresh** staging tree on
failure rather than trusting partial installation. Downloads and compilation
use `tempfile` outside Git; set `TMPDIR` to a builder volume with free space
rather than a small RAM-backed `/tmp`. Allow **3 GiB** temporary disk space and
at least **3 GiB available builder RAM** for the two-job C++ build. These are
planning allowances, not worst-case guarantees across all compilers.

The complete exact CMake flag list is `CMAKE_FLAGS` in `package.py` and is copied
into output provenance. Important constraints:

- Release, `BUILD_SHARED_LIBS=OFF`, static libstdc++/libgcc; glibc remains dynamic.
  **Build inside bookworm**, not a newer host, to preserve Debian 12's glibc
  baseline. An Ubuntu prebuilt executable is not shipped.
- `-march=x86-64 -mtune=generic`; `GGML_NATIVE`, SSE4.2, AVX, AVX2, AVX-VNNI,
  AVX512, BMI2, FMA, F16C, AMX and CPU-variant dispatch disabled. Baseline x86-64
  includes SSE2. No ARM/Apple Silicon or 32-bit support is claimed.
- CPU backend only, no BLAS/llamafile/OpenMP or GPU/RPC backends. OpenSSL,
  legacy CURL option, subprocess tools, Web UI download/build and llama-connect
  disabled. Only `llama-server` is built, with **two concurrent build jobs**.
- The packager actually executes `--version` and `--help`, checks offline/Web UI
  flags, and rejects shared llama/ggml/OpenMP/SSL/CURL dependencies with `ldd`.

Installed layout beneath the target root:

```text
ai/runtime/llama-server
models/Qwen3-0.6B-Q8_0.gguf
ai/package.json
ai/BUILD_PROVENANCE.json
ai/sources/llama.cpp.tar.gz
ai/sources/CMakeCache.txt
ai/licenses/Qwen-LICENSE
ai/licenses/llama.cpp-LICENSE
ai/upstream/Qwen-README.md
```

Provenance records compiler, builder libc, linked dependencies, runtime version,
compiled executable SHA-256, all source/model/document pins and exact flags.
It is a rebuild recipe and integrity record, not a promise of bitwise-identical
binaries from changing Debian packages.

## Runtime and failure behavior

The parent live-build hook enables `gravestone-ai.service`. It starts after
`live-config.service` as `user`, binds **127.0.0.1:8767** only and explicitly uses
CPU mode, context **2048 tokens**, **2 generation and prompt threads**, **1 slot**,
and **128-token server prediction default**. Web UI and online downloads are
disabled. `NoNewPrivileges`, read-only system/home, private temporary/device
namespaces, dropped capabilities and loopback-only systemd IP policy restrict
it. The IP policy depends on systemd/kernel cgroup-BPF support; the explicit
loopback binding still applies if that optional enforcement is unavailable.
Do not add `PrivateNetwork=yes`: the app must reach the same loopback namespace.

No GPU or AVX is required by the packaged build. Plan **4 GiB total machine RAM**
for the live desktop, and **2 GiB available RAM before enabling AI**. The weights
alone are 639446688 bytes; KV cache, compute buffers, allocator and OS/page-cache
usage are additional and depend on context/build. This is a conservative target,
not a measured hard minimum or a guarantee that every 4 GiB machine works. A
2 GiB graphical VM is **not** a supported AI acceptance target. Runtime uses two
CPU threads but HTTP/control helper threads also exist. Older baseline CPUs can
be much slower than modern AVX-enabled verification binaries. Do not promise
interactive latency; a bounded application timeout must fall back to keywords.

The backend POSTs to `/v1/chat/completions` with
`response_format={"type":"json_object"}`,
`chat_template_kwargs={"enable_thinking":false}` and `max_tokens=128` in production (`96` in the direct protocol probe). The template
is embedded in the pinned GGUF; no template download is needed. Only short
search terms may be accepted by the app, never generated safety advice.

Missing files skip this optional service. Startup/loader errors or OOM are
visible in `journalctl -b -u gravestone-ai.service`; it does not continuously
restart or gate app startup. A successful `/health` only means model readiness,
not correctness of suggestions. Connection failure, timeout, malformed JSON or
unsupported responses must leave ordinary keyword search usable.

## Verification

Lightweight tests (no network/model required):

```sh
python3 -m unittest discover -s tests -p test_ai_package.py -v
```

The real-inference test is deliberately skipped unless actual artifact paths
are supplied. It checks the full model size/hash, starts an actual CPU server
on a temporary loopback port, waits for `/health`, sends the exact JSON-mode
request, validates returned terms and terminates only its own child process:

```sh
uptime; free -m
GRAVESTONE_AI_SERVER=/path/to/staged-app/ai/runtime/llama-server \
GRAVESTONE_AI_MODEL=/path/to/staged-app/models/Qwen3-0.6B-Q8_0.gguf \
GRAVESTONE_AI_EVIDENCE=/tmp/gravestone-real-inference.json \
python3 -m unittest discover -s tests -p test_ai_package.py -v
```

Evidence must be outside Git. This is real inference, not a model stub. A local
upstream prebuilt can separately validate model/protocol compatibility, but does
**not** establish the packaged baseline binary's compatibility or performance.
Require the source-built bookworm binary and an actual image boot test before
claiming the shipped live image's AI works.
