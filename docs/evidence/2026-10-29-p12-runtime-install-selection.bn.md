# P12 Native AI runtime ইনস্টল নির্বাচন

Phase: `P12`

**অবস্থা:** source বাস্তবায়ন ও fixture যাচাই পাস করেছে; clean-device installer apply এখনো যাচাই হয়নি।

## নির্বাচনব্যবস্থা

Guided workstation installer-এ CPU, Vulkan এবং experimental HTP0 runtime-এর multi-select আছে; device probe সমর্থন করলেই প্রাসঙ্গিক পছন্দ দেখায়। SM8735 হলে default HTP0; নইলে Native GPU probe পাস করলে Vulkan; অন্যথায় CPU। ব্যবহারকারী একাধিক runtime নিতে পারেন, অথবা স্পষ্টভাবে কোনো AI runtime না-ও নিতে পারেন। HTP0 নিলে CPU fallback-এর জন্য Termux `llama-cpp` package-ও স্বয়ংক্রিয়ভাবে নির্বাচিত হয়। Vulkan নিলে `llama-cpp` ও `llama-cpp-backend-vulkan`—দুটিই অন্তর্ভুক্ত হয়।

HTP0 নির্বাচিত হলে installer একক approval-এর আগে combined workstation plan-এ exact pinned runtime preview সংরক্ষণ করে। Preview-তে b11849 upstream asset, SHA-256, MIT notice, archive size, extraction সীমা এবং network download লাগবে কি না থাকে। Reviewed plan-এ archive সংরক্ষণ ও runtime extraction-এর storage estimate থাকে। Combined plan অনুমোদনের পরেই apply হয় এবং apply-এর সময় preview পুনরায় যাচাই হয়। বর্তমান installer pinned MIT upstream asset-ই নামায়; Ternuxx-এর reproducible candidate এখনো internal-only এবং installer সেটি থেকে runtime আনে না।

## যাচাই

- `tests.test_install_wizard`, `tests.test_install_master` এবং `tests.test_npu_inference`: **৪৬টি পাস**।
- Master-plan coordinator fixture নিশ্চিত করে HTP-এর exact preview approval-এর আগে নেওয়া হয়, apply approval-এর পরেই হয়, আর প্রত্যাখ্যান করলে HTP download বা install হয় না।
- `bash -n lib/install_wizard.sh lib/install_master.sh lib/phases.sh`, `python3 -m py_compile lib/install_master_plan.py lib/npu_inference.py` এবং `git diff --check` পাস করেছে।
- প্রথম পূর্ণ repository run-এ omitted-component তালিকা নিয়ে একটি পুরোনো প্রত্যাশা ব্যর্থ হয়েছিল। সেটি সংশোধনের পর `bash scripts/repo_test.sh` **২৪৪.৯৮৬ সেকেন্ডে ১,৩৫৬টি পরীক্ষা পাস করেছে**। প্রাথমিক ব্যর্থতা ও সংশোধনের তথ্য এই নথিতে রাখা হয়েছে।
- এই fixture test-এ package transaction, runtime download বা নতুন device install করা হয়নি।

## বাকি যাচাই

নতুন Native install-এ প্রতিটি runtime selection চালিয়ে actual Termux package transaction, HTP archive integrity, backend probe এবং rollback/recovery যাচাই করতে হবে। এরপর controlled model inference-এর আগে নতুন করে দুইটি thermal preflight sample পাস করতে হবে। Internal Ternuxx HTP build candidate-এ device qualification এখনো বাকি; Ternuxx-এর নিজস্ব source-এর license হিসেবে owner GPL-3.0-or-later বেছে নিয়েছেন; third-party runtime redistribution, provenance ও device qualification এখনো বাকি।

## প্রমাণ

- English version: [2026-10-29-p12-runtime-install-selection.md](2026-10-29-p12-runtime-install-selection.md)।
- Installer: `lib/install_wizard.sh`, `lib/install_master.sh`, `lib/install_master_plan.py` এবং `lib/phases.sh`।
- Test: `tests/test_install_wizard.py`, `tests/test_install_master.py` এবং `tests/test_npu_inference.py`।
