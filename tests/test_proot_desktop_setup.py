from __future__ import annotations
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_desktop_setup


class DesktopInstallPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-desktop-plan-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.prefix = base / "prefix"
        self.root = self.prefix / "var/lib/proot-distro/containers/debian/rootfs"
        (self.root / "etc/apt/sources.list.d").mkdir(parents=True)
        (self.root / "etc/os-release").write_text('ID=debian\nVERSION_CODENAME=trixie\n')
        status = self.root / "var/lib/dpkg/status"
        status.parent.mkdir(parents=True)
        status.write_text("Package: xfce4\nStatus: install ok installed\nVersion: 4.20.1\n\n"
                          "Package: xfce4-terminal\nStatus: install ok installed\nVersion: 1.1.4-1\n")
        self.state = self.home / ".local/share/ternuxx"
        self.calls = []

    def fake_runner(self, args, **kwargs):
        self.calls.append(args)
        applying = "-y" in args
        simulating = "--simulate" in args
        if applying:
            status = self.root / "var/lib/dpkg/status"
            with status.open("a") as stream:
                stream.write("\n\nPackage: gnome-core\nStatus: install ok installed\nVersion: 1:48+2\n")
            output = "0 upgraded, 1 newly installed, 0 to remove and 1 not upgraded.\n"
            return subprocess.CompletedProcess(args, 0, output, "")
        output = ("Inst gnome-core (1:48+2 Debian:13/stable [arm64])\n"
                  "0 upgraded, 1 newly installed, 0 to remove and 1 not upgraded.\n")
        if not simulating:
            output += ("Need to get 11 MB/12 MB of archives.\n"
                       "After this operation, 30 MB of additional disk space will be used.\n"
                       "Do you want to continue? [Y/n] N\nAbort.\n")
        return subprocess.CompletedProcess(args, 0 if simulating else 1, output, "")

    def test_preview_pins_transaction_without_changing_guest_and_apply_checks_exact_delta(self):
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["gnome"], runner=self.fake_runner)
            self.assertEqual(plan["status"], "preview")
            self.assertEqual(plan["transaction"]["new_package_count"], 1)
            self.assertEqual(plan["transaction"]["disk"], {"value": 30.0, "unit": "MB"})
            self.assertEqual(plan["transaction"]["download"], {"value": 11.0, "unit": "MB"})
            self.assertIn("Acquire::https::User-Agent=curl/8", self.calls[0])
            self.assertIn("Acquire::https::Pipeline-Depth=0", self.calls[0])
            self.assertNotIn("gnome-core", (self.root / "var/lib/dpkg/status").read_text())
            result = proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id=plan["plan_id"], confirmed=True, runner=self.fake_runner)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["desktop_environments"], ["gnome"])
        self.assertTrue(any("gnome-core=1:48+2" in call for call in self.calls))

    def test_preview_repairs_a_missing_required_plasma_x11_package(self):
        status = self.root / "var/lib/dpkg/status"
        with status.open("a", encoding="utf-8") as stream:
            stream.write("\n\nPackage: kde-plasma-desktop\nStatus: install ok installed\nVersion: 5:162\n")

        def runner(args, **kwargs):
            output = ("Inst kwin-x11 (4:6.3.6-1 Debian:13/stable [arm64])\n"
                      "0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n")
            if "--simulate" not in args:
                output += ("Need to get 12 MB/14 MB of archives.\n"
                           "After this operation, 40 MB of additional disk space will be used.\n"
                           "Do you want to continue? [Y/n] N\nAbort.\n")
            return subprocess.CompletedProcess(args, 0 if "--simulate" in args else 1, output, "")

        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["plasma"], runner=runner)
        self.assertEqual(plan["operation"]["requested_packages"], ["kde-plasma-desktop", "kwin-x11"])
        self.assertEqual(plan["operation"]["requested_versions"],
                         [["kde-plasma-desktop", "5:162"], ["kwin-x11", "4:6.3.6-1"]])
        self.assertEqual(plan["transaction"]["new_package_count"], 1)
        self.assertTrue(plan["operation"]["guest_packages_changed"] is False)

    def test_os_release_symlink_is_allowed_only_inside_the_managed_rootfs(self):
        release = self.root / "etc/os-release"
        release.unlink()
        target = self.root / "usr/lib/os-release"
        target.parent.mkdir(parents=True)
        target.write_text("ID=debian\nVERSION_CODENAME=trixie\n")
        release.symlink_to("../usr/lib/os-release")
        identity = proot_desktop_setup._rootfs(str(self.prefix))[1]
        self.assertIn("rootfs_inode", identity)
        release.unlink()
        release.symlink_to("/etc/passwd")
        with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "outside the managed rootfs"):
            proot_desktop_setup._rootfs(str(self.prefix))

    def test_simulation_rejects_upgrades_or_removals(self):
        output = "Inst libx [1] (2 Debian:stable [arm64])\n0 upgraded, 1 newly installed, 1 to remove and 0 not upgraded.\n"
        fake = lambda *a, **k: subprocess.CompletedProcess(a[0], 1, output, "")
        with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "upgrade or remove"):
            proot_desktop_setup._run_guest(str(self.prefix), ["gnome-core"], apply=False, runner=fake)

    def test_resume_preview_pins_pending_dpkg_records_and_repair_archive(self):
        import json
        import proot_fresh_setup
        identity = proot_desktop_setup._rootfs(str(self.prefix))[1]
        status = self.root / "var/lib/dpkg/status"
        status.write_text(status.read_text() + "\n\nPackage: gnome-core\nStatus: install ok unpacked\nVersion: 1:48+2\nArchitecture: all\n")
        updates = self.root / "var/lib/dpkg/updates"
        updates.mkdir(parents=True)
        (updates / "0000").write_text("Package: broken-theme\nStatus: install reinstreq half-installed\nVersion: 1.2-3\nArchitecture: all\n")
        archive = self.root / "var/cache/apt/archives/broken-theme_1.2-3_all.deb"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"approved cached package")
        state_root = proot_fresh_setup._state_root(str(self.home), str(self.state), create=True)
        failed_id = "a" * 64
        saved = {"plan_id": failed_id, "rootfs_identity": identity,
                 "apt_sources_sha256": proot_desktop_setup._source_digest(self.root),
                 "transaction_packages": [["gnome-core", "1:48+2"], ["broken-theme", "1.2-3"]],
                 "desktop_environments": ["gnome"]}
        proot_fresh_setup._private_write(state_root / "previews" / f"desktop-{failed_id}.json", saved)
        proot_fresh_setup._private_write(state_root / f"desktop-{failed_id}.journal.json",
                                         {"plan_id": failed_id, "state": "failed"})
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            result = proot_desktop_setup.resume_preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), failed_plan_id=failed_id)
        self.assertEqual(result["repair_archive_count"], 1)
        self.assertEqual(result["pending_package_count"], 2)
        operation = result["operation"]
        self.assertEqual(operation["repair_archives"][0][0], "broken-theme")
        self.assertEqual(operation["repair_archives"][0][2], __import__("hashlib").sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(operation["dpkg_update_files"][0][0], "0000")

    def test_resume_preview_rejects_pending_package_outside_failed_plan(self):
        import proot_fresh_setup
        identity = proot_desktop_setup._rootfs(str(self.prefix))[1]
        status = self.root / "var/lib/dpkg/status"
        status.write_text(status.read_text() + "\n\nPackage: unexpected\nStatus: install ok unpacked\nVersion: 1\n")
        state_root = proot_fresh_setup._state_root(str(self.home), str(self.state), create=True)
        failed_id = "b" * 64
        saved = {"plan_id": failed_id, "rootfs_identity": identity,
                 "apt_sources_sha256": proot_desktop_setup._source_digest(self.root),
                 "transaction_packages": [["gnome-core", "1:48+2"]], "desktop_environments": ["gnome"]}
        proot_fresh_setup._private_write(state_root / "previews" / f"desktop-{failed_id}.json", saved)
        proot_fresh_setup._private_write(state_root / f"desktop-{failed_id}.journal.json",
                                         {"plan_id": failed_id, "state": "failed"})
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "unexpected package"):
                proot_desktop_setup.resume_preview(prefix=str(self.prefix), home=str(self.home),
                    state_dir=str(self.state), failed_plan_id=failed_id)

    def test_failed_or_unconfirmed_apply_is_refused(self):
        with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "requires --yes"):
            proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id="0" * 64, confirmed=False, runner=self.fake_runner)


if __name__ == "__main__":
    unittest.main()
