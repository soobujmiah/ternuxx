from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
import subprocess
import tempfile
import unittest

import optional_software


NOW = datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)


class FakePackageCommands:
    def __init__(self):
        self.installed = {}
        self.simulation = """Inst htop (3.5.3 termux-main stable:stable [aarch64])
Inst utf8proc (2.12.0 termux-main stable:stable [aarch64])
0 upgraded, 2 newly installed, 0 to remove and 0 not upgraded.
"""
        self.candidates = {"htop": "3.5.3", "utf8proc": "2.12.0", "tmux": "3.8", "tree": "2.3.2"}
        self.candidate_source = "https://packages.termux.dev/apt/termux-main"
        self.calls = []
        self.actual_returncode = 0

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        command = Path(argv[0]).name
        if command == "dpkg-query":
            package = argv[-1]
            if package not in self.installed:
                return subprocess.CompletedProcess(argv, 1, "", "")
            return subprocess.CompletedProcess(argv, 0,
                f"install ok installed\t{self.installed[package]}\n", "")
        if command == "apt-cache":
            package = argv[-1]
            candidate = self.candidates.get(package, "1.0")
            text = (f"{package}:\n  Installed: (none)\n  Candidate: {candidate}\n"
                    f"  Version table:\n     {candidate} 500\n        500 {self.candidate_source} stable/main aarch64 Packages\n")
            return subprocess.CompletedProcess(argv, 0, text, "")
        if command == "dpkg":
            left, operator, right = argv[-3:]
            def version_tuple(value):
                import re
                return tuple((0, int(part)) if part.isdigit() else (1, part)
                             for part in re.findall(r"[0-9]+|[A-Za-z]+", value))
            if operator == "gt":
                rc = 0 if version_tuple(left) > version_tuple(right) else 1
            else:
                rc = 2
            return subprocess.CompletedProcess(argv, rc, "", "")
        if command == "apt-get" and "-s" in argv:
            return subprocess.CompletedProcess(argv, 0, self.simulation, "")
        if command == "apt-get":
            return subprocess.CompletedProcess(argv, self.actual_returncode, "transaction output\n", "")
        raise AssertionError(f"unexpected command: {argv}")


class OptionalSoftwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-app-catalog-")
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.state_dir = self.home / ".local/share/ternuxx"
        self.prefix = Path(self.temp.name) / "prefix"
        lists = self.prefix / "var/lib/apt/lists"
        lists.mkdir(parents=True)
        apt = self.prefix / "etc/apt"
        (apt / "sources.list.d").mkdir(parents=True)
        (apt / "sources.list").write_text(
            "deb https://packages.termux.dev/apt/termux-main stable main\n"
            "deb https://packages.termux.dev/apt/termux-x11 x11 main\n", encoding="utf-8")
        stamp = format_datetime(NOW - timedelta(days=1), usegmt=True)
        for repo in optional_software.OFFICIAL_REPOSITORIES:
            (lists / f"mirror_{repo}_InRelease").write_text(f"Date: {stamp}\n", encoding="utf-8")
        self.fake = FakePackageCommands()

    def tearDown(self):
        self.temp.cleanup()

    def preview(self, action="install", app_id="process-monitor"):
        return optional_software.preview(app_id, action, prefix=str(self.prefix),
                                         home=self.home, state_dir=self.state_dir,
                                         runner=self.fake, now=NOW)

    def test_install_preview_is_curated_official_and_full_closure(self):
        plan = self.preview()
        self.assertTrue(plan["read_only"])
        self.assertTrue(plan["requires_confirmation"])
        self.assertEqual(plan["repository"], "termux-main")
        self.assertEqual(plan["candidate_version"], "3.5.3")
        self.assertEqual([(item["package"], item["version"]) for item in plan["changes"]],
                         [("htop", "3.5.3"), ("utf8proc", "2.12.0")])
        self.assertEqual(plan["plan_id"].__len__(), 64)
        self.assertTrue(any("-s" in call for call in self.fake.calls))

    def test_unknown_app_id_and_unofficial_candidate_are_refused(self):
        with self.assertRaisesRegex(optional_software.SoftwareError, "curated"):
            self.preview(app_id="arbitrary-package")
        self.fake.candidate_source = "https://repo.example/apt/termux-main"
        with self.assertRaisesRegex(optional_software.SoftwareError, "not from official"):
            self.preview()

    def test_nonofficial_dependency_source_is_refused(self):
        self.fake.simulation = """Inst htop (3.5.3 termux-main stable:stable [aarch64])
Inst helper (1 tur-packages tur [aarch64])
0 upgraded, 2 newly installed, 0 to remove and 0 not upgraded.
"""
        with self.assertRaisesRegex(optional_software.SoftwareError, "non-official"):
            self.preview()

    def test_stale_or_future_index_blocks_install_and_update(self):
        lists = self.prefix / "var/lib/apt/lists"
        old = format_datetime(NOW - timedelta(days=15), usegmt=True)
        (lists / "mirror_termux-main_InRelease").write_text(f"Date: {old}\n", encoding="utf-8")
        with self.assertRaisesRegex(optional_software.SoftwareError, "indexes are not usable"):
            self.preview()

    def test_native_package_commands_drop_foreign_library_path(self):
        observed = {}
        def runner(argv, **kwargs):
            observed.update(kwargs["env"])
            return subprocess.CompletedProcess(argv, 0, "", "")
        optional_software._run(["apt-get", "--version"],
                               env={"PREFIX": str(self.prefix), "LD_LIBRARY_PATH": "/codex/lib"},
                               runner=runner)
        self.assertNotIn("LD_LIBRARY_PATH", observed)

    def test_apply_recomputes_exact_plan_and_passes_bounded_arguments(self):
        plan = self.preview()
        result = optional_software.apply("process-monitor", "install", plan["plan_id"], True,
                                         prefix=str(self.prefix), home=self.home,
                                         state_dir=self.state_dir, runner=self.fake, now=NOW)
        self.assertTrue(result["complete"])
        command = self.fake.calls[-1]
        self.assertEqual(command[:5], ["apt-get", "--assume-yes", "--no-install-recommends", "--no-remove", "--no-upgrade"])
        self.assertEqual(command[-3:], ["install", "htop=3.5.3", "utf8proc=2.12.0"][-3:])
        self.assertNotIn("remove", command)

    def test_changed_simulation_or_missing_confirmation_refuses_apply(self):
        plan = self.preview()
        self.fake.simulation += "\n"
        with self.assertRaisesRegex(optional_software.SoftwareError, "changed"):
            optional_software.apply("process-monitor", "install", plan["plan_id"], True,
                                    prefix=str(self.prefix), home=self.home,
                                    state_dir=self.state_dir, runner=self.fake, now=NOW)
        with self.assertRaisesRegex(optional_software.SoftwareError, "confirmation"):
            optional_software.apply("process-monitor", "install", plan["plan_id"], False,
                                    prefix=str(self.prefix), home=self.home,
                                    state_dir=self.state_dir, runner=self.fake, now=NOW)
        self.assertFalse(any("--assume-yes" in call for call in self.fake.calls))

    def test_saved_plan_is_private_expires_and_cannot_be_replayed(self):
        plan = self.preview()
        record_path = self.state_dir / "software-plans" / f"{plan['plan_id']}.json"
        self.assertEqual(record_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.state_dir / "software-plans").stat().st_mode & 0o777, 0o700)
        later = NOW + timedelta(seconds=optional_software.PLAN_TTL_SECONDS + 1)
        with self.assertRaisesRegex(optional_software.SoftwareError, "expired"):
            optional_software.apply("process-monitor", "install", plan["plan_id"], True,
                prefix=str(self.prefix), home=self.home, state_dir=self.state_dir,
                runner=self.fake, now=later)
        result = optional_software.apply("process-monitor", "install", plan["plan_id"], True,
            prefix=str(self.prefix), home=self.home, state_dir=self.state_dir,
            runner=self.fake, now=NOW)
        self.assertTrue(result["complete"])
        with self.assertRaisesRegex(optional_software.SoftwareError, "no longer available"):
            optional_software.apply("process-monitor", "install", plan["plan_id"], True,
                prefix=str(self.prefix), home=self.home, state_dir=self.state_dir,
                runner=self.fake, now=NOW)

    def test_state_symlink_and_state_outside_home_are_refused(self):
        external = Path(self.temp.name) / "external"
        external.mkdir()
        with self.assertRaisesRegex(optional_software.SoftwareError, "inside HOME"):
            optional_software.preview("process-monitor", "install", prefix=str(self.prefix),
                home=self.home, state_dir=external, runner=self.fake, now=NOW)
        bad = self.home / ".local"
        bad.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(optional_software.SoftwareError, "symbolic link"):
            optional_software.preview("process-monitor", "install", prefix=str(self.prefix),
                home=self.home, state_dir=self.home / ".local/share/ternuxx",
                runner=self.fake, now=NOW)

    def test_remove_preview_can_use_installed_state_and_never_autoremoves(self):
        self.fake.installed["htop"] = "3.5.3"
        self.fake.simulation = "Remv htop [3.5.3]\n0 upgraded, 0 newly installed, 1 to remove.\n"
        plan = self.preview("remove")
        self.assertEqual(plan["changes"], [{"action": "remove", "package": "htop"}])
        result = optional_software.apply("process-monitor", "remove", plan["plan_id"], True,
                                         prefix=str(self.prefix), home=self.home,
                                         state_dir=self.state_dir, runner=self.fake, now=NOW)
        self.assertTrue(result["complete"])
        command = self.fake.calls[-1]
        self.assertIn("--no-auto-remove", command)
        self.assertEqual(command[-2:], ["remove", "htop"])
        self.assertNotIn("autoremove", command)

    def test_remove_refuses_dependency_removal(self):
        self.fake.installed["htop"] = "3.5.3"
        self.fake.simulation = "Remv htop [3.5.3]\nRemv utf8proc [2.12.0]\n"
        with self.assertRaisesRegex(optional_software.SoftwareError, "outside the selected app"):
            self.preview("remove")

    def test_directory_tree_handoff_is_fixed_argv_home_scoped_and_read_only(self):
        (self.prefix / "bin").mkdir(parents=True)
        executable = self.prefix / "bin/tree"
        executable.write_text("test executable", encoding="utf-8")
        executable.chmod(0o700)
        folder = self.home / "Documents"
        folder.mkdir()
        (folder / "notes.txt").write_text("private body must not be read", encoding="utf-8")
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, ".\n└── notes.txt\n", "")
        result = optional_software.inspect_directory_tree("Documents", home=self.home,
            prefix=str(self.prefix), runner=runner)
        self.assertEqual(result["path"], "~/Documents")
        self.assertEqual(result["kind"], "directory")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["contents_read"])
        argv, kwargs = calls[0]
        self.assertEqual(argv, [str(executable), "-L", "2", "--filelimit", "32", "-n", "-q", "--noreport", "--", "."])
        self.assertEqual(kwargs["cwd"], str(folder))
        self.assertEqual(kwargs["timeout"], 8)
        self.assertNotIn("private body", result["output"])

    def test_directory_tree_handoff_accepts_a_regular_file_without_opening_contents(self):
        (self.prefix / "bin").mkdir(parents=True)
        executable = self.prefix / "bin/tree"
        executable.write_text("test executable", encoding="utf-8"); executable.chmod(0o700)
        folder = self.home / "notes"; folder.mkdir()
        target = folder / "report.txt"; target.write_text("secret body")
        seen = {}
        def runner(argv, **kwargs):
            seen.update(argv=argv, kwargs=kwargs)
            return subprocess.CompletedProcess(argv, 0, "report.txt\n", "")
        result = optional_software.inspect_directory_tree(str(target), home=self.home,
            prefix=str(self.prefix), runner=runner)
        self.assertEqual(result["path"], "~/notes/report.txt")
        self.assertEqual(result["kind"], "file")
        self.assertIn("--fromfile", seen["argv"])
        self.assertEqual(seen["kwargs"]["input"], "report.txt\n")
        self.assertEqual(seen["kwargs"]["cwd"], str(folder))

    def test_directory_tree_handoff_bounds_output_and_rejects_special_files(self):
        import os
        (self.prefix / "bin").mkdir(parents=True)
        executable = self.prefix / "bin/tree"
        executable.write_text("test executable", encoding="utf-8"); executable.chmod(0o700)
        folder = self.home / "large"; folder.mkdir()
        def oversized(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "x" * 40000, "")
        result = optional_software.inspect_directory_tree("large", home=self.home,
            prefix=str(self.prefix), runner=oversized)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["output"].encode("utf-8")), 32768 + 64)
        fifo = self.home / "pipe"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(optional_software.SoftwareError, "regular files and directories"):
            optional_software.inspect_directory_tree("pipe", home=self.home,
                prefix=str(self.prefix), runner=lambda *a, **k: self.fail("special path reached tree"))

    def test_directory_tree_handoff_rejects_escape_symlink_and_arbitrary_app(self):
        (self.prefix / "bin").mkdir(parents=True)
        executable = self.prefix / "bin/tree"
        executable.write_text("test executable", encoding="utf-8"); executable.chmod(0o700)
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "secret").write_text("do not read")
        link = self.home / "escape"; link.symlink_to(outside, target_is_directory=True)
        runner = lambda argv, **kwargs: (_ for _ in ()).throw(AssertionError("runner must not be called"))
        for value in ("../outside", str(outside), "escape"):
            with self.subTest(path=value), self.assertRaises(optional_software.SoftwareError):
                optional_software.inspect_directory_tree(value, home=self.home,
                    prefix=str(self.prefix), runner=runner)

    def test_list_reports_freshness_and_current_catalog_only(self):
        result = optional_software.list_apps(prefix=str(self.prefix), runner=self.fake, now=NOW)
        self.assertEqual(result["index_status"], "fresh")
        self.assertEqual([item["id"] for item in result["apps"]],
                         ["process-monitor", "terminal-multiplexer", "directory-tree"])
        self.assertTrue(all(item["status"] == "available" for item in result["apps"]))


if __name__ == "__main__":
    unittest.main()
