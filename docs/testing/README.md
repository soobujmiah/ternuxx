# Testing and qualification

Run repository checks from Native Termux. The suite uses private fixture state and does not require closing the Termux app, active desktop, or Native services.

## Repository checks

```sh
env -u LD_LIBRARY_PATH bash scripts/repo_test.sh
bash tests/test_cli_help.sh
python3 tools/audit_documents.py --check
git diff --check
```

The repository suite covers lifecycle ownership/refusal, package planning, state and recovery, service wrappers, authorization, HTTP sessions, and management clients. A green fixture suite does not prove Android boot delivery, visible GUI acceptance, physical audio, GPU/NPU workloads, or clean-install reproducibility.

## Read-only device checks

```sh
./tx status --json
./tx doctor --json
DISPLAY=:1 ./tx doctor --graphics --json
```

Doctor is read-only. Graphics probes use the selected display and report the exact failure or detection evidence; they do not start/stop the desktop or claim acceleration from hardware discovery alone. See the [current device profile](reports/2026-10-24-native-profile-25053RT47C.md) and [known limitations](KNOWN-LIMITATIONS.md).

## Web and client checks

The authenticated Web client binds to loopback. Its session/reconnect behavior, HTTP authorization, typed operation handling, and JavaScript syntax are covered by repository tests. For visible review, start the Web client through `tx guides` or `tx web`, use the displayed loopback URL in a Native browser, then check login, resource search, operation descriptions, confirmation details, result messages, reload/reconnect, and narrow-screen layout. Do not expose the session URL or secret in screenshots or logs. CLI, TUI, Web, and GTK operations should match the shared catalog and authorization contract; see the [client capability matrix](../architecture/CAPABILITY-MATRIX.md).

## Private Native monitor replay

With Native Runit tools already installed, run `python3 tools/check_monitor_service.py --interval-check`. It starts only a fixed fixture service under a private temporary root and separate monitoring state. It verifies registration, idle policy, two Linux-only ticks, unchanged workstation policy, and exact fixture-service cleanup. It does not stop existing services or alter Android monitoring settings. Android Activity/focus behavior and cold-boot delivery require separate qualification.

## Evidence and release limits

[Device compatibility](DEVICE-COMPATIBILITY.md), [CPU](CPU-BASELINE.md), [GPU](GPU-ACCELERATION.md), and [NPU](NPU-ACCELERATION.md) separate detection from workload qualification. Use the [report template](reports/REPORT-TEMPLATE.md) for new tests. Synthetic tests are not physical-device evidence. Reboot or installed-package changes require a separately planned maintenance window and must preserve the active Termux session.

For repeatable, guarded Native CPU/Vulkan/HTP calls, use the [Native accelerator qualification procedure](NATIVE-ACCEL-QUALIFICATION.md). Its JSON report records the observed backend, layer offload, resource samples, and cleanup checks; each physical-device run still needs its own dated evidence record.
