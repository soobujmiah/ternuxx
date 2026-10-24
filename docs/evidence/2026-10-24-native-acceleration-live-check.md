# Native Termux acceleration live check — 2026-10-24

Phase: `P12`

**Snapshot note:** This was the initial bounded discovery check, before Ternuxx's pinned HTP runtime was installed and exercised. Its NPU “unavailable” finding is true only for this check and is superseded by the later [HTP runtime integrity follow-up](2026-10-24-p12-htp-runtime-integrity-followup.md), [complete offload gate](2026-10-24-p12-complete-offload-gate.md), and the current [NPU status](../testing/NPU-ACCELERATION.md). The GPU package/install statements below are likewise time-bound to this check.

## Evidence

This is a fresh bounded check on the current Native Termux session. It separates graphics rendering from model inference; an accelerated renderer does not imply an accelerated inference backend.

## CPU inference

`printf 'Say hello in three words.' | ./tx ai run --max-tokens 8` completed successfully. The result reported backend `CPU`, `gpu_layers=0`, model `qwen3-0.6b-q4_0`, exit 0, and output `Hello!`. The run path verifies the pinned model file's size, permissions, and SHA-256 before execution. The lightweight status path still reports `present-unverified`; it does not hash the 429 MB model on every status request. This smoke does not add a timing, thermal, or sustained-performance measurement.

Three bounded CPU smokes used owner-provided GGUFs from shared storage through Native Termux `llama-cli` 0.7.0, each with four CPU threads, context 256, and an eight-token cap. All returned the requested text; the final Qwen Q4_K_M command exited 0. Reported prompt/generation rates were Qwen2.5 1.5B Q4_0 24.0/18.0, Qwen2.5 1.5B Q4_K_M 25.5/18.1, and Llama 3.2 3B Q4_K_M 12.1/9.4 tokens/s. These short one-off smokes verify CPU compatibility for these three files; they are not repeatable benchmarks or sustained-performance measurements. The fourth available Qwen 1.5B/Q4_K_M-style file was Qwen Q4_K_M above; no test on the QNN image-generation archive was run. Ternuxx's managed workflow still only accepts its pinned, private HOME model.

## GPU graphics

The active experimental Native Mesa/Freedreno candidate rendered on Adreno 825 in three independent bounded checks:

| API/workload | Result |
|---|---|
| OpenGL `glmark2` off-screen | Rendered, Adreno 825, score 768, exit 0 |
| GLES shader pbuffer, 1280×720, 5 seconds | Rendered, 1,141 frames, 228.03 frames/second, Adreno 825, exit 0 |
| Vulkan `vkcube`, X11 display `:1` | Rendered 120 frames; enumerated and selected device both Adreno 825; exit 0 |

These are graphics workloads only. They do not prove GPU model inference, general app compatibility, sustained thermals, or a supported clean installation path. The selected Mesa artifact is still an experimental community draft candidate.

## GPU inference

The installed Termux `llama-cpp` 0.7.0 package is built with `GGML_VULKAN=ON`, `GGML_OPENCL=ON`, and dynamic backend loading in the [official Termux package recipe](https://github.com/termux/termux-packages/blob/master/packages/llama-cpp/build.sh). Termux publishes each backend as a version-matched package, so a separate Ternuxx source build and custom GitHub release artifact are not needed; upstream also documents a direct [Native Termux llama.cpp build](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md#build-cli-on-android-using-termux) if the package route changes. The official prebuilt arm64 `.deb` was downloaded to a private scratch directory and matched package-index SHA-256 `df315cf92013d10611705e08c56a20a1336b5be58fb55526137702b29ff36eb1`; its only payload is `libggml-vulkan.so` (26,528,440 bytes). It was extracted for testing, not installed into `$PREFIX`.

The stock Termux ICD rejected Adreno 825 (`gpu_id=6830`, `VK_ERROR_INCOMPATIBLE_DRIVER`). Reusing the already selected experimental Mesa/Freedreno candidate and its isolated ICD manifest made the same backend enumerate `Vulkan0: Adreno (TM) 825`. With the official backend library loaded from a temporary test prefix and the selected candidate environment, each owner-provided model returned the requested text and logged full GPU delegation:

| GGUF workload | GPU offload | Prompt / generation rate |
|---|---:|---:|
| Qwen2.5 1.5B Q4_0 | 29/29 layers | 51.9 / 23.7 tokens/s |
| Qwen2.5 1.5B Q4_K_M | 29/29 layers | 43.4 / 20.9 tokens/s |
| Llama 3.2 3B Q4_K_M | 29/29 layers | 22.9 / 13.3 tokens/s |

The Ternuxx inference API path was also exercised with the pinned Qwen3 0.6B model through that temporary prefix: it selected Vulkan0, returned `Hello!`, recorded `gpu_layers=29`, and exited 0 in 2.039 seconds. The short one-off timings are not a comparative benchmark or sustained-performance result. The downloaded backend was not installed into the live Termux prefix, so ordinary `tx ai devices` still needs the optional Termux package installation before it can discover the backend. The current sandbox cannot write to `$PREFIX`; a read-only `tx ai runtime preview vulkan` is available before the owner applies the package transaction. No public custom build artifact was published because the Termux package repository already supplies the reusable version-matched binary.

The matching OpenCL backend package was also downloaded and checksum-verified (`5be19dd135001e3fcd166e3aa0753b9c9d84f1bc900c03951f7208f61c3815dc`). Loading its plugin into the installed `llama-cli` returned `platform IDs not available` and no devices, so OpenCL inference was not run. A bounded current Termux package-index search found Vulkan and OpenCL backend packages but no QNN, SNPE, or Hexagon runtime package.

## NPU

The bounded Native probe saw Android vendor libraries `libQnnHtp.so`, `libcdsprpc.so`, `libadsprpc.so`, and `libSNPE.so`. It saw no candidate FastRPC device nodes and found only `llama-cli`; no QNN or SNPE runner was available on PATH. `/dev` enumeration was permission-denied in this workspace, so node absence was unknown. The owner-provided QNN image-model archive contained MNN components and compiled QNN `.bin` artifacts; three supplied 512×512 PNGs had adjacent UNet/decoder logs reporting SM8735 detection and successful graph execution. These were prior user-supplied run artifacts, not a reproducible Ternuxx run, and did not establish runtime availability, model correctness, or performance. No NPU workload was run in this check, and its bounded Termux package-index search found no QNN/SNPE/Hexagon runner candidate. At the time of this check, NPU inference had not been integrated or qualified; later implementation evidence is linked in the snapshot note above.

## Outcome

At this snapshot, Native CPU inference worked for the pinned bounded smoke and one owner-provided Qwen2.5 Q4_0 smoke. Experimental Native GPU graphics worked for the three named rendering checks. GPU inference was not enabled or verified, though a Termux Vulkan backend package candidate was available for a Termux package transaction that this workspace could not apply. Prior owner-provided QNN logs and images indicated successful graph calls on SM8735, but Ternuxx had no NPU runtime integration and this check could not reproduce that workload. No package was installed, no persistent graphics setting changed, and no Termux desktop, supervisor, or service was stopped.


## Upstream Android Snapdragon accelerator artifact probe

On 2026-10-24, downloaded the official `ggml-org/llama.cpp` `b11849` Android Snapdragon release asset. GitHub release API digest matched the downloaded archive SHA-256 `2d0f1a989a8f0c4329839c3bb85b6fb70edb03e0b017fee0be4cf55b7ece8f6c`. Its `llama-cli --version` reported `0.7.0-dev (build 11849, commit 0ae0e1976)`. With artifact-local libraries and the observed Termux/vendor library paths, `--list-devices` reported no devices: OpenCL has no platform, and the Hexagon loader cannot resolve `libbinder_ndk.so` while opening `/vendor/lib64/libcdsprpc.so` in the app namespace. The release archive is preserved under `$HOME/.local/share/ternuxx/artifacts/llama.cpp-snapdragon-b11849/`; it was not installed into `$PREFIX` and no model inference was attempted. This does not qualify the NPU route; see [NPU feasibility](../testing/NPU-ACCELERATION.md).

## Follow-up: install the version-matched Vulkan backend and run live workloads

After reviewing `tx ai runtime preview vulkan`, the exact Native Termux transaction showed one new package, `llama-cpp-backend-vulkan` 0.7.0, with no removals or upgrades. The configured Termux main mirror supplied the package; `apt-get install -y llama-cpp-backend-vulkan` installed only that package. `dpkg-query` reports both `llama-cpp` and its Vulkan backend at 0.7.0. The read-only `tx ai devices` operation now reports `Vulkan0: Adreno (TM) 825`.

A live `printf 'Say hello in three words.\\n' | tx ai run --backend vulkan --device Vulkan0 --max-tokens 8` returned `Hello!`, exit 0, and verified 29/29 model layers offloaded to Vulkan in 2.105 seconds. The Ternuxx path supplied the selected experimental Mesa/Freedreno ICD and loader environment; no global loader setting changed.

The owner-authorized `/sdcard/LAI/models` directory contains three direct regular GGUF files. Each was run once with the installed Termux `llama-cli` 0.7.0, the validated Ternuxx GPU environment, four CPU threads, context 256, an eight-token cap, deterministic temperature/seed, and a 180-second process bound. All returned exit 0 and explicit 29/29 GPU-layer offload:

| Model | Result | Prompt / generation rate |
|---|---|---|
| `qwen2.5-1.5b-instruct-q4-0.gguf` | `Hello world.` | 58.0 / 22.9 tokens/s |
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | `Hello there!` | 39.1 / 20.6 tokens/s |
| `llama-3.2-3b-instruct-q4_k_m.gguf` | `Hello there!` | 18.4 / 13.0 tokens/s |

These are single short smoke runs, not CPU/GPU comparisons or sustained thermal/memory qualifications. They establish working Native GPU inference on this device and these models with the installed backend plus the selected experimental ICD. The ICD remains an experimental private candidate; a clean-install/release path, broader correctness, longer memory and thermal testing, OpenCL execution, and NPU inference remain open.


## P12 follow-up: Ternuxx-owned Native HTP integration and repeat check

The earlier NPU findings above are the initial probe snapshot and are superseded by this follow-up. Ternuxx now owns a pinned, private-cache `llama.cpp` Snapdragon runtime path in `lib/npu_inference.py`, exposed through the shared management service and CLI/TUI/Web/GTK. The runtime is the official MIT-licensed `b11849` release asset `llama-b11849-bin-android-arm64-snapdragon.tar.gz`; SHA-256 `2d0f1a989a8f0c4329839c3bb85b6fb70edb03e0b017fee0be4cf55b7ece8f6c`. The installer retains only the required CLI, shared objects, and license under `$HOME/.local/share/ternuxx/artifacts/`; it validates archive paths, member types, size, digest, SoC, and a fresh exact preview. It does not copy or patch Android system/vendor libraries or alter global loader configuration.

Live `tx ai npu status --json` reports SM8735, HTP0, release `b11849`, `available=true`, and `silent_fallback=false`. A controlled CLI comparison used the same pinned Qwen3 0.6B Q4_0 model, exact prompt `2 + 2? Reply with one digit.`, and an eight-token limit. Three CPU runs returned `2 + 2 = 4.` in 1.727, 1.704, and 2.002 seconds (`gpu_layers=0`). Three HTP runs returned the same answer in 4.241, 4.087, and 4.265 seconds; every run reported `npu_layers=29`, `total_layers=29`, `npu_model_buffer_mib=319.96`, backend `Hexagon HTP`, device `HTP0`, and `silent_fallback=false`. This directly verifies workload correctness and full HTP delegation for the named model and prompt, while also showing the HTP route is slower than CPU in this test. It is not a general benchmark.

Raw readable sysfs thermal zones had a maximum reported value of 51.7 C before and 62.9 C after the six short runs. These zones were not identified as CPU, GPU, or battery sensors, so the values are recorded without assigning a component. No longer stress run was made after this rise. Sustained thermals, memory pressure under competing workloads, broader operator/model coverage, clean-device runtime acquisition, and release qualification remain open. Earlier bounded cancellation/restart evidence remains: the HTP process group received SIGINT, exited 130 after session cleanup, and a subsequent known-answer run passed.

Focused tests after CLI/TUI/Web/GTK integration passed 148 tests across the four client/bridge/UI/HTTP suites. The GTK management client was rebuilt and installed; its recorded source C hash `7f98b845f6c2ce41a5e00a5e65c817c0098b46343a0e581b725e86b08a9a2183`, bridge hash `c91546a8962d8aa4f312b7848cd5e4095b652fab9a99a9cc190222080441b6f1`, and binary hash `9f954d92a54d7cba1d44d3031dca59d1804b58c2fa56b114cbb18acc13440b42` match the installed identity record. This is source/build parity evidence; it does not claim a separately human-operated GTK visual acceptance run. Native XFCE remained running on `:1` throughout.

The `tx ai npu runtime preview` CLI command was rechecked after its parser was corrected to accept the documented `preview` action; it now returns a read-only exact plan (`plan_id` `f158a2c092d923d687e08350`, `already_installed=true`, `network_required=false`, `runtime_state=ready`). The CLI help contract exposed by `tx help ai` matches that command and the `cpu|vulkan|npu` backend list. The combined `bash scripts/repo_test.sh` run passed all 1,000 Python tests plus the CLI help/preview contract. `scripts/repo_test.sh` invokes the shell-level CLI contract after Python discovery so the top-level regression command verifies both suites.

### Isolated HTP runtime installation replay

A fresh isolated install replay used a temporary state directory under HOME and a private copy of the retained archive. The source archive digest matched the pinned SHA-256. A read-only preview reported `already_installed=false` and `network_required=false`; applying its exact plan with `INSTALL` extracted the pinned CLI/shared objects/license and wrote the runtime manifest. A live runtime device probe then reported `available=true`, `HTP0`, and `SM8735`. The temporary state was removed automatically after the check. This verifies fresh extraction and manifest validation from the cached exact artifact; it does not verify downloading the artifact on an empty cache or clean Termux installation. Raw readable thermal-zone max before/after this extraction was 53.7 C / 55.7 C, without assigning those zones to a component; the device battery sensor stayed at 42.0 C and 68% charge, unplugged.
