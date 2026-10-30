# P12 অভ্যন্তরীণ প্রার্থী হস্তান্তর যাচাইকারী

পর্যায়: `P12`

**অবস্থা:** বাস্তবায়ন ও স্থানীয় পরীক্ষা সম্পন্ন। ডিভাইস যোগ্যতা যাচাইয়ের আগে মালিকের দেওয়া সম্পূর্ণ অভ্যন্তরীণ প্রার্থী ডিরেক্টরি পরীক্ষা করে এই উপকরণ। এটি artifact ডাউনলোড, হস্তান্তর পরিবর্তন, runtime স্থাপন বা release অনুমোদন করে না।

## যাচাইয়ের নিয়ম

`python3 tools/package_snapdragon_release.py verify-candidate --candidate-dir PATH` নির্দিষ্ট সম্পূর্ণ ফাইলসমষ্টি চায়। অনুপস্থিত বা অতিরিক্ত ফাইল, symbolic link, নিয়মিত ফাইল নয় এমন বা খালি ফাইল, ত্রুটিপূর্ণ বা না-মেলা সম্পূর্ণ প্যাকেজের SHA-256 তালিকা, না-মেলা archive `SHA256SUMS`, এবং archive ও manifest-এর অসামঞ্জস্য থাকলে এটি ব্যর্থ হয়। এটি যাচাইকৃত archive ও manifest-এর সঙ্গে দুইটি build-এর পুনরুৎপাদনযোগ্যতার নথি মেলায়, toolchain, source-input ও submodule-এর নথি যাচাই করে এবং দুইটি SPDX নথি পড়ে। ফলাফলে package/file সংখ্যা ও লাইসেন্স পরিচয়ের সারাংশ থাকে; অমীমাংসিত `NOASSERTION`/`NONE` দাবিও দেখানো হয়।

যাচাই সফল হলেও ফলাফলে সবসময় `distribution_cleared: false` থাকে। এটি শুধু অখণ্ডতা ও build-নথি যাচাই করে। মালিক/আইনি পর্যালোচনা, উৎস-স্বীকৃতি, স্থাপন এবং নির্দিষ্ট ডিভাইসে inference যোগ্যতা আলাদা শর্ত।

Actions workflow পুনরুৎপাদনযোগ্যতার নথি তৈরির পর `CANDIDATE.SHA256SUMS` তৈরি করে এবং অভ্যন্তরীণ candidate আপলোডের আগে এই যাচাই চালায়। archive-এর আগের `SHA256SUMS` আলাদা থাকে এবং শুধু archive-টিকে যাচাই করে।

## যাচাইয়ের ফল

- `python3 -m py_compile tools/package_snapdragon_release.py`: সফল।
- `python3 -m unittest tests.test_package_snapdragon_release`: **১০টি সফল**; synthetic candidate, সঠিক ফাইলসমষ্টি, পরিবর্তিত নথি, ত্রুটিপূর্ণ SPDX এবং archive checksum অমিলের পরীক্ষা অন্তর্ভুক্ত।
- `git diff --check`: সফল।

এগুলো স্থানীয় উপকরণ ও নমুনা-নথির পরীক্ষা। প্রকৃত Actions artifact `artifacts/incoming`-এ দেওয়া হয়নি, তাই যাচাইকারীটি প্রকৃত candidate এখনো পরীক্ষা করেনি। কোনো ডিভাইস পরীক্ষা, তাপমাত্রা-যোগ্যতা, লাইসেন্স অনুমোদন, public release বা স্থিতিশীলতার দাবি করা হচ্ছে না।
