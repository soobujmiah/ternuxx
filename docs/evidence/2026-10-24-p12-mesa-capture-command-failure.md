# P12 Mesa capture command failure

**Observed:** 2026-10-24 18:57 UTC  
**Workflow:** [P12 Mesa build provenance, run 40121730611](https://github.com/soobujmiah/ternuxx/actions/runs/40121730611)  
**Ternuxx source:** `bd9557b2bedb987bedd52c32d5f0909196350860`  
**Pinned Termux packages source:** `0219ff84b372c9d38aad4e40f448c20ec3d1588e`  
**Pinned Mesa source:** `98f3d6229d61452cef80f8563af7c56ae599dc14`

The workflow passed recipe-pin validation and compiled all 391 configured Mesa host targets. The instrumented recipe then failed at the first host Meson capture with:

```text
/home/builder/termux-packages/packages/mesa/build.sh: line 45: /usr/bin/python3 /home/builder/.termux-build/_cache/meson-1.11.0/meson.py: No such file or directory
```

`TERMUX_MESON` is a command string containing an interpreter and script path. The capture helper surrounded the entire value with quotes, so Bash tried to execute the combined string as one file. This was separate from the earlier AppArmor capture-path failures: capture now runs under `/home/builder/p12-mesa-evidence` and `docker cp` successfully copied that directory to the workflow workspace.

The local fix parses `TERMUX_MESON` into a Bash argument array and invokes it as separate words. A regression test sources the instrumented function with a multiword Meson command and confirms all five `introspect` calls complete. Focused tests pass. The failed run uploaded only `build-metadata.json` and `builder-image.txt`; it contains no Meson/Ninja graph, package-staging manifest, or built archives. Rerun the workflow after this correction is committed to verify builder behavior; no Mesa provenance gate is closed by this failed run.
