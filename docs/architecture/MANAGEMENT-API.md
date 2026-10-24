# Management API

Ternuxx exposes one local management service for Native Termux operations. The CLI and TUI call it directly, the GTK client uses a narrow local bridge, and the Web UI uses an authenticated loopback adapter. The caller label is diagnostic metadata, not authentication.

The service rejects unknown operations and validates typed arguments. HTTP sessions receive only explicitly granted capabilities. Mutating operations require the applicable preview and exact plan ID. No endpoint accepts arbitrary shell commands, caller-provided environment maps, unrestricted file paths, or ADB forwarding. The sole file-path handoff is the read-only directory-tree action: one selected regular file or directory below Native HOME, no symlink traversal, fixed argv, depth/entry/output bounds, and filenames only.

Cron clients submit form-level typed create values to `cron.jobs.mutation.preview`. The shared service generates registry IDs and ownership metadata, applies safe defaults, validates the schedule, and stores the exact plan for later confirmation. Supported schedule types are `cron` expressions, fixed `interval`s, daily or specific `calendar` entries, and `one_time` UTC-offset datetimes. CLI, TUI, Web, and GTK use this same mutation path.

The shared service includes selected Native and Debian PRoot operations. Client coverage is not uniform; use the [capability matrix](CAPABILITY-MATRIX.md) for per-client reach and the source modules below for the current typed contract. The prior Native-only contract snapshot is preserved in [historical API documentation](../history/MANAGEMENT-API-pre-native-only-2026-10-24.md).

The Web adapter binds to loopback. Browser choices are Android or installed Native Termux browsers. Debian operations are dispatched through the Native-hosted service; the Web UI does not connect directly to the guest.
