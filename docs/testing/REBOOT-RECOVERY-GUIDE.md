# Native Termux reboot and recovery guide

Ternuxx recovery runs in Native Termux. It records state and readiness; it does not reboot Android or resume work automatically. The owner must use Android's normal power controls for any reboot. Do not restart the device to test a code change or to make an incomplete checkpoint pass.

## Before a planned reboot

1. Keep the Termux app and current desktop open until you have saved work and checked the current [phase status](../PHASE-STATUS.md).
2. Read the current private recovery state with `tx reboot status` and `tx boot status`. Do not copy checkpoint IDs, nonces, boot IDs, credentials, or private logs into Git, screenshots, or chat.
3. If a dedicated reboot qualification has been approved, prepare a new unique test with `tx reboot prepare --test-id ID --baseline-json JSON`. The command previews a private `NOT_READY` record and asks for the exact phrase `CREATE REBOOT TEST RECORD`. For a reviewed automation flow, pass `--yes --plan-id ID` from the current preview. In JSON mode the command only previews; it never applies implicitly. Never reuse an old test ID. Preparing it does not authorize a reboot.
4. Use Android's normal power menu. Ternuxx must not call a shell reboot command.

## After Android starts

Open Native Termux directly and allow its startup hooks and services to settle. Check each result separately:

```sh
tx status --json
tx boot status
tx ssh inspect
tx reboot status
```

For a previously prepared, unique test, run `tx reboot verify TEST_ID`. Review its preview and type `VERIFY REBOOT TEST`; reviewed automation can use `--yes --plan-id ID` from the current preview. Then inspect `tx reboot resume-info TEST_ID`. Verification is evidence only. A changed boot ID, observer event, service status, and authenticated SSH check establish different facts; do not treat one as proof of the others. `NOT_READY`, `unknown`, or partial status means the gate remains open. Never invoke the boot observer manually to simulate Termux:Boot delivery.

Detailed reboot-test preparation and verification remain CLI-only. The TUI, Web and GTK checkpoint screens manage the simpler task checkpoint lifecycle; they do not collect the full reboot-test baseline. Web also has no grant for the broader `continuity.manage` capability. Keep this boundary until a dedicated scoped capability and complete owner-mediated forms exist in each client.

## If managed SSH is unavailable

Open the Termux app locally. Inspect the fixed service and its logs without changing the Android network or SSH settings:

```sh
sv status ternuxx-sshd
tail -n 60 "$HOME/.local/share/ternuxx/log/sshd-runit.log"
tail -n 60 "$HOME/.local/share/ternuxx/continuity/boot-logs/ternuxx-services.log"
```

Check the service configuration with `tx ssh inspect` and follow the exact preview/apply guidance from `tx ssh --help`. Do not enable wildcard listeners, replace credentials, or start a second daemon as a shortcut. Keep the current Termux session open while investigating.

## Current evidence and limits

The latest recorded owner-operated boot qualification is RB08, described in the [2026-10-22 postboot audit](../evidence/2026-10-22-p3-rb08-postboot-exit-audit.md). Its checkpoint remains `NOT_READY` because the automated observation did not capture managed-service health at the required time. That dated result does not prove current Android boot delivery, current SSH reachability, or readiness after a later reboot. A separate pre-Native-only procedure is preserved in [historical reboot notes](../history/REBOOT-RECOVERY-GUIDE-pre-native-only-2026-10-24.md).

No task resumes automatically. Keep application and workload recovery owner-mediated, and preserve current state and logs when reporting a failure. Debian PRoot recovery uses the current Ternuxx exact-preview session and setup procedures; historical guest-retirement instructions do not apply to the restored guest.
