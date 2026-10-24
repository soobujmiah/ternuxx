# Research & Evidence

> **Dated research record.** This file contains historical measurements and source reviews. The owner reauthorized optional Debian PRoot support on 2026-10-24 after a temporary Native-only decision. Use [current phase status](PHASE-STATUS.md), [PRoot restoration evidence](evidence/2026-10-24-p11-proot-source-restoration-audit.md), and the [capability matrix](testing/FEATURE-MATRIX.yaml) for current implementation and qualification claims.

Dated source links and evidence classifications for Ternuxx design decisions.

> **Research snapshot.** This research began on 2026-10-17 and includes former provider proposals and dated device observations. Native Termux remains the host/control plane, and Debian PRoot is an optional workload provider under P11. Older observations are not proof of current runtime behavior; use the current device matrix, capability matrix, and phase status for current claims.

---

## Source Hierarchy (per owner brief)

1. **Primary:** Official upstream documentation
2. **Secondary:** Termux package metadata (pkg search results)
3. **Tertiary:** Read-only reference from existing ternux project
4. **Not used:** Forum posts, unverified claims

Each claim below includes: source URL, access date, and confidence level.

---

## 1. Termux:X11 Setup

**Accessed:** 2026-10-17
**Confidence:** verified

The upstream guide documents:
- The Android X server app (`termux-x11`)
- The companion `termux-x11` Termux package
- The `x11-repo` repository that provides it
- Launch command: `termux-x11 :1 -xstartup "dbus-launch --exit-with-session xfce4-session"`
- Fallback without `dbus-launch` for some setups

**Evidence classification:** verified — observed in upstream README.

---

## 2. PRoot-Distro Storage Layout

**Source:** https://github.com/termux/proot-distro
**Accessed:** 2026-10-17
**Confidence:** verified

PRoot rootfs lives under the Termux PREFIX proot-distro tree. Earlier audit text called this an external Ternux deployment path; that statement is superseded by the 2026-10-20 owner direction and direct Ternuxx integration. The existing Debian rootfs remains preserved and is accessed by bounded, typed Ternuxx operations.

**Evidence classification:** verified — confirmed by inspecting `proot-distro list` output and directory structure.

---

## 3. GPU Device Nodes

**Observation date:** 2026-10-17
**Confidence:** verified (from adb session)

- `/dev/kgsl-3d0` — present (Adreno kernel interface)
- `/dev/dri/renderD128` — present
- GPU model: **Adreno 825** (from `cat /sys/class/kgsl/kgsl-3d0/gpu_model`)
- SoC: **SM8735** (Snapdragon platform)
- Device: **[redacted device serial]** (codename: onyx)

**Evidence classification:** verified — direct device read.

**Important distinction:** KGSL present in ADB context does NOT automatically mean it's accessible from within the Termux app sandbox. Native-Termux GPU path must be validated separately from PRoot-Ternux path.

---

## 4. Mesa Zink / Turnip — evidence boundary

The device has Adreno 825 / SM8735 and exposes KGSL/DRM nodes in the observed ADB context. The existing Ternux project source configures a separate Zink/Turnip route inside Debian PRoot; details and lifecycle limits are recorded in §9 and [PRoot GPU reuse](PROOT-GPU.md).

The presence of `libvulkan_freedreno.so`, a Vulkan loader response, or a Zink-named shader-cache directory does not prove that a current GUI process renders on the Adreno GPU. The strongest runtime check for the OpenGL desktop path is the live guest renderer string from `glxinfo -B` while the relevant display session is active. `llvmpipe` is software rendering.

Native Termux and Debian PRoot load different userspace Mesa packages. Therefore the native Termux Turnip rejection in §8 does not by itself invalidate the PRoot route, and the PRoot route does not establish that native Termux graphics work.

**Evidence classification:** Ternux PRoot setup is source-verified and documented. A live Debian 13 PRoot renderer check on active native X11 display `:1` selected Zink/Turnip with `Accelerated: yes`; the Ternux-owned `:0` desktop and workload performance remain unverified. Native Turnip rejection is directly observed for the recorded package/process.

## 5. Available Termux Packages (Read-Only Survey)

**Date:** 2026-10-17
**Source:** `pkg search` against grimler.se mirror + termux-x11 repo
**Confidence:** verified (package index queried, not installed)

| Package | Repo | Status |
|---------|------|--------|
| xfce4-session | termux-x11 | Available |
| xfce4-panel | termux-x11 | Available |
| xfwm4 | termux-x11 | Available |
| thunar | termux-x11 | Available |
| xfce4-terminal | termux-x11 | Available |
| chromium | termux-x11 | Available |
| alacritty | termux-x11 | Available |
| kitty | termux-x11 | Available |
| pulseaudio | termux-stable | Already installed |
| dbus-x11 | termux-stable | Already installed |
| vulkaninfo | termux-stable | Already installed |
| glxinfo | termux-stable | NOT available |
| mesa-vulkan-icd-freedreno | termux-stable | Already installed (v26.2.4) |
| virglrenderer-android | termux-stable | Already installed |
| termux-x11 | termux-x11 | Already installed |
| termux-api | termux-stable | Already installed (v0.53.0) |
| termux-share | termux-api | Available (`/usr/bin/termux-share`) |

**Evidence classification:** historical read-only package survey. Package indexes change; re-query before using these names in an installation command.

---

## 6. TUR (Termux User Repository)

**Source:** https://github.com/termux-user-repository/tur
**Accessed:** 2026-10-17
**Confidence:** observed

TUR is configured in `/etc/apt/sources.list.d/tur.list`:
```
deb https://tur.kcubeterm.com tur-packages tur tur-on-device tur-continuous
```

**Decision:** Do NOT enable TUR by default. Verify package provenance before recommending any TUR package. Blender is available via TUR (`blender/tur-packages 1:3.6.23-13`).

**Evidence classification:** observed — confirmed from sources.list.d.

---

## 7. Existing Ternux Architecture (Read-Only Reference)

**Source:** https://github.com/soobujmiah/ternux
**Accessed:** 2026-10-17
**Confidence:** observed

Read-only inspection of:
- `bin/ternux` — CLI dispatch pattern (lazy-loaded lib modules)
- `lib/phases.sh` — 11-phase install with state tracking
- `lib/desktop.sh` — start/stop/restart lifecycle
- `install.sh` — standalone bootstrapper with remote fallback
- `docs/ARCHITECTURE.md` — PRoot+X11+Mesa stack diagram
- `docs/INSTALLATION.md` — requirements table

**Key patterns adopted for Ternuxx:**
- Same shebang: `#!/data/data/com.termux/files/usr/bin/bash`
- Same lazy-load module pattern (`_tnx_use()` → `_nt_use()`)
- Same command dispatch (`tnx_cmd_*` → `nt_cmd_*`)
- Same JSON output support (`--json` flag)
- Same version/help structure

**Evidence classification:** observed — read-only file inspection, no edits made.

---

## 8. Native Termux GPU test

**Observed:** 2026-10-17, on device `[redacted device serial]` / `onyx`, Android 16, Adreno 825 (SM8735). The read-only native Termux invocation of `vulkaninfo --summary` returned:

```text
TU: error: ../src/src/freedreno/vulkan/tu_device.cc:1686: device (chip_id = 44030000, gpu_id = 6830) is unsupported (VK_ERROR_INCOMPATIBLE_DRIVER)
ERROR: [Loader Message] Code 0 : setup_loader_term_phys_devs: Failed to detect any valid GPUs in the current config
```

At the time of the observation, `mesa-vulkan-icd-freedreno` was reported as Termux version `26.2.4`. This is evidence that the tested native ICD rejected the device. It is not a claim that every native Mesa build rejects it, or that all native graphics must use software rendering; a live native OpenGL renderer check was not available (`glxinfo` was absent).

**Classification:** directly observed native command output; package version reported by the native package survey. Recheck both when package versions change.

**Live OpenGL follow-up (2026-10-18):** After an APT simulation showed `mesa-demos` and its two dependencies (`glu`, `freeglut`) as three new packages, zero upgrades, and zero removals, those packages were installed in native Termux to obtain `glxinfo`. During the active native Termux:X11 `:1` session, `DISPLAY=:1 glxinfo -B` reported Mesa `llvmpipe (LLVM 21.1.8, 128 bits)` and `Accelerated: no`. Thus this native desktop is software-rendered; the earlier glxinfo-unavailable statement above is a historical snapshot. The native Vulkan rejection also remains. This result does not test the separate Ternux Debian PRoot Zink/Turnip route.

**Classification:** direct live native OpenGL output in the active `:1` display context. Renderer identification only; no performance or workload qualification.

## 9. Existing Ternux PRoot graphics path

**Reference project:** https://github.com/soobujmiah/ternux
**Local source inspected:** `/home/sbj/ternux-tools`, commit `ef65cb4` (`2026-10-17`)
**Relevant files:** `lib/phases.sh`, `lib/desktop.sh`, `docs/INSTALLATION.md`, `docs/MANUAL.md`, `docs/CONFIGURATION.md`

The launcher source for the Zink backend enters the configured PRoot-Distro guest with shared temporary storage; binds `/dev/kgsl-3d0` to guest `/dev/kgsl` and `/dev/dri`; sets `DISPLAY`, `MESA_LOADER_DRIVER_OVERRIDE=zink`, `GALLIUM_DRIVER=zink`, and other Mesa/Turnip variables; then starts XFCE. The installation guide describes Adreno 825 / Zink as a measured route. The manual identifies the live guest `glxinfo` renderer string as the runtime check and distinguishes Zink/Turnip from `llvmpipe`.

This source and its documentation support the conclusion that the **existing Ternux PRoot route is designed and documented for GPU acceleration**, independently from native Termux's packaged Turnip ICD. On 2026-10-18, a read-only `glxinfo -B` in Debian 13 PRoot on active display `:1`, with the documented KGSL/DRM bindings and Zink/Turnip environment, reported `zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))` and `Accelerated: yes`. This directly verifies renderer selection for that guest process. It did not run the existing Ternux-owned `:0` desktop or a representative application workload. A Zink cache directory or a successful Vulkan instance query alone is not proof that a current OpenGL process is using the Adreno GPU.

**Lifecycle risk observed in source:** Ternux `start` runs `~/x.sh`; the launcher and stop path manage Termux:X11/PulseAudio and clean shared socket paths. Its existing desktop lifecycle must therefore remain under Ternux's control. Ternuxx must not invoke Ternux cleanup, rewrite its launcher, or start a concurrent desktop on the same display without an explicit ownership-aware integration.

**Classification:** source behavior and documentation reviewed; live Debian PRoot renderer directly observed on Ternuxx display `:1`; exact Ternux-owned `:0` session and workload behavior remain unverified. See [P4 renderer evidence](evidence/P4-proot-gpu-renderer-2026-10-18.md).

## 10. Ternuxx scope and evidence limits

This section supersedes the 2026-10-17 audit snapshot. Ternuxx now verifies the selected Debian guest and hands off Native :1 display/audio plus Zink/Turnip settings without calling the separate Ternux CLI. Since this section's original snapshot, same-session terminal operation passed across CLI, authenticated Web API, TUI, and installed GTK/VTE; receipt-bound replay-guest retirement/restore also passed. On 2026-10-23, the pinned Debian Trixie package/setup replay verified all 50 selected packages while preserving the existing default guest. General workload routing, existing-guest package/config migration, clean-device reproduction, complete setup rollback, and GUI/audio/Turnip workload qualification remain open. See [four-client evidence](evidence/2026-10-22-gtk-vte-same-session.md), [retirement evidence](evidence/2026-10-22-replay-guest-retirement.md), and [fresh setup replay](evidence/2026-10-23-disposable-debian-replay.md).

## Evidence ledger

| Claim | Evidence | Status |
|---|---|---|
| Adreno 825 / SM8735 and relevant device nodes exist | Read-only ADB observation | Verified at observation time |
| Native Termux Turnip rejected the device | Captured `vulkaninfo --summary` output | Verified for tested native package/process |
| Ternux PRoot launcher passes through KGSL/DRM and selects Zink | Ternux source at local commit `ef65cb4` | Source verified; runtime not rerun |
| Debian PRoot GL renderer on active display `:1` is Zink/Turnip | Live `glxinfo -B` in PRoot on 2026-10-18 | Verified for this process/display; see P4 evidence |
| Existing Ternux-owned `:0` session uses Zink/Turnip | Ternux documentation and owner's prior report | Not independently verified in this review |
| Ternuxx can reuse the Debian rootfs for bounded operations | Typed Native-to-PRoot adapter supports inventory, isolated verification, and selected explicit guest operations; active guest/session ownership remains separately verified | Implemented in bounded scope; broad lifecycle and workload qualification remain incomplete |
| Shader cache alone proves current hardware acceleration | Insufficient evidence | Rejected |


## 11. CPU, GPU, and NPU runtime research

**Research date:** 2026-10-17

**Current-status note (2026-10-24):** The NPU feasibility and “unknown/unverified” conclusions below are historical snapshots from before Ternuxx integrated its experimental Native SM8735 HTP path. The current implementation, exact runtime provenance, live workload evidence, and remaining qualification gates are maintained in [NPU acceleration](testing/NPU-ACCELERATION.md) and [P12 status](PHASE-STATUS.md). This research remains background for architecture and external-runtime risks; it is not the current capability authority.

The product goal is a pocket mobile workstation with CPU, GPU, and NPU acceleration. This is a target, not a claim that all accelerators are currently accessible to Ternuxx. CPU is the baseline. GPU and NPU support must be demonstrated for the exact workload and process context.

### Android NPU / AI runtime evidence

- Android's [NNAPI migration guide](https://developer.android.com/ndk/guides/neuralnetworks/migration-guide) states NNAPI was deprecated in Android 15 and recommends migration to alternatives. Ternuxx should not make NNAPI its future foundation.
- Google AI Edge documents a [LiteRT NPU delegate for Qualcomm devices](https://ai.google.dev/edge/litert/android/npu). That page describes the Qualcomm delegate as backed by NNAPI, which Android has deprecated. Treat this page as a research lead only: confirm a currently supported non-NNAPI path and supported device/model before considering implementation. It does not prove the SDK/runtime is callable from a Termux shell or Debian PRoot.
- Qualcomm documents [Qualcomm AI Engine Direct / AI Runtime](https://docs.qualcomm.com/nav/home/QNN_general_overview.html?product=924033590759186372) as a vendor runtime with accelerator backends. The exact device SKU, supported Android integration, runtime distribution, ABI, licensing, and process access need confirmation before implementation.
- The inspected device is recorded as Adreno 825 / SM8735. Qualcomm's [Snapdragon 8s Gen 4 product brief](https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/Product-Brief-Snapdragon-8s-Gen-4.pdf) identifies SM8735 and lists a Hexagon NPU. That verifies silicon capability for the platform, not runtime access on this phone. The current [LiteRT Qualcomm integration](https://github.com/google-ai-edge/LiteRT/tree/main/litert/vendors/qualcomm) describes QAIRT-backed HTP/DSP/GPU paths and Android-target tooling; this does not prove a usable Termux shell or PRoot package for this device.
- **New primary-source lead (checked 2026-10-17):** upstream [llama.cpp Snapdragon backend documentation](https://github.com/ggml-org/llama.cpp/tree/master/docs/backend/snapdragon) now describes CPU, Adreno GPU through OpenCL, and Hexagon HTP backends, with Android cross-build/deployment examples and sample logs that explicitly select HTP. It labels the Hexagon backend experimental. The docs do not establish an SM8735-specific test, a Termux-app-context run, or a PRoot run. Upstream also documents [building/running its CLI in Termux](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md), but that general CPU build path does not establish the Snapdragon OpenCL/HTP backends in Termux.
- The repo's practical inference candidates are therefore (1) a portable CPU baseline, (2) llama.cpp Snapdragon/OpenCL for Android-native GPU and (3) llama.cpp/GGML Hexagon or a QAIRT-backed Android app integration for HTP. All are external-runtime research leads, not Ternuxx code or capabilities. Before selecting one, check upstream commit/version, license and notices, SDK/model terms, exact SM8735 HTP architecture support, binary ABI and loader requirements, package size, Termux-vs-Android app permissions, and coexistence of `/vendor/lib64` OpenCL libraries with FastRPC/Hexagon loading. Do not copy upstream implementation code into Ternuxx; use published interfaces and add original integration/tests only after approval.
- A current upstream issue reports a Hexagon session failure under a particular Termux `LD_LIBRARY_PATH` configuration on a different Snapdragon 8 Elite Gen 5 device; another upstream issue reports a correctness bug for a specific HTP operation/device path. Treat issue reports as risk signals, not proof about this SM8735 device. They reinforce why backend selection, output correctness, and exact execution-context tests are mandatory. [Issue #27677](https://github.com/ggml-org/llama.cpp/issues/27677), [Issue #25876](https://github.com/ggml-org/llama.cpp/issues/25876).

**Research update:** an NPU is present in the documented SM8735 platform and credible upstream Android HTP backends now exist. This changes NPU feasibility from “runtime candidate not identified” to “candidate runtime exists; exact device/context/workload remains unverified.” Ternuxx NPU validation remains `UNKNOWN` for end-to-end execution. No SDK/toolchain/model was downloaded or installed.

### Required proof before an NPU feature claim

1. Identify the exact device/SoC and Android build.
2. Identify an official, currently supported runtime/delegate for that SKU and its distribution/license constraints.
3. Show that the runtime is accessible in the intended execution context (native Termux process, dedicated Android app, or PRoot guest); do not extrapolate between contexts.
4. Run a representative model and record that the NPU delegate was actually selected, supported operators, correctness, latency/throughput, memory, and thermal behavior.
5. Record CPU and GPU fallback behavior. A model that silently falls back to CPU is not evidence of NPU acceleration.

**Evidence classification:** official vendor/framework/upstream project documentation verified as research references; the platform NPU is documented; Ternuxx device NPU process access, model execution, correctness, and performance remain untested.

### Existing Ternux AI provider (separate project; reviewed 2026-10-17)

The independent public [`soobujmiah/ternux` main branch](https://github.com/soobujmiah/ternux/tree/9fda63162426f77ee575b5f6729d8799a30f51b7), observed at commit `9fda63162426f77ee575b5f6729d8799a30f51b7`, has AI work that should be evaluated for reuse before Ternuxx builds another runtime. Its [benchmark record](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/docs/BENCHMARKS.md) documents CPU and Adreno Vulkan llama.cpp tests from the existing Debian/PRoot workstation. A bounded Qwen2.5 1.5B Q4_0 run reports CPU `59.04` prompt / `2.38` decode tok/s, Adreno Vulkan `92.19` / `13.27` tok/s, and conservative HVX HTP `34.20` / `12.02` tok/s; one-device totals were `264.39`, `71.30`, and `129.46` seconds respectively. These are Ternux-published single-run measurements, not rerun here or Ternuxx results. Its separate [Hexagon HTP extension](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/guides/llama-htp-experimental.md) remains experimental: the bounded HVX matrix-multiply suite passed, but HMX and flash-attention correctness failures and incomplete broad operator coverage remain. The separate [QNN SD1.5 experiment](https://github.com/soobujmiah/ternux/blob/9fda63162426f77ee575b5f6729d8799a30f51b7/experiments/qnn-native/README.md) has HTP graph execution evidence, while independent tensor correctness remains open.

These remain Ternux-repository reports for named PRoot/Android workloads, not Ternuxx implementation or release qualification; this audit did not rerun them. Owner direction makes Ternuxx the independent final workstation: no Ternux CLI/state adapter is required. Research may guide provider selection with attribution, but do not copy Ternux source/artifacts or call its generic cleanup/start path. Its recorded lifecycle includes broad X11/PulseAudio termination and wildcard socket cleanup.

### CPU/GPU/NPU claims policy

- CPU is the baseline, not an accelerator claim. Report actual execution backend and workload measurements.
- Native Termux GPU and Debian PRoot GPU are separate capability records. Ternuxx has a current guest graphics route under P11; old Ternux benchmarks remain external research and do not qualify Ternuxx inference or current guest workloads.
- Do not claim “world-class”, faster, GPU accelerated, or NPU accelerated as a measured result until comparable workloads have correctness, throughput/latency, memory, and thermal/power evidence. “World-class mobile workstation” describes the product vision.


## 12. Native Termux desktop packages and host integrations

**Observed on device:** 2026-10-17, read-only SSH session. **This is a dated package-index snapshot, not a promise about later installs.**

### Environment and repository provenance

- Termux app: `0.119.0-beta.3`; Android: 16; ABI: `aarch64` (from the earlier read-only device inventory for this project).
- Installed Termux X11 companion package: `termux-x11-nightly 1.03.01-6`; installed native packages include `termux-api 0.60.0`, `pulseaudio 17.0-4`, and `dbus 1.16.2-3`. `termux-x11`, `dbus-launch`, `xauth`, `pulseaudio`, and `termux-share` commands were present. XFCE itself was not installed.
- Current signed local package indexes showed official Termux main index dated `2026-10-17 06:48 UTC` and official Termux:X11 index dated `2026-10-17 01:12 UTC`. Configured sources also included TUR and a Hermes canary repository; Ternuxx package choices below use the official Termux main/X11 indexes only. No third-party repository is enabled by Ternuxx.
- These checks did not update indexes or install/remove packages. Before any real package transaction, refresh/verify the index under the user's chosen package-management workflow, then show the exact package plan and ask for explicit consent.

### Official Termux:X11 setup requirements

Historical setup notes record that the Android X11 app and its matching Termux companion package are both required, and that backgrounded Termux processes may receive less CPU time. The inspected device is Android 16 and already has the companion command/package, but this review did not launch a session or re-check the Android app package/signature. Verify current package names and device compatibility before release.

### Package candidates in official local indexes

`apt-cache policy` reported the following candidates from `https://grimler.se/termux/termux-x11` (`x11/main`, `aarch64`):

| Package | Candidate | Intended use |
|---|---:|---|
| `xfce4` | 4.20 | Complete XFCE metapackage |
| `xfce4-session` | 4.20.4-1 | Session manager |
| `xfce4-panel` | 4.20.8 | Panel |
| `xfwm4` | 4.20.0-3 | Window manager |
| `thunar` | 4.20.10 | File manager |
| `xfce4-terminal` | 1.2.0 | Terminal |
| `chromium` | 155.0.8059.79 | Optional browser |
| `alacritty` | 0.17.0 | Optional terminal |
| `kitty` | 0.49.2 | Optional terminal |

`xfce4` metadata describes a small metapackage whose dependencies include the XFCE settings, notification, power-management and terminal components. An `apt-get -s install xfce4` simulation showed a broader transaction, including recommended/related packages such as WebKitGTK and archive utilities. A separate `apt-get -s --no-install-recommends install xfce4-session xfce4-panel xfwm4 thunar xfce4-terminal` still resolved a substantial GTK/X11 dependency closure. Both commands were simulations; no package transaction occurred. Use a preview of the exact chosen plan and measured package sizes before implementation offers installation. Do not repeat the earlier unmeasured 2 GB estimate as fact.

### Termux/Android-facing workflows

The device has the `termux-api` command package and `termux-share`; the package alone does not prove the Termux:API Android add-on is installed or that each Android permission is granted. The official [Termux:API project](https://github.com/termux/termux-api) describes Android device functions exposed to scripts, while Termux's [filesystem/API guidance](https://github.com/termux/termux-packages/wiki/Termux-file-system-layout) documents explicit permission boundaries for external command access. Treat API actions and file sharing as opt-in, user-triggered workflows; do not scan shared storage or assume broad access.

### Native desktop implementation follow-up (2026-10-23)

At the time of the 2026-10-17 package survey, the upstream X11 session example was `termux-x11 :1 -xstartup "dbus-launch --exit-with-session xfce4-session"`, and the Native lifecycle was still a candidate. Since then, Ternuxx implemented preview-first Native package setup and ownership-aware desktop start/stop/status; the P2 device acceptance passed on the recorded Android 16 / aarch64 profile, with display :1 and owner-confirmed XFCE/audio behavior. This does not certify other devices or make package candidates permanent across dates. The existing Ternux-owned :0 desktop remains separately managed; Ternuxx controls only its validated Native :1 session. See [P2 completion evidence](evidence/P2-phase-completion-2026-10-18.md), [current installation limits](INSTALLATION.md), and the [active phase status](PHASE-STATUS.md).

**Evidence classification:** package names, versions, source priority, and dependency plans were observed from the device's signed local APT indexes on the date above; install simulations were read-only. Upstream setup/API requirements were checked against official documentation. Native XFCE launch, application compatibility, Android add-on state, API permissions, and package-size totals remain untested.


## Termux:Boot and Termux:API

Official upstream references checked 2026-10-17:

- [Termux:Boot](https://github.com/termux/termux-boot) runs user scripts from `~/.termux/boot/` after device boot. Its setup requires opening the add-on once; documentation notes optional wake-lock use. Treat this as an opt-in background service hook, not proof that a graphical session can appear unattended. Device-vendor background limits still need per-device verification.
- [Termux:API](https://github.com/termux/termux-api) exposes Android functions through Termux command-line clients and a companion app. Upstream states the add-on must use the same signing key as Termux for permissions to work. Ternuxx must check the installed command and app capability at runtime and leave Android permission decisions to Android.

These references establish available integration mechanisms, not that every API works on every Android version or device.


## Wireless ADB, Shizuku, and watchdog boundary

Research checked 2026-10-17:

- [Upstream Shizuku API requirements](https://github.com/RikkaApps/Shizuku-API#requirements) say non-root Shizuku must be restarted with ADB after each reboot; Android 11+ lets the user start it on-device through Wireless debugging. Therefore, boot auto-start/watchdog is not assumed for the standard upstream installation.
- Owner's ADT documentation records a device-tested custom Shizuku build with a boot receiver, WorkManager dispatch, and foreground `WatchdogService`, including a dated observation of recovery after force-stop. This is a snapshot for that custom build, not a claim about upstream Shizuku or Ternuxx. Re-check the exact installed build and boot behavior before depending on it.
- The detailed owner audit is [ADT's on-device ADB/Shizuku operational dependency report](https://github.com/soobujmiah/adt/blob/abece9e714a3bcb24d4a8dcc9f001feb421c1411/docs/ON_DEVICE_ADB_SHIZUKU_OPERATIONAL_DEPENDENCY.md). Its 2026-09-13 snapshot distinguishes the local PRoot ADB relay on `127.0.0.1:5037` from the Android-side TCP `:5555` transport and `shizuku_server` bridge; the relay itself was manually started, while the custom Shizuku boot receiver/watchdog maintained the device-side bridge after boot. It reports the `:5555` property surviving a mid-session Shizuku stop but not a full reboot. Treat those details as evidence for the audited ADT/device topology, not a current Ternuxx guarantee; the live Ternuxx observation is separately recorded in the P3 ADB evidence.
- [Termux services](https://github.com/termux/termux-services) provides runit-based process supervision in Termux. Combined with [Termux:Boot](https://github.com/termux/termux-boot), this is the lower-dependency path for starting and supervising Termux-owned workstation processes. It does not grant Android shell privileges or turn on protected Wireless debugging settings.
- Keep standard paired Wireless debugging separate from a fixed TCP `adbd` listener such as port 5555. They have different discovery, pairing, authorization, and network-exposure behavior. A setting/property, open port, Shizuku process, or watchdog message alone does not prove an authorized working ADB transport.
- Any Ternuxx ADB-over-Wi-Fi automation remains off by default and requires explicit consent, transport-specific verification, bounded recovery, and a clear disable path. No device setting was changed during this research.


## Sustainable workload optimization

Official Android performance guidance checked 2026-10-17:

- [Android Dynamic Performance Framework](https://developer.android.com/games/optimize/adpf) and [Thermal API](https://developer.android.com/games/optimize/adpf/thermal) recommend responding to changing thermal conditions and reducing workload to sustainable levels. These are Android application APIs, not proof that a Termux shell can read all thermal signals. A Ternuxx Android companion or another supported host API would need separate implementation and permission review before thermal automation is advertised.
- [PowerManager thermal status](https://developer.android.com/reference/android/os/PowerManager) exposes thermal-status callbacks to Android apps on supported API levels. Ternuxx reports unavailable when no supported bridge exists; it does not read guessed vendor sysfs paths as a portable substitute.
- [Termux services](https://github.com/termux/termux-services) supplies process supervision but not CPU/GPU clock control or Android thermal APIs.

**Native Termux bridge check (2026-10-24):** The current CLI has no verified Android thermal-status/headroom interface. `termux-thermal-status` and `dumpsys` were unavailable; `termux-battery-status` exposed battery data only. The NDK `AThermal_*` calls could not link against Termux's private `libandroid.so`, while the system library's direct `dlopen` failed on `libbinder_ndk.so` in the app linker namespace. See the [device probe](evidence/2026-10-24-native-thermal-api-access-check.md). This is process/device evidence, not a claim that Android lacks the API or that another Android app context cannot use it.

For this project, sustainable per-workload adaptation is the target: lower parallelism, model batch/context, render quality, or pause when measured pressure requires it. Device-specific tuning and performance claims require a comparable baseline and longer-duration workload evidence.


## 13. Native Wine/Hangover and accelerator boundary

**Sources:** [Hangover upstream](https://github.com/AndreRH/hangover); [Android NNAPI migration guide](https://developer.android.com/ndk/guides/neuralnetworks/migration-guide)
**Accessed:** 2026-10-17
**Confidence:** upstream architecture verified; device package index observed; application and accelerator behavior unverified

A read-only `apt-cache policy` on the device's configured Termux indexes found `hangover`, `hangover-wine`, `hangover-libarm64ecfex`, `hangover-libwow64fex`, and `hangover-wowbox64`, each uninstalled with candidate 11.16 from the official Termux:X11 index. The configured TUR index also had older 10.0-1 package candidates. This confirms current index visibility only; show source/version and avoid mixing repositories. It does not confirm runtime health, app compatibility, or successful x86 translation. No packages were installed.

Hangover upstream describes x86/x86-64 Windows application execution on ARM64 Wine using emulator DLLs (FEX/Box64 paths) and documents a Vulkan 1.3 plus feature requirement for DXVK. The recorded native Termux Vulkan probe on this device failed with `VK_ERROR_INCOMPATIBLE_DRIVER`; therefore native DXVK is currently unverified/unavailable for the tested configuration. This is separate from the existing Ternux guest configuration and its shader cache.

Android's official migration guide states NNAPI was deprecated in Android 15. Any NPU route needs an explicit Android-side inference runtime and bridge; Wine/Hangover and PRoot do not grant NPU access by themselves. Official Termux package issues include version-specific reports of x86/x86-64 launch failure and package build/update failure. These are not evidence that the current 11.16 candidate fails, but they require an actual architecture/runtime smoke test before compatibility claims.

Detailed support gate: [Native Wine and Hangover](WINE-NATIVE.md). Sources: [Termux launch report](https://github.com/termux/termux-packages/issues/27663), [Termux package update report](https://github.com/termux/termux-packages/issues/29816), and [Termux X11 package source tree](https://github.com/termux/termux-packages/tree/master/x11-packages).
### Direct Native NPU discovery — 2026-10-20

A read-only `tx doctor --json` on Native Termux (`u0_a490`, Termux 0.119.0-beta.3, Android 16, aarch64) now reports evidence by layer: visible Android vendor files (`libQnnHtp.so`, `libcdsprpc.so`, `libadsprpc.so`, `libSNPE.so`); no visible `/dev/adsprpc-smd`, `/dev/adsprpc-smd-secure`, or `/dev/fastrpc-cdsp` nodes; and no checked `qnn-net-run`, `qnn-platform-validator`, `snpe-net-run`, or `llama-cli` in the Native command path. These bounded path/command checks do not prove the files cannot be accessed by another route. They also do not prove a loadable ABI, HTP permission, delegate selection, or NPU execution. The report explicitly keeps NPU execution unverified.

The same `DISPLAY=:1 tx doctor --graphics --json` invocation observed Native `llvmpipe (LLVM 21.1.8, 128 bits)` and `VK_ERROR_INCOMPATIBLE_DRIVER`; this was separate from the live Debian PRoot `:1` Zink/Turnip Adreno 825 renderer and authenticated Native PulseAudio client path. At that 2026-10-20 snapshot, CPU remained the Native inference baseline and no Ternuxx model integration existed. No native graphics or NPU runtime, SDK, model, package, node permission, service, guest file, or Android setting was changed by that check. Later P12 work integrated experimental Native HTP inference; its current status and limits are in [NPU qualification](testing/NPU-ACCELERATION.md). The historical audit recommended preserving CPU, Zink/Turnip and VirGL as distinct routes and did not assess the later HTP implementation.
