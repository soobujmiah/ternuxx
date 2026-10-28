# Native Termux-এ Ternuxx ইনস্টল নির্দেশিকা

Ternuxx Native Termux-কে হোস্ট ও নিয়ন্ত্রণ স্তর হিসেবে ব্যবহার করে; চাইলে এর মাধ্যমে আলাদা Debian PRoot পরিবেশ পরিচালনা করা যায়। Native প্যাকেজ ও Debian পরিবেশের প্রস্তুতি আলাদা পূর্বরূপ এবং নিশ্চিতকরণের মাধ্যমে হয়।

## ইনস্টল

Termux-এ X11 প্যাকেজ-উৎস চালু করে Git ইনস্টল করুন। এরপর Ternuxx সংগ্রহস্থল নামিয়ে প্যাকেজ পরিকল্পনা দেখুন:

```sh
pkg update && pkg install x11-repo git && pkg update
git clone https://github.com/soobujmiah/ternuxx.git "$HOME/ternuxx"
cd "$HOME/ternuxx"
```

প্রিভিউ-ভিত্তিক ইনস্টলার দিয়ে `tx` কমান্ডটি Native Termux-এ যুক্ত করুন। এটি `$PREFIX/bin/tx`-এ একটি ছোট শিম বসায়, যা এই সংগ্রহস্থলের কোড চালায়:

```sh
python3 scripts/cli_entrypoint.py preview
python3 scripts/cli_entrypoint.py apply --yes --plan-id PLAN_ID
tx help
```

শিমটি `$HOME/ternuxx` পথের চেকআউট চালায়। প্যাকেজ ও নির্ভরতার পরিবর্তন পর্যালোচনা করে কেবল সংরক্ষিত পরিকল্পনার পরিচিতি দিয়ে প্রয়োগ করুন:

```sh
tx install preview --verbose
tx install apply --yes --plan-id PLAN_ID
```

এই পরিকল্পনায় প্যাকেজ অপসারণ বা হালনাগাদ হয় না। Ternuxx নিজে হালনাগাদ করতে:

```sh
tx install update preview
tx install update apply --yes --plan-id PLAN_ID
```

হালনাগাদ পরিকল্পনা প্যাকেজ অপসারণ, আগের সংস্করণে ফেরা, অথবা Termux-এর সরকারি প্যাকেজ-উৎসের বাইরের পরিবর্তন প্রত্যাখ্যান করে। ডেস্কটপের জন্য Android-এ উপযুক্ত Termux:X11 অ্যাপ আলাদাভাবে ইনস্টল করতে হবে।

## প্রথম পরীক্ষা ও ডেস্কটপ

```sh
tx help
tx guides
tx doctor
tx info
```

Android-এ Termux:X11 অ্যাপ খুলে Native ডেস্কটপ চালু করুন:

```sh
tx start
```

পর্দাভিত্তিক ব্যবস্থাপনার জন্য `tx tui`, `tx web` অথবা `tx mng center` চালান। কোন কাজের বোতাম বা নির্দেশ পাওয়া যাবে, তা মাধ্যমভেদে আলাদা হতে পারে। বিস্তারিত [সক্ষমতার তালিকা](../docs/architecture/CAPABILITY-MATRIX.md)-তে।

## SSH ও পুনরুদ্ধার

`tx ssh inspect` Native SSH-এর অবস্থা দেখায়। পরিচালিত SSH সেবার প্রতিটি চালু, বন্ধ বা পুনরারম্ভের আগে পূর্বরূপ ও নিশ্চিতকরণ লাগে। Ternuxx-এর পরিচালিত সেবা স্থানীয় সংযোগ-দ্বার 8023-এ চলে; অন্য Native SSH কনফিগারেশন Ternuxx পরিচালনা করে না।

`tx backup`, `tx recovery` এবং `tx checkpoint` Native অবস্থার ব্যাকআপ ও পুনরুদ্ধারে সহায়তা করে। পরিবর্তনের আগে লক্ষ্য ও পরিকল্পনা যাচাই করুন। Ternuxx যৌথ সংরক্ষণস্থান খোঁজে না বা নির্বিচারে ফাইল পরিচালনা করে না।

## ঐচ্ছিক Debian PRoot

ঐচ্ছিক পরিচালিত Debian বা Ubuntu guest সেটআপ/পরিবর্তন করতে Native Termux-এর সংযুক্ত terminal-এ unified command চালান:

```sh
tx install proot
```

Distro, guest account, desktop ও app selector-এ বাছাই করে নির্দিষ্ট package plan পর্যালোচনা ও নিশ্চিত করুন। সরাসরি বাছাইয়ের জন্য `tx install proot debian xfce` বা `tx install proot ubuntu xfce` চালান। কেবল fresh-rootfs review/apply চাইলে `tx proot setup fresh-preview --user USER` এবং এরপর exact plan দিয়ে `tx proot setup fresh-install --yes --plan-id PLAN_ID` ব্যবহার করুন। `--sudo-mode passwordless` শুধু guest-এর ভেতরে NOPASSWD sudo দেয়।

আগে `tx proot status` দিয়ে Native `proot`/`proot-distro` ও Debian পরিবেশের তালিকা দেখুন। নতুন Debian পরিবেশের জন্য নির্দিষ্ট ব্যবহারকারীর নামসহ পূর্বরূপ তৈরি করুন, লক্ষ্য ও ডিস্ক-ছবির নির্দিষ্ট SHA-256 পরিচিতি যাচাই করুন, তারপর শুধু সেই পরিকল্পনা প্রয়োগ করুন:

```sh
tx proot setup fresh-preview --user USER --sudo-mode passwordless --desktops xfce,lxqt
tx proot setup fresh-install --yes --plan-id PLAN_ID
```

প্রস্তুতির সময় `sudo`-র গোপন সংকেত গোপন-লেখা ঘরে দিন; নির্দেশে বা ফাইলে রাখবেন না। আগে থেকে থাকা পরিবেশ ইনস্টলার প্রতিস্থাপন করে না। Debian-এর নির্দেশ-সারি ও ডেস্কটপ Native Termux থেকেই চালান: `tx db` এবং `tx pgui`।

## ঐচ্ছিক স্থানীয় কৃত্রিম বুদ্ধিমত্তা

`tx ai status` দিয়ে মডেল ও Termux-পরিচালিত চালনা-পরিবেশ দেখুন। CPU-তে অনুমানের জন্য `tx ai run --backend cpu` চালান। Vulkan ব্যবহার করতে আগে `tx ai devices` দিয়ে যন্ত্র দেখুন, তারপর `tx ai run --backend vulkan` চালান। মডেলের সব স্তর GPU-তে পাঠানোর প্রমাণ না মিললে Vulkan কাজ ব্যর্থ হয়। পরীক্ষামূলক NPU পথ `tx ai run --backend npu` কেবল SM8735/HTP0-তে চলে এবং CPU-তে নীরবে ফিরে যায় না; পরীক্ষিত ছোট নির্দেশে এটি CPU-র চেয়ে ধীর ছিল। GPU/NPU-র ফল নির্দিষ্ট যন্ত্র ও কাজের জন্য; এগুলো সাধারণ সমর্থন বা প্রকাশযোগ্যতার নিশ্চয়তা নয়।

## সীমাবদ্ধতা

বর্তমান যন্ত্র আগে থেকেই সাজানো; তাই এটি নতুন যন্ত্রে একইভাবে কাজ করার প্রমাণ নয়। প্যাকেজের সংস্করণ বদলাতে পারে, আর সংরক্ষিত পূর্বরূপ ইন্টারনেটবিহীন প্যাকেজ-ভাণ্ডার নয়। CPU/Vulkan/HTP-তে সীমিত কাজের পরীক্ষা হয়েছে; দীর্ঘসময় তাপ ও স্মৃতি-ব্যবহার, পরিষ্কার ইনস্টল-উৎস, বিস্তৃত যন্ত্র-সমর্থন, প্রত্যাবর্তন এবং প্রকাশের উপযোগিতা আলাদা যাচাই চায়।

## ঐচ্ছিক Native অ্যাপ

আলাদা বাছাইকৃত তালিকায় htop, tmux ও tree আছে। `tx app list` দিয়ে দেখুন; এরপর নির্দিষ্ট ইনস্টল পরিকল্পনা পূর্বরূপে দেখে প্রয়োগ করুন। tree ইনস্টল থাকলে `tx app run directory-tree HOME_PATH` Native HOME-এর ভেতরের নির্দিষ্ট পথের নাম-তালিকা দেখায়। এটি যৌথ সংরক্ষণস্থান বা ফাইলের বিষয়বস্তু পড়ে না। বিস্তারিত [সফটওয়্যার তালিকা](../docs/SOFTWARE-CATALOG.md)-তে।
