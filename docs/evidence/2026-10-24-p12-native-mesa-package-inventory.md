# P12 Native Mesa package inventory — 2026-10-24

Phase: `P12` — in progress
Evidence class: read-only local package inspection and package-level SPDX generation
Observed: 2026-10-24 15:33 UTC

## Evidence

The preserved aarch64 Actions bundle is `debs-aarch64-0219ff84b372c9d38aad4e40f448c20ec3d1588e.tar`, SHA-256 `8b8f3dfccefd4dc3dba65a0099dc9c3efdfd6afc7f9679f3b92a2b8b781a9353`. Running its checksum sidecar from the bundle directory verified all five `.deb` archives. Their individual checksums, versions, architectures, and exact Debian `Depends` metadata are in the [SPDX 2.3 package inventory](2026-10-24-p12-native-mesa-package-sbom.spdx.json).

Live GitHub metadata confirms Termux PR #25 is still open and draft at packaging commit `0219ff84b372c9d38aad4e40f448c20ec3d1588e`. Its `packages/mesa/build.sh` pins Mesa source commit `98f3d6229d61452cef80f8563af7c56ae599dc14`, sets `TERMUX_PKG_LICENSE="MIT"`, and names `docs/license.rst` as the license file. This is the recipe declaration, not a complete component-license conclusion.

Direct `dpkg-deb --field` inspection found no `Source` or `License` control field in any of the five package archives. `dpkg-deb --contents` found `share/doc/mesa/license.rst` only in the base `mesa` package; the four split packages contain no separate license/copyright notice path. Mesa's generic license document warns that component licenses vary and points to per-file SPDX identifiers. The [SPDX inventory](2026-10-24-p12-native-mesa-package-sbom.spdx.json) therefore sets `licenseDeclared` to the recipe's `MIT`, `licenseConcluded` to `NOASSERTION`, and `filesAnalyzed` to `false` for each package. Per SPDX package semantics, `filesAnalyzed=false` means the package contents were not subjected to file-level analysis ([SPDX 2.3 package information](https://spdx.github.io/spdx-spec/v2.3/package-information/)).

## Validation

- `python3 -m unittest tests.test_deb_package_sbom -v`: 5 tests passed for control parsing, archive hashing, package-level SPDX fields, and required license evidence.
- `python3 -m unittest discover -s tests -p 'test_*.py' -q`: 1033 tests passed in 119.722 seconds.
- `python3 -m json.tool` parsed the generated SPDX JSON. An independent local check matched every one of its five package SHA-256 values to the extracted `.deb` bytes, checked its bundle SHA-256 against the preserved tarball, and confirmed five described package IDs/relationships with no file-level claims.
- `python3 tools/audit_documents.py --check`, `python3 -m tools.repo_knowledge verify`, and `git diff --check` passed.

## Qualification boundary

This inventory improves package provenance and checksum traceability; it is not a complete source-component SBOM, per-file license map, redistribution approval, stable release asset, or supported installer. Do not re-host or advertise the candidate as clean-installable. P12 still needs source/build-component mapping for the enabled Mesa features, complete license notices, independent review, a durable Bionic build source, and a clean-install replay. No package was installed, downloaded, or modified during this audit.

A later read-only sample at 2026-10-24 15:37 UTC reported CPU 56.1°C, GPU 48.3°C, HTP 50.3°C, battery 42.56°C, `socd=82.0°C`, and `MemAvailable=4,131,412 KiB`. The SoC remained above the 70°C qualification guard, so the multi-case inference suite was not started.
