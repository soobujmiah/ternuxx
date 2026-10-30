# P12 Snapdragon HTP candidate artifact নিরীক্ষা

পর্যায়: `P12`

**অবস্থা:** `40962919123` run-এর অভ্যন্তরীণ Actions artifact ২০২৬-১০-৩০ তারিখে ব্যক্তিগত project handoff directory `artifacts/incoming`-এ ডাউনলোড করা হয়েছে। archive, manifest, reproducibility record ও SPDX প্রতিবেদন পরীক্ষা করা হয়েছে। এই artifact থেকে কোনো runtime স্থাপন বা inference করা হয়নি।

## Artifact পরিচয় ও পরীক্ষা

- Candidate নাম: `ternuxx-p12-htp-reproducible-candidate-40962919123`; artifact ID `12936224523`; Actions run সফল; মেয়াদ শেষ `2027-01-27T22:04:01Z`।
- Archive আকার: 49,219,753 bytes; SHA-256: `f1a6f9ade2dd6b31503bf9b12c87c92a63ef6b043ffb318bf4a4e10692156b29`।
- নির্দিষ্ট upstream source: llama.cpp `b11849`, commit `0ae0e1976670fac25f4e0ed864df30021accc764`।
- `sha256sum -c artifacts/incoming/SHA256SUMS`: সফল।
- `python3 tools/package_snapdragon_release.py verify --archive ... --manifest ...`: সফল; runtime file ২৩টি।
- দুই build-এর নথিতে archive SHA-256 একই এবং `license_and_device_release_gates_closed: false`।
- ডাউনলোড করা bundle-এর জন্য স্থানীয় checksum receipt তৈরির পর পুরো candidate verifier সফল হয়েছে। Actions artifact-টি `CANDIDATE.SHA256SUMS` তৈরির workflow পরিবর্তনের আগের। স্থানীয় receipt ডাউনলোড করা sidecar-গুলোকে নথিভুক্ত করে; এটিকে Actions-তৈরি স্বাক্ষর বা provenance attestation বলা হচ্ছে না।

## SPDX ফল ও সীমাবদ্ধতা

দুইটি SPDX নথিই SPDX 2.3 হিসেবে পড়া যায়। Source SBOM-এ package ২২৭টি ও file ১০২টি; package এবং file-এর সব license দাবি `NOASSERTION` (package-এর ৪৫৪টি field-দাবি ও file-এর ২০৪টি দাবি)। Runtime SBOM-এ package ১টি ও file ২২টি; এখানেও `NOASSERTION` অমীমাংসিত (package-এর ২টি field-দাবি ও file-এর ৪৪টি দাবি)। অখণ্ডতা যাচাই এসব দাবির নিষ্পত্তি বা পুনর্বিতরণের অনুমতি দেয় না। Verifier-এ `distribution_cleared: false` থাকে।

Candidate এখনো অভ্যন্তরীণ; এটি public installer-এ যুক্ত নয়। এর ২৩টি runtime file ব্যক্তিগত project-এর আলাদা probe directory-তে খোলা হয়েছে; app runtime path-এ নয়। Candidate binary-এর `--list-devices` কমান্ড exit 0 দিয়ে Adreno OpenCL এবং `HTP0: Hexagon`—দুটিই দেখিয়েছে। HTP-এর জন্য tool 0 MiB free দেখিয়েছে; এটিকে probe-এর হুবহু ফল হিসেবে রাখা হয়েছে, memory capacity-এর মাপ হিসেবে ব্যাখ্যা করা হয়নি। কোনো inference শুরু হয়নি। বিস্তারিত: [candidate device discovery](2026-10-30-p12-htp-candidate-device-discovery.json)।

২০২৬-১০-৩০ ০১:২৫:৫২ UTC-তে সর্বশেষ guarded NPU preflight-এ CPU 53.2°C ও HTP 45.9°C ছিল; empirical launch ceiling যথাক্রমে 50°C ও 40°C। কোনো `llama-cli` process চলছিল না, inference শুরু হয়নি, thermal limit উপেক্ষা করা হয়নি; [preflight report](2026-10-30-p12-npu-candidate-preflight-1.json) দেখুন। নির্দিষ্ট output, সম্পূর্ণ offload, পুনরাবৃত্ত স্থিতিশীলতা, তাপমাত্রা আচরণ, rollback, clean-install, সম্পূর্ণ provenance/license পর্যালোচনা ও মালিকের release acceptance বাকি। পরের যোগ্যতা পরীক্ষার জন্য artifact এবং আলাদা probe runtime `artifacts/incoming`-এ রাখা হয়েছে; কোনোটিই Git-এ commit করা হয়নি।
