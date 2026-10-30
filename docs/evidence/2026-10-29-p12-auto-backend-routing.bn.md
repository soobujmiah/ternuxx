# P12 স্বয়ংক্রিয় ইনফারেন্স ব্যাকএন্ড নির্বাচন

**পর্যবেক্ষণ:** ২০২৬-১০-২৯ ২২:২৭ UTC
**পরিধি:** Native Termux `tx ai run`-এর স্বয়ংক্রিয় ব্যাকএন্ড নির্বাচন
**অবস্থা:** নির্বাচন-ব্যবস্থা বাস্তবায়িত ও পর্যবেক্ষিত; মডেল ইনফারেন্স এখনো অযোগ্যতাপ্রাপ্ত

## প্রয়োজনীয় নির্বাচনক্রম

মালিকের নির্ধারিত স্বয়ংক্রিয় ক্রম হলো `SM8735 HTP0 → Vulkan GPU → CPU fallback`; CPU ডিফল্ট হবে না। `--backend cpu|vulkan|npu` দিয়ে নির্দিষ্ট পথ বাধ্যতামূলক করা যায়। ইনফারেন্সের আগে হার্ডওয়্যার নির্বাচন হয়। ইনফারেন্স শুরু হওয়ার পর ত্রুটি হলে নির্বাচিত ব্যাকএন্ডের নামসহ ত্রুটি ফেরে; নীরবে অন্য ব্যাকএন্ডে আবার চেষ্টা হয় না। এতে অফলোড ব্যর্থতা ও পুনরাবৃত্ত কাজ আড়াল হয় না।

Ternuxx-এর শেয়ার্ড সার্ভিসে এখন `inference.auto.run` আছে। এটি আগে HTP0 পরীক্ষা করে; HTP0 না থাকলেই শুধু Vulkan পরীক্ষা করে। llama.cpp যে প্রথম বৈধ Vulkan ডিভাইস জানায়, সেটি বেছে নেয়; সেটিও না থাকলে CPU বেছে নেয়। সফল ফলাফলে `backend_selection`-এ নির্বাচিত পথ, প্রোবের ত্রুটি এবং পুনরায় চেষ্টা না করার নীতি থাকে। CLI, TUI, Web এবং GTK-তে এই পথটি যোগ হয়েছে।

## Native Termux-এ সরাসরি পর্যবেক্ষণ

২০২৬-১০-২৯ ২২:২৭:১২ UTC-তে read-only status-এ SM8735-এর HTP0 এবং `b11849` runtime পাওয়া গেছে; Termux `llama-cpp` 0.7.0-ও আছে। Ternuxx-এর app-private model path-এ pinned Qwen3 0.6B Q4_0 মডেলটি অনুপস্থিত ছিল।

ডিফল্ট কমান্ড `printf '2 + 2 = ? reply with one digit' | bash tx ai run --max-tokens 1` `inference_failed` ফেরায় এবং জানায়: `Automatic routing selected npu; inference failed (InferenceError) and was not retried on another backend`। পরে নির্দিষ্ট `pgrep -x llama-cli` পরীক্ষায় কোনো process পাওয়া যায়নি। অর্থাৎ নির্বাচন HTP0 করেছে, কিন্তু মডেল অনুপস্থিতির কারণে ইনফারেন্স শুরু হয়নি; output, latency, offload, token rate, memory বা তাপমাত্রার ফল পাওয়া যায়নি। এটি মডেল-অনুপস্থিতি রক্ষার পরীক্ষা, HTP workload পরীক্ষা নয়।

## যাচাই

- `tests/test_ai_backend_selection.py`: অগ্রাধিকারক্রম, অকার্যকর device মান এবং CPU fallback fixture।
- `tests/test_management_service.py`: NPU/Vulkan/CPU dispatch এবং নির্বাচিত NPU ব্যর্থ হলে পুনরায় চেষ্টা না করা।
- `tests/test_terminal_ui.py`: TUI-তে পছন্দের ব্যাকএন্ড action।
- `tests/test_management_desktop_bridge.py`: GTK bridge route।
- `tests/test_management_http_runtime.py`: Web action ও authorization contract।
- Web script সংশোধনের পর cross-client focused run-এ **২৬০টি test পাস** করেছে; এর মধ্যে inline Web JavaScript syntax check আছে। `bash tests/test_cli_help.sh`, `py_compile` এবং `git diff --check`-ও পাস করেছে।
- প্রথম পূর্ণ suite run-এ **১,৩৫১টি test-এর মধ্যে একটি error** হয়েছিল: নতুন Web action-এ একটি অতিরিক্ত closing brace ছিল। সেটি সংশোধন করা হয়েছে।
- সংশোধনের পর `bash scripts/repo_test.sh` **২১৬.৯১৯ সেকেন্ডে ১,৩৫১টি test পাস** করেছে। `python3 -m tools.repo_knowledge verify` শূন্য finding জানিয়েছে; `python3 tools/doc_bridge.py check --strict --project-id ternuxx README.md` পাস করেছে।

## বাকি যাচাই

নিয়ন্ত্রিত CPU/HTP তুলনার আগে মালিক-অনুমোদিত Ternuxx private model path-এ মডেল থাকতে হবে। প্রকল্প নির্দেশে Ternuxx-কে shared `/sdcard` storage পড়তে নিষেধ করা হয়েছে; তাই সেখানে থাকা কোনো LAI মডেল দেখা হয়নি। ইনফারেন্স শুরুর আগে নতুন করে দুইটি thermal preflight sample পাস করতে হবে। এরপর সঠিক উত্তর, নির্দিষ্ট layer offload, model SHA-256, ব্যাকএন্ড, token সংখ্যা, সময়, process cleanup এবং sampled thermal/memory telemetry সংরক্ষণ করতে হবে।

নির্দেশিত installer-এ এখন CPU/Vulkan/HTP AI চালন-পরিবেশের একাধিক নির্বাচন আছে; যন্ত্র যাচাই অনুযায়ী বিকল্প দেখায়—SM8735-এ HTP, Native Vulkan যাচাই পাস করলে Vulkan, এবং CPU fallback। SM8735-এ HTP, অন্যথায় সমর্থিত হলে Vulkan, আর তাও না হলে CPU প্রাথমিক নির্বাচন। HTP বাছলে CPU fallback-এর প্যাকেজও যোগ হয়। Installer নির্দিষ্ট upstream b11849 archive ব্যবহার করে; Ternuxx-এর নিজস্ব নির্মিত অভ্যন্তরীণ প্রার্থী স্থাপন করে না। দেখুন [চালন-পরিবেশ স্থাপন-নির্বাচন প্রতিবেদন](2026-10-29-p12-runtime-install-selection.md)। নতুন যন্ত্রে স্থাপন ও পূর্বাবস্থায় ফেরানো এখনও যাচাই করা হয়নি। অভ্যন্তরীণ প্রার্থীর যন্ত্র-যোগ্যতা ও বিতরণ-অনুমতি বাকি; Mesa-র উৎস-ইতিহাস ও জনসমক্ষে প্রকাশও অমীমাংসিত। ছবি-তৈরি/QNN যোগ্যতা যাচাই আলাদা কাজ; এই chat inference route তা অন্তর্ভুক্ত করে না।

## ২০২৬-১০-৩০ তারিখে installer নির্বাচন পুনর্যাচাই

বর্তমান উৎস ও fixture পুনর্যাচাইয়ে নির্দেশিত installer-এর একাধিক চালন-পরিবেশ নির্বাচনের বাস্তবায়ন নিশ্চিত হয়েছে। `tests.test_install_wizard`, `tests.test_install_master` এবং `tests.test_npu_inference` মিলিয়ে **৫০টি পরীক্ষা পাস** করেছে। এতে নির্বাচন ও স্থাপন-পরিকল্পনার fixture যাচাই হয়; নতুন যন্ত্রে প্যাকেজ লেনদেন, চালন-পরিবেশ নামানো, অথবা HTP মডেল-গণনা প্রমাণিত হয় না।

## প্রমাণ

- বাস্তবায়ন: `lib/ai_backend_selection.py`, `lib/management_service.py` এবং `lib/ai.sh`।
- Client integration: `lib/terminal_ui.py`, `lib/management_web_ui.html`, `apps/management-center/management-center.c` এবং `scripts/management_desktop_bridge.py`।
- Test: `tests/test_ai_backend_selection.py`, `tests/test_management_service.py`, `tests/test_terminal_ui.py`, `tests/test_management_http_runtime.py`, `tests/test_management_desktop_bridge.py`, `tests/test_management_center_ui_contract.py` এবং `tests/test_cli_help.sh`।
- Live observation শুধু Native HTP0/runtime status এবং উপরে বর্ণিত মডেল-অনুপস্থিতির refusal পর্যন্ত সীমিত; কোনো live workload চালানো হয়নি।
