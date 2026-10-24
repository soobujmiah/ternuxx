#!/usr/bin/env python3
"""Exercise read-only Native core commands with injected optional PRoot failures."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PREFIX = Path(os.environ.get("PREFIX", ""))
CORE_PROBES = {
    "cli_help": ["./tx", "--help"],
    "management_catalog": ["./tx", "mng", "catalog", "list", "--json"],
    "boot_helper_status": ["./tx", "mng", "boot", "helpers", "status", "--json"],
    "native_graphics_status": ["./tx", "graphics", "native", "status", "--json"],
    "ssh_diagnostics": ["./tx", "ssh", "inspect", "--json"],
    "recovery_status": ["./tx", "recovery", "status", "--json"],
    "proot_status": ["./tx", "proot", "status", "--json"],
    "doctor": ["./tx", "doctor", "--json"],
}
GUEST_VERIFY = [
    "./tx", "proot", "verify", "--distro", "debian", "--guest-user", "ternuxx_probe",
    "--display", ":1", "--backend", "zink", "--json",
]


def _run_json(name: str, command: list[str], env: dict[str, str]) -> dict[str, object]:
    run = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
    entry: dict[str, object] = {"exit_code": run.returncode}
    if name == "cli_help":
        entry["passed"] = run.returncode == 0 and "Ternuxx" in run.stdout
        return entry
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        entry.update(passed=False, error=f"invalid JSON: {exc}")
        return entry
    entry["ok"] = payload.get("ok")
    if name == "doctor":
        findings = [item for item in payload.get("findings", [])
                    if item.get("id") == "NTX-PROOT-001"]
        entry["overall"] = payload.get("overall")
        entry["read_only"] = payload.get("read_only")
        entry["proot_finding"] = ({"severity": findings[0].get("severity"),
                                   "observed": findings[0].get("observed")}
                                  if findings else None)
        entry["passed"] = bool(run.returncode in (0, 1) and payload.get("read_only") is True
                               and (not findings or findings[0].get("severity") == "info"))
    else:
        entry["passed"] = bool(run.returncode == 0 and payload.get("ok") is True)
    return entry


def _run_guest_verify(env: dict[str, str]) -> dict[str, object]:
    run = subprocess.run(GUEST_VERIFY, cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return {"passed": False, "exit_code": run.returncode,
                "error": f"invalid JSON: {exc}"}
    data = payload.get("data", {})
    safety = data.get("safety", {})
    return {
        "passed": run.returncode == 0 and payload.get("ok") is True,
        "exit_code": run.returncode,
        "status": data.get("status"),
        "guest_entered_reported_by_operation": data.get("guest_entered"),
        "guest_write_command_invoked": safety.get("guest_write_command_invoked"),
        "packages_changed": safety.get("packages_changed"),
        "blockers": data.get("blockers", []),
    }


def _scenario(mode: str, shell: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"ternuxx-{mode}-proot-") as temporary:
        temp = Path(temporary)
        trace = temp / "manager-calls.log"
        proot_call = temp / "proot.called"
        manager = temp / "proot-distro"
        manager.write_text(
            f"#!{shell}\n"
            f"printf '%s\\n' \"$1\" >> {shlex.quote(str(trace))}\n"
            f"if [ \"$1\" = list ]; then\n"
            "  printf '%s\\n' 'Installed containers:'\n"
            f"  if [ \"$TERNUXX_P4_GUEST_MODE\" = broken ]; then printf '%s\\n' ' * Debian'; fi\n"
            "  printf '%s\\n' 'Log in with: proot-distro login <name>'\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = login ]; then\n"
            "  if [ \"$TERNUXX_P4_GUEST_MODE\" = broken ]; then\n"
            "    echo 'injected guest login failure' >&2; exit 127\n"
            "  fi\n"
            "  echo 'unexpected guest login' >&2; exit 98\n"
            "fi\n"
            "echo 'unexpected proot-distro operation' >&2; exit 97\n",
            encoding="utf-8",
        )
        manager.chmod(0o700)
        proot = temp / "proot"
        proot.write_text(
            f"#!{shell}\nprintf called > {shlex.quote(str(proot_call))}\nexit 127\n",
            encoding="utf-8",
        )
        proot.chmod(0o700)
        env = dict(os.environ)
        env["PATH"] = f"{temp}{os.pathsep}{env.get('PATH', '')}"
        env["TERNUXX_P4_GUEST_MODE"] = mode
        if (shutil.which("proot-distro", path=env["PATH"]) != str(manager)
                or shutil.which("proot", path=env["PATH"]) != str(proot)):
            raise RuntimeError("injected PRoot shims are not first on PATH; refusing to run probes")

        probes = {name: _run_json(name, command, env)
                  for name, command in CORE_PROBES.items()}
        guest = _run_guest_verify(env)
        calls = trace.read_text(encoding="utf-8").splitlines() if trace.exists() else []
        real_launcher_shim_called = proot_call.exists()
        expected_guest_status = "not_installed" if mode == "missing" else "unknown"
        expected_calls = ["list", "list", "login"] if mode == "broken" else ["list", "list"]
        passed = (
            all(item.get("passed") is True for item in probes.values())
            and guest.get("passed") is True
            and guest.get("status") == expected_guest_status
            and not real_launcher_shim_called
            and calls == expected_calls
            and guest.get("guest_write_command_invoked") is False
            and guest.get("packages_changed") is False
        )
        return {
            "passed": passed,
            "core_probes": probes,
            "guest_verify": guest,
            "injected_manager_calls": calls,
            "proot_launcher_tripwire_called": real_launcher_shim_called,
            "guest_mutation_command_run": False,
            "guest_process_started": False,
            "guest_entry_note": (
                "The verifier reports an attempted entry; the injected manager refused login before real PRoot ran."
                if mode == "broken" else "The guest inventory excluded Debian, so login was never requested."
            ),
        }


def _manager_failure(shell: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="ternuxx-manager-failure-") as temporary:
        temp = Path(temporary)
        marker = temp / "proot-distro.called"
        shim = temp / "proot-distro"
        shim.write_text(f"#!{shell}\ntouch {shlex.quote(str(marker))}\n"
                        "echo injected-proot-distro-failure >&2\nexit 127\n", encoding="utf-8")
        shim.chmod(0o700)
        proot_call = temp / "proot.called"
        proot = temp / "proot"
        proot.write_text(
            f"#!{shell}\nprintf called > {shlex.quote(str(proot_call))}\nexit 127\n",
            encoding="utf-8",
        )
        proot.chmod(0o700)
        env = dict(os.environ)
        env["PATH"] = f"{temp}{os.pathsep}{env.get('PATH', '')}"
        if (shutil.which("proot-distro", path=env["PATH"]) != str(shim)
                or shutil.which("proot", path=env["PATH"]) != str(proot)):
            raise RuntimeError("injected PRoot shims are not first on PATH; refusing to run probes")
        probes = {name: _run_json(name, command, env)
                  for name, command in CORE_PROBES.items()}
        launcher_called = proot_call.exists()
        passed = (marker.is_file() and not launcher_called
                  and all(item.get("passed") is True for item in probes.values()))
        return {"passed": passed, "shim_invoked": marker.is_file(), "core_probes": probes,
                "proot_launcher_tripwire_called": launcher_called,
                "guest_mutation_command_run": False}


def main() -> int:
    if "com.termux/files/usr" not in str(PREFIX) or not (ROOT / "tx").is_file():
        raise SystemExit("Run this check from the Native Termux Ternuxx checkout.")
    shell = PREFIX / "bin/sh"
    if not shell.is_file():
        raise SystemExit("Native Termux shell was not found under PREFIX.")
    scenarios = {
        "manager_command_fails": _manager_failure(shell),
        "debian_guest_missing": _scenario("missing", shell),
        "debian_guest_login_broken": _scenario("broken", shell),
    }
    print(json.dumps({"scenarios": scenarios}, indent=2, sort_keys=True))
    return 0 if all(item.get("passed") is True for item in scenarios.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
