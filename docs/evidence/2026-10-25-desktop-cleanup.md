# Debian desktop cleanup and post-cleanup routes

**Observed:** 2026-10-25 19:30 UTC (2026-10-26 01:30 Asia/Dhaka)  
**Checkout:** `/data/data/com.termux/files/home/ternuxx`; origin `soobujmiah/ternuxx`  
**Scope:** Remove locally installed DE package sets that failed or were partial; preserve passing package sets and the catalog implementation.

## Removal and package integrity

A read-only APT simulation was reviewed before each removal.

- Debian PRoot: `apt-get --simulate --yes remove --auto-remove gnome-core gnome-session cinnamon-desktop-environment cinnamon cinnamon-session cinnamon-control-center` proposed 202 GNOME/Cinnamon packages and 497 MB freed. The same transaction completed successfully. `dpkg --audit` returned no findings and `apt-get check` succeeded afterward.
- Native Termux: `pkg uninstall -y` for the installed Cinnamon and LXQt package sets was preceded by `apt-get --simulate --yes remove --auto-remove` using the same package arguments. The simulation selected 25 DE-specific packages, including orphaned `muffin`, `nemo`, `libfm-qt`, and LXQt file tools; apply completed successfully and reported 91 MB freed.

The catalog and source metadata remain in Ternuxx. Post-removal `proot_desktops.installed_desktops()` returned `xfce`, `lxqt`, `lxde`, `mate`, and `plasma`. The Native desktop inventory reports `xfce`, `mate`, and `plasma` installed, with `lxqt` and `cinnamon` absent.

## Live route checks

Native `tx status` reported the Native XFCE supervisor, Termux:X11, and XFCE live on `:1`. Debian standalone `:0` was stopped. After cleanup, `tx pgui start --mode nested --desktop xfce` launched Xephyr `:2`; its root-window tree included `xfce4-session`, `xfwm4`, `xfce4-panel`, and `xfdesktop`, confirming the full session window tree. The nested session was then closed with Ctrl-C. Final status reported Native `:1` live, standalone `:0` stopped, and nested `:2` stopped.

## Graphics boundary

Nested Xephyr startup printed `zink Vulkan 1.4 (Adreno (TM) 825 (MESA_TURNIP))` for its GLES context. That observation identifies the Xephyr startup context; it does not establish an application draw. A guest GLX probe with the nested launch environment reported `DRI3 not available` and `couldn't find RGB GLX visual or fbconfig`; default guest GLX reported `llvmpipe` and `Accelerated: no`. Native `:1` also remains llvmpipe with Vulkan unavailable. Therefore nested XFCE passed desktop startup/window-tree checks, while accelerated guest application rendering and Android presentation remain unverified.

## Commands used for post-checks

```sh
./tx status
./tx pgui status
PYTHONPATH=lib python3 -c 'import proot_desktops; print(proot_desktops.installed_desktops("/data/data/com.termux/files/usr/var/lib/proot-distro/containers/debian/rootfs"))'
proot-distro run debian --isolated -- /usr/bin/dpkg --audit
proot-distro run debian --isolated -- /usr/bin/apt-get check
proot-distro run debian --isolated --env DISPLAY=:2 -- /usr/bin/xwininfo -root -tree
```

This evidence records one live device and its installed packages; it is not a general compatibility claim for other Android devices or Debian images.
