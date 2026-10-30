# P12 QNN chhobi-toiri path ebong AAR porjalochona

**Tarikh:** 2026-10-30

Phase: `P12`
**Poridhi:** onurodh kora QNN 2.29 runtime artifact-er version, package metadata, ebong bortoman Ternuxx Native Termux eta install/byabohar korte pare kina ta porjalochona. Shudhu gobeshona: AAR/model download, device inference, ba release asset toiri hoyni.

## Pawa tothyo

1. **Version-er ortho:** Qualcomm-er [QNN API revision history](https://docs.qualcomm.com/nav/home/general_api_version_history.html?product=924033590759186372)-te API 2.29.0-er shathe QAIRT SDK 2.39.0-er mil dekhano. API 2.29 ager release-gulor shathe backward-compatible ebong 2.28/2.28.1-er shathe ABI-compatible. Tai "QNN 2.29 AAR" namti osposto; sambhabyo Maven coordinate holo com.qualcomm.qti:qnn-runtime:2.39.0, tobe image model-er compiler/runtime-er shathe milate hobe.
2. **Artifact-er uposthiti:** Maven Central-er POM HTTP 200 diyeche; sekhane AAR packaging, version 2.39.0 ebong Qualcomm AI Hub Model License-er nam o license PDF link ache. AAR-er metadata-only HTTP HEAD request HTTP 200, Content-Length 56275752 (56,275,752 byte), Last-Modified 2025-10-03 diyeche. AAR-er mul byte download hoyni. Maven Central-e thaka Ternuxx-ke punorbitoroner odhikar dey na.
3. **License-er onumoti o sima:** [Qualcomm AI Model Hub License](https://apigwx-aws.qualcomm.com/qsc/public/v1/api/download/software/licenses/ai_model_hub/v1/LICENSE.pdf)-e bola ache download/byabohar korle license grohon kora hoy. Software application toiri ebong benchmarking-er jonno byabohar/copy korar onumoti deya hoy; distribution/sublicense shudhu license-grohonkarir software application-er shathe jukto object-code akare, standalone distribution noy. Object/compiled software reverse-engineer ba decompile kora nishedh, ebong proprietary notice rakhte hoy. Qualcomm-er [SDK page](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk)-eo Product License Agreement link o otirikto sharter sotorkota ache. Ei porjalochona license-er dhara record kore, kintu Ternuxx packaging-e dhara-ti kibhabe projojjo ta ainogoto bhabe nirdharon kore na.
4. **Integration-er dhoron:** source-e Android Gradle project, AndroidManifest.xml, Gradle wrapper ba AAR file nei. [ExecuTorch QNN HTP test APK udahorone](https://github.com/pytorch/executorch/blob/main/examples/qualcomm/qnn-htp-test/README.md) QNN library APK jniLibs-e rakhe, app-private ADSP_LIBRARY_PATH set kore, ebong Android uses-native-library diye libcdsprpc.so ghoshona kore. Eta backend/session access porikkha kore, puro image workload noy; device talikay SM8735 nei. Eta packaging udahoron, Ternuxx qualification noy.
5. **Ponno simana:** Ternuxx AI holo Native Termux shell/Python service. AAR shell runtime installere sorasori jog kora jay na. Ei route porikkhar age Android APK/provider bridge ba onno app-private simana nirbachon o bastobayon korte hobe.

## Joggotar o release siddhanto

- Bortoman shell installer-e AAR bundle koro na, Ternuxx release asset hisebeo prokash koro na.
- License-grohonkarir AI Model Hub License pora o grohon kora chara AAR download/byabohar koro na. Chuktite standalone AAR/runtime bundle-er onumoti nei; shudhu software application-er moddhe object-code distribution-er kotha ache. Ternuxx packaging boundary-r jonno ainogoto porjalochona nao.
- Android route nile prothome SM8735-e chhoto HTP session probe bastobayon koro; Android API, target SDK, SELinux context, QNN API/SDK, HTP architecture, output o telemetry record koro. Shudhu backend toiri howa model qualification noy.
- Tarpor puro text-to-image pipeline qualify koro: model/asset hash, graph placement, swadhin output check, latency, memory, thermal sample, cancellation/restart o failure. Niyontroto obosthay CPU o upolobdho GPU-r shathe tulona koro.
- Ei gate chat llama.cpp qualification theke alada. Reproducible chat candidate ba bahirer LAI/Ternux test image-generation gate pass koray na.

## Sutro

- [Qualcomm QNN API revision history](https://docs.qualcomm.com/nav/home/general_api_version_history.html?product=924033590759186372)
- [qnn-runtime 2.39.0 Maven Central POM](https://repo.maven.apache.org/maven2/com/qualcomm/qti/qnn-runtime/2.39.0/qnn-runtime-2.39.0.pom)
- [qnn-runtime 2.39.0 Maven Central AAR](https://repo.maven.apache.org/maven2/com/qualcomm/qti/qnn-runtime/2.39.0/qnn-runtime-2.39.0.aar) (shudhu metadata HEAD; binary download hoyni)
- [Qualcomm AI Model Hub License PDF](https://apigwx-aws.qualcomm.com/qsc/public/v1/api/download/software/licenses/ai_model_hub/v1/LICENSE.pdf)
- [Qualcomm SDK ebong Product License Agreement link](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk)
- [ExecuTorch QNN HTP test APK README](https://github.com/pytorch/executorch/blob/main/examples/qualcomm/qnn-htp-test/README.md)

## Pro-maner simaboddhota

Ei porjalochona prokashito version mapping, Maven metadata ebong source packaging dhoron nischit kore. Eta Qualcomm license-er ainogoto byakhya, punorbitoroner odhikar, AAR porikkha, malik-er external image model poridorshon, ei AAR SM8735-e kaj kore kina, Android app bastobayon, ba image-er gunoman/performance/thermal joggota proman kore na.

## Evidence

Ei protibedone QNN API 2.29-er shathe QAIRT SDK 2.39.0-er mapping, Maven Central AAR/POM metadata, ebong Android AAR keno bortoman Native shell runtime-e sorasori jog hoy na ta record kora hoyeche. License-er onumoti/sima record kora hoyeche; license grohon, Ternuxx packaging-er byakhya ebong image workload qualification ekhono omimangshito.
