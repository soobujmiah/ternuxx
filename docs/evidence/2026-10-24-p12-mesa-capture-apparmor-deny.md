# P12 Mesa evidence capture blocked by builder AppArmor policy — 2026-10-24

Phase: `P12` — in progress  
Evidence class: failed pinned GitHub Actions build and pinned recipe-policy inspection  
Runs: [40117390685](https://github.com/soobujmiah/ternuxx/actions/runs/40117390685), [40119127629](https://github.com/soobujmiah/ternuxx/actions/runs/40119127629)

## Observed failure

Both workflow runs reached the Mesa host build and then failed when the gated capture tried to create `aarch64` below a directory inside `/home/builder/termux-packages`. The first attempt used a hidden output directory; the second renamed it and made the host checkout directory mode `0777`, but failed at the same builder path. The second run's log ends with:

```text
mkdir: cannot create directory ‘/home/builder/termux-packages/p12-mesa-evidence/aarch64’: Permission denied
```

The second run completed all 391 host Ninja targets and installed its host tools before capture failed. Capture stopped before target Meson metadata, target compilation, package staging manifests, or the post-build validation. Its artifact contains only `build-metadata.json` and `builder-image.txt`; no build graph or package map exists.

## Verified cause

The pinned `lfdevs/termux-packages` `scripts/run-docker.sh` bind-mounts the recipe checkout at `/home/builder/termux-packages` and loads `scripts/profile-restricted.apparmor` before executing the build. At the pinned recipe commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`, that profile contains:

```text
deny /home/builder/termux-packages/[^o]** wlk,
allow /home/builder/termux-packages/output/** rw,
```

The capture path is expressly under the denied tree; host-side chmod cannot override the container's AppArmor denial. The first hidden-directory naming also prevented the default artifact uploader from including hidden files, but it was not the cause of the in-container mkdir denial.

## Correction under verification

The capture helper now defaults to `$HOME/p12-mesa-evidence`, and the workflow sets this to `/home/builder/p12-mesa-evidence`, outside the restricted recipe tree. The workflow uses a dedicated builder container and copies the evidence out with `docker cp` after the build command exits, preserving the original build exit status. The host artifact path remains non-hidden. This correction is implemented and locally syntax/test checked; a new remote build run is required before claiming it works.

No `.deb` archives are uploaded. Continue to treat Mesa source-to-package provenance as unverified until a successful run produces and validates both host/target graphs and package payload manifests.
