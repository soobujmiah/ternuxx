"""Read-only SSH diagnostics tests using synthetic procfs and fake sshd."""

from __future__ import annotations

from pathlib import Path
import errno
import ipaddress
import os
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import ssh_diagnostics  # noqa: E402


class SshDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-ssh-fixture-")
        self.root = Path(self.temp.name)
        self.prefix = self.root / "prefix"
        self.config = self.prefix / "etc/ssh/sshd_config"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("# synthetic config; diagnostics must not emit this\n", encoding="utf-8")
        self.home = self.root / "home"
        (self.home / ".termux/boot").mkdir(parents=True)
        managed = self.home / ".config/ternuxx/sshd_recovery.conf"
        managed.parent.mkdir(parents=True)
        managed.write_text("# managed fixture\n", encoding="utf-8")
        self.proc = self.root / "proc"
        (self.proc / "123").mkdir(parents=True)
        (self.proc / "123/comm").write_text("sshd\n", encoding="utf-8")
        (self.proc / "net").mkdir()
        (self.proc / "net/tcp").write_text(
            "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
            "0: 0100007F:1F92 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1000 0 111\n"
            "1: 00000000:1F92 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1000 0 222\n"
            "2: 0F02000A:1F92 00000000:0000 01 00000000:00000000 00:00000000 00000000 1000 0 223\n",
            encoding="ascii",
        )
        (self.proc / "net/tcp6").write_text(
            "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
            "0: 00000000000000000000000001000000:1F92 00000000000000000000000000000000:0000 0A 0:0 00:0 0 0 0 333\n",
            encoding="ascii",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_service_definition_identity_requires_fixed_owned_exact_script(self) -> None:
        source = self.root / "source-run"
        service_dir = self.prefix / "var/service/ternuxx-sshd"
        run = service_dir / "run"
        service_dir.mkdir(parents=True)
        source.write_text("#!/bin/sh\necho expected\n", encoding="utf-8")
        run.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        run.chmod(0o700)
        verified = ssh_diagnostics._managed_service_definition_identity(self.prefix, source)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["source_sha256"], verified["installed_sha256"])

        run.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
        mismatch = ssh_diagnostics._managed_service_definition_identity(self.prefix, source)
        self.assertEqual(mismatch["status"], "mismatch")
        self.assertNotEqual(mismatch["source_sha256"], mismatch["installed_sha256"])

        run.unlink()
        run.symlink_to(source)
        unsafe = ssh_diagnostics._managed_service_definition_identity(self.prefix, source)
        self.assertEqual(unsafe["status"], "unsafe")

        unsafe_prefix = self.root / "unsafe-prefix"
        unsafe_prefix.mkdir()
        (unsafe_prefix / "var").mkdir()
        (unsafe_prefix / "var/service").symlink_to(service_dir.parent, target_is_directory=True)
        redirected = ssh_diagnostics._managed_service_definition_identity(unsafe_prefix, source)
        self.assertEqual(redirected["status"], "unsafe")

    def test_installed_module_resolves_canonical_checkout_service_source(self) -> None:
        home = self.root / "device-home"
        source = home / "ternuxx/scripts/termux-services/ternuxx-sshd/run"
        source.parent.mkdir(parents=True)
        source.write_text("#!/bin/sh\necho managed\n", encoding="utf-8")
        source.chmod(0o700)
        run_dir = self.prefix / "var/service/ternuxx-sshd"
        run_dir.mkdir(parents=True)
        installed = run_dir / "run"
        installed.write_bytes(source.read_bytes())
        installed.chmod(0o700)
        installed_module = self.prefix / "lib/ternuxx/ssh_diagnostics.py"
        with patch.object(ssh_diagnostics, "__file__", str(installed_module)), \
             patch("pathlib.Path.home", return_value=home):
            identity = ssh_diagnostics._managed_service_definition_identity(self.prefix)
        self.assertEqual(identity["status"], "verified")
        self.assertEqual(identity["source_sha256"], identity["installed_sha256"])

    def test_report_allowlists_policy_and_does_not_correlate_global_listeners(self) -> None:
        calls: list[list[str]] = []

        class FakeSocket:
            def recv(self, _size: int) -> bytes:
                return b"SSH-2.0-fixture"

            def close(self) -> None:
                return None

        def which(command: str) -> str | None:
            return {"sshd": "/synthetic/sshd", "sv": None}.get(command)

        def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if args[1] == "status":
                return subprocess.CompletedProcess(args, 0, f"run: {args[2]}: (pid 1) 2s\n", "")
            if args[1] == "-t":
                return subprocess.CompletedProcess(args, 0, "", "")
            port = "8027" if str(self.home / ".config/ternuxx/sshd_recovery.conf") in args else "8026"
            address = "127.0.0.1" if port == "8027" else "0.0.0.0"
            return subprocess.CompletedProcess(
                args, 0,
                f"port {port}\nlistenaddress {address}:{port}\npubkeyauthentication yes\npasswordauthentication no\n"
                "hostkey /private/path\n# password never-output\n",
                "",
            )

        report = ssh_diagnostics.inspect_native(
            prefix=self.prefix, home=self.home, proc_root=self.proc,
            which=lambda command: {"sshd": "/synthetic/sshd", "sv": "/synthetic/sv"}.get(command), runner=runner,
            socket_connector=lambda endpoint, timeout: FakeSocket(),
        )
        checks = report["checks"]
        schema = __import__("json").loads((ROOT / "schemas/native-ssh-diagnostic-report.schema.json").read_text())
        correlation_enum = schema["properties"]["checks"]["properties"]["listener_daemon_correlation"]["enum"]
        self.assertIn(checks["listener_daemon_correlation"], correlation_enum)
        self.assertEqual(checks["config_syntax"], "valid")
        self.assertIn(checks["policy_context"], {"default_without_connection_context", "native_user_loopback"})
        self.assertEqual(checks["external_config_authentication"]["passwordauthentication"], ["no"])
        self.assertEqual(checks["configured_listener_bind_scope"], "wildcard")
        status_call = next(call for call in calls if len(call) > 1 and call[1] == "status")
        self.assertEqual(status_call, ["/synthetic/sv", "status", str(self.prefix / "var/service/ternuxx-sshd")])
        self.assertEqual(checks["managed_service"]["status"], "running")
        timing = checks["managed_service"]["startup_timing"]
        self.assertIn(timing["status"], {"observed", "unavailable", "inconsistent"})
        self.assertNotIn("pid", timing)
        self.assertEqual(checks["managed_service"]["effective_policy"]["port"], ["8027"])
        self.assertEqual(checks["managed_service"]["effective_policy"]["listenaddress"], ["127.0.0.1:8027"])
        self.assertEqual(checks["managed_service"]["listener_bind_scope"], "loopback_only")
        self.assertEqual(checks["managed_service"]["loopback_ssh_probe"],
                         {"status": "ssh_banner", "address": "127.0.0.1", "port": 8027})
        self.assertNotIn("hostkey", checks["external_config_authentication"])
        self.assertNotIn("port", checks["external_config_authentication"])
        self.assertEqual(checks["observed_tcp_listener_count"], 3)
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(checks["listener_daemon_correlation"], "unknown")
        self.assertEqual(checks["tcp_listener_observation"], "complete")
        self.assertEqual(checks["daemon_process_present"], True)
        self.assertNotIn("observed_tcp_listeners_all_processes", checks)
        public_json = __import__("json").dumps(report, sort_keys=True)
        self.assertNotIn("8026", public_json)
        self.assertNotIn("0.0.0.0", public_json)
        self.assertFalse(report["safety"]["credential_files_read"])
        self.assertEqual(len(calls), 5)

    def test_netlink_sock_diag_decodes_tcp_listeners_and_complete_dump(self) -> None:
        class FakeNetlinkSocket:
            def __init__(self, family: int) -> None:
                self.family = family
                self.packet: bytes | None = None
                self.closed = False

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendto(self, request: bytes, _address: tuple[int, int]) -> int:
                length, message_type, flags, seq, _pid = struct.unpack_from("=IHHII", request)
                self.assert_request(length, message_type, flags, request[16:])
                self.sequence = seq
                return len(request)

            def assert_request(self, length: int, message_type: int, flags: int, body: bytes) -> None:
                self_outer.assertEqual(length, 72)
                self_outer.assertEqual(message_type, 20)
                self_outer.assertEqual(flags, 0x301)
                family, protocol, ext, pad, states = struct.unpack_from("=BBBBI", body)
                self_outer.assertEqual(family, self.family)
                self_outer.assertEqual(protocol, socket.IPPROTO_TCP)
                self_outer.assertEqual((ext, pad), (0, 0))
                self_outer.assertEqual(states, 1 << 10)
                self_outer.assertEqual(len(body[8:]), 48)

            def recvfrom(self, _size: int) -> tuple[bytes, tuple[int, int]]:
                if self.packet is None:
                    body = bytearray(72)
                    body[0] = self.family
                    body[1] = 10  # TCP_LISTEN
                    struct.pack_into("!H", body, 4, 8023 if self.family == socket.AF_INET else 8022)
                    address = ("127.0.0.1" if self.family == socket.AF_INET else "::1")
                    packed = ipaddress.ip_address(address).packed
                    body[8:8 + len(packed)] = packed
                    struct.pack_into("=I", body, 68, 9876 if self.family == socket.AF_INET else 9877)
                    diag = struct.pack("=IHHII", 88, 20, 2, self.sequence, 0) + body
                    done = struct.pack("=IHHII", 16, 3, 2, self.sequence, 0)
                    self.packet = diag + done
                packet, self.packet = self.packet, b""
                return packet, (0, 0)

            def close(self) -> None:
                self.closed = True

        self_outer = self
        channels: list[FakeNetlinkSocket] = []

        def factory(_family: int, _kind: int, _protocol: int) -> FakeNetlinkSocket:
            self.assertEqual(_family, socket.AF_NETLINK)
            channel = FakeNetlinkSocket(socket.AF_INET if not channels else socket.AF_INET6)
            channels.append(channel)
            return channel

        rows, status = ssh_diagnostics._netlink_tcp_listener_sockets(factory)
        self.assertEqual(status, "complete")
        self.assertEqual(rows, [
            {"address": "127.0.0.1", "port": 8023, "inode": "9876"},
            {"address": "::1", "port": 8022, "inode": "9877"},
        ])
        self.assertEqual(len(channels), 2)
        self.assertTrue(all(channel.closed for channel in channels))

    def test_netlink_sock_diag_permission_denial_stays_unknown(self) -> None:
        class DeniedSocket:
            def settimeout(self, _timeout: float) -> None:
                pass

            def sendto(self, _request: bytes, _address: tuple[int, int]) -> int:
                raise PermissionError(errno.EPERM, "permission denied")

            def close(self) -> None:
                pass

        rows, status = ssh_diagnostics._netlink_tcp_listener_sockets(
            lambda *_args: DeniedSocket())
        self.assertEqual(rows, [])
        self.assertEqual(status, "permission_denied")

    def test_netlink_listener_fallback_supersedes_partial_procfs_snapshot(self) -> None:
        (self.proc / "net/tcp6").unlink()
        fallback = [{"address": "127.0.0.1", "port": 8023, "inode": "444"}]
        rows, status = ssh_diagnostics._read_tcp_listener_sockets(
            self.proc, netlink_reader=lambda: (fallback, "complete"))
        self.assertEqual(status, "complete")
        self.assertEqual(rows, fallback)

    def test_runit_listener_correlation_requires_process_tree_and_socket_inode(self) -> None:
        run = self.proc / "10"
        child = self.proc / "11"
        (run / "fd").mkdir(parents=True)
        (child / "fd").mkdir(parents=True)
        def proc_stat(pid: int, comm: str, ppid: int, start: int) -> str:
            fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)]
            return f"{pid} ({comm}) " + " ".join(fields) + "\n"
        (run / "comm").write_text("run\n", encoding="utf-8")
        (run / "stat").write_text(proc_stat(10, "run", 1, 100), encoding="ascii")
        (child / "comm").write_text("sshd\n", encoding="utf-8")
        (child / "stat").write_text(proc_stat(11, "sshd", 10, 101), encoding="ascii")
        (child / "fd/5").symlink_to("socket:[444]")
        with (self.proc / "net/tcp").open("a", encoding="ascii") as stream:
            stream.write("3: 0100007F:1F5B 00000000:0000 0A 0:0 00:0 0 0 0 444\n")
        policy = {"port": ["8027"], "listenaddress": ["127.0.0.1:8027"]}
        sockets, status = ssh_diagnostics._read_tcp_listener_sockets(self.proc)
        self.assertEqual(status, "complete")
        self.assertEqual(ssh_diagnostics._correlate_runit_listener(self.proc, 10, policy, sockets, status), "verified")
        wrong_endpoint = {"port": ["8026"], "listenaddress": ["127.0.0.1:8026"]}
        self.assertEqual(ssh_diagnostics._correlate_runit_listener(self.proc, 10, wrong_endpoint, sockets, status), "not_verified")
        self.assertEqual(ssh_diagnostics._correlate_runit_listener(self.proc, 999, policy, sockets, status), "unknown")
        self.assertEqual(ssh_diagnostics._correlate_runit_listener(self.proc, 10, policy, sockets, "unavailable"), "unknown")

    def test_managed_service_process_identity_verifies_only_exact_runit_child(self) -> None:
        service_dir = self.prefix / "var/service/ternuxx-sshd"
        service_dir.mkdir(parents=True)
        (self.proc / "20").mkdir()
        (self.proc / "21").mkdir()
        (self.proc / "22").mkdir()
        (self.proc / "20/cwd").symlink_to(service_dir, target_is_directory=True)
        (self.proc / "21/cwd").symlink_to(service_dir, target_is_directory=True)

        def write_process(pid: int, comm: str, ppid: int, start: int, argv: list[str]) -> None:
            directory = self.proc / str(pid)
            fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)]
            (directory / "comm").write_text(comm + "\n", encoding="utf-8")
            (directory / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n", encoding="ascii")
            (directory / "status").write_text(f"Name:\t{comm}\nUid:\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\t{os.getuid()}\n", encoding="ascii")
            (directory / "cmdline").write_bytes(b"\0".join(item.encode() for item in argv) + b"\0")

        write_process(20, "runsv", 1, 200, ["runsv", "ternuxx-sshd"])
        bash_path = "/data/data/com.termux/files/usr/bin/bash"
        write_process(21, "run", 20, 201, [bash_path, "./run"])
        (self.proc / "21/exe").symlink_to(bash_path)
        config = self.home / ".config/ternuxx/sshd_recovery.conf"
        sshd_path = "/synthetic/sshd"
        write_process(22, "sshd", 21, 202, [sshd_path, "-D", "-e", "-f", str(config)])

        result = ssh_diagnostics._managed_service_process_identity(
            self.proc, 21, service_dir, sshd_path, config)
        self.assertEqual(result, "verified")
        (self.proc / "21/exe").unlink()
        (self.proc / "21/exe").symlink_to("/synthetic/not-bash")
        self.assertEqual(ssh_diagnostics._managed_service_process_identity(
            self.proc, 21, service_dir, sshd_path, config), "not_verified")
        (self.proc / "21/exe").unlink()
        (self.proc / "21/exe").symlink_to(bash_path)
        (self.proc / "20/cwd").unlink()
        (self.proc / "20/cwd").symlink_to(self.prefix, target_is_directory=True)
        self.assertEqual(ssh_diagnostics._managed_service_process_identity(
            self.proc, 21, service_dir, sshd_path, config), "not_verified")
        (self.proc / "20/cwd").unlink()
        (self.proc / "20/cwd").symlink_to(service_dir, target_is_directory=True)
        (self.proc / "22/cmdline").write_bytes(
            b"\0".join(item.encode() for item in [sshd_path, "-D", "-e", "-f", "/other/config"]) + b"\0")
        self.assertEqual(ssh_diagnostics._managed_service_process_identity(
            self.proc, 21, service_dir, sshd_path, config), "not_verified")

    def test_runit_startup_timing_is_sanitized_and_fail_closed(self) -> None:
        line = "run: ternuxx-sshd: (pid 456) 1h 20m 3s, normally down"
        result = ssh_diagnostics._runit_startup_timing("running", line, lambda: 5000.0)
        self.assertEqual(result, {
            "status": "observed",
            "kernel_uptime_seconds": 5000,
            "runit_service_age_seconds": 4803,
            "seconds_after_kernel_boot": 197,
        })
        self.assertNotIn("pid", result)
        self.assertEqual(
            ssh_diagnostics._runit_startup_timing("stopped", "", lambda: 10.0)["status"],
            "not_running",
        )
        self.assertEqual(
            ssh_diagnostics._runit_startup_timing("running", "unparseable", lambda: 10.0)["status"],
            "unavailable",
        )
        self.assertEqual(
            ssh_diagnostics._runit_startup_timing(
                "running", "run: ternuxx-sshd: (pid 456) 20s", lambda: 10.0
            )["status"],
            "inconsistent",
        )
        self.assertEqual(
            ssh_diagnostics._runit_startup_timing(
                "running", "run: ternuxx-sshd: (pid 456) 2s", lambda: None
            )["status"],
            "unavailable",
        )

    def test_proc_listener_permission_denial_is_distinguished_from_absence(self) -> None:
        original = Path.read_text
        def deny_network_tables(path: Path, *args, **kwargs):
            if path.name in {"tcp", "tcp6"}:
                raise PermissionError(errno.EACCES, "permission denied")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", deny_network_tables):
            sockets, status = ssh_diagnostics._read_tcp_listener_sockets(
                self.proc, netlink_reader=lambda: ([], "permission_denied"))
        self.assertEqual(sockets, [])
        self.assertEqual(status, "permission_denied")

    def test_missing_tools_and_procfs_report_unknown_without_failing(self) -> None:
        report = ssh_diagnostics.inspect_native(
            prefix=self.prefix, home=self.home, proc_root=self.root / "missing-proc",
            which=lambda _command: None,
            netlink_reader=lambda: ([], "unavailable"),
        )
        checks = report["checks"]
        self.assertFalse(checks["sshd_available"])
        self.assertEqual(checks["daemon_process_present"], None)
        self.assertEqual(checks["observed_tcp_listener_count"], 0)
        self.assertEqual(checks["tcp_listener_observation"], "unavailable")
        self.assertEqual(checks["config_syntax"], "unknown")
        self.assertEqual(checks["managed_service"]["loopback_ssh_probe"]["status"], "not_attempted")

    def test_absent_process_in_visible_procfs_is_not_promoted_to_false(self) -> None:
        (self.proc / "123/comm").write_text("python\n", encoding="utf-8")
        self.assertIsNone(ssh_diagnostics._proc_has_sshd(self.proc))

    def test_listener_bind_scope_distinguishes_loopback_and_address_classes(self) -> None:
        classify = ssh_diagnostics.listener_bind_scope
        self.assertEqual(classify({"listenaddress": ["127.0.0.1:8022", "[::1]:8022"]}), "loopback_only")
        self.assertEqual(classify({"listenaddress": ["0.0.0.0:8022", "[::]:8022"]}), "wildcard")
        self.assertEqual(classify({"listenaddress": ["192.168.1.9:8022"]}), "non_loopback")
        self.assertEqual(classify({}), "unknown")

    def test_loopback_probe_is_restricted_to_explicit_loopback_policy(self) -> None:
        called: list[tuple[tuple[str, int], float]] = []

        class FakeSocket:
            def recv(self, _size: int) -> bytes:
                return b"SSH-2.0-fixture"

            def close(self) -> None:
                return None

        def connector(endpoint: tuple[str, int], *, timeout: float) -> FakeSocket:
            called.append((endpoint, timeout))
            return FakeSocket()

        wildcard = ssh_diagnostics._managed_loopback_ssh_probe(
            {"port": ["8023"], "listenaddress": ["0.0.0.0:8023"]}, connector)
        self.assertEqual(wildcard["status"], "not_applicable")
        self.assertEqual(called, [])

        result = ssh_diagnostics._managed_loopback_ssh_probe(
            {"port": ["8023"], "listenaddress": ["127.0.0.1:8023"]}, connector)
        self.assertEqual(result["status"], "ssh_banner")
        self.assertEqual(called, [(('127.0.0.1', 8023), 1.0)])

    def test_loopback_probe_distinguishes_unreachable_and_non_ssh_responses(self) -> None:
        def unavailable(_endpoint: tuple[str, int], *, timeout: float) -> object:
            raise ConnectionRefusedError("fixture")

        result = ssh_diagnostics._managed_loopback_ssh_probe(
            {"port": ["8023"], "listenaddress": ["127.0.0.1:8023"]}, unavailable)
        self.assertEqual(result["status"], "unreachable")

        class OtherService:
            def recv(self, _size: int) -> bytes:
                return b"HTTP/"

            def close(self) -> None:
                return None

        result = ssh_diagnostics._managed_loopback_ssh_probe(
            {"port": ["8023"], "listenaddress": ["127.0.0.1:8023"]},
            lambda _endpoint, timeout: OtherService())
        self.assertEqual(result["status"], "unexpected_protocol")


if __name__ == "__main__":
    unittest.main()
