# Native Freedreno runtime recheck — 2026-10-25

At 11:44 UTC, the exact saved `graphical` Native package plan installed `mesa-vulkan-icd-freedreno` version `26.2.5` from the official `termux-main` repository. The transaction added only that package (1.6 MB download; 13.9 MB reported disk use), with no upgrades or removals.

The package files and ICD manifest are present, but presence did not imply device support. With the manifest explicitly selected, `vulkaninfo --summary` returned exit 1. Mesa Turnip reported `device (chip_id = 44030000, gpu_id = 6830) is unsupported (VK_ERROR_INCOMPATIBLE_DRIVER)`; the Vulkan loader then found no valid GPUs. `tx mng graphics verify native vulkan --json` likewise reports `status: unavailable`, no device, and no draw.

The Native X11 desktop remains on display `:1`. Read-only status after restoring the saved backend to `system` reports OpenGL renderer `llvmpipe (LLVM 21.1.8, 128 bits)`, GLES context renderer `llvmpipe`, `render_verified: false`, and Vulkan unavailable. No Adreno/Zink/Turnip rendering claim is supported by this run. The desktop was not restarted.

Ternuxx now preflights `vulkaninfo --summary` before saving the `termux-zink` preference. On this device, `tx mng graphics select native termux-zink` fails with `graphics_backend_unavailable` and the bounded Mesa incompatibility diagnostic; no graphics selection file is written. The default `system` selection remains active. This is a runtime support gate, not a fix for the missing device support in the installed Mesa driver.

The ICD package remains installed as part of the requested Native graphical profile.
