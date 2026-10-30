# P12 HTP runtime third-party notice audit

Date: 2026-10-30

Phase: `P12`

## Source and linkage scope

The upstream source was checked out at pinned llama.cpp commit `0ae0e1976670fac25f4e0ed864df30021accc764`; the recursive submodule inventory is empty. The archived runtime includes `libllama-common.so` and `libmtmd.so`. At this commit, `common/CMakeLists.txt` links cpp-httplib, nlohmann/json, and sheredom/subprocess.h. `tools/mtmd/CMakeLists.txt` links vendor/hash, miniaudio, stb, and sheredom/subprocess.h. The hash target compiles xxHash, SHA-1, and SHA-256 and includes rotate-bits code.

The source headers and license files state these terms: cpp-httplib MIT; xxHash BSD-2-Clause; rotate-bits MIT; SHA-1 and SHA-256 Public Domain; nlohmann/json MIT; sheredom/subprocess.h Unlicense; stb_image MIT or Unlicense; miniaudio MIT-0 or Unlicense. The project root `LICENSE` already carries the llama.cpp MIT text. These are recorded source facts, not a legal opinion. The Snapdragon toolchain container's own redistribution terms and the exact licensing conclusion for each linked binary remain unresolved.

## Change prepared

A deterministic notice collector reads those license texts and attributions from the pinned source tree and generates `THIRD_PARTY_NOTICES.txt`. The release package verifier requires that file for newly built candidates. The Native HTP installer selects and hashes the notice file when an archive provides it, while remaining compatible with the previously pinned upstream archive that lacks it. The SPDX normalizer records the notice file and binds its SHA-256 to the package manifest; it does not treat the notice collection as a single software license.

## Verification and limits

- The collector produced nine component notices from the exact pinned source checkout.
- 31 targeted tests passed across notice collection, package construction/SPDX normalization, and Native NPU runtime integrity.
- The new two-builder candidate has not yet been produced. The retained 23-file candidate predates this notice change and does not satisfy the new package requirement.
- Device inference remains blocked until two independent thermal preflight samples pass. The latest preflight (06:19:40 UTC) read CPU 49.2°C and HTP 43.2°C, failing the 40°C HTP launch ceiling. No runtime inference was run for this audit.
- This change does not apply the selected project root license to original project material; separately resolve Snapdragon toolchain terms, binary `NOASSERTION` findings, or release/device qualification.

## Evidence

The exact source was inspected locally; its CMake target links and the shipped `libllama-common.so` and `libmtmd.so` establish the notice scope above. The collector was executed against the pinned source checkout, and the targeted unittest command passed: `python3 -m unittest tests.test_collect_snapdragon_notices tests.test_package_snapdragon_release tests.test_npu_inference`.
