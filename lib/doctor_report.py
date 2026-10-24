#!/usr/bin/env python3
"""Read-only Ternuxx host report with stable finding IDs."""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import config_recovery
import adb_diagnostics
import cpu_inference
import runtime_diagnostics
import ssh_diagnostics


FINDINGS: list[dict[str, str]] = []


def add(code: str, severity: str, scope: str, observed: str, action: str) -> None:
    FINDINGS.append({
        "id": code,
        "severity": severity,
        "scope": scope,
        "observed": observed,
        "suggested_action": action,
    })


def run(argv: list[str], timeout: float = 3.0, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv, check=False, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout,
            env={**(env if env is not None else os.environ), "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def native_graphics_probe_env() -> dict[str, str]:
    """Keep Termux runtime libraries ahead of tool-private injected loaders."""
    env = dict(os.environ)
    prefix = env.get("PREFIX", "/data/data/com.termux/files/usr")
    termux_lib = str(Path(prefix) / "lib")
    paths = [termux_lib, *env.get("LD_LIBRARY_PATH", "").split(os.pathsep)]
    env["LD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys(path for path in paths if path))
    return env


def command_path(name: str) -> str | None:
    return shutil.which(name)


def path_presence(path: Path) -> bool | None:
    try:
        return path.exists()
    except OSError:
        return None


def native_npu_evidence() -> str:
    """Summarize read-only NPU hints without treating them as execution proof."""
    vendor_paths = (
        Path("/vendor/lib64/libQnnHtp.so"),
        Path("/vendor/lib64/libQnnDsp.so"),
        Path("/vendor/lib64/libcdsprpc.so"),
        Path("/vendor/lib64/libadsprpc.so"),
        Path("/vendor/lib64/libSNPE.so"),
    )
    node_paths = (
        Path("/dev/adsprpc-smd"),
        Path("/dev/adsprpc-smd-secure"),
        Path("/dev/fastrpc-cdsp"),
    )
    runtime_names = ("qnn-net-run", "qnn-platform-validator", "snpe-net-run", "llama-cli")

    visible_vendor = [p.name for p in vendor_paths if path_presence(p) is True]
    unknown_vendor = any(path_presence(p) is None for p in vendor_paths)
    visible_nodes = [p.name for p in node_paths if path_presence(p) is True]
    unknown_nodes = any(path_presence(p) is None for p in node_paths)
    runtime_tools = [name for name in runtime_names if command_path(name)]
    if visible_vendor:
        vendor_status = "visible=" + ",".join(visible_vendor)
    else:
        vendor_status = "visibility=unknown" if unknown_vendor else "none-visible"
    if visible_nodes:
        node_status = "visible=" + ",".join(visible_nodes)
    else:
        node_status = "visibility=unknown" if unknown_nodes else "none-visible"
    runtime_status = "found=" + ",".join(runtime_tools) if runtime_tools else "no-known-runtime-cli-found"
    return f"Android vendor libraries {vendor_status}; FastRPC candidate nodes {node_status}; Termux runtime tools {runtime_status}; NPU execution=unverified"


def prop(name: str) -> str:
    path = command_path("getprop")
    if not path:
        return "unknown"
    result = run([path, name], 1.0)
    return (result.stdout.strip().splitlines()[0][:160]
            if result and result.returncode == 0 and result.stdout.strip()
            else "unknown")


def app_version_code(package: str) -> str:
    """Return an Android package versionCode only; it does not identify the signer."""
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        return "unknown (invalid package name)"
    queries: list[list[str]] = []
    cmd = command_path("cmd")
    pm = command_path("pm")
    if cmd:
        queries.append([cmd, "package", "list", "packages", "--show-versioncode", package])
    if pm:
        queries.append([pm, "list", "packages", "--show-versioncode", package])
    if not queries:
        return "unknown (Android package version query unavailable)"
    for argv in queries:
        result = run(argv, 2.0)
        if result is None or result.returncode != 0:
            continue
        matches = []
        for line in result.stdout.splitlines():
            m = re.fullmatch(
                rf"package:{re.escape(package)}\s+versionCode:([0-9]+)",
                line.strip(),
            )
            if m:
                matches.append(m.group(1))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return "unknown (ambiguous package version output)"
        if not result.stdout.strip():
            return "not detected"
    return "unknown (Android package version query failed or was ambiguous)"


def pulse_server_status() -> tuple[str, str]:
    """Probe only the explicit loopback TCP server; this cannot autospawn locally."""
    command = command_path("pactl")
    if not command:
        return "unavailable", "pactl is unavailable"
    cookie = Path.home() / ".config/pulse/cookie"
    env = {**os.environ, "PULSE_SERVER": "tcp:127.0.0.1:4713",
           "PULSE_COOKIE": str(cookie), "LC_ALL": "C"}
    try:
        result = subprocess.run([command, "--server", "tcp:127.0.0.1:4713", "info"],
                                check=False, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=2.0, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", "explicit loopback protocol probe timed out or could not run"
    if result.returncode != 0:
        return "unavailable", "explicit loopback PulseAudio endpoint did not respond"
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"Server Name", "Default Sink"}:
            value = value.strip()
            if re.fullmatch(r"[A-Za-z0-9_.:+-]{1,128}", value):
                values[key] = value
    if not values.get("Server Name"):
        return "unknown", "explicit loopback response was malformed"
    return "ready", f"authenticated loopback endpoint ready; sink={values.get('Default Sink', 'unknown')}"


def rish_bundle_status(home: Path | None = None) -> str:
    """Inspect only the two expected private-home files; never execute them."""
    root = home or Path.home()
    wrapper, dex = root / "rish", root / "rish_shizuku.dex"
    try:
        wi, di = wrapper.lstat(), dex.lstat()
    except OSError:
        return "not found or unreadable"
    if (not stat.S_ISREG(wi.st_mode) or not stat.S_ISREG(di.st_mode)
            or wi.st_uid != os.getuid() or di.st_uid != os.getuid()
            or wi.st_mode & 0o077 or di.st_mode & 0o077 or not wi.st_mode & 0o100):
        return "unsafe identity, type, or permissions"
    return "private wrapper and DEX present; invocation not verified"


def shizuku_server_process_status() -> str:
    """Return a bounded process-name hint; absence never proves the service is stopped."""
    pidof = command_path("pidof")
    if not pidof:
        return "unknown (pidof unavailable)"
    result = run([pidof, "shizuku_server"], 1.0)
    if result is None:
        return "unknown (pidof timed out or could not run)"
    output = result.stdout.strip()
    if result.returncode == 0 and output:
        pids = output.split()
        if all(re.fullmatch(r"[0-9]+", pid) for pid in pids):
            return f"observed ({len(pids)} process name match{'es' if len(pids) != 1 else ''})"
        return "unknown (pidof output was ambiguous)"
    if result.returncode == 1 and not output:
        return "not observed (process visibility unknown)"
    return "unknown (pidof failed or returned ambiguous output)"


def native_termux() -> bool:
    prefix = os.environ.get("PREFIX", "")
    return bool(os.environ.get("TERMUX_VERSION")) or prefix.startswith(
        "/data/data/com.termux/files/usr"
    )


def package_status(package: str) -> tuple[str, str]:
    tool = command_path("dpkg-query")
    if not tool:
        return "unknown", "dpkg-query unavailable"
    result = run([tool, "-W", "-f=${Status}\t${Version}", package], 2.0)
    if not result or result.returncode != 0:
        return "missing", "not installed"
    fields = result.stdout.strip().split("\t", 1)
    if not fields or fields[0] != "install ok installed":
        return "missing", "not installed"
    return "installed", fields[1] if len(fields) > 1 else "version unknown"


def app_path(package: str) -> str:
    """Query Android package presence through `cmd` first, then the `pm` wrapper."""
    queries: list[list[str]] = []
    cmd = command_path("cmd")
    pm = command_path("pm")
    if cmd:
        queries.append([cmd, "package", "path", package])
    if pm:
        queries.append([pm, "path", package])
    if not queries:
        return "unknown (Android package query unavailable)"
    last_exit: int | None = None
    had_result = False
    for argv in queries:
        result = run(argv, 2.0)
        if not result:
            continue
        had_result = True
        if result.returncode != 0:
            last_exit = result.returncode
            continue
        last_exit = None
        output = result.stdout.strip()
        if any(line.strip().startswith("package:") for line in output.splitlines()):
            return "present"
        normalized = output.lower()
        if any(message in normalized for message in (
            "unable to find package", "unknown package", "package not found",
            "was not found", "is not installed",
        )):
            return "not detected"
    if last_exit is not None:
        return f"unknown (Android package query failed with exit {last_exit})"
    if not had_result:
        return "unknown (Android package query failed or timed out)"
    return "unknown (Android package query returned ambiguous output)"


def proc_identity(role: str, record: object, *, proc_root: Path = Path("/proc")) -> tuple[bool | None, str]:
    if not isinstance(record, dict):
        return None, "no process identity recorded"
    pid = record.get("pid")
    expected_ticks = str(record.get("start_ticks") or "")
    marker = str(record.get("command_marker") or "")
    if not isinstance(pid, int) or not expected_ticks or not marker:
        return None, "incomplete process identity"
    try:
        stat = (proc_root / str(pid) / "stat").read_text(encoding="ascii")
        _comm, sep, rest = stat.rpartition(")")
        if not sep:
            return None, "process identity unavailable"
        fields = rest.strip().split()
        ticks = fields[19]
        cmdline = (proc_root / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", "replace"
        )
    except (OSError, IndexError):
        return False, "recorded process is not present"
    if ticks != expected_ticks or marker not in cmdline:
        return False, "recorded PID identity does not match"
    pgid = fields[2] if len(fields) > 2 else ""
    sid = fields[3] if len(fields) > 3 else ""
    has_group_identity = "pgid" in record or "sid" in record
    if has_group_identity:
        if record.get("pgid") is None or record.get("sid") is None:
            return None, "incomplete process group/session identity"
        if str(record.get("pgid")) != pgid or str(record.get("sid")) != sid:
            return False, "recorded process group/session does not match"
        return True, f"verified pid={pid}, pgid={pgid}, sid={sid}"
    return True, f"verified pid={pid}; process group/session not recorded"


def discover_live_session_state(state_root: Path) -> Path | None:
    """Return one verified live-session state path; never mutate or signal processes."""
    helper = Path(__file__).with_name("desktop_session_discovery.py")
    supervisor = Path(__file__).with_name("desktop-supervisor.sh")
    result = run([sys.executable, str(helper), str(supervisor), str(Path.home()), str(state_root)])
    if result is None or result.returncode != 0:
        return None
    candidate = Path(result.stdout.strip())
    try:
        home = Path.home().resolve(strict=True)
        candidate = candidate.resolve(strict=True)
        if candidate == home or home not in candidate.parents:
            return None
        return candidate
    except OSError:
        return None


def check_session(state_root: Path) -> None:
    try:
        home = Path.home().resolve()
        root = state_root.resolve()
        if root == home or home not in root.parents:
            add("NTX-SESSION-001", "error", "native-session",
                "configured state path is outside Termux HOME",
                "Review TERNUXX_STATE_DIR; do not move or delete data automatically.")
            return
    except OSError:
        add("NTX-SESSION-001", "error", "native-session",
            "configured state path cannot be resolved",
            "Inspect the configured state path manually.")
        return

    state_file = root / "session.json"
    state_presence = path_presence(state_file)
    if state_presence is False:
        discovered = discover_live_session_state(root)
        if discovered is not None:
            root = discovered
            state_file = root / "session.json"
            state_presence = path_presence(state_file)
        if state_presence is False:
            add("NTX-SESSION-010", "info", "native-session",
                "no session record at configured path; no unique verified live session state discovered",
                "Start a session when ready, or inspect ambiguous/unverifiable supervisor state manually.")
            return
    if state_presence is None:
        add("NTX-SESSION-011", "warning", "native-session", "session record path is inaccessible",
            "Check access manually; Doctor does not change permissions.")
        return
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        add("NTX-SESSION-011", "error", "native-session", "session record is unreadable or invalid JSON",
            "Keep the record and log; inspect them before using recovery commands.")
        return
    if not isinstance(state, dict) or state.get("owner") != "ternuxx":
        add("NTX-SESSION-012", "error", "native-session", "record owner is not Ternuxx",
            "Do not manage this record as a Ternuxx session.")
        return
    schema = state.get("schema")
    status = str(state.get("status", "unknown"))
    if schema != 2:
        add("NTX-SESSION-013", "warning", "native-session", f"unsupported session schema: {schema!r}",
            "Use the documented recovery procedure; do not signal recorded processes.")
        return
    add("NTX-SESSION-014", "info", "native-session", f"recorded state={status}, display={state.get('display', 'unknown')}",
        "Use start/stop only after reviewing ownership and conflicts.")
    for role in ("supervisor", "x11", "desktop"):
        alive, message = proc_identity(role, state.get(role))
        if alive is True:
            severity = "pass"
        elif alive is False:
            severity = "warning" if status in ("running", "starting", "stop_incomplete") else "info"
        else:
            severity = "info" if status in ("stopped", "failed") else "warning"
        add(f"NTX-SESSION-{20 + ('supervisor', 'x11', 'desktop').index(role):03d}", severity,
            "native-session", f"{role}: {message}",
            "Review the session record and log; Doctor does not stop or repair processes.")


def check_process_inventory(state_root: Path, proc_root: Path = Path("/proc")) -> None:
    """Count known desktop processes and mark ownership only after identity validation."""
    labels = {
        "termux-x11", "xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop",
        "thunar", "xfce4-terminal", "dbus-daemon",
    }
    owned_pids: set[str] = set()
    owned_roles: dict[str, str] = {}
    owned_sids: set[str] = set()
    try:
        home = Path.home().resolve(strict=True)
        root = state_root.expanduser().resolve(strict=True)
        if root == home or home not in root.parents:
            raise OSError("state path is outside HOME")
        state_file = root / "session.json"
        if not state_file.is_file():
            discovered = discover_live_session_state(root)
            if discovered is not None:
                root = discovered
                state_file = root / "session.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if isinstance(state, dict) and state.get("owner") == "ternuxx" and state.get("schema") == 2:
            for role in ("supervisor", "x11", "desktop"):
                record = state.get(role)
                if isinstance(record, dict):
                    valid, _detail = proc_identity(role, record, proc_root=proc_root)
                    if valid is True:
                        owned_pids.add(str(record.get("pid")))
                        owned_roles[str(record.get("pid"))] = role
                        if record.get("sid") is not None:
                            owned_sids.add(str(record["sid"]))
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError):
        # Session diagnostics already report path/record failures; inventory must fail closed.
        owned_pids.clear()
        owned_roles.clear()
        owned_sids.clear()

    candidates: dict[str, int] = {}
    verified_owned: dict[str, int] = {}
    same_session: dict[str, int] = {}
    try:
        entries = list(proc_root.iterdir())
        for entry in entries:
            if not entry.name.isdecimal():
                continue
            try:
                name = (entry / "comm").read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if name not in labels and entry.name not in owned_roles:
                continue
            if entry.name in owned_pids:
                role = owned_roles[entry.name]
                verified_owned[role] = verified_owned.get(role, 0) + 1
                continue
            try:
                stat_text = (entry / "stat").read_text(encoding="ascii")
                _comm, sep, rest = stat_text.rpartition(")")
                fields = rest.strip().split() if sep else []
                session_id = fields[3] if len(fields) > 3 else ""
            except (OSError, UnicodeError):
                session_id = ""
            if session_id and session_id in owned_sids:
                same_session[name] = same_session.get(name, 0) + 1
            else:
                candidates[name] = candidates.get(name, 0) + 1
    except OSError:
        add("NTX-SESSION-030", "info", "desktop-process-inventory",
            "process inventory unavailable; ownership of other desktop processes is unknown",
            "Review the session and display state manually; Doctor does not manage unverified processes.")
        return

    owned_text = ", ".join(f"{name}={count}" for name, count in sorted(verified_owned.items())) or "none"
    session_text = ", ".join(f"{name}={count}" for name, count in sorted(same_session.items())) or "none"
    other_text = ", ".join(f"{name}={count}" for name, count in sorted(candidates.items())) or "none"
    add("NTX-SESSION-030", "info", "desktop-process-inventory",
        f"verified Ternuxx-owned roots: {owned_text}; same recorded session candidates: {session_text}; owner unverified: {other_text}",
        "Same-session membership is not standalone lifecycle ownership. Unverified candidates may belong to Termux or Android; inspect before action. Hidden processes may not appear.")


def check_operations(state_root: Path) -> None:
    try:
        home = Path.home().resolve()
        root = state_root.resolve()
        if root == home or home not in root.parents:
            add("NTX-OP-004", "error", "native-operations", "configured operation journal path is outside Termux HOME",
                "Review TERNUXX_STATE_DIR; Doctor does not read or change external paths.")
            return
    except OSError:
        add("NTX-OP-004", "warning", "native-operations", "configured operation journal path cannot be resolved",
            "Inspect the configured state path manually.")
        return
    operations = root / "operations"
    try:
        entries = sorted(operations.glob("*.json")) if operations.exists() else []
    except OSError:
        add("NTX-OP-001", "warning", "native-operations", "operation journal is inaccessible",
            "Inspect journal permissions and records manually; Doctor never repairs or resumes operations.")
        return
    if not entries:
        add("NTX-OP-001", "info", "native-operations", "no operation journal records",
            "No action needed until a lifecycle operation is run.")
        return
    active_statuses = {"starting", "stopping", "needs_recovery"}
    for path in entries:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            add("NTX-OP-002", "warning", "native-operations", "an operation journal record is unreadable",
                "Keep all records and inspect the journal manually; do not remove it to bypass recovery.")
            continue
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            add("NTX-OP-002", "warning", "native-operations", "an operation journal record has an unsupported schema",
                "Inspect the record and follow the documented recovery procedure.")
            continue
        status = str(record.get("status", "unknown"))
        kind = str(record.get("kind", "unknown"))
        if status in active_statuses:
            add("NTX-OP-003", "warning", "native-operations",
                f"unresolved operation: {kind}, status={status}",
                "Review session.json and desktop.log alongside this journal record; Doctor does not resume or mutate.")
    if not any(
        finding["id"] == "NTX-OP-003" for finding in FINDINGS
    ) and not any(f["id"] == "NTX-OP-002" for f in FINDINGS):
        add("NTX-OP-001", "info", "native-operations",
            f"operation journal records present: {len(entries)}; none unresolved",
            "No recovery action is pending.")


def check_backups(state_root: Path) -> None:
    """Report Ternuxx backup integrity without creating or repairing state."""
    try:
        home = Path.home().resolve(strict=True)
        state = state_root.expanduser().absolute()
        if state == home or home not in state.parents:
            raise config_recovery.RecoveryError("state path is outside HOME")
        result = config_recovery.list_backups(home=str(home), state_dir=str(state))
    except (OSError, config_recovery.RecoveryError):
        add("NTX-BACKUP-001", "warning", "native-recovery",
            "backup state is inaccessible or fails the private-path checks",
            "Inspect the Ternuxx backup directory and permissions manually; Doctor does not repair it.")
        return
    backups = result.get("backups", [])
    invalid = sum(item.get("integrity") != "valid" for item in backups)
    if invalid:
        add("NTX-BACKUP-002", "warning", "native-recovery",
            f"backup archives present: {len(backups)}; integrity failures: {invalid}",
            "Keep the archives unchanged and inspect each with `tx backup inspect`; do not restore an invalid archive.")
    elif backups:
        add("NTX-BACKUP-001", "pass", "native-recovery",
            f"backup archives present: {len(backups)}; all integrity checks passed",
            "No action needed.")
    else:
        add("NTX-BACKUP-001", "info", "native-recovery", "no Ternuxx configuration backups found",
            "Create a preview with `tx backup create` if configuration recovery is needed.")


def check_service_manager() -> None:
    """Summarize the fixed Ternuxx SSH unit through read-only service diagnostics."""
    if not native_termux():
        add("NTX-SVC-001", "info", "native-service-manager",
            "Termux service manager is not inspected outside the native Termux host",
            "Run Doctor from native Termux for service-manager state.")
        return
    prefix = os.environ.get("PREFIX")
    if not prefix:
        add("NTX-SVC-001", "info", "native-service-manager",
            "Termux PREFIX is unavailable; service-manager state is unknown",
            "Inspect the native Termux environment manually; Doctor does not switch providers.")
        return
    try:
        report = ssh_diagnostics.inspect_native(prefix=prefix, home=str(Path.home()))
        checks = report.get("checks", {})
        service = checks.get("managed_service", {}) if isinstance(checks, dict) else {}
        configured_scope = checks.get("configured_listener_bind_scope", "unknown") if isinstance(checks, dict) else "unknown"
        configured_policy = checks.get("configured_policy", {}) if isinstance(checks, dict) else {}
        password_values = configured_policy.get("passwordauthentication", []) if isinstance(configured_policy, dict) else []
        password_auth = "enabled" if any(str(value).lower() == "yes" for value in password_values) else "not_reported_enabled"
        manager = service.get("manager", "unknown") if isinstance(service, dict) else "unknown"
        service_id = service.get("service_id", "unknown") if isinstance(service, dict) else "unknown"
        status = service.get("status", "unknown") if isinstance(service, dict) else "unknown"
        syntax = service.get("config_syntax", "unknown") if isinstance(service, dict) else "unknown"
        loopback_probe = service.get("loopback_ssh_probe", {}) if isinstance(service, dict) else {}
        probe_status = loopback_probe.get("status", "not_attempted") if isinstance(loopback_probe, dict) else "not_attempted"
        definition = service.get("definition_identity", {}) if isinstance(service, dict) else {}
        definition_status = definition.get("status", "unavailable") if isinstance(definition, dict) else "unavailable"
        process_identity = service.get("process_identity", "unknown") if isinstance(service, dict) else "unknown"
        listener_correlation = checks.get("listener_daemon_correlation", "unknown") if isinstance(checks, dict) else "unknown"
        listener_observation = checks.get("tcp_listener_observation", "unknown") if isinstance(checks, dict) else "unknown"
        listener_procfs = checks.get("tcp_listener_procfs_observation", "unknown") if isinstance(checks, dict) else "unknown"
        listener_netlink = checks.get("tcp_listener_netlink_observation", "unknown") if isinstance(checks, dict) else "unknown"
        listener_source = checks.get("tcp_listener_source", "unknown") if isinstance(checks, dict) else "unknown"
        if not isinstance(probe_status, str):
            probe_status = "not_attempted"
        if not isinstance(definition_status, str):
            definition_status = "unavailable"
        if not isinstance(process_identity, str):
            process_identity = "unknown"
        if not isinstance(listener_correlation, str):
            listener_correlation = "unknown"
        if not isinstance(listener_observation, str):
            listener_observation = "unknown"
        if not isinstance(listener_procfs, str):
            listener_procfs = "unknown"
        if not isinstance(listener_netlink, str):
            listener_netlink = "unknown"
        if not isinstance(listener_source, str):
            listener_source = "unknown"
        if not isinstance(configured_scope, str):
            configured_scope = "unknown"
    except (OSError, TypeError, ValueError):
        manager, service_id, status, syntax, probe_status, definition_status = "unknown", "unknown", "unknown", "unknown", "not_attempted", "unavailable"
        process_identity, listener_correlation, listener_observation = "unknown", "unknown", "unknown"
        listener_procfs, listener_netlink, listener_source = "unknown", "unknown", "unknown"
        configured_scope, password_auth = "unknown", "not_reported_enabled"
    if configured_scope in {"wildcard", "non_loopback"}:
        add("NTX-SSH-001", "warning" if configured_scope == "wildcard" else "info", "native-ssh-configuration",
            f"configured native SSH bind scope={configured_scope}; password authentication={password_auth}; process owner and external reachability=unknown",
            "Review the selected SSH bind and authentication policy before remote use; Doctor does not change SSH configuration or listener state.")
    if manager == "runit" and definition_status in {"mismatch", "unsafe"}:
        add("NTX-SVC-001", "warning", "native-service-manager",
            f"manager=runit; service={service_id}; status={status}; installed service definition identity={definition_status}; service actions are not ownership-verified",
            "Keep the service unchanged and compare its fixed run script with the Ternuxx-owned definition before any action.")
    elif manager != "runit":
        add("NTX-SVC-001", "info", "native-service-manager",
            f"Termux runit manager unavailable or unknown; managed SSH service status={status}",
            "No manager fallback is automatic; review native SSH diagnostics before any service action.")
    elif status == "running" and syntax == "valid" and process_identity == "not_verified":
        add("NTX-SVC-001", "warning", "native-service-manager",
            f"manager=runit; service={service_id}; status=running; config syntax=valid; managed process identity=not_verified; loopback SSH probe={probe_status}; listener-to-port correlation={listener_correlation} (tcp observation={listener_observation}; procfs={listener_procfs}; netlink={listener_netlink}; source={listener_source})",
            "Keep the service unchanged and inspect its exact runit-to-daemon process identity; Doctor does not start, stop, or repair it.")
    elif status == "running" and syntax == "valid" and probe_status in {"unreachable", "no_banner", "unexpected_protocol", "timeout"}:
        add("NTX-SVC-001", "warning", "native-service-manager",
            f"manager=runit; service={service_id}; status=running; config syntax=valid; managed process identity={process_identity}; loopback SSH probe={probe_status}; listener-to-port correlation={listener_correlation} (tcp observation={listener_observation}; procfs={listener_procfs}; netlink={listener_netlink}; source={listener_source})",
            "Inspect the named Ternuxx service and port configuration; Doctor will not start, stop, or repair it.")
    elif status == "running" and syntax == "valid":
        add("NTX-SVC-001", "pass", "native-service-manager",
            f"manager=runit; service={service_id}; status=running; config syntax=valid; managed process identity={process_identity}; loopback SSH probe={probe_status}; listener-to-port correlation={listener_correlation} (tcp observation={listener_observation}; procfs={listener_procfs}; netlink={listener_netlink}; source={listener_source})",
            "The process identity and SSH banner are reported separately from listener-to-port correlation and external reachability.")
    else:
        add("NTX-SVC-001", "warning", "native-service-manager",
            f"manager=runit; service={service_id}; status={status}; config syntax={syntax}",
            "Inspect the named Ternuxx service and its journal manually; Doctor does not start, stop, or repair it.")




def graphics_probe() -> None:
    if not os.environ.get("DISPLAY"):
        add("NTX-GPU-101", "info", "native-graphics", "DISPLAY is unset; renderer probe skipped",
            "Run the graphics probe from the same display/session as the target workload.")
        return
    glx = command_path("glxinfo")
    if glx:
        result = run([glx, "-B"], 5.0, env=native_graphics_probe_env())
        if result and result.returncode == 0:
            renderer = next((line.split("OpenGL renderer string:", 1)[1].strip()
                             for line in result.stdout.splitlines()
                             if "OpenGL renderer string:" in line), "renderer string not reported")
            severity = "warning" if "llvmpipe" in renderer.lower() else "info"
            add("NTX-GPU-102", severity, "native-graphics", f"OpenGL renderer: {renderer[:240]}",
                "Treat this as evidence only for this display/process context; verify the actual workload separately.")
        else:
            add("NTX-GPU-102", "warning", "native-graphics", "glxinfo failed or timed out",
                "Check the selected display and run the target workload's own renderer check.")
    else:
        add("NTX-GPU-102", "info", "native-graphics", "glxinfo unavailable; OpenGL renderer unverified",
            "Install or select a renderer inspection tool only through a reviewed package plan.")
    vk = command_path("vulkaninfo")
    if not vk:
        add("NTX-GPU-103", "info", "native-graphics", "vulkaninfo unavailable; Vulkan unprobed",
            "Do not infer Vulkan support from device nodes or libraries.")
        return
    result = run([vk, "--summary"], 8.0, env=native_graphics_probe_env())
    if result and result.returncode == 0:
        lines = [line.strip() for line in result.stdout.splitlines() if "deviceName" in line]
        observed = "; ".join(lines[:3]) if lines else "probe returned success; workload backend not verified"
        add("NTX-GPU-103", "info", "native-graphics", observed[:300],
            "A Vulkan summary is not proof that a workload used the GPU.")
    else:
        detail = "probe failed or timed out"
        if result and result.stdout.strip():
            detail = " ".join(result.stdout.split())[:240]
        add("NTX-GPU-103", "warning", "native-graphics", detail,
            "Record the tested driver/runtime; do not generalize this result beyond the observed Native workload.")


def build_report(graphics: bool, state_root: Path) -> dict[str, object]:
    FINDINGS.clear()
    if native_termux():
        version = os.environ.get("TERMUX_VERSION") or "unknown"
        add("NTX-HOST-001", "pass", "termux-host", f"native Termux context; version={version}",
            "No action needed.")
    else:
        add("NTX-HOST-001", "warning", "termux-host", "native Termux context not detected",
            "Run this report from the Termux host for native package/device findings.")

    package_checks = (
        ("termux-x11", "termux-x11-nightly", "Review the official Termux:X11 setup guide."),
        ("dbus-launch", "dbus", "Review the native package preview if D-Bus is needed."),
        ("xfce4-session", "xfce4-session", "Review the native desktop package preview."),
        ("xfce4-panel", "xfce4-panel", "Review the native desktop package preview."),
        ("xfwm4", "xfwm4", "Review the native desktop package preview."),
        ("thunar", "thunar", "Review the native desktop package preview."),
        ("xfce4-terminal", "xfce4-terminal", "Review the native desktop package preview."),
        ("pulseaudio", "pulseaudio", "Audio is optional; choose its owner before starting it."),
        ("python3", "python", "Python is required by the Ternuxx lifecycle and state tools."),
    )
    for index, (name, package, action) in enumerate(package_checks, start=1):
        path = command_path(name)
        if native_termux():
            status, version = package_status(package)
            if status == "installed":
                severity = "pass" if path else "warning"
                observed = f"package {version}; command {'available' if path else 'missing'}"
            else:
                severity = "warning" if package != "pulseaudio" else "info"
                observed = f"package {status}; command {'available' if path else 'missing'}"
        else:
            severity = "info"
            observed = "not checked outside native Termux"
        add(f"NTX-PKG-{index:03d}", severity, "termux-native", f"{package}: {observed}", action)

    if native_termux():
        audio_status, audio_detail = pulse_server_status()
        audio_severity = "pass" if audio_status == "ready" else "info" if audio_status == "unavailable" else "warning"
        add("NTX-AUDIO-001", audio_severity, "native-audio",
            f"PulseAudio client readiness={audio_status}; {audio_detail}",
            "Native Ternuxx owns the loopback audio service; use tx audio start/status for Native audio state.")

    if native_termux():
        add("NTX-APP-101", "info", "android-addons", f"Termux:X11 Android app: {app_path('com.termux.x11')}",
            "Install/open the official companion app only if needed and after checking its signing source.")
        boot = runtime_diagnostics.inspect_boot(home=Path.home())
        boot_observed = (
            f"Termux:Boot app: {boot.get('app', 'unknown')}; package: {boot.get('package_enabled', 'unknown')}; "
            f"BOOT_COMPLETED receiver: {boot.get('boot_completed_receiver', 'unknown')}; "
            f"scripts: {boot.get('regular_script_count', 'unknown')} regular, "
            f"{boot.get('non_executable_script_count', 'unknown')} non-executable; "
            f"system delivery policy: {boot.get('system_delivery_policy', 'unknown')}"
        )
        add("NTX-APP-102", "info", "android-addons", boot_observed,
            "Package/receiver state does not prove boot delivery. Review a reboot checkpoint; Doctor does not start scripts or change Android policy.")
        shizuku_package = "moe.shizuku.privileged.api"
        shizuku_presence = app_path(shizuku_package)
        shizuku_version = app_version_code(shizuku_package) if shizuku_presence == "present" else "unknown"
        rish_presence = "available" if command_path("rish") else "not found"
        rish_bundle = rish_bundle_status(Path.home())
        server_process = shizuku_server_process_status()
        add("NTX-APP-103", "info", "android-addons",
            f"Shizuku app: {shizuku_presence}; package ID: {shizuku_package}; package versionCode: {shizuku_version}; rish command: {rish_presence}; private-home rish bundle: {rish_bundle}; shizuku_server process-name signal: {server_process}; provider identity (upstream/custom): unverified; Ternuxx provider: not implemented; signer/release identity, granted permission, and watchdog health: unknown",
            "Package ID, versionCode, rish presence, and process-name match are discovery hints only; they do not prove upstream/custom release identity, Binder health, or granted permission. Verify the app signing source, service, and permission before provider integration; no ADB-over-Wi-Fi operation is enabled.")
        adb_server = adb_diagnostics.inspect_local_server()
        adb_status = adb_server.get("status", "unknown")
        if adb_status == "available":
            adb_observed = (
                f"local ADB server responds at 127.0.0.1:5037; protocol version="
                f"0x{adb_server.get('server_protocol_version_hex', 'unknown')}; "
                "process owner/bind scope, device transport/authorization, and Shizuku readiness=unknown"
            )
        elif adb_status == "not_observed":
            adb_observed = (
                "no local ADB server response at 127.0.0.1:5037; this does not prove "
                "ADB is absent elsewhere or that Wireless Debugging is disabled"
            )
        elif adb_status == "protocol_error":
            adb_observed = (
                "127.0.0.1:5037 responded but did not satisfy the bounded ADB host:version "
                "protocol check; process owner and device/Shizuku state=unknown"
            )
        else:
            adb_observed = (
                "local ADB server state at 127.0.0.1:5037 is unknown; device transport "
                "and Shizuku state were not checked"
            )
        add("NTX-ADB-001", "info", "adb-local-server", adb_observed,
            "Doctor only sends ADB host:version to loopback; it does not start ADB, list devices, send device commands, inspect bind scope, or change Wireless Debugging/Shizuku state.")
        add("NTX-API-101", "info", "termux-api", f"termux-share command: {'available' if command_path('termux-share') else 'not found'}",
            "Termux:API app, command, and permissions are separate checks; use only user-selected file actions.")
    else:
        add("NTX-APP-101", "info", "android-addons", "Android companion-app state not checked outside native Termux",
            "Run from Termux host for add-on package visibility.")

    if native_termux():
        cpu_arch = platform.machine() or "unknown"
        logical_cpus = os.cpu_count()
        cpu_count = str(logical_cpus) if logical_cpus is not None else "unknown"
        try:
            inference = cpu_inference.status(prefix=os.environ.get("PREFIX"))
            runtime = inference["runtime"]
            model = inference["model"]
            runtime_state = runtime["version"] if runtime["available"] else "unavailable"
            model_state = model["state"]
            cpu_detail = (
                f"CPU inference workflow=available; runtime={runtime_state}; "
                f"model={model_state}; model_id={model['id']}; backend=CPU"
            )
            if not runtime["available"]:
                cpu_action = "Review `tx ai runtime preview cpu` before installing the Termux-managed llama-cpp runtime."
            elif model_state == "missing":
                cpu_action = "Use `tx ai model preview` then apply if you want the pinned model; inference verifies its hash before running."
            elif model_state in {"present-unverified", "invalid-size", "unsafe", "unsafe-permissions"}:
                cpu_action = "Use `tx ai status` and run the inference workflow to verify the model hash; replace it only through the reviewed model workflow."
            else:
                cpu_action = "Use `tx ai run` for bounded CPU inference; execution verifies the pinned model hash."
        except (cpu_inference.InferenceError, OSError, KeyError, TypeError):
            cpu_detail = "CPU inference workflow status=unknown"
            cpu_action = "Use `tx ai status` to inspect the Native CPU inference runtime and model state."
        add("NTX-CPU-001", "info", "native-compute",
            f"CPU is the native execution baseline; architecture={cpu_arch}; logical CPUs={cpu_count}; {cpu_detail}",
            cpu_action)

        node_paths = (Path("/dev/kgsl-3d0"), Path("/dev/dri/renderD128"))
        nodes = [p for p in node_paths if path_presence(p) is True]
        inaccessible = [p for p in node_paths if path_presence(p) is None]
        if nodes:
            add("NTX-GPU-001", "info", "native-graphics", "device nodes present: " + ", ".join(map(str, nodes)),
                "A device node does not prove renderer access or workload acceleration.")
        elif inaccessible:
            add("NTX-GPU-001", "info", "native-graphics", "device node access unavailable: " + ", ".join(map(str, inaccessible)),
                "Doctor does not change device-node permissions; renderer availability remains unverified.")
        else:
            add("NTX-GPU-001", "info", "native-graphics", "known KGSL/DRM render nodes not detected",
                "GPU availability remains unverified; this is not a workload test.")
        model = Path("/sys/class/kgsl/kgsl-3d0/gpu_model")
        if path_presence(model) is True:
            try:
                gpu = model.read_text(encoding="utf-8").strip()[:160]
            except OSError:
                gpu = "unreadable"
            add("NTX-GPU-002", "info", "native-graphics", f"KGSL model: {gpu}",
                "Hardware identification does not establish a supported native driver/workload.")
        add("NTX-NPU-001", "info", "native-accelerator",
            native_npu_evidence(),
            "Vendor libraries and device nodes are discovery hints only. Verify a supported runtime, delegate selection, and correct representative workload before claiming NPU acceleration.")
    else:
        add("NTX-GPU-001", "info", "native-graphics", "native GPU nodes not checked outside Termux",
            "Run from Termux host; interpret only within the observed Native workload.")
        add("NTX-NPU-001", "info", "native-accelerator", "native NPU capability not checked outside Termux",
            "Run on the Termux host and require a named runtime/workload before claiming NPU support.")

    if graphics:
        graphics_probe()
    else:
        add("NTX-GPU-100", "info", "native-graphics", "renderer/Vulkan probes skipped by default",
            "Use `doctor --graphics` to query the current DISPLAY; this does not launch a desktop or workload.")

    check_session(state_root)
    check_process_inventory(state_root)
    check_operations(state_root)
    check_service_manager()
    check_backups(state_root)
    try:
        usage = shutil.disk_usage(Path.home())
        free = usage.free
        gib = free / (1024 ** 3)
        add("NTX-STORAGE-001", "info", "termux-home", f"free space on HOME filesystem: {gib:.1f} GiB",
            "This is filesystem free space, not a package/rootfs size estimate.")
    except OSError:
        add("NTX-STORAGE-001", "warning", "termux-home", "HOME filesystem capacity unavailable",
            "Check storage manually; Doctor does not scan other directories.")

    severity = "error" if any(f["severity"] == "error" for f in FINDINGS) else (
        "warning" if any(f["severity"] == "warning" for f in FINDINGS) else "pass"
    )
    return {
        "schema_version": 1,
        "command": "doctor",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "read_only": True,
        "overall": severity,
        "device": {
            "model": prop("ro.product.model"),
            "android_release": prop("ro.build.version.release"),
            "abi": prop("ro.product.cpu.abi"),
            "termux_version": os.environ.get("TERMUX_VERSION", "unknown"),
        },
        "findings": FINDINGS,
        "summary": {
            level: sum(f["severity"] == level for f in FINDINGS)
            for level in ("pass", "info", "warning", "error")
        },
    }


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in ("0", "1") or sys.argv[2] not in ("0", "1"):
        print("usage: doctor_report.py GRAPHICS JSON STATE_DIR", file=sys.stderr)
        return 2
    graphics = sys.argv[1] == "1"
    json_output = sys.argv[2] == "1"
    report = build_report(graphics, Path(sys.argv[3]))
    if json_output:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print("Ternuxx Doctor — read-only report")
        print(f"Overall: {report['overall']} | Termux: {report['device']['termux_version']} | Android: {report['device']['android_release']}")
        for item in FINDINGS:
            print(f"[{item['severity'].upper():7}] {item['id']}  {item['scope']}: {item['observed']}")
            if item['severity'] in ("warning", "error"):
                print(f"           Next: {item['suggested_action']}")
        print(f"Summary: {report['summary']}")
        print("Read-only: no package, service, process, setting, or file changes were made.")
    return 2 if report["overall"] == "error" else (1 if report["overall"] == "warning" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
