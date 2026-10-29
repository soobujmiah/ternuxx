# P12 Snapdragon HTP runtime build প্রস্তুতি

Phase: `P12`

**অবস্থা:** বাস্তবায়ন প্রস্তুত; GitHub Actions workflow এখনো চালানো হয়নি, তাই কোনো build artifact বা reproducibility ফল নেই। Public release তৈরি করা হয়নি।

## Build-এর নিয়ম

Manual workflow `.github/workflows/p12-htp-reproducible-build.yml` শুধু `main` ref-এ চলবে এবং আলাদা Ubuntu 24.04 runner-এ Android ARM64 Snapdragon runtime দুবার build করবে। এটি upstream `b11849` tag fetch করে; tag-টি `0ae0e1976670fac25f4e0ed864df30021accc764` commit-এ না মিললে থেমে যাবে। [Upstream release page](https://github.com/ggml-org/llama.cpp/releases/tag/b11849)-এ source tag-টি verified signed commit হিসেবে দেখানো হয়েছে। Workflow-টি pinned [upstream release workflow](https://github.com/ggml-org/llama.cpp/blob/b11849/.github/workflows/release.yml)-এর Android Snapdragon CMake preset ও relative install-RPATH ব্যবহার করে।

Snapdragon Android toolchain `ghcr.io/snapdragon-toolchain/arm64-android:v0.8`-এর OCI index digest `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf` দিয়ে pin করা। GitHub Actions ও SBOM action-ও পূর্ণ commit-এ pin করা। Artifact packager upstream source commit-এর সময় ব্যবহার করে নির্ধারিত সময়ের tar archive বানায়; এতে শুধু `llama-cli`, সরাসরি `.so` runtime file এবং upstream MIT `LICENSE` থাকবে। Symlink, অনিরাপদ/অপ্রত্যাশিত path, দরকারি HTP/OpenCL library অনুপস্থিতি, এবং installer-এর extraction সীমার বেশি package প্রত্যাখ্যান হয়। Manifest-এ source/build input এবং প্রতিটি runtime file-এর size/hash থাকে। Source ও packaged runtime—দুটির জন্য SPDX SBOM তৈরি হবে।

Verify job দুই archive ও manifest আলাদাভাবে যাচাই করে, তারপর archive-এর SHA-256 হুবহু মেলে কি না নিশ্চিত করে। সফল হলে ৯০ দিনের internal Actions candidate upload হবে; GitHub Release হবে না। Build candidate device test ও distribution review পাস না করা পর্যন্ত `lib/npu_inference.py`-এর installer pin অপরিবর্তিত থাকবে।

## Local যাচাই ও সীমা

- `python3 -m unittest tests.test_package_snapdragon_release`: **৫টি পাস** (একই tar bytes তৈরি, archive tampering ধরা, file ও directory symlink প্রত্যাখ্যান, pinned-source manifest যাচাই)।
- `python3 -m unittest discover -s tests`: remote `main`-এর clean worktree-তে **১,৩৩৯টি test, ৪টি failure**। চারটিই পুরোনো installer/CLI-help assertion (Native GPU help এবং Debian/PRoot command/help wording); কোনোটিই P12 packager-এর নয়।
- `python3 -m py_compile tools/package_snapdragon_release.py tests/test_package_snapdragon_release.py`: পাস।
- PyYAML দিয়ে workflow YAML ও pinned image/matrix গঠন যাচাই; `git diff --check` পাস।
- GitHub build এখনো চালানো হয়নি। Cross-run reproducibility, Android install, model correctness, thermal/sustained qualification, license clearance বা public release—কোনোটিই প্রমাণিত নয়।

## বাকি release gate

প্রথমে manual workflow চালিয়ে source/runtime SPDX output ও দুই-build comparison পর্যালোচনা করতে হবে। তারপর নির্দিষ্ট model দিয়ে Ternuxx-owned candidate device test: সঠিক output, সম্পূর্ণ HTP offload, failure/restart এবং telemetry; GPU/CPU fallback ও setup selection qualify; Mesa এবং সম্পূর্ণ dependency-license/provenance review শেষ; Ternuxx project license ও clean-install/release acceptance মীমাংসা করতে হবে। QNN SD1.5 image route-এর independent oracle ও Qualcomm license acceptance আলাদা gate; এই chat runtime build সেগুলো বন্ধ করে না।

## Evidence

- Workflow: `.github/workflows/p12-htp-reproducible-build.yml`।
- Deterministic package tool: `tools/package_snapdragon_release.py`।
- Local package tests: `tests/test_package_snapdragon_release.py`।
- Clean-worktree full-suite command: `python3 -m unittest discover -s tests`।
