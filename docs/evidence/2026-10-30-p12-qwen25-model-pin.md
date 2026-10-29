# P12: pin a 1–2 GB chat-model candidate

Date: 2026-10-30
Phase: `P12`

**Status:** pinned model is downloaded into Ternuxx private storage and exercised on CPU, Vulkan, and HTP. HTP has one passing call; CPU and the three-call Vulkan qualification did not pass thermal guards. No backend is stable or release-ready.

## Artifact pin

- Publisher/repository: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`
- Repository revision: `91cad51170dc346986eccefdc2dd33a9da36ead9`
- File: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Exact size: `1,117,320,736` bytes
- SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`
- Declared license: Apache-2.0
- Ternuxx target: private `$HOME/.local/share/ternuxx/models/`; no shared-storage path is used.

The official model repository exposes this revision, file, license, and metadata. The pinned revision URL prevents model download from silently following a mutable `main` branch. The file is 1.12 GB decimal, within the requested 1–2 GB range.

## Security review and limits

Hugging Face's current file metadata reports the aggregate file status as safe, JFrog as a safe GGUF, and VirusTotal as 0/74 detections. The same metadata also contains a Protect AI `PAIT-GGUF-100` finding, while the overall status remains `safe`; the public rule material reviewed does not explain this exact rule number. The embedded template inspected through the official repository metadata is a short role/string formatting template without Python object-introspection operators. The unresolved scanner finding is retained for review; these observations are not a security guarantee.

The model was downloaded only to `$HOME/.local/share/ternuxx/models/`, size `1,117,320,736` bytes, mode `0600`. SHA-256 matched the pin before the controlled test sequence and again after it. Two thermal preflight samples passed before each backend attempt; the reports retain per-run samples and process/RSS data. The conservative CPU/GPU/HTP limit was 60°C, battery 45°C, SoC 70°C, and minimum available memory 2,048 MiB; these are test guards, not OEM-rated limits.

## Native runtime qualification evidence

- **CPU:** qualification was cancelled after 4.497 seconds when CPU telemetry reached 61.2°C. Peak observed `llama-cli` RSS was 1,186,356 KiB; no output was accepted, and no process remained. This is not a CPU baseline result.
- **Vulkan:** first call passed with the known-answer check, Vulkan0, and full 29/29 layer offload. The backend-reported inference time was 3.426 seconds; peak process RSS was 271,644 KiB. The next call was cancelled at 60.4°C CPU, so the requested three-call sequence failed.
- **HTP / b11849:** one call passed with HTP0, all 29/29 layers on HTP, silent fallback disabled, and the known-answer check. Backend-reported inference time was 4.335 seconds; runner wall time was 7.259 seconds and peak process RSS was 283,112 KiB. HTP reached 59.0°C during the call, below but close to the 60°C guard. A single passing call does not establish stability.

The three machine-readable runner reports are [CPU](2026-10-30-p12-cpu-qualification.json), [Vulkan](2026-10-30-p12-vulkan-qualification.json), and [HTP](2026-10-30-p12-htp-qualification.json). The initial runner schema retained answer verification and output word count but omitted exact generated text; this evidence limitation is fixed in the runner for future runs. Model hash was rechecked after all three attempts and still matches the pinned digest. No thermal override was used.

## Source changes and checks

The app's single pinned model spec now names this exact Qwen2.5 artifact. Model download continues to require a current exact preview plus `DOWNLOAD`; the file will stay in Ternuxx's private model directory. CPU/GPU/NPU documentation and the third-party notice now distinguish this new, unqualified Q4_K_M artifact from historical Qwen3 Q4_0 and Qwen2.5 Q4_0 workload results.

`tests.test_cpu_inference`, `tests.test_npu_inference`, `tests.test_management_service`, `tests.test_management_catalog`, and `tests.test_terminal_ui`: **168 passed** (focused local suite). `tests.test_native_accel_qualify`: **18 passed** after adding exact-output retention, model/runtime integrity snapshots, and fail-closed verification coverage. Full repository suite: `bash scripts/repo_test.sh` passed **1,362 tests** in **245.137 seconds** after integrity-report hardening. Repo knowledge verification reported 0 findings, strict README bridge check passed, and `git diff --check` passed. These are code/repository checks and do not qualify device runtime stability.

## Primary sources

- [Official Qwen model repository at pinned revision](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9)
- [Official Hugging Face model metadata API](https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF)
- [Hugging Face malware scanning policy](https://huggingface.co/docs/hub/main/security-malware)
- [JFrog GGUF template security note](https://research.jfrog.com/model-threats/gguf-ssti/)
- [Palo Alto AI model-security rule guidance](https://docs.paloaltonetworks.com/prisma-airs/ai-supply-chain-security/ai-supply-chain-security/model-security-to-secure-your-ai-models/understanding-ai-model-security-rules)

Bengali version: [2026-10-30-p12-qwen25-model-pin.bn.md](2026-10-30-p12-qwen25-model-pin.bn.md).
