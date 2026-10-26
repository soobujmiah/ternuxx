# Installer reliability follow-up — 2026-10-26

Evidence class: Native Termux source review and isolated fixture/PTY tests. No live
package installation, guest replacement, service control or Android setting change.

The owner reported a post-Native-package `KeyError: changed`. The real shim returns
an `ok/data` envelope; the guided caller previously assumed a flat result. A real
preview/apply/reinstall fixture now covers this boundary. Human summaries replace
the shim JSON preview while exact plan IDs remain internal.

Owner-approved additions: bounded transport retry/verified-cache reuse and reviewed
Native resume; default shared management tools with separate service activation;
bootstrap/docs now with artifact packaging in roadmap; session lock, storage/package
preflight and redacted failure diagnostic, preserving existing sessions/guests.

The fixed terminal frame shares one alternate screen with keyboard selection and
restores terminal state. Guest credentials are collected before bulk installation
and passed by a private FD. Shared clients use an allowlisted authenticated installer
handoff, preserving Termux external-app opt-in and showing a manual command fallback.

Local full-suite observation: 1,258 tests ran, with two import errors because local
PyYAML is absent; remaining tests passed. Focused installer/frame/credential/lock and
retry tests pass. CI installs declared development requirements and owns the complete
suite result in generated repository status. C syntax was checked against installed
GTK/VTE headers. Physical reinstall, visual terminal acceptance, Android intent,
rendered clients, actual playback and GPU workloads remain owner/device checks.
