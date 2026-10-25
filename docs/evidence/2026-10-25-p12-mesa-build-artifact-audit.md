# P12 pinned Mesa build provenance follow-up — 2026-10-25

Phase: `P12` — in progress
Evidence class: successful pinned GitHub Actions aarch64 build artifact, validated and re-audited locally
Workflow run: [40128850286](https://github.com/soobujmiah/ternuxx/actions/runs/40128850286)
Ternuxx source commit used by the workflow: `9ea68a4f5ed824021501d730d33a2b7d84c98370`

## Evidence

### Build result

The latest `P12 Mesa build provenance` workflow completed successfully on 2026-10-24. Its one `mesa-aarch64` job passed all 15 steps, including the pinned recipe instrumentation, aarch64 package build, build-graph capture, package staging-manifest capture, validation, and metadata-only artifact upload. The build used Termux package recipe commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`, Mesa source commit `98f3d6229d61452cef80f8563af7c56ae599dc14`, and builder image `ghcr.io/termux/package-builder@sha256:e2de051a518d8b188c59c4a1ecf357d373b9ccf48d6c06d7681fdc3f61a77287`. The package recipe PR remains open and draft; this is build evidence, not an upstream merge or an installed package.

The downloaded artifact passed `python3 tools/p12_mesa_build_evidence.py validate-capture`. Durable copies of the build metadata, target Meson graph, configured source map, five package staging manifests, and locally generated package-to-target candidate audit are under [`docs/evidence/data`](data/).

## Configured source coverage

The target Meson graph records 322 targets and 1,579 unique source paths: 1,567 paths under the pinned Mesa source root and 12 outside it. The source map recognized SPDX header identifiers on 402 source-root paths; 1,165 have no recognized SPDX header. It records 75 generated source paths. These are configured source-membership counts, not final object/link provenance or license conclusions.

The 12 external inputs consist of seven Wayland protocol XML paths from the build's Termux `wayland-protocols` package (target dependency version 1.49) and five generated Rust binding paths under the build directory. The 75 generated outputs include Mesa compiler/parser tables, Freedreno and Vulkan entrypoints, Wayland protocol code, Rusticl bindings, and other generated sources. Captured Ninja commands and target metadata preserve build context, but this review has not yet audited each generator's complete input set, the license of every external protocol file, or license propagation to generated output.

## Package and notice boundary

The five expected split packages are present in the staging manifests with archive hashes, control fields, and payload path/hash records. The candidate audit found 11 unique output-basename matches among 21 payload files, 46 package symlinks resolving to candidate files, no ambiguous basename matches, and 10 payload files without target-output basename matches. It also found 341 configured build outputs without a payload basename match. Basename correspondence is only a candidate; it does not prove install rules, link closure, or target-to-package provenance.

Only the base `mesa` package includes `share/doc/mesa/license.rst` in the inspected payloads; the four split packages contain no file whose path identifies a license/copyright/notice document. The source license says components carry different licenses and directs reviewers to per-file SPDX tags and the `licenses/` directory. Therefore `TERMUX_PKG_LICENSE=MIT`, these headers, and one bundled license document do not establish complete notices or per-package license conclusions. The existing package SBOM remains `filesAnalyzed=false` / `NOASSERTION`. No built archive was installed or rehosted.

## Next gate

Audit the 12 external source inputs and all 75 generated outputs back to their generator inputs, source origins, license metadata, and shipped notice obligations. Resolve per-file license records for the 1,165 configured source paths without recognized SPDX headers, and strengthen package attribution beyond output-basename candidates before changing SPDX conclusions. Re-run Native CPU, Vulkan, and HTP workloads only when every live sensor satisfies the unchanged guards; broader correctness, clean-install provenance, and sustained thermal qualification remain open.

## Retained artifacts

- [Build metadata](data/2026-10-25-p12-mesa-build-metadata-40128850286.json)
- [Configured target-source map](data/2026-10-25-p12-mesa-configured-target-source-map-40128850286.json)
- [Target Meson graph](data/2026-10-25-p12-mesa-target-graph-40128850286.json)
- [Package staging manifests](data/2026-10-25-p12-mesa-package-staging-manifests-40128850286.json)
- [Package-to-target candidate audit](data/2026-10-25-p12-mesa-package-target-audit-40128850286.json)
