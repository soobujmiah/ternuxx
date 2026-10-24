# Native graphics and software-fallback recheck — 2026-10-24

Phase: `P6`

## Evidence

The initial snapshot, loader-order correction, artifact provenance, and fresh-state package extraction recheck are recorded below.

### Initial snapshot before the loader-order fix

The following results preserve the first run and its then-current environment. The Vulkan failure was later corrected; it is historical evidence, not the current Vulkan status.

Direct bounded verification through the shared `graphics.provider.verify` operation on the current Native Termux device, Android 16 / API 36, Adreno 825, active display `:1`. No package was installed or upgraded, no persistent backend setting was changed, and the active desktop/services remained running.

| Operation | Result | Interpretation |
|---|---|---|
| `./tx mng graphics verify native opengl :1` | `rendered`; renderer `Adreno (TM) 825`; score `670`; exit 0 | A bounded off-screen glmark2 OpenGL draw passed through the currently selected private KGSL/Freedreno candidate. This is one synthetic graphics workload, not application-wide support or an inference claim. |
| `./tx mng graphics verify native gles :1` | GLES 3.2; `Adreno (TM) 825`; shader draw `643` frames over 5 seconds at 1280×720; exit 0 | A surfaceless EGL pbuffer shader draw completed with `glFinish` per frame. This is off-screen throughput, not presented UI frame rate. |
| `./tx mng graphics verify native vulkan :1` | `unavailable`; no device, exit 1, no draw attempted | Exact diagnostic: `CANNOT LINK EXECUTABLE ... cannot locate symbol "_ZNSt6__ndk113__hash_memoryEPKvm" ...`. The Vulkan API is unavailable in this observed process/package combination. |
| OpenGL verification with private temporary state and `MESA_LOADER_DRIVER_OVERRIDE=zink` | Primary exited 1; explicit `llvmpipe (LLVM 21.1.8, 128 bits)` fallback rendered, score `111`; status `fallback-rendered` | Failure injection exercised the real bounded fallback path without changing persistent Ternuxx state. The temporary state directory was removed after the check. |
| OpenGL verification with private temporary state and software rendering forced | `llvmpipe` rendered, score `111`; `accelerated=false` | Confirms the CPU software-rendering path is available on this profile. It does not establish a model-inference CPU runtime. |

The GL/GLES candidate reports Mesa `26.3.0-devel (git-98f3d6229d)`. The installed package database separately reports `mesa-vulkan-icd-freedreno 26.2.4`, `vulkan-tools 1.4.365`, and `libc++ 30`. The experimental candidate's original provenance and missing clean-install reproduction are documented in the [graphics qualification record](2026-10-20-workstation-qualification-execution.md). Package-index candidates are not applied by these checks.

In this initial snapshot, the bounded Vulkan verifier returned one capped linker/error line with an unavailable result. `tests/test_graphics_management.py` retains coverage for that failure path and confirms that no draw is attempted after enumeration fails. The loader-order follow-up below records the corrected environment and successful draw.

## Current verified status and remaining limits

After the loader-order fix below, the shared Vulkan operation rendered a bounded on-screen `vkcube` workload on the Adreno 825. The earlier linker failure remains useful regression evidence, but Vulkan is not currently unavailable in the corrected environment. OpenGL and GLES bounded draws and explicit `llvmpipe` fallback also passed. At this P6 checkpoint, the experimental acceleration candidate still lacked reproducible clean-install distribution and provenance review; ordinary application-specific GPU behavior, inference acceleration, sustained stability, and NPU execution were not established. P6 is now complete; current remaining acceleration qualification is tracked in P12 and the current repository audit.

## Recheck acceptance

- The shared service records bounded OpenGL, GLES, Vulkan, and CPU software-fallback outcomes from the current Native device.
- The pre-fix Vulkan linker error is visible as historical evidence, and the corrected loader order is verified by an on-screen Adreno 825 draw.
- Fallback verification used private ephemeral state and left the active desktop, audio, and persistent graphics selection unchanged.
- Current behavior, evidence class, and remaining clean-install/workload limits are separated from the initial snapshot.


## Follow-up: Vulkan loader environment and source provenance — 2026-10-24

The previous failure was reproducible with the exact inherited launch environment. `LD_LIBRARY_PATH` contained the Codex CLI's private `bin` directory and its `libc++_shared.so`. Putting the selected Mesa candidate library first but leaving that tool directory before the Termux runtime library caused `vulkaninfo` to fail linking `_ZNSt6__ndk113__hash_memoryEPKvm`. In a controlled read-only comparison, the same candidate ICD succeeded when `$PREFIX/lib` was placed before the inherited tool path and enumerated the Adreno 825 Turnip device.

`lib/graphics_manager.py` now constructs candidate environments in this order: selected Mesa candidate libraries, the active Termux `$PREFIX/lib`, then inherited loader paths. The change preserves inherited paths while ensuring the current Termux runtime's C++ ABI wins over unrelated launcher libraries. A regression test covers this ordering.

After that change, the shared management operation `DISPLAY=:1 ./tx mng graphics verify native vulkan :1` returned `status=rendered`, enumerated `Adreno (TM) 825`, and completed a bounded 120-frame `vkcube` draw on the same device (enumeration exit 0, draw exit 0). This is a direct on-screen Vulkan workload on the active X11 display; it does not establish other applications, inference, sustained stability, or release readiness. No package or persistent selection changed, and the active desktop stayed running. A repeat after the loader fix also rendered the existing OpenGL workload at score `643` and the GLES pbuffer workload at `709` frames / `141.69` FPS over five seconds (Adreno 825, 1280×720). The earlier GLES run was `643` frames / five seconds. These are independent bounded runs, not a controlled thermal or comparative benchmark. The graphics test module passes 17 tests.

### Artifact provenance

The exact source PR is [lfdevs/termux-packages#25](https://github.com/lfdevs/termux-packages/pull/25), still marked Draft on 2026-10-24. Its [GitHub Actions run](https://github.com/lfdevs/termux-packages/actions/runs/36377469447) reports Success for source commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e` and lists artifact `debs-aarch64-0219ff84b372c9d38aad4e40f448c20ec3d1588e` with GitHub artifact SHA-256 `8493482210f9cc625f4fadb95e53cb417650c31f6e2b5a0d8725a2ef3c82ff5e`. The retained package checksum list independently validates all five extracted `.deb` files; its file SHA-256 is `50211fa943b8d41fb6e750f921488e9250a8e2c25694635e34294160a4ea1d8f`. The retained extracted tar SHA-256 is `8b8f3dfccefd4dc3dba65a0099dc9c3efdfd6afc7f9679f3b92a2b8b781a9353`; it is a locally retained tar payload, not the GitHub artifact container whose digest appears on the run page.

This improves traceability but does not create a stable distribution URL or a clean-install installer. The PR remains a community draft and is not an official Termux release. The experimental candidate is qualified only for bounded workloads on the recorded device.


## Repository regression status after the loader fix

`env -u LD_LIBRARY_PATH bash scripts/repo_test.sh` passed all 658 tests in 92.302 seconds. The focused graphics suite passed all 17 tests, CLI help contract passed, `docs/testing/FEATURE-MATRIX.yaml` parsed successfully, document inventory/link audit reported zero broken local links, and `git diff --check` passed. The suite's retired-route checks continue to return `feature_removed`; the active Native desktop was not stopped.

### Fresh-state extraction from retained package set — 2026-10-24

All five retained Mesa `.deb` files passed `sha256sum -c` against the recorded package checksum list. They were extracted with `dpkg-deb -x` into a new private temporary candidate tree under `$HOME/.cache`; the existing extracted provider tree and persistent selection were not used. `graphics_manager.configure_native("kgsl-freedreno", ...)` validated the pinned driver files and generated a temporary selection. The shared `graphics_manager.verify` implementation then returned:

| API/workload | Result | Observed output |
|---|---|---|
| OpenGL off-screen glmark2 | `rendered`, exit 0 | Adreno (TM) 825; score 639 |
| GLES pbuffer shader draw | `rendered`, exit 0 | Adreno (TM) 825; 626 frames / 125.02 FPS over 5 seconds at 1280×720 |
| Vulkan X11 `vkcube` | `rendered`, enumeration/draw exit 0 | Adreno (TM) 825 selected; 120 frames on display `:1` |

The temporary tree, including its selection file, was removed at scope exit. No package was installed, the package database and persistent graphics selection were unchanged, and a post-run `tx status --json` still reported the Native desktop, X11, XFCE, supervisor, and audio owner live. The PRoot packages and state remained absent.

This verifies fresh extraction and workload reproduction from the locally retained, checksummed package set. It does not verify download/install from a stable public URL, a clean Termux package database, or an official Termux release. The candidate remains experimental until provenance and a reproducible distribution/install path are resolved.

### GitHub artifact availability recheck — 2026-10-24

The GitHub Actions API for run `36377469447` was queried read-only. It confirms successful source commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`; the aarch64 artifact remains unexpired and is listed with expiration `2026-12-27T04:23:02Z`. Its artifact ID/download URL is a temporary Actions distribution mechanism, not a stable release URL. The local bundle and five package hashes match the profile/checksum list, but a fresh Ternuxx install still has no supported acquisition and installation workflow. P12 therefore retains the clean-install provenance gate; the date-based artifact's current availability must not be described as durable distribution.
