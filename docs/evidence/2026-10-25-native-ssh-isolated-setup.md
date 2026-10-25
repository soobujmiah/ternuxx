# Native Ternuxx SSH isolated setup and authentication

**Date:** 2026-10-25 (UTC)
**Evidence class:** direct Native Termux runtime
**Repository:** `soobujmiah/ternuxx`, checkout `$HOME/ternuxx`

The first-time `tx ssh deploy` preview proposed only a Ternuxx-owned config at `$HOME/.config/ternuxx/sshd_recovery.conf` and the fixed `ternuxx-sshd` Runit service. The validated policy was loopback `127.0.0.1:8023`, `AuthenticationMethods publickey`, password and keyboard-interactive authentication disabled, root login disabled, and `$HOME/.ssh/ternuxx-keys/authorized_keys`. OpenSSH `sshd -t` and `sshd -T` validation passed, and the preview observed port 8023 available.

The exact preview was applied. The operation response initially reported a generic failure because the setup readiness code expected probe status `connected`, while the diagnostic's actual successful SSH protocol status is `ssh_banner`. A subsequent read-only `tx ssh inspect --json` verified the config syntax and effective policy, Runit status `running`, service process identity `verified`, and loopback SSH banner response. The setup readiness check and its regression fixture now accept the diagnostic's `ssh_banner` status.

A Native Ed25519 client recovery key was generated through preview/apply under the private `.ssh/ternuxx-keys` directory; the private key remains on-device with mode `0600` and was not copied into evidence. Its public key was enrolled through a separate exact preview/apply into the dedicated Ternuxx authorized-key file. `tx ssh keys-list --json` reported one valid key and verified that configured file. A strict-host-key local SSH test pinned the existing Ed25519 host public key in a temporary `known_hosts` file, authenticated with the new client key to `127.0.0.1:8023`, ran `id -un`, matched the Native account, and removed the temporary host file.

Before and after hashes were unchanged for the owner-managed `$PREFIX/etc/ssh/sshd_config` (`e67c23a449d32c881d76becc523b97742288317758205c431ead2371e2ab4bd1`) and `$HOME/.ssh/authorized_keys` (empty file SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). Ternuxx did not alter the owner-managed SSH config or shared authorized-key file. `tx doctor --json` reports the managed service as pass. The separate owner-managed SSH config remains wildcard-bound with password authentication enabled and is outside Ternuxx's management scope.

Android denied kernel TCP listener inspection through procfs and netlink, so listener-to-process correlation and external reachability remain unknown. The successful local authenticated SSH command is direct evidence of a usable loopback access path; the diagnostic's banner probe alone is not authentication evidence.
