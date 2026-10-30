# P12 পৃথক build run-এ HTP archive-এর অমিল ও build input pin করা

পর্যায়: `P12`

**অবস্থা:** পৃথক run তুলনায় দেখা গেছে, প্রতিটি run-এর ভেতরে reproducible build সফল হলেও run-দুটির archive এক নয়। একই run-এর দুই builder-এর মিলের চেয়ে এটি শক্তিশালী যাচাই। একটি পরিবর্তনশীল বাহ্যিক UI input শনাক্ত হয়েছে এবং candidate workflow-এ সেটি বন্ধ করা হয়েছে; পরের পৃথক run-এর build দিয়ে সংশোধনটি নিশ্চিত করতে হবে।

## পর্যবেক্ষিত তুলনা

দুইটি Actions run-ই সফল হয়েছে এবং প্রতিটিতে দুইটি স্বাধীন builder-এর archive একই পাওয়া গেছে:

| Run | Archive SHA-256 | আকার | Source commit | Builder image |
|---|---|---:|---|---|
| [`40962919123`](https://github.com/soobujmiah/ternuxx/actions/runs/40962919123) | `f1a6f9ade2dd6b31503bf9b12c87c92a63ef6b043ffb318bf4a4e10692156b29` | 49,219,753 | `0ae0e1976670fac25f4e0ed864df30021accc764` | `sha256:e39e5e9c0957550a92c0de756b7556d81196c7c7f7328ed80de252bfb4878adf` |
| [`40985050416`](https://github.com/soobujmiah/ternuxx/actions/runs/40985050416) | `f2f15c869da065137078f4219a7ee8770816dda91a4d0c19b03ec07f2dc75bbb` | 49,219,269 | একই | একই |

Manifest-এর runtime তালিকায় একটি file অমিল: `lib/libllama-server-impl.so`—একটিতে 39,865,136 bytes, SHA-256 `a4ffc659d0b782911cd18e498cbebd8e4192cd00c8062df8d5634e39b0fb1544`; অন্যটিতে 39,865,608 bytes, SHA-256 `9fe009c09d5fef8b5e5e5f18df41dc59c48938e6a942e6ee5932333ad5b178ec`। ELF string-এ আলাদা hash-যুক্ত web-UI asset পাওয়া গেছে।

নির্দিষ্ট upstream [UI CMake config](https://github.com/ggml-org/llama.cpp/blob/0ae0e1976670fac25f4e0ed864df30021accc764/tools/ui/CMakeLists.txt)-এ prebuilt UI default-এ চালু। pinned [asset provisioner](https://github.com/ggml-org/llama.cpp/blob/0ae0e1976670fac25f4e0ed864df30021accc764/scripts/ui-assets.cmake) প্রথমে version-যুক্ত Hugging Face bucket, পরে `latest` চেষ্টা করে। Run log নিশ্চিত করে—দুই build-ই `b1` download করতে না পেরে `https://huggingface.co/buckets/ggml-org/llama-ui/resolve/latest/dist.tar.gz` থেকে ৭০টি asset embed করেছে। পৃথক run-এর অমিলের পর্যবেক্ষিত কারণ এটি। একই run-এর দুই job একই সময়কার `latest` পেয়ে যাওয়ায় আগের ভেতরকার তুলনায় এই সমস্যা ধরা পড়েনি।

## সংশোধিত build নিয়ম

Reproducible workflow-এ প্রথমে CLI-শুধু package-এর জন্য `LLAMA_BUILD_SERVER=OFF`, `LLAMA_BUILD_UI=OFF` এবং `LLAMA_USE_PREBUILT_UI=OFF` দেওয়া হয়। প্রথম post-change run [`40986902773`](https://github.com/soobujmiah/ternuxx/actions/runs/40986902773) দুই Android build-এই ব্যর্থ হয়: upstream-এ `LLAMA_BUILD_TESTS` চালু থাকায় server বন্ধ করার পরও server test target compile হয়; `mtmd.h` না পাওয়ার চারটি compile error আসে। কোনো candidate artifact তৈরি হয়নি।

পরের run [`40987954678`](https://github.com/soobujmiah/ternuxx/actions/runs/40987954678)-এ দুই builder-ই compile শেষ করলেও packaging ধাপে ব্যর্থ হয়। pinned upstream CMake-এ `tools/cli` কেবল `LLAMA_BUILD_SERVER` চালু থাকলে তৈরি হয়; server flag বন্ধ করায় দরকারি `llama-cli` executable-ও বাদ পড়ে। কোনো candidate artifact তৈরি হয়নি। পরের সংশোধনে upstream build switch চালু থাকবে, তবে UI, test, example ও unified app বন্ধই থাকবে; packager শুধু CLI ও প্রয়োজনীয় runtime library নেবে।

সংশোধিত workflow PR [#10](https://github.com/soobujmiah/ternuxx/pull/10) হিসেবে `5e3ff398d4fcf6dcd34fa86eab7f982ced03f194` commit-এ main branch-এ মিশেছে। main branch-এর run [`40989392795`](https://github.com/soobujmiah/ternuxx/actions/runs/40989392795)-এ দুই স্বাধীন build, একই run-এর দুই archive-এর byte-সমতা এবং candidate যাচাই সফল হয়েছে। ডাউনলোড করা archive-টিও স্থানীয়ভাবে সম্পূর্ণ যাচাই হয়েছে: SHA-256 `fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`, আকার ৪৫,৮৯৬,৯৩৮ byte, runtime file ২৩টি। source ও runtime SPDX নথিতে মোট ৪৫৬টি package-license দাবির নিষ্পত্তি হয়নি; verifier যথাযথভাবে `distribution_cleared=false` দেখিয়েছে।

দ্বিতীয়, পৃথক main-branch run [`41004311539`](https://github.com/soobujmiah/ternuxx/actions/runs/41004311539)-এও দুই স্বাধীন নির্মাণ, একই run-এর archive তুলনা এবং candidate-এর সম্পূর্ণ যাচাই সফল হয়েছে। ডাউনলোড করা archive-এর SHA-256 প্রথমটির সমান (`fde7c7c4643f4df8b38a437231c59dad4516ce7c7bb986971b110a7494b9e356`) এবং আকারও সমান (৪৫,৮৯৬,৯৩৮ byte)। দুই পৃথক run-এর archive স্থানীয় verifier দিয়ে যাচাই করা হয়েছে। এই নির্দিষ্ট source, workflow ও নির্মাণ-সরঞ্জামের জন্য পৃথক run-এ পুনরুৎপাদনযোগ্যতা প্রমাণিত; এতে যন্ত্রে inference-এর যোগ্যতা বা বিতরণের অনুমোদন প্রমাণিত হয় না।

## Release অবস্থা

সংশোধিত candidate পুনরুৎপাদনযোগ্য এবং অখণ্ডতা-যাচাইকৃত, তবে অভ্যন্তরীণ ব্যবহারের মধ্যেই সীমিত। উভয় SPDX SBOM-এ `NOASSERTION` লাইসেন্স-দাবি অমীমাংসিত; Ternuxx প্রকল্পের লাইসেন্স ও উৎস-পর্যালোচনাও বাকি। সংশোধিত candidate-টি পরিচালিত app runtime-এ বসানো বা inference দিয়ে যোগ্যতা যাচাই করা হয়নি। ২০২৬-১০-৩০ তারিখ ০৪:৫৪, ০৫:০০, ০৫:০৫ ও ০৫:১০ UTC-র চারটি সাম্প্রতিক (মোট নমুনা ৩–৬) শুধু-প্রাথমিক-যাচাই নমুনায় CPU/HTP ছিল যথাক্রমে ৫১.২/৪৪.৮°C, ৫০.০/৪৪.০°C, ৪৯.৬/৪৩.৬°C ও ৫০.০/৪৩.৬°C; চালুর সীমা ৫০/৪০°C। চারবারই inference শুরু হয়নি। Ternuxx-এর ব্যক্তিগত সংরক্ষণস্থলে Qwen2.5 1.5B Q4_K_M model আছে; SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`।

যাচাইকৃত candidate archive-টি `npu_inference.install_runtime` ব্যবহার করে অস্থায়ী, বিচ্ছিন্ন state directory-তে খোলা হয়েছে; পরীক্ষার প্রক্রিয়ায় archive-এর প্রত্যাশিত আকার, SHA-256 ও URL শুধু স্মৃতিতে candidate অনুযায়ী নির্ধারণ করা হয়েছিল এবং archive-টি আগে থেকেই স্থানীয় cache-এ রাখা হয়েছিল। Preview-তে network download লাগেনি; extraction ও `_runtime_valid` যাচাই সফল হয়েছে; কাজ শেষে অস্থায়ী directory মুছে গেছে। এতে শুধু installer-এর সঙ্গে archive-এর গঠন মেলার প্রমাণ পাওয়া যায়: চলমান managed runtime এখনো upstream b11849, production source এখনো upstream artifact-ই নেয়, এবং candidate দিয়ে যন্ত্রে inference হয়নি। স্থির ELF পরীক্ষা দেখিয়েছে `llama-cli` হলো Android 34/NDK r29-এর ELF64 AArch64 executable; HTP-এর পাঁচটি DSP module হলো ELF32 Qualcomm DSP6।
