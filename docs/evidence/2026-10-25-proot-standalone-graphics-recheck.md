# Standalone Debian graphics recheck — 2026-10-25

Native XFCE was running on `:1`, standalone Debian GUI was stopped, and no nested `:2` socket or PRoot process was present before the test. The existing Debian guest and its desktop selection were retained.

`tx stop` cleanly stopped the Ternuxx-owned Native desktop. `tx pgui start --mode standalone --desktop xfce` then started the managed Debian XFCE on standalone display `:0`. `tx pgui graphics verify` reported OpenGL ES 3.2 with renderer `zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))`; GLX direct rendering was yes with the same renderer; and Vulkan enumerated Adreno 825 Turnip devices plus llvmpipe. This probe checks context creation and enumeration, not presentation.

The stronger bounded `tx proot verify --distro debian --guest-user sobuj --display :0 --backend zink` probe completed with no blockers. It verified X11, GLES context, GLX draw, and Native PulseAudio reachability. `glx_draw_frames` was 475, and the draw renderer was `zink Vulkan 1.4(Adreno (TM) 825 (MESA_TURNIP))`. The probe reported `gles_draw_verified: false`, so this evidence does not claim a GLES draw, XFCE compositor acceleration, every application surface, sustained performance, or inference offload. The user-facing XFCE About label was not visually inspected.

After the test, `tx pgui stop` stopped only the verified standalone `:0` guest GUI, then `tx start` restored Native XFCE on `:1`. Final status showed Native XFCE running, standalone PRoot GUI stopped, no PRoot processes or nested `:2` socket, and Native graphics still using `llvmpipe` with Vulkan unavailable. No guest packages or saved graphics selections changed.
