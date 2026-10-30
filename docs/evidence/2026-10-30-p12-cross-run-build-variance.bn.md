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

Reproducible workflow এখন CLI-শুধু package চায়: `LLAMA_BUILD_SERVER=OFF`, `LLAMA_BUILD_UI=OFF` এবং `LLAMA_USE_PREBUILT_UI=OFF`। Ternuxx inference path-এ `llama-cli` চলে; `llama-server` ডাকা হয় না। Server/UI বন্ধ রাখলে পরিবর্তনশীল web-asset ডাউনলোড বাদ যায় এবং package থেকে অপ্রয়োজনীয় server library সরে যায়। Manifest-এ এই নির্দিষ্ট flag লেখা হয় এবং verifier তা বাধ্যতামূলক করে। Test নিশ্চিত করে workflow-এ অনির্দিষ্ট asset path আবার চালু না হয়।

এই পরিবর্তন এখনো পৃথক run-এর মধ্যে যোগ্যতা পায়নি। প্রয়োজনীয় প্রমাণ: পরিবর্তনের পর main branch-এ আলাদা দুইটি সফল workflow run-এর যাচাইকৃত archive SHA-256 একই হতে হবে। প্রত্যেক run-এ দুই স্বাধীন builder-এর মিল এবং সম্পূর্ণ candidate verifier-ও pass করতে হবে।

## Release অবস্থা

আগের দুই archive-এর অখণ্ডতা যাচাই হয়েছে, তবে সংশোধিত build contract-এর যোগ্যতা এগুলো পায়নি। সর্বশেষ SPDX SBOM-এ `NOASSERTION` এখনো অমীমাংসিত। এই প্রতিবেদনে কোনো runtime-কে release-cleared বা app path-এ installed, কিংবা inference-যোগ্য বলা হচ্ছে না।
