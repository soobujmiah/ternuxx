# Native Termux Android thermal API access check — 2026-10-24

Phase: `P12`

## Scope

Read-only Native Termux capability check after repeated HTP sensor excursions. No Termux package was installed/upgraded, no system/vendor library was copied, and no service or desktop was changed. The one-shot C probe and its build output were kept in app-private HOME state.

## Observed results

- `termux-thermal-status` and `dumpsys` are unavailable in the current PATH. `termux-api` 0.60.0 and `termux-battery-status` are present; the latter returned battery health, temperature, voltage, and charge only, not CPU/GPU/HTP thermal status.
- Android's NDK header `$PREFIX/include/android/thermal.h` declares `AThermal_*` APIs. The default Termux compiler target is API 24, so those declarations are unavailable to that target. Setting the compile target to Android API 36 then failed to link the symbols from Termux's `$PREFIX/lib/libandroid.so`, which does not export them.
- The system `/system/lib64/libandroid.so` does export `AThermal_acquireManager`, `AThermal_getCurrentThermalStatus`, and `AThermal_getThermalHeadroom`. A private `dlopen("/system/lib64/libandroid.so")` probe failed before calling any API:

  ```text
  dlopen failed: cannot find "libbinder_ndk.so" from verneed[1] in DT_NEEDED list for "/system/lib64/libandroid.so"
  ```

- `cmd -l` lists `thermalservice`, but `timeout 3 cmd thermalservice help` produced no output and timed out with status 124. No read-only thermal-status command was verified through that interface.

Android documents `PowerManager.getCurrentThermalStatus()` from API 29 and the NDK `AThermal_getCurrentThermalStatus()` from API 30; the NDK headroom API starts at API 31. These app APIs describe a supported Android-side bridge, not a capability demonstrated for this Termux command process. See the [PowerManager reference](https://developer.android.com/reference/android/os/PowerManager) and [Android NDK Thermal reference](https://developer.android.com/ndk/reference/group/thermal).

## Qualification impact

The current Ternuxx Native CLI has no verified Android thermal-status/headroom bridge. Keep sysfs sensor values as dated observations and explicitly selected test guards only; they are not portable thermal limits or proof of throttling. Do not work around the app linker boundary by copying system libraries or forcing private dependencies into the Termux process. A future companion running inside an Android app context would need its own narrowly scoped design and verification. P12 remains open because HTP repeated-load qualification stopped at its guard and no device-level status bridge is available to interpret that reading.

## Evidence

- Compiler/linker: `clang --target=aarch64-linux-android36 ... -landroid` failed with undefined `AThermal_*` symbols from Termux's private libandroid.
- Runtime: a private C `dlopen` probe against `/system/lib64/libandroid.so` failed on missing `libbinder_ndk.so`; no thermal API call executed.
- Termux API: `termux-battery-status` succeeded; thermal-status command and `dumpsys` were unavailable.
