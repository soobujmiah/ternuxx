"""Default-deny capability policy for authenticated management adapters.

This module does not authenticate callers and is not a transport. An adapter
must establish a trusted session, then pass that session's explicit grants to
``authorize`` before dispatching an allowlisted operation.
"""
from __future__ import annotations

from collections.abc import Iterable


# One narrow capability per operation. New application operations must be
# reviewed here before any non-CLI adapter can expose them.
OPERATION_CAPABILITIES: dict[str, str] = {
    "installer.open": "software.manage",
    "management.catalog": "diagnostics.read",
    "proot.status": "diagnostics.read",
    "proot.setup.catalog": "diagnostics.read",
    "proot.setup.fresh.preview": "proot.install.manage",
    "proot.setup.fresh.apply": "proot.install.manage",
    "proot.sessions.list": "diagnostics.read",
    "proot.sessions.show": "diagnostics.read",
    "proot.sessions.health": "diagnostics.read",
    "proot.recovery.inspect": "diagnostics.read",
    "proot.recovery.reconcile.preview": "diagnostics.read",
    "proot.recovery.reconcile": "proot.session.manage",
    "proot.profiles.list": "diagnostics.read",
    "proot.profiles.show": "diagnostics.read",
    "proot.start.preview": "diagnostics.read",
    "proot.stop.preview": "diagnostics.read",
    "proot.start": "proot.session.manage",
    "proot.stop": "proot.session.manage",
    "proot.app.launch": "applications.launch",
    "proot.shortcuts.sync.preview": "diagnostics.read",
    "proot.shortcuts.sync.apply": "applications.shortcuts.manage",
    "proot.shortcuts.sync.rollback.list": "diagnostics.read",
    "proot.shortcuts.sync.rollback.preview": "diagnostics.read",
    "proot.shortcuts.sync.rollback.apply": "applications.shortcuts.manage",
    "proot.shortcuts.list": "diagnostics.read",
    "proot.shortcuts.preview": "diagnostics.read",
    "proot.shortcuts.apply": "applications.shortcuts.manage",
    "proot.guest.verify": "graphics.manage",
    "proot.setup.retire.preview": "proot.replay.manage",
    "proot.setup.retire.apply": "proot.replay.manage",
    "proot.setup.restore.preview": "proot.replay.manage",
    "proot.setup.restore.apply": "proot.replay.manage",
    "proot.setup.icd-migrate.preview": "proot.guest.manage",
    "proot.setup.icd-migrate.apply": "proot.guest.manage",
    "proot.setup.icd-migrate.rollback.preview": "proot.guest.manage",
    "proot.setup.icd-migrate.rollback.apply": "proot.guest.manage",
    "terminal.broker.status": "diagnostics.read",
    "terminal.broker.service.status": "diagnostics.read",
    "terminal.broker.service.install.preview": "proot.session.manage",
    "terminal.broker.service.install.apply": "proot.session.manage",
    "terminal.broker.service.start.preview": "proot.session.manage",
    "terminal.broker.service.start.apply": "proot.session.manage",
    "terminal.start.preview": "proot.session.manage",
    "terminal.start": "proot.session.manage",
    "terminal.attach": "proot.session.manage",
    "terminal.input": "proot.session.manage",
    "terminal.resize": "proot.session.manage",
    "terminal.output": "proot.session.manage",
    "terminal.detach": "proot.session.manage",
    "terminal.close.preview": "proot.session.manage",
    "terminal.close": "proot.session.manage",
    "management.logs.list": "diagnostics.read",
    "management.logs.read": "diagnostics.read",
    "graphics.provider.status": "diagnostics.read",
    "graphics.provider.verify": "graphics.manage",
    "graphics.provider.select": "graphics.manage",
    "inference.cpu.status": "diagnostics.read",
    "inference.gpu.status": "diagnostics.read",
    "inference.gpu.run": "ai.local.run",
    "inference.npu.status": "diagnostics.read",
    "inference.npu.runtime.preview": "diagnostics.read",
    "inference.npu.runtime.apply": "ai.local.manage",
    "inference.npu.run": "ai.local.run",
    "inference.auto.run": "ai.local.run",
    "inference.cpu.model.preview": "diagnostics.read",
    "inference.cpu.model.apply": "ai.local.manage",
    "inference.cpu.run": "ai.local.run",
    "software.apps.list": "diagnostics.read",
    "software.app.preview": "software.manage",
    "software.app.apply": "software.manage",
    "software.app.run": "software.manage",
    "agent.hermes.status": "diagnostics.read",
    "cron.status": "diagnostics.read",
    "cron.scheduler.start": "cron.scheduler.manage",
    "cron.scheduler.stop": "cron.scheduler.manage",
    "cron.executor.self_test": "diagnostics.read",
    "cron.jobs.list": "diagnostics.read",
    "cron.jobs.show": "diagnostics.read",
    "cron.jobs.validate": "diagnostics.read",
    "cron.jobs.next_runs": "diagnostics.read",
    "cron.jobs.mutation.preview": "cron.manage",
    "cron.jobs.mutation.apply": "cron.manage",
    "cron.executions.list": "diagnostics.read",
    "cron.executions.show": "diagnostics.read",
    "timezone.status": "diagnostics.read",
    "timezone.list": "diagnostics.read",
    "timezone.set": "timezone.manage",
    "desktop.status": "diagnostics.read",
    "desktop.monitor.status": "diagnostics.read",
    "desktop.monitor.configure": "desktop.monitor.manage",
    "desktop.start": "desktop.manage",
    "desktop.stop": "desktop.manage",
    "desktop.restart": "desktop.manage",
    "doctor.report": "diagnostics.read",
    "ssh.inspect": "diagnostics.read",
    "ssh.keys.list": "ssh.credentials.read",
    "ssh.keys.add.preview": "ssh.credentials.manage",
    "ssh.keys.add.apply": "ssh.credentials.manage",
    "ssh.keys.remove.preview": "ssh.credentials.manage",
    "ssh.keys.remove.apply": "ssh.credentials.manage",
    "ssh.keys.rollback.list": "ssh.credentials.read",
    "ssh.keys.rollback.preview": "ssh.credentials.manage",
    "ssh.keys.rollback.apply": "ssh.credentials.manage",
    "ssh.client-key.create.preview": "ssh.credentials.manage",
    "ssh.client-key.create.apply": "ssh.credentials.manage",
    "ssh.service.autostart.status": "diagnostics.read",
    "ssh.service.autostart.preview": "ssh.managed.lifecycle",
    "ssh.service.autostart.apply": "ssh.managed.lifecycle",
    "remote.access.preview": "remote_policy.read",
    "ssh.service.start": "ssh.managed.lifecycle",
    "ssh.service.stop": "ssh.managed.lifecycle",
    "ssh.service.restart": "ssh.managed.lifecycle",
    "ssh.service.deploy": "services.manage",
    "ssh.service.deploy.rollback.preview": "diagnostics.read",
    "ssh.service.deploy.rollback.apply": "services.manage",
    "boot.status": "diagnostics.read",
    "boot.profile.status": "diagnostics.read",
    "boot.profile.preview": "diagnostics.read",
    "boot.helpers.status": "diagnostics.read",
    "boot.helpers.preview": "boot.helpers.manage",
    "boot.helpers.apply": "boot.helpers.manage",
    "boot.enable": "boot.manage",
    "boot.disable": "boot.manage",
    "boot.cron.status": "diagnostics.read",
    "boot.cron.validate": "diagnostics.read",
    "boot.cron.preview": "diagnostics.read",
    "boot.cron.enable": "boot.cron.manage",
    "boot.cron.disable": "boot.cron.manage",
    "backup.create": "state.backup",
    "backup.list": "diagnostics.read",
    "backup.inspect": "diagnostics.read",
    "restore.preview": "diagnostics.read",
    "restore.apply": "state.restore",
    "recovery.status": "diagnostics.read",
    "recovery.resolve": "recovery.manage",
    "recovery.inspect": "diagnostics.read",
    "recovery.rollback.preview": "diagnostics.read",
    "recovery.rollback.apply": "recovery.manage",
    "wakelock.status": "diagnostics.read",
    "wakelock.ssh-policy.status": "diagnostics.read",
    "wakelock.ssh-policy.preview": "wakelock.policy.manage",
    "wakelock.ssh-policy.apply": "wakelock.policy.manage",
    "wakelock.acquire": "wakelock.manage",
    "wakelock.release": "wakelock.manage",
    "continuity.status": "continuity.read",
    "continuity.prepare.preview": "continuity.checkpoint.manage",
    "continuity.prepare": "continuity.checkpoint.manage",
    "continuity.verify.preview": "continuity.checkpoint.manage",
    "continuity.verify": "continuity.checkpoint.manage",
    "continuity.prepare-reboot-test.preview": "continuity.reboot-test.manage",
    "continuity.prepare-reboot-test": "continuity.reboot-test.manage",
    "continuity.verify-reboot-test.preview": "continuity.reboot-test.manage",
    "continuity.verify-reboot-test": "continuity.reboot-test.manage",
    "continuity.resume-info": "continuity.read",
}



def required_capability(operation: object) -> str | None:
    """Return the exact scope required for a known operation; unknown denies."""
    if not isinstance(operation, str):
        return None
    return OPERATION_CAPABILITIES.get(operation)


def authorize(operation: object, grants: Iterable[str]) -> bool:
    """Authorize only an explicitly granted exact capability.

    Strings/bytes are rejected as grant containers to avoid treating one
    capability string as an iterable of characters. No wildcard inheritance
    or implicit read/write escalation is supported.
    """
    required = required_capability(operation)
    if required is None or isinstance(grants, (str, bytes)):
        return False
    try:
        return required in grants
    except TypeError:
        return False
