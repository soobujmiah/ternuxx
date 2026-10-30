# P12 Snapdragon HTP runtime build প্রস্তুতি

Phase: `P12`

**অবস্থা:** প্রথম GitHub Actions চেষ্টায় pinned source checkout ও source SPDX তৈরি হয়েছে, কিন্তু CMake ভুল করে Ternuxx workspace root থেকে চালানোয় workflow fail করেছে। কোনো runtime artifact বা reproducibility ফল তৈরি হয়নি; upstream `llama.cpp` directory থেকে চালানোর fix `main`-এর `c2a4a5903cab69c6417023d32f0b74fbc7bfc352` commit-এ আছে। প্রথম corrected HTP run [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123) চলছে; candidate artifact এখনো নেই। Public release তৈরি করা হয়নি।

## Build-এর নিয়ম

Manual workflow `.github/workflows/p12-htp-reproducible-build.yml` শুধু `main` ref-এ চলবে এবং আলাদা Ubuntu 24.04 runner-এ Android ARM64 Snapdragon runtime দুবার build করবে। এটি upstream `b11849` tag fetch করে; tag-টি `0ae0e1976670fac25f4e0ed864df30021accc764` commit-এ না মিললে থেমে যাবে। [Upstream release page](https://github.com/ggml-org/llama.cpp/releases/tag/b11849)-এ source tag-টি verified signed commit হিসেবে দেখানো হয়েছে। Workflow-টি pinned [upstream release workflow](https://github.com/ggml-org/llama.cpp/blob/b11849/.github/workflows/release.yml)-এর Android Snapdragon CMake preset ও relative install-RPATH ব্যবহার করে।

Snapdragon Android toolchain `ghcr.io/snapdragon-toolchain/arm64-android:v0.8`-এর OCI index digest `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf` দিয়ে pin করা। GitHub Actions ও SBOM action-ও পূর্ণ commit-এ pin করা। Artifact packager upstream source commit-এর সময় ব্যবহার করে নির্ধারিত সময়ের tar archive বানায়; এতে শুধু `llama-cli`, সরাসরি `.so` runtime file এবং upstream MIT `LICENSE` থাকবে। Symlink, অনিরাপদ/অপ্রত্যাশিত path, দরকারি HTP/OpenCL library অনুপস্থিতি, এবং installer-এর extraction সীমার বেশি package প্রত্যাখ্যান হয়। Manifest-এ source/build input এবং প্রতিটি runtime file-এর size/hash থাকে। Source ও packaged runtime—দুটির জন্য SPDX SBOM তৈরি হবে।

Verify job দুই archive ও manifest আলাদাভাবে যাচাই করে, তারপর archive-এর SHA-256 হুবহু মেলে কি না নিশ্চিত করে। সফল হলে ৯০ দিনের internal Actions candidate upload হবে; GitHub Release হবে না। Build candidate device test ও distribution review পাস না করা পর্যন্ত `lib/npu_inference.py`-এর installer pin অপরিবর্তিত থাকবে।

## Local যাচাই ও সীমা

- `python3 -m unittest tests.test_package_snapdragon_release`: **৫টি পাস** (একই tar bytes তৈরি, archive tampering ধরা, file ও directory symlink প্রত্যাখ্যান, pinned-source manifest যাচাই)।
- Clean `main`-এর প্রথম suite-এ **১,৩৩৯টি test-এর মধ্যে installer/CLI-help-এর ৪টি পুরোনো assertion fail** করেছিল। বর্তমান help/output-এর সঙ্গে শুধু ওই assertion-গুলো মিলিয়ে rerun-এ **১,৩৩৯টি test ২০১.৫৮৯ সেকেন্ডে পাস** করেছে।
- ওই ৪টি focused test এবং `bash tests/test_cli_help.sh` পাস করেছে।
- GitHub suite run [`40962905557`](https://github.com/soobujmiah/ternuxx/actions/runs/40962905557)-এ আরেকটি host-dependent assertion ধরা পড়ে: PRoot graphics test ধরে নিয়েছিল physical device-এ KGSL আছে, তাই সবসময় Zink বেছে নেবে। test-এ প্রত্যাশিত Zink preference explicit mock করা হয়েছে। পরের GitHub run [`40963452566`](https://github.com/soobujmiah/ternuxx/actions/runs/40963452566)-এ ১,৩৩৯টি Python test পাস করলেও shell CLI-help gate-এর পুরোনো `tx ai run` syntax assertion ব্যর্থ হয়েছে; বর্তমান command syntax অনুযায়ী assertion স্থানীয়ভাবে ঠিক করা হয়েছে, GitHub rerun বাকি।
- `python3 -m py_compile tools/package_snapdragon_release.py tests/test_package_snapdragon_release.py`: পাস।
- PyYAML দিয়ে workflow YAML ও pinned image/matrix গঠন যাচাই; `git diff --check` পাস।
- GitHub run [`40962133386`](https://github.com/soobujmiah/ternuxx/actions/runs/40962133386) দুই runner-এই CMake configure ধাপে fail করেছে: Ternuxx workspace root-এ `CMakePresets.json` খুঁজেছে। `c2a4a5903cab69c6417023d32f0b74fbc7bfc352` commit-এ preset চালানোর আগে workflow `upstream` directory-তে যায়। GitHub run-এ কোনো artifact নেই; runtime archive তৈরি হয়নি। পরের run [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123)-এ একটি runner compile ও package ধাপে পৌঁছেছে, অন্যটি compile করছে; দুই-build hash comparison ও SBOM verification শেষ না হওয়া পর্যন্ত candidate যাচাইকৃত নয়। Cross-run reproducibility, Android install, model correctness, thermal/sustained qualification, license clearance বা public release—কোনোটিই প্রমাণিত নয়।

## Native Termux-এর বর্তমান অবস্থা

বর্তমান device session-এ read-only check-এ দেখা গেছে:

- `bash tx ai npu status`: SM8735-এ HTP0 available; runtime release `b11849`, এবং silent fallback বন্ধ।
- `bash tx ai status`: Termux `llama-cpp` 0.7.0 available, কিন্তু Ternuxx-এর private model path-এ configured Qwen3 model file নেই; তাই CPU inference চালানো হয়নি।
- `bash tx ai devices`: Vulkan `Vulkan0`, Adreno 825 enumerate করেছে; probe-এর হিসাবে মোট ৮,৪২৫ MiB এবং free ৫,০০৩ MiB। এটি শুধু device enumeration; GPU inference workload চালানো হয়নি।

এগুলো বর্তমান Native runtime observation; failed/retried CI build এবং পুরোনো inference evidence থেকে আলাদা। এগুলো নতুন build candidate, sustained performance বা thermal behavior qualify করে না।

এরপর default guard রেখে inference ছাড়া নতুন thermal/resource preflight দুবার পাস হয়েছে (`cpu/gpu/htp <60 C`, battery `<45 C`, SoCD `<70 C`, `MemAvailable >=2048 MiB`); কোনো active `llama-cli` process ছিল না। দুই sample-এই `thermal_limits_ignored: false` এবং `will_start_inference: false` ছিল:

| Sample (UTC) | CPU C | GPU C | HTP C | Battery C | SoCD C | MemAvailable KiB | ফল |
|---|---:|---:|---:|---:|---:|---:|---|
| 2026-10-29 22:09:51.615 | 48.0 | 39.2 | 41.2 | 38.68 | 12.0 | 5,707,888 | পাস |
| 2026-10-29 22:10:03.465 | 48.8 | 39.6 | 40.8 | 38.69 | 12.0 | 5,704,104 | পাস |

এই ছোট sample দুটি controlled test শুরুর জন্য চাওয়া preflight count পূরণ করে; এগুলো inference, দীর্ঘমেয়াদি thermal stability বা OEM thermal limit প্রমাণ করে না। Ternuxx-এর private Qwen3 model অনুপস্থিত, তাই controlled CPU/HTP workload এখনো pending।

## বাকি release gate

সংশোধিত manual workflow আবার চালিয়ে source/runtime SPDX output ও দুই-build comparison পর্যালোচনা করতে হবে। তারপর নির্দিষ্ট model দিয়ে Ternuxx-owned candidate device test: সঠিক output, সম্পূর্ণ HTP offload, failure/restart এবং telemetry; GPU/CPU fallback ও setup selection qualify; Mesa এবং সম্পূর্ণ dependency-license/provenance review শেষ; Ternuxx-এর নিজস্ব source-এর জন্য owner-selected GPL-3.0-or-later scope প্রয়োগ করতে হবে এবং clean-install/release acceptance সম্পন্ন করতে হবে। QNN SD1.5 image route-এর independent oracle ও Qualcomm license acceptance আলাদা gate; এই chat runtime build সেগুলো বন্ধ করে না।

## Evidence

- Workflow: `.github/workflows/p12-htp-reproducible-build.yml`।
- Deterministic package tool: `tools/package_snapdragon_release.py`।
- Local package tests: `tests/test_package_snapdragon_release.py`।
- Clean-worktree full-suite command: `python3 -m unittest discover -s tests`।
