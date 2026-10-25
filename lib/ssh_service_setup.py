"""Preview-first first-time provisioning for the loopback Ternuxx SSH service."""
from __future__ import annotations

import hashlib
import json
import subprocess

import fixed_service_deployment
import ssh_diagnostics
import ssh_managed_config

SERVICE_ID = "ternuxx-sshd"


class SshSetupError(RuntimeError):
    pass


def _core(prefix, home, state_dir, *, runner):
    config = ssh_managed_config.preview(prefix=prefix, home=home, runner=runner)
    service = fixed_service_deployment.preview_install(
        prefix=prefix, service_id=SERVICE_ID)
    core = {"service_id": SERVICE_ID, "config_plan_id": config.get("plan_id"),
            "config_changed": config.get("changed"), "service_plan_id": service.get("plan_id"),
            "service_target_state": service.get("target_state"),
            "service_source_sha256": service.get("source_sha256"),
            "service_manager_sha256": service.get("service_manager_sha256"),
            "config_sha256": config.get("after_sha256"),
            "port": 8023, "bind": "127.0.0.1", "authentication": "publickey-only",
            "external_ssh_config_unchanged": True}
    plan_id = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return core, config, service, plan_id


def preview(*, prefix, home, state_dir, runner=None):
    core, config, service, plan_id = _core(prefix, home, state_dir, runner=runner or subprocess.run)
    return {**core, "plan_id": plan_id, "requires_confirmation": True, "read_only": True,
            "config": config, "service": service,
            "impact": "Creates the dedicated Native SSH config and registers/starts only ternuxx-sshd on 127.0.0.1:8023. Password and keyboard-interactive auth are disabled. Only the Ternuxx-owned key file and config are selected; unrelated Native SSH configuration is untouched.",
            "verification_required": ["Runit reports ternuxx-sshd running", "sshd answers on 127.0.0.1:8023"],
            "runner_injected": runner is not None}


def apply(*, prefix, home, state_dir, confirmed: bool, plan_id: str | None, runner=None):
    if confirmed is not True:
        return preview(prefix=prefix, home=home, state_dir=state_dir, runner=runner)
    kwargs = {} if runner is None else {"runner": runner}
    current = preview(prefix=prefix, home=home, state_dir=state_dir, runner=runner)
    if not isinstance(plan_id, str) or plan_id != current["plan_id"]:
        raise SshSetupError("exact fresh SSH setup preview and plan ID are required")
    if current["config"].get("changed"):
        config_result = ssh_managed_config.apply(
            prefix=prefix, home=home, state_dir=state_dir, confirmed=True,
            plan_id=current["config"]["plan_id"], **kwargs)
    else:
        config_result = {"status": "already_configured", "service_started": False,
                         "config_sha256": current["config"]["after_sha256"]}
    try:
        service_result = fixed_service_deployment.install(
            prefix=prefix, service_id=SERVICE_ID, confirmed=True,
            plan_id=current["service"]["plan_id"], **kwargs)
    except Exception as exc:
        raise SshSetupError(f"SSH config is in place but service registration/start failed: {exc}") from exc
    diagnostic = ssh_diagnostics.inspect_native(prefix=prefix, home=home)
    managed = diagnostic.get("checks", {}).get("managed_service", {})
    probe = managed.get("loopback_ssh_probe", {}) if isinstance(managed, dict) else {}
    service_status = managed.get("status") if isinstance(managed, dict) else None
    if service_status != "running" or not isinstance(probe, dict) or probe.get("status") != "ssh_banner":
        raise SshSetupError("Runit accepted the service but SSH readiness was not verified; inspect tx ssh inspect before retrying")
    return {"status": "ready", "service_id": SERVICE_ID, "service": service_result,
            "config": config_result, "readiness": {"runit": service_status,
            "loopback_ssh_probe": probe.get("status"), "listener_correlation": managed.get("listener_correlation"),
            "authenticated_access": "not_tested"}, "external_ssh_config_unchanged": True, "read_only": False}
