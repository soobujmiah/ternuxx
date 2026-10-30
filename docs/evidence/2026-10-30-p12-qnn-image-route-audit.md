# P12 QNN image-generation route and AAR audit

**Date:** 2026-10-30

Phase: `P12`
**Scope:** clarify the requested QNN 2.29 runtime artifact, check published metadata, and determine whether current Ternuxx Native Termux can install/use it. Research only: no AAR/model downloaded, no device inference run, and no release asset created.

## Findings

1. **Version naming:** Qualcomm's [QNN API revision history](https://docs.qualcomm.com/nav/home/general_api_version_history.html?product=924033590759186372) maps API 2.29.0 to QAIRT SDK 2.39.0. API 2.29 is backward compatible with earlier releases and ABI-compatible with 2.28/2.28.1. Thus "QNN 2.29 AAR" is ambiguous; likely Maven coordinate: com.qualcomm.qti:qnn-runtime:2.39.0, subject to matching the image model compiler/runtime.
2. **Artifact presence:** Maven Central's canonical POM returned HTTP 200 and declares AAR packaging, version 2.39.0, and license name Qualcomm AI Hub Model License, linked to Qualcomm's license PDF. Metadata-only HTTP HEAD for the AAR returned HTTP 200, Content-Length 56275752 (56,275,752 bytes), Last-Modified 2025-10-03. The AAR bytes were not fetched. Availability does not grant Ternuxx redistribution rights.
3. **License grant and restrictions:** the [Qualcomm AI Model Hub License](https://apigwx-aws.qualcomm.com/qsc/public/v1/api/download/software/licenses/ai_model_hub/v1/LICENSE.pdf) says downloading/using constitutes acceptance. Its grant covers use/copying to develop software applications and benchmarking, and permits distribution/sublicensing only in object-code form incorporated into the licensee’s software application; it expressly excludes standalone distribution. It also prohibits reverse engineering/decompilation of object/compiled software and requires preserving proprietary notices. Qualcomm’s [SDK page](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk) separately links a Product License Agreement and warns that additional terms may apply. This audit records the clause text but does not determine how a Ternuxx package fits that agreement.
4. **Integration shape:** current source has no Android Gradle project, AndroidManifest.xml, Gradle wrapper, or AAR file. The [ExecuTorch QNN HTP test APK example](https://github.com/pytorch/executorch/blob/main/examples/qualcomm/qnn-htp-test/README.md) packages QNN libraries in APK jniLibs, sets app-private ADSP_LIBRARY_PATH, and declares libcdsprpc.so with Android uses-native-library. It checks backend/session access, not a full image workload; its device list does not include SM8735. This is a packaging example, not Ternuxx qualification.
5. **Product boundary:** Ternuxx AI is a Native Termux shell/Python service. An AAR cannot simply be added to the shell runtime installer. An Android APK/provider bridge or another app-private boundary must be chosen and implemented before this route can be tested.

## Qualification and release decision

- Do not bundle this AAR in the current shell installer or publish it as a Ternuxx release asset.
- Do not fetch or use the AAR until the licensee reviews and accepts Qualcomm’s AI Model Hub License. The agreement appears to permit object-code distribution only when incorporated into a software application, not a standalone AAR/runtime bundle; obtain legal review for the intended Ternuxx packaging boundary.
- If choosing an Android route, first implement a minimal SM8735 HTP session probe and record Android API, target SDK, SELinux context, QNN API/SDK, HTP architecture, output and telemetry. Backend creation alone is not model qualification.
- Then qualify the complete text-to-image pipeline: model/asset hashes, graph placement, independent output checks, latency, memory, thermal samples, cancellation/restart and failures. Compare CPU and available GPU under controlled conditions.
- Keep this gate separate from chat llama.cpp qualification. The reproducible chat candidate and external LAI/Ternux tests do not close the image-generation gate.

## Sources

- [Qualcomm QNN API revision history](https://docs.qualcomm.com/nav/home/general_api_version_history.html?product=924033590759186372)
- [Maven Central POM for qnn-runtime 2.39.0](https://repo.maven.apache.org/maven2/com/qualcomm/qti/qnn-runtime/2.39.0/qnn-runtime-2.39.0.pom)
- [Maven Central AAR for qnn-runtime 2.39.0](https://repo.maven.apache.org/maven2/com/qualcomm/qti/qnn-runtime/2.39.0/qnn-runtime-2.39.0.aar) (metadata HEAD only; binary not downloaded)
- [Qualcomm AI Model Hub License PDF](https://apigwx-aws.qualcomm.com/qsc/public/v1/api/download/software/licenses/ai_model_hub/v1/LICENSE.pdf)
- [Qualcomm SDK and Product License Agreement link](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk)
- [ExecuTorch QNN HTP test APK README](https://github.com/pytorch/executorch/blob/main/examples/qualcomm/qnn-htp-test/README.md)

## Evidence limits

This audit verifies published version mapping, Maven metadata and source packaging shape. It does not interpret the Qualcomm license, establish redistribution permission, test the AAR, access the owner's external image model, prove this AAR works on SM8735, implement an Android app, or qualify image quality/performance/thermal behavior.

## Evidence

This report clarifies that QNN API 2.29 maps to QAIRT SDK 2.39.0, records the published Maven Central AAR/POM metadata, and documents why an Android AAR does not integrate directly into the current Native shell runtime. It records the license grant/restrictions while leaving license acceptance, Ternuxx packaging interpretation, and image-workload qualification open.
