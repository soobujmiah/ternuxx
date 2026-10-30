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

পুনর্নির্মাণ এখনো বাকি। দরকারি প্রমাণ হলো: সংশোধনের পর main branch-এর আলাদা দুই run সফল হবে এবং যাচাইকৃত archive-এর SHA-256 মিলবে; প্রতিটি run-এ ভেতরের দুই builder-এর তুলনা ও পুরো candidate verifier pass করতে হবে।

## Release অবস্থা

আগের দুই archive-এর অখণ্ডতা যাচাই হয়েছে, তবে সংশোধিত build contract-এর যোগ্যতা এগুলো পায়নি। সর্বশেষ SPDX SBOM-এ `NOASSERTION` এখনো অমীমাংসিত। এই প্রতিবেদনে কোনো runtime-কে release-cleared বা app path-এ installed, কিংবা inference-যোগ্য বলা হচ্ছে না।
