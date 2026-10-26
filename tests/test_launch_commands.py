"""Native launch command and retired-route contract tests."""
from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LaunchCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-launch-")
        self.root = Path(self.temp.name)
        self.prefix = self.root / "prefix"
        self.prefix.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.root),
            "PREFIX": str(self.prefix),
            "PATH": os.environ["PATH"],
            "TERNUXX_STATE_DIR": str(self.root / "state"),
            "TERNUXX_LOG_DIR": str(self.root / "log"),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), *args],
            capture_output=True, text=True, env=self.env, timeout=15,
        )

    def test_restored_guest_routes_are_documented_and_status_stays_read_only(self):
        self.env["PREFIX"] = "/data/data/com.termux/files/usr"
        self.env["TERMUX_VERSION"] = "fixture"
        for command in ("proot", "db", "pgui"):
            with self.subTest(command=command):
                result = self.cli(command, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertIn("Debian", result.stdout)
        status = self.cli("--json", "proot", "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertTrue(payload["data"]["read_only"])
        self.assertFalse(payload["data"]["guest_entered"])
        self.assertIsInstance(payload["data"]["installed_distributions"], list)

    def test_native_app_command_is_live_not_a_retired_guest_alias(self):
        result = self.cli("app")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Native Termux", result.stderr)
        self.assertNotIn("retired", result.stdout + result.stderr)

    def test_debian_menu_app_compatibility_route_reaches_the_shared_guest_service(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        fake_python = fake_bin / "python3"
        fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$TERNUXX_TEST_CAPTURE\"\n", encoding="utf-8")
        fake_python.chmod(0o755)
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "PATH": f"{fake_bin}:{self.env['PATH']}",
               "TERNUXX_TEST_CAPTURE": str(capture)}
        result = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "app", "--", "thunar"],
                                capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertEqual(args[-4:], ["--operation", "proot.app.launch", "--app-id", "files"])
        self.assertTrue(args[0].endswith("/lib/management_service.py"))

    def test_management_app_launch_routes_dynamic_debian_desktop_id_through_shared_service(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        fake_python = fake_bin / "python3"
        fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$TERNUXX_TEST_CAPTURE\"\n", encoding="utf-8")
        fake_python.chmod(0o755)
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "TERNUXX_JSON": "1",
               "PATH": f"{fake_bin}:{self.env['PATH']}", "TERNUXX_TEST_CAPTURE": str(capture)}
        result = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "--json", "mng", "app", "launch",
             "--desktop-id", "xfce4-about.desktop", "--display", ":0"],
            capture_output=True, text=True, env=env, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("--operation", args)
        self.assertEqual(args[args.index("--operation") + 1], "proot.app.launch")
        self.assertEqual(args[args.index("--desktop-id") + 1], "xfce4-about.desktop")
        self.assertEqual(args[args.index("--display") + 1], ":0")
        self.assertIn("--json", args)

    def test_management_app_launch_rejects_missing_id_and_invalid_display_before_guest(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "TERNUXX_TEST_CAPTURE": str(capture)}
        missing_id = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "mng", "app", "launch", "--display", ":0"],
            capture_output=True, text=True, env=env, timeout=15,
        )
        self.assertEqual(missing_id.returncode, 2)
        self.assertIn("Provide a fixed APP_ID", missing_id.stderr)
        invalid_display = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "mng", "app", "launch",
             "--desktop-id", "xfce4-about.desktop", "--display", "0"],
            capture_output=True, text=True, env=env, timeout=15,
        )
        self.assertEqual(invalid_display.returncode, 2)
        self.assertIn("Display must be an X11 display", invalid_display.stderr)
        self.assertFalse(capture.exists())

    def test_proot_session_cli_uses_shared_typed_operations_and_exact_stop_plan(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        fake_python = fake_bin / "python3"
        fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$TERNUXX_TEST_CAPTURE\"\n", encoding="utf-8")
        fake_python.chmod(0o755)
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "TERNUXX_JSON": "1",
               "PATH": f"{fake_bin}:{self.env['PATH']}", "TERNUXX_TEST_CAPTURE": str(capture)}
        listed = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "sessions", "list"],
                                capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.sessions.list", args)
        session_id, plan_id = "proot-" + "a" * 32, "plan-" + "b" * 24
        stopped = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "stop", session_id,
                                  "--yes", "--plan-id", plan_id],
                                 capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.stop", args)
        self.assertEqual(args[args.index("--session-id") + 1], session_id)
        self.assertEqual(args[args.index("--plan-id") + 1], plan_id)
        reconciled = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "reconcile", session_id,
                                     "--yes", "--plan-id", "plan-" + "c" * 64],
                                    capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(reconciled.returncode, 0, reconciled.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.recovery.reconcile", args)
        self.assertEqual(args[args.index("--plan-id") + 1], "plan-" + "c" * 64)

    def test_proot_stop_apply_requires_explicit_confirmation_and_saved_plan(self):
        result = self.cli("proot", "stop", "proot-" + "a" * 32)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--yes", result.stderr)
        self.assertIn("--plan-id", result.stderr)

    def test_proot_shortcut_cli_uses_shared_preview_and_exact_apply(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        fake_python = fake_bin / "python3"
        fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$TERNUXX_TEST_CAPTURE\"\n", encoding="utf-8")
        fake_python.chmod(0o755)
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "TERNUXX_JSON": "1",
               "PATH": f"{fake_bin}:{self.env['PATH']}", "TERNUXX_TEST_CAPTURE": str(capture)}
        preview = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts",
                                  "preview", "add", "thunar"], capture_output=True, text=True,
                                 env=env, timeout=15)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.preview", args)
        self.assertEqual(args[args.index("--shortcut-action") + 1], "add")
        self.assertEqual(args[args.index("--app-id") + 1], "thunar")
        applied = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts",
                                  "apply", "remove", "thunar", "--yes", "--plan-id", "a" * 24],
                                 capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.apply", args)
        self.assertEqual(args[args.index("--shortcut-action") + 1], "remove")
        self.assertEqual(args[args.index("--plan-id") + 1], "a" * 24)
        sync = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts", "sync", "preview"],
                              capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(sync.returncode, 0, sync.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.sync.preview", args)
        sync_apply = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts", "sync",
                                     "apply", "--yes", "--plan-id", "c" * 24],
                                    capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(sync_apply.returncode, 0, sync_apply.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.sync.apply", args)
        self.assertEqual(args[args.index("--plan-id") + 1], "c" * 24)
        rollback_preview = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts",
                                           "rollback", "preview", "b" * 32],
                                          capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(rollback_preview.returncode, 0, rollback_preview.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.sync.rollback.preview", args)
        self.assertEqual(args[args.index("--rollback-id") + 1], "b" * 32)
        rollback_apply = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "proot", "shortcuts",
                                         "rollback", "apply", "b" * 32, "--yes", "--plan-id", "d" * 24],
                                        capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(rollback_apply.returncode, 0, rollback_apply.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.shortcuts.sync.rollback.apply", args)
        self.assertEqual(args[args.index("--rollback-id") + 1], "b" * 32)
        self.assertEqual(args[args.index("--plan-id") + 1], "d" * 24)

    def test_proot_icd_migration_cli_uses_shared_preview_and_rollback_plans(self):
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        capture = self.root / "python-args.txt"
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$TERNUXX_TEST_CAPTURE\"\n",
            encoding="utf-8")
        fake_python.chmod(0o755)
        env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr",
               "TERMUX_VERSION": "fixture", "PATH": f"{fake_bin}:{self.env['PATH']}",
               "TERNUXX_TEST_CAPTURE": str(capture)}
        migration_id = "a" * 64
        preview = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "proot", "setup",
             "icd-migrate-preview", "--alias", "debian"],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.setup.icd-migrate.preview", args)
        self.assertEqual(args[args.index("--alias") + 1], "debian")

        apply = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "proot", "setup", "icd-migrate",
             "--alias", "debian", "--yes", "--plan-id", migration_id],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(apply.returncode, 0, apply.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.setup.icd-migrate.apply", args)
        self.assertEqual(args[args.index("--plan-id") + 1], migration_id)
        self.assertIn("--yes", args)

        rollback_preview = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "proot", "setup",
             "icd-rollback-preview", "--operation-id", migration_id],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(rollback_preview.returncode, 0, rollback_preview.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.setup.icd-migrate.rollback.preview", args)
        self.assertEqual(args[args.index("--operation-id") + 1], migration_id)

        rollback = subprocess.run(
            [shutil.which("bash"), str(ROOT / "tx"), "proot", "setup", "icd-rollback",
             "--operation-id", migration_id, "--yes", "--plan-id", "b" * 64],
            capture_output=True, text=True, env=env, timeout=15)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("proot.setup.icd-migrate.rollback.apply", args)
        self.assertEqual(args[args.index("--plan-id") + 1], "b" * 64)

    def test_help_documents_native_host_and_optional_debian_guest(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("tx gui", result.stdout)
        self.assertIn("tx guides", result.stdout)
        self.assertIn("optional managed PRoot", result.stdout)
        self.assertIn("Debian: db", result.stdout)

    def test_native_management_alias_and_proot_help(self):
        result = self.cli("mng", "--help")
        self.assertIn("tx mng cron", result.stdout)
        proot_help = self.cli("help", "proot")
        self.assertEqual(proot_help.returncode, 0, proot_help.stderr)
        self.assertIn("tx proot sessions list", proot_help.stdout)
        self.assertIn("tx proot shortcuts list", proot_help.stdout)
        self.assertIn("shortcuts sync preview", proot_help.stdout)
        self.assertIn("shortcuts rollback list", proot_help.stdout)
        self.assertIn("tx proot setup catalog", proot_help.stdout)
        self.assertIn("offers desktop choices (comma-separated IDs; blank keeps XFCE)", proot_help.stdout)
        self.assertIn("tx proot setup fresh-install --yes --plan-id ID", proot_help.stdout)
        self.assertIn("tx proot setup icd-migrate-preview --alias debian", proot_help.stdout)
        self.assertIn("hidden prompts", proot_help.stdout)
        self.assertIn("tx mng app launch --desktop-id APP.desktop --display :N", proot_help.stdout)
        legacy_env = {**self.env, "PREFIX": "/data/data/com.termux/files/usr", "TERMUX_VERSION": "fixture"}
        legacy_proot = subprocess.run([shutil.which("bash"), str(ROOT / "tx"), "mng", "proot", "status"],
                                      capture_output=True, text=True, env=legacy_env, timeout=15)
        self.assertEqual(legacy_proot.returncode, 0, legacy_proot.stderr)
        self.assertIn("proot_distribution_inventory", legacy_proot.stdout)

    def test_proot_verify_uses_the_management_service_guest_user_option(self):
        script = (ROOT / "lib/proot.sh").read_text(encoding="utf-8")
        service = (ROOT / "lib/management_service.py").read_text(encoding="utf-8")
        self.assertIn("args+=(--guest-user-from rootfs)", script)
        self.assertNotIn("--guest-user-source", script)
        self.assertIn('parser.add_argument("--guest-user-from", "--user-source"', service)

    def test_proot_setup_catalog_lists_only_complete_install_profiles(self):
        self.env["PREFIX"] = "/data/data/com.termux/files/usr"
        self.env["TERMUX_VERSION"] = "fixture"
        result = self.cli("proot", "setup", "catalog")
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = json.loads(result.stdout)["profiles"]
        self.assertEqual({item["distro"] for item in profiles}, {"debian", "ubuntu"})
        self.assertEqual({item["package_manager"] for item in profiles}, {"apt"})
        self.assertEqual(next(item for item in profiles if item["distro"] == "ubuntu")["desktops"][0]["id"], "xfce")

    def test_distro_named_debian_install_requests_account_before_guest_preview(self):
        result = self.cli("install", "debian", "preview")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Choose a Debian Trixie guest account with --user NAME", result.stderr)
        self.assertNotIn("Unknown install option", result.stderr)


if __name__ == "__main__":
    unittest.main()
