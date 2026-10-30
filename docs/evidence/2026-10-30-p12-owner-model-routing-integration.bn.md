# আগে থেকে থাকা মডেল দিয়ে P12 পরিচালিত চালনা

**তারিখ:** ২০২৬-১০-৩০
**পর্যায়:** `P12`
**পরিধি:** Native Ternuxx CPU, Vulkan, HTP, CLI, TUI, Web ও GTK-তে মডেল নির্বাচন

## পরিবর্তন

স্থানীয় inference allowlist-এ মালিকের নির্দিষ্ট করে দেওয়া আগের Qwen2.5 1.5B Instruct Q4_0 GGUF মডেল যুক্ত হয়েছে। এর নির্দিষ্ট অবস্থান `/sdcard/LAI/models/qwen2.5-1.5b-instruct-q4-0.gguf`, প্রত্যাশিত আকার 1,066,227,232 byte এবং প্রত্যাশিত SHA-256 `dcd819ff094852c38faba6873d8ff0c9d51eadb2844539e52042ae5d647bbfdb`। মডেলটি শুধু পড়া হয়; Ternuxx এটিকে নকল, নামানো, মোছা বা পাশে lock file লিখে না। ব্যবহারের আগে নির্দিষ্ট অবস্থান, সাধারণ ফাইলের ধরন, সঠিক আকার ও SHA-256 যাচাই করা হয়। Ternuxx-এর আগের Qwen3 মডেলই পূর্বনির্ধারিত থাকে।

`tx ai run --model qwen2.5-1.5b-instruct-q4_0` দিয়ে CPU, Vulkan, NPU অথবা স্বয়ংক্রিয় চালনার জন্য এই মডেল বেছে নেওয়া যায়। Shared service অনুমোদিত মডেল-পরিচয় যাচাই করে; CLI, TUI, Web, GTK ও desktop bridge একই service-এ নির্বাচিত পরিচয় পাঠায়। স্বয়ংক্রিয় চালনায় অগ্রাধিকার HTP, Vulkan, তারপর CPU। নির্বাচিত চালনা ব্যর্থ হলে নীরবে অন্য backend-এ পুনরায় চেষ্টা করা হয় না। ব্যবস্থাপনা তালিকায় মালিকের মডেলকে নির্দিষ্ট অবস্থানের শুধু-পাঠযোগ্য মডেল হিসেবে বর্ণনা করা হয়েছে।

## এই worktree-তে যাচাই

- `python3 -m unittest tests.test_management_service tests.test_cpu_inference`: ৯৪টি পরীক্ষা উত্তীর্ণ।
- `python3 -m unittest tests.test_install_wizard tests.test_launch_commands`: ৩৭টি পরীক্ষা উত্তীর্ণ।
- `bash tests/test_cli_help.sh`: উত্তীর্ণ।
- `python3 -m py_compile lib/cpu_inference.py lib/npu_inference.py lib/management_service.py lib/terminal_ui.py scripts/management_desktop_bridge.py`: উত্তীর্ণ।
- Catalog পরিবর্তনের আগে `git diff --check` উত্তীর্ণ হয়েছিল; চূড়ান্ত পরিবর্তন ও পূর্ণ test run-এর পর আবার চালাতে হবে।

এগুলো কৃত্রিম তথ্যভিত্তিক পরীক্ষা ও source যাচাই। এই worktree থেকে shared-storage মডেল দেখা বা পড়া হয়নি এবং inference চালানো হয়নি। যন্ত্রে পরীক্ষা করতে হলে `CURRENT_STATE.md`-এর তাপমাত্রা-ভিত্তিক পূর্বপরীক্ষার নিয়ম মানতে হবে; কোনো backend-কে স্থিতিশীল বা প্রকাশের জন্য যোগ্য বলা যাচ্ছে না।

## বাকি যাচাই

পরিবর্তনগুলোকে বর্তমান `origin/main`-এর সঙ্গে rebase করে পূর্ণ test ও CI gate পাস করাতে হবে এবং integration-এর আগে পর্যালোচনা করতে হবে। সঠিক output, runtime ও মডেলের অখণ্ডতা, যন্ত্রের telemetry এবং নিয়ন্ত্রিত CPU/GPU/HTP তুলনাসহ যন্ত্রে যোগ্যতা যাচাই বাকি। মডেল বিতরণের শর্ত যাচাই করা হয়নি; এই পরিবর্তন শুধু মালিকের আগের স্থানীয় ফাইল ব্যবহার করে। Ternuxx-এর নিজস্ব ও নির্ভরশীল runtime-এর license, installer-এ একাধিক runtime বাছাই, পরিচ্ছন্ন installation পুনরাবৃত্তি, signing এবং release অনুমোদনও আলাদা বাকি ধাপ।
