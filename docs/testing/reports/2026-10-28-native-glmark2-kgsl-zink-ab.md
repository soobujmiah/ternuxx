# Native visible OpenGL app A/B: KGSL vs Zink/Turnip

- Report ID: `TERN-TEST-2026-10-28-NATIVE-GLMARK2-AB-01`
- Run date: 2026-10-28 local (Asia/Dhaka; UTC date 2026-10-27)
- Verdict: **Both GPU paths rendered the bounded glmark2 workload. No robust performance winner established.**
- Scope: one visible, windowed, Native Termux OpenGL app run on each process-scoped backend; not a Blender qualification or long-run benchmark.

## Device and runtime

- Redmi Turbo 4 Pro (`25053RT47C`), Adreno 825, Android 16, aarch64.
- Ternuxx Native XFCE/Termux:X11 display `:1` remained running.
- `glmark2 2023.01`; both runs used Mesa `26.3.0-devel (git-98f3d6229d)`, a 640×360 visible X11 window, and the same `build`, `texture`, and `shading` scenes for 4 seconds each.
- Current Native Blender 4.5.14 remained open during both benchmark runs. It was then cleanly closed at the owner's request; `bpy.data.is_dirty` was false. The Native desktop was left running.
- No package, desktop-session, or persistent backend-selection change was made. Post-run status still reported selected backend `kgsl-freedreno` and OpenGL renderer Adreno 825.

## Results

| Process backend | OpenGL renderer reported | Build FPS | Texture FPS | Shading FPS | glmark2 score | Exit |
|---|---|---:|---:|---:|---:|---:|
| Native KGSL/Freedreno | `Adreno (TM) 825` | 688 | 667 | 663 | 671 | 0 |
| Native Zink over Turnip | `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))` | 691 | 678 | 594 | 653 | 0 |

KGSL's score was 18 points (2.8%) higher in this single pass. Zink was slightly higher in build and texture, while KGSL was higher in shading. The difference is too small and the run count too low to call a stable speed winner. Both renderer identities were checked with `glxinfo -B` before launching glmark2, and glmark2 itself logged the renderer and completed all three draw workloads.

The windows were opened visibly on display `:1` as requested. No screen capture was taken, so this report does not score owner-perceived visual artifacts. The KGSL run logged a DRM file-description permission warning but still completed with exit 0. Zink/Turnip loaded the isolated Native Mesa candidate's Freedreno ICD only for the glmark2 process; it did not switch the live XFCE or saved backend. The exact runner and outputs are in the [evidence directory](../../evidence/2026-10-28-native-visible-graphics-ab/).

## Interpretation and limits

This confirms that **both Native paths can run this separate OpenGL benchmark on Adreno 825**. It does not establish that either path is generally better or predict Blender's complex viewport/render correctness. Existing Blender evidence remains mixed: KGSL produced corrupted pixels on the Mithyar Mic frame and on a separate fresh scene; Native Zink/Turnip on the same experimental Mesa candidate crashed Blender 4.5.14 while opening a test scene. PRoot Zink/Turnip uses a different userland and Blender 4.3.2 and is not the same Native test.

A stronger selection needs repeated balanced-order runs and, most importantly, a representative Blender scene under each supported route with visual correctness review. For this benchmark, both are GPU-verified; the score difference alone should not change the Blender backend choice.

## Reproduction

From Native Termux with the Ternuxx Native `:1` session live and `glmark2` installed:

```sh
TERNUXX_STATE_DIR="$HOME/.local/share/ternuxx" python docs/evidence/2026-10-28-native-visible-graphics-ab/run_glmark2.py kgsl --duration 4
TERNUXX_STATE_DIR="$HOME/.local/share/ternuxx" python docs/evidence/2026-10-28-native-visible-graphics-ab/run_glmark2.py zink --duration 4
```

The runner checks `glxinfo -B` for the requested renderer before starting the visible workload and refuses the run if it sees the wrong renderer. The KGSL run uses Ternuxx's validated selected process environment. The Zink run keeps the same isolated candidate Mesa libraries and sets `MESA_LOADER_DRIVER_OVERRIDE=zink`, `GALLIUM_DRIVER=zink`, and the candidate Turnip ICD for that child process only.

- Runner SHA-256: `6e67fdc6c666f37f2505a2c9706d8c2b6ff2b4a6d46bd858f797f8983b4c3f26`.
- [KGSL log](../../evidence/2026-10-28-native-visible-graphics-ab/kgsl.log)
- [Zink/Turnip log](../../evidence/2026-10-28-native-visible-graphics-ab/zink-turnip.log)
