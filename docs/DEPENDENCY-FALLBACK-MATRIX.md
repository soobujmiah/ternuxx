# Dependency and capability fallback matrix

Native Termux is the host and control plane; Debian PRoot is an optional isolated guest provider. This is the source-level fallback contract. Package availability and live status must be checked when an operation is requested. The [capability matrix](architecture/CAPABILITY-MATRIX.md) describes client reach; the [feature matrix](testing/FEATURE-MATRIX.yaml) records qualification and evidence.

| Component or capability | Readiness evidence | Missing or unknown behavior | Boundary |
|---|---|---|---|
| Native Termux:X11/XFCE | Package preview and desktop prerequisite checks | CLI remains available; start reports the missing prerequisite and does not launch another runtime | Native desktop |
| Termux:X11 Android app | Android package presence is checked separately from server readiness | Unknown visibility stays unknown; Ternuxx does not open Android settings | Android Activity visibility is not inferred from server readiness |
| Termux:Boot | App/package, script directory, and script inventory are checked separately | Unknown app state blocks boot-profile changes; manual CLI control remains available | Native Termux only |
| Runit / managed Native SSH | Fixed service definition and process/config identity | Missing manager or ambiguous ownership fails closed; no alternate daemon or broad process signal | Product service binds only to 127.0.0.1:8023; other Native SSH configurations are external |
| Native graphics | Selected backend plus bounded API/workload result | Missing tools or failed API reports unavailable; no automatic renderer switch | Native Bionic userspace; workload evidence is separate from Debian graphics |
| Native audio | Exact Ternuxx-owned PulseAudio process/config | Unknown or competing ownership blocks lifecycle mutation | Native service only |
| Wake Lock / Termux:API | Command availability and owner-scoped lease | Unknown lock state causes no acquire/release | Android app-global state remains separate |
| CPU inference | Termux llama.cpp runtime, pinned model hash, and bounded CPU run | Missing runtime/model fails with setup guidance; no cloud route | Native Termux; CPU is the explicit baseline |
| Vulkan inference | Runtime device enumeration and positive GPU-layer-offload proof | Missing device or incomplete offload fails; user may explicitly select CPU | Native Vulkan; current result depends on experimental Mesa/Freedreno ICD |
| HTP inference | Pinned runtime integrity, SM8735 gate, HTP0 discovery, layer and buffer proof | Any missing proof fails; CPU/Vulkan are not selected silently | Experimental SM8735-only path; tested short prompts are slower than CPU |
| Debian PRoot guest | Native `proot`/`proot-distro`, guest inventory, and session identity | Guest-only actions report unavailable; Native host actions remain available and are not substituted for guest actions | Optional Debian workload provider managed from Native Termux |

## Fallback contract

- A missing dependency changes the readiness of that capability only; it does not silently change the selected provider or workload.
- CPU can be selected explicitly as the inference baseline. Vulkan and HTP failures do not silently fall back to CPU.
- Native and Debian workloads keep separate userspace, process ownership, graphics, and evidence. A guest result does not qualify the Native host, or vice versa.
- Distinguish package presence, command presence, service readiness, Android app visibility, process ownership, and workload execution.
- Preview exact package and guest transactions, require explicit confirmation, and preserve an existing Debian rootfs.
