"""Read-only Doctor report contract tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import doctor_report  # noqa: E402


class DoctorReportTest(unittest.TestCase):
    def test_graphics_probes_put_termux_runtime_before_injected_loader_path(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=1, stdout="probe unavailable")
        with patch.dict("os.environ", {
                "DISPLAY": ":1", "PREFIX": "/termux", "LD_LIBRARY_PATH": "/codex/private:/custom/lib"}),                 patch.object(doctor_report, "command_path", side_effect=lambda name: "/mock/" + name),                 patch.object(doctor_report.subprocess, "run", side_effect=fake_run):
            doctor_report.FINDINGS.clear()
            doctor_report.graphics_probe()
        self.assertEqual(len(calls), 2)
        for _, kwargs in calls:
            self.assertEqual(kwargs["env"]["LD_LIBRARY_PATH"],
                             "/termux/lib:/codex/private:/custom/lib")
        self.assertEqual(calls[0][0], ["/mock/glxinfo", "-B"])
        self.assertEqual(calls[1][0], ["/mock/vulkaninfo", "--summary"])

    def test_native_npu_report_separates_vendor_libraries_nodes_and_runtime(self):
        def present(path):
            return path.name in {"libQnnHtp.so", "libcdsprpc.so"}
        with patch.object(doctor_report, "path_presence", side_effect=present), \
                patch.object(doctor_report, "command_path", return_value=None):
            evidence = doctor_report.native_npu_evidence()
        self.assertIn("Android vendor libraries visible=libQnnHtp.so,libcdsprpc.so", evidence)
        self.assertIn("FastRPC candidate nodes none-visible", evidence)
        self.assertIn("no-known-runtime-cli-found", evidence)
        self.assertIn("NPU execution=unverified", evidence)

    def test_native_npu_report_keeps_inaccessible_probes_unknown(self):
        with patch.object(doctor_report, "path_presence", return_value=None), \
                patch.object(doctor_report, "command_path", return_value=None):
            evidence = doctor_report.native_npu_evidence()
        self.assertIn("Android vendor libraries visibility=unknown", evidence)
        self.assertIn("FastRPC candidate nodes visibility=unknown", evidence)
        self.assertIn("NPU execution=unverified", evidence)

    def test_native_npu_report_does_not_infer_access_from_runtime_name_alone(self):
        with patch.object(doctor_report, "path_presence", return_value=False), \
                patch.object(doctor_report, "command_path", side_effect=lambda name: "/mock/" + name if name == "qnn-net-run" else None):
            evidence = doctor_report.native_npu_evidence()
        self.assertIn("Termux runtime tools found=qnn-net-run", evidence)
        self.assertIn("NPU execution=unverified", evidence)

    def test_pulse_probe_uses_only_explicit_loopback_tcp_endpoint(self):
        with patch.object(doctor_report, "command_path", return_value="/mock/pactl"), \
                patch.object(doctor_report.subprocess, "run", return_value=SimpleNamespace(
                    returncode=0, stdout="Server Name: PulseAudio\nDefault Sink: Speaker\n")) as run:
            status, detail = doctor_report.pulse_server_status()
        self.assertEqual(status, "ready")
        self.assertIn("authenticated loopback endpoint", detail)
        self.assertEqual(run.call_args.args[0], ["/mock/pactl", "--server", "tcp:127.0.0.1:4713", "info"])
        self.assertTrue(run.call_args.kwargs["env"]["PULSE_COOKIE"].endswith("/.config/pulse/cookie"))

    def test_rish_bundle_inspection_requires_private_owned_files_and_never_executes(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-rish-") as temporary:
            root = Path(temporary)
            wrapper, dex = root / "rish", root / "rish_shizuku.dex"
            wrapper.write_text("#!/system/bin/sh\n", encoding="utf-8")
            dex.write_bytes(b"dex\n037\0")
            wrapper.chmod(0o700)
            dex.chmod(0o400)
            self.assertIn("invocation not verified", doctor_report.rish_bundle_status(root))
            dex.chmod(0o644)
            self.assertIn("unsafe", doctor_report.rish_bundle_status(root))

    def test_addon_presence_query_failure_is_unknown_not_absent(self):
        failed = SimpleNamespace(returncode=2, stdout="package service unavailable")
        with patch.object(doctor_report, "command_path", return_value="/mock/pm"), \
                patch.object(doctor_report, "run", return_value=failed):
            self.assertEqual(doctor_report.app_path("com.termux.x11"),
                             "unknown (Android package query failed with exit 2)")

    def test_addon_presence_prefers_direct_cmd_package_query(self):
        calls = []
        def fake_run(argv, timeout=3.0):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="package:/data/app/com.termux.boot/base.apk")
        def fake_path(name):
            return {"cmd": "/mock/cmd", "pm": "/mock/pm"}.get(name)
        with patch.object(doctor_report, "command_path", side_effect=fake_path), \
                patch.object(doctor_report, "run", side_effect=fake_run):
            result = doctor_report.app_path("com.termux.boot")
        self.assertEqual(result, "present")
        self.assertEqual(calls, [["/mock/cmd", "package", "path", "com.termux.boot"]])

    def test_android_package_version_code_is_read_only_metadata(self):
        calls = []
        def fake_path(name):
            return {"cmd": "/mock/cmd", "pm": "/mock/pm"}.get(name)
        def fake_run(argv, timeout=3.0):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="package:moe.shizuku.privileged.api versionCode:1318\n")
        with patch.object(doctor_report, "command_path", side_effect=fake_path):
            with patch.object(doctor_report, "run", side_effect=fake_run):
                result = doctor_report.app_version_code("moe.shizuku.privileged.api")
        self.assertEqual(result, "1318")
        self.assertEqual(calls, [[
            "/mock/cmd", "package", "list", "packages", "--show-versioncode",
            "moe.shizuku.privileged.api",
        ]])

    def test_android_package_version_code_keeps_ambiguous_output_unknown(self):
        with patch.object(doctor_report, "command_path", return_value="/mock/cmd"):
            with patch.object(doctor_report, "run", return_value=SimpleNamespace(
                    returncode=0, stdout="package:other.app versionCode:5\n")):
                result = doctor_report.app_version_code("moe.shizuku.privileged.api")
        self.assertEqual(result, "unknown (Android package version query failed or was ambiguous)")

    def test_addon_presence_falls_back_to_pm_but_keeps_empty_output_unknown(self):
        calls = []
        def fake_run(argv, timeout=3.0):
            calls.append(argv)
            if argv[0] == "/mock/cmd":
                return SimpleNamespace(returncode=2, stdout="")
            return SimpleNamespace(returncode=0, stdout="")
        def fake_path(name):
            return {"cmd": "/mock/cmd", "pm": "/mock/pm"}.get(name)
        with patch.object(doctor_report, "command_path", side_effect=fake_path), \
                patch.object(doctor_report, "run", side_effect=fake_run):
            result = doctor_report.app_path("com.termux.boot")
        self.assertEqual(result, "unknown (Android package query returned ambiguous output)")
        self.assertEqual(calls, [["/mock/cmd", "package", "path", "com.termux.boot"],
                                 ["/mock/pm", "path", "com.termux.boot"]])

    def test_finding_ids_and_json_contract_are_stable(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-") as temporary:
            home = Path(temporary)
            state = home / ".local" / "share" / "ternuxx"
            with (
                patch.object(doctor_report.Path, "home", return_value=home),
                patch.object(doctor_report, "native_termux", return_value=True),
                patch.object(doctor_report, "prop", return_value="fixture-value"),
                patch.object(doctor_report, "command_path", side_effect=lambda name: None if name == "rish" else f"/mock/{name}"),
                patch.object(doctor_report, "native_npu_evidence", return_value="fixture NPU execution=unverified"),
                patch.object(doctor_report, "app_version_code", return_value="1318"),
                patch.object(doctor_report, "shizuku_server_process_status", return_value="not observed (process visibility unknown)"),
                patch.object(doctor_report, "package_status", return_value=("installed", "1.0")),
                patch.object(doctor_report, "app_path", return_value="present"),
                patch.object(doctor_report.runtime_diagnostics, "inspect_boot", return_value={
                    "app": "installed", "package_enabled": "enabled",
                    "boot_completed_receiver": "enabled", "regular_script_count": 2,
                    "non_executable_script_count": 0, "system_delivery_policy": "unknown",
                }),
                patch.object(doctor_report.adb_diagnostics, "inspect_local_server", return_value={
                    "status": "available", "server_protocol_version_hex": "0029",
                }),
                patch.object(doctor_report.shutil, "disk_usage", return_value=SimpleNamespace(free=4 * 1024**3)),
                patch.object(doctor_report, "pulse_server_status", return_value=("ready", "protocol connected")),
                patch.object(doctor_report.cpu_inference, "status", return_value={
                    "runtime": {"available": True, "version": "llama.cpp fixture"},
                    "model": {"state": "present-unverified", "id": "qwen3-0.6b-q4_0"},
                }),
                patch.object(doctor_report, "check_session") as check_session, \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value={"checks": {}}),
            ):
                first = doctor_report.build_report(False, state)
                first_ids = [finding["id"] for finding in first["findings"]]
                second = doctor_report.build_report(False, state)
                second_ids = [finding["id"] for finding in second["findings"]]

            self.assertEqual(first_ids, second_ids)
            self.assertEqual(len(first_ids), len(set(first_ids)))
            for finding_id in first_ids:
                self.assertRegex(finding_id, r"^NTX-[A-Z]+-[0-9]{3}$")
            self.assertTrue(first["read_only"])
            self.assertEqual(first["schema_version"], 1)
            self.assertEqual(first["overall"], "pass")
            self.assertFalse(any(f["id"] == "NTX-PROOT-001" for f in first["findings"]))
            cpu = next(f for f in first["findings"] if f["id"] == "NTX-CPU-001")
            self.assertEqual(cpu["scope"], "native-compute")
            self.assertIn("CPU is the native execution baseline", cpu["observed"])
            self.assertIn("CPU inference workflow=available", cpu["observed"])
            self.assertIn("runtime=llama.cpp fixture", cpu["observed"])
            self.assertIn("model=present-unverified", cpu["observed"])
            self.assertNotIn("/models/", cpu["observed"])
            self.assertIn("verify the model hash", cpu["suggested_action"])
            shizuku = next(f for f in first["findings"] if f["id"] == "NTX-APP-103")
            termux_boot = next(f for f in first["findings"] if f["id"] == "NTX-APP-102")
            adb_server = next(f for f in first["findings"] if f["id"] == "NTX-ADB-001")
            self.assertIn("package: enabled", termux_boot["observed"])
            self.assertIn("BOOT_COMPLETED receiver: enabled", termux_boot["observed"])
            self.assertIn("system delivery policy: unknown", termux_boot["observed"])
            self.assertIn("does not prove boot delivery", termux_boot["suggested_action"])
            self.assertIn("package versionCode: 1318", shizuku["observed"])
            self.assertIn("rish command: not found", shizuku["observed"])
            self.assertIn("package ID: moe.shizuku.privileged.api", shizuku["observed"])
            self.assertIn("shizuku_server process-name signal: not observed", shizuku["observed"])
            self.assertIn("provider identity (upstream/custom): unverified", shizuku["observed"])
            self.assertNotIn("upstream shizuku_server process-name signal", shizuku["observed"])
            self.assertIn("Ternuxx provider: not implemented", shizuku["observed"])
            self.assertIn("signer/release identity, granted permission, and watchdog health: unknown", shizuku["observed"])
            self.assertIn("upstream/custom release identity", shizuku["suggested_action"])
            self.assertIn("no ADB-over-Wi-Fi operation is enabled", shizuku["suggested_action"])
            self.assertIn("127.0.0.1:5037", adb_server["observed"])
            self.assertIn("0x0029", adb_server["observed"])
            self.assertIn("does not start ADB", adb_server["suggested_action"])
            self.assertEqual(sum(first["summary"].values()), len(first["findings"]))
            self.assertEqual(check_session.call_count, 2)
            encoded = json.dumps(first)
            self.assertEqual(json.loads(encoded)["command"], "doctor")

    def test_doctor_backup_check_is_read_only_when_empty(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-backups-") as temporary:
            home = Path(temporary)
            state = home / ".local" / "share" / "ternuxx"
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home):
                doctor_report.check_backups(state)
            finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-BACKUP-001")
            self.assertEqual(finding["severity"], "info")
            self.assertFalse(state.exists())

    def test_doctor_warns_when_backup_integrity_is_invalid(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-backups-") as temporary:
            home = Path(temporary)
            state = home / ".local" / "share" / "ternuxx"
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home), patch.object(
                doctor_report.config_recovery, "list_backups",
                return_value={"backups": [{"backup_id": "sample", "integrity": "invalid"}], "read_only": True},
            ):
                doctor_report.check_backups(state)
            finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-BACKUP-002")
            self.assertEqual(finding["severity"], "warning")
            self.assertIn("integrity failures: 1", finding["observed"])

    def test_doctor_warns_when_backup_path_is_unsafe(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-home-") as home, \
                tempfile.TemporaryDirectory(prefix="ternuxx-doctor-outside-") as outside:
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=Path(home)):
                doctor_report.check_backups(Path(outside))
            finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-BACKUP-001")
            self.assertEqual(finding["severity"], "warning")
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_doctor_reports_owned_runit_service_without_claiming_listener_reachability(self):
        result = {"checks": {"managed_service": {"manager": "runit", "service_id": "ternuxx-sshd",
                  "status": "running", "config_syntax": "valid"}}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SVC-001")
        self.assertEqual(finding["severity"], "pass")
        self.assertIn("managed process identity=unknown", finding["observed"])
        self.assertIn("listener-to-port correlation=unknown", finding["observed"])

    def test_doctor_warns_when_managed_runit_process_identity_is_not_verified(self):
        result = {"checks": {"managed_service": {"manager": "runit", "service_id": "ternuxx-sshd",
                  "status": "running", "config_syntax": "valid", "process_identity": "not_verified",
                  "loopback_ssh_probe": {"status": "ssh_banner"}},
                  "listener_daemon_correlation": "unknown", "tcp_listener_observation": "permission_denied"}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SVC-001")
        self.assertEqual(finding["severity"], "warning")
        self.assertIn("managed process identity=not_verified", finding["observed"])
        self.assertIn("listener-to-port correlation=unknown", finding["observed"])

    def test_doctor_warns_on_wildcard_native_ssh_config_without_claiming_reachability(self):
        result = {"checks": {"configured_listener_bind_scope": "wildcard",
                  "external_config_authentication": {"passwordauthentication": ["yes"]},
                  "managed_service": {"manager": "runit", "service_id": "ternuxx-sshd",
                  "status": "running", "config_syntax": "valid", "loopback_ssh_probe": {"status": "ssh_banner"}}}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SSH-001")
        self.assertEqual(finding["severity"], "warning")
        self.assertIn("bind scope=wildcard", finding["observed"])
        self.assertIn("password authentication=enabled", finding["observed"])
        self.assertIn("external reachability=unknown", finding["observed"])
        self.assertIn("does not change SSH configuration", finding["suggested_action"])

    def test_doctor_warns_when_running_managed_service_has_no_loopback_ssh_banner(self):
        result = {"checks": {"managed_service": {"manager": "runit", "service_id": "ternuxx-sshd",
                  "status": "running", "config_syntax": "valid",
                  "loopback_ssh_probe": {"status": "unreachable"}}}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SVC-001")
        self.assertEqual(finding["severity"], "warning")
        self.assertIn("loopback SSH probe=unreachable", finding["observed"])
        self.assertIn("will not start, stop, or repair", finding["suggested_action"])

    def test_doctor_warns_when_managed_service_definition_mismatches_checkout(self):
        result = {"checks": {"managed_service": {"manager": "runit", "service_id": "ternuxx-sshd",
                  "status": "running", "config_syntax": "valid",
                  "definition_identity": {"status": "mismatch"}}}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SVC-001")
        self.assertEqual(finding["severity"], "warning")
        self.assertIn("definition identity=mismatch", finding["observed"])
        self.assertIn("Keep the service unchanged", finding["suggested_action"])

    def test_doctor_service_manager_absence_does_not_silently_fallback(self):
        result = {"checks": {"managed_service": {"manager": "not_detected", "service_id": "ternuxx-sshd",
                  "status": "unknown", "config_syntax": "unknown"}}}
        doctor_report.FINDINGS.clear()
        with patch.object(doctor_report, "native_termux", return_value=True), \
                patch.dict(doctor_report.os.environ, {"PREFIX": "/termux"}), \
                patch.object(doctor_report.ssh_diagnostics, "inspect_native", return_value=result):
            doctor_report.check_service_manager()
        finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SVC-001")
        self.assertEqual(finding["severity"], "info")
        self.assertIn("No manager fallback is automatic", finding["suggested_action"])

    def test_process_inventory_separates_verified_owner_from_unverified_candidates(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-inventory-") as temporary:
            root = Path(temporary)
            home = root / "home"
            state = home / ".local" / "share" / "ternuxx"
            proc = root / "proc"
            home.mkdir()
            state.mkdir(parents=True)
            proc.mkdir()
            session = {"schema": 2, "owner": "ternuxx", "status": "running", "display": ":1",
                       "x11": {"pid": 123, "start_ticks": "1", "command_marker": "termux-x11", "pgid": "123", "sid": "123"}}
            (state / "session.json").write_text(json.dumps(session), encoding="utf-8")
            owned = proc / "123"
            owned.mkdir()
            stat_fields = ["S", "0", "123", "123"] + ["0"] * 15 + ["1"]
            (owned / "stat").write_text("123 (termux-x11) " + " ".join(stat_fields), encoding="ascii")
            (owned / "cmdline").write_bytes(b"termux-x11\0")
            (owned / "comm").write_text("termux-x11\n", encoding="ascii")
            other = proc / "456"
            other.mkdir()
            (other / "comm").write_text("xfce4-session\n", encoding="ascii")
            other_stat = ["S", "0", "456", "456"] + ["0"] * 15 + ["1"]
            (other / "stat").write_text("456 (xfce4-session) " + " ".join(other_stat), encoding="ascii")
            session_child = proc / "457"
            session_child.mkdir()
            (session_child / "comm").write_text("xfce4-panel\n", encoding="ascii")
            child_stat = ["S", "0", "457", "123"] + ["0"] * 15 + ["2"]
            (session_child / "stat").write_text("457 (xfce4-panel) " + " ".join(child_stat), encoding="ascii")
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home):
                doctor_report.check_process_inventory(state, proc_root=proc)
            finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SESSION-030")
            self.assertIn("verified Ternuxx-owned roots: x11=1", finding["observed"])
            self.assertIn("same recorded session candidates: xfce4-panel=1", finding["observed"])
            self.assertIn("owner unverified: xfce4-session=1", finding["observed"])
            self.assertNotIn("456", finding["observed"])

    def test_process_inventory_does_not_call_other_processes_external(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-inventory-") as temporary:
            root = Path(temporary)
            home = root / "home"
            state = home / "state"
            proc = root / "proc"
            home.mkdir()
            state.mkdir()
            proc.mkdir()
            other = proc / "789"
            other.mkdir()
            (other / "comm").write_text("xfwm4\n", encoding="ascii")
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home):
                doctor_report.check_process_inventory(state, proc_root=proc)
            finding = next(f for f in doctor_report.FINDINGS if f["id"] == "NTX-SESSION-030")
            self.assertIn("xfwm4=1", finding["observed"])
            self.assertIn("owner unverified", finding["observed"])
            self.assertIn("may belong to Termux or Android", finding["suggested_action"])

    def test_proc_identity_allows_supervisor_without_group_fields(self):
        import os

        pid = os.getpid()
        stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rpartition(")")[2].strip().split()
        ticks = stat_fields[19]
        marker = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0", 1)[0].decode()
        verified, detail = doctor_report.proc_identity("supervisor", {
            "pid": pid, "start_ticks": ticks, "command_marker": marker,
        })
        self.assertTrue(verified, detail)
        self.assertIn("not recorded", detail)

    def test_proc_identity_checks_recorded_child_process_groups(self):
        import os

        pid = os.getpid()
        stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rpartition(")")[2].strip().split()
        ticks = stat_fields[19]
        marker = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0", 1)[0].decode()
        verified, detail = doctor_report.proc_identity("child", {
            "pid": pid, "start_ticks": ticks, "command_marker": marker,
            "pgid": -999, "sid": -999,
        })
        self.assertFalse(verified)
        self.assertEqual(detail, "recorded process group/session does not match")

    def test_session_report_discovers_one_verified_live_state_when_default_is_missing(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-discovered-") as temporary:
            home = Path(temporary)
            configured = home / ".local" / "share" / "ternuxx"
            discovered = home / ".local" / "share" / "active-session"
            discovered.mkdir(parents=True)
            (discovered / "session.json").write_text(json.dumps({
                "schema": 2, "owner": "ternuxx", "provider": "native",
                "status": "running", "display": ":1",
            }), encoding="utf-8")
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home), \
                    patch.object(doctor_report, "discover_live_session_state", return_value=discovered):
                doctor_report.check_session(configured)
            observed = [finding["observed"] for finding in doctor_report.FINDINGS]
            self.assertIn("recorded state=running, display=:1", observed)
            self.assertNotIn("no session record at configured path; no unique verified live session state discovered", observed)

    def test_current_ternuxx_session_owner_is_accepted(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-current-owner-") as temporary:
            home = Path(temporary)
            state = home / ".local" / "share" / "ternuxx"
            state.mkdir(parents=True)
            (state / "session.json").write_text(json.dumps({
                "schema": 2, "owner": "ternuxx", "status": "failed", "display": ":9",
            }), encoding="utf-8")
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=home):
                doctor_report.check_session(state)
            self.assertNotIn("NTX-SESSION-012", [finding["id"] for finding in doctor_report.FINDINGS])
            self.assertIn("recorded state=failed, display=:9", [finding["observed"] for finding in doctor_report.FINDINGS])

    def test_state_outside_home_is_reported_without_reading_it(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-doctor-home-") as home, \
                tempfile.TemporaryDirectory(prefix="ternuxx-doctor-outside-") as outside:
            doctor_report.FINDINGS.clear()
            with patch.object(doctor_report.Path, "home", return_value=Path(home)):
                doctor_report.check_session(Path(outside))
            self.assertEqual(doctor_report.FINDINGS[0]["id"], "NTX-SESSION-001")
            self.assertEqual(doctor_report.FINDINGS[0]["severity"], "error")
            self.assertEqual(list(Path(outside).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
