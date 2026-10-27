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
        status.write_text("Package: xfce4\nStatus: install ok installed\nArchitecture: all\nVersion: 4.20.1\n\n"
                          "Package: xfce4-terminal\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1.1.4-1\n")
        self.state = self.home / ".local/share/ternuxx"
        self.calls = []

    def fake_runner(self, args, **kwargs):
        self.calls.append(args)
        applying = "-y" in args
        simulating = "--simulate" in args
        if applying:
            status = self.root / "var/lib/dpkg/status"
            with status.open("a") as stream:
                stream.write("\n\nPackage: lxde-core\nStatus: install ok installed\nArchitecture: all\nVersion: 1:48+2\n")
            output = "0 upgraded, 1 newly installed, 0 to remove and 1 not upgraded.\n"
            return subprocess.CompletedProcess(args, 0, output, "")
        output = ("Inst lxde-core (1:48+2 Debian:13/stable [arm64])\n"
                  "0 upgraded, 1 newly installed, 0 to remove and 1 not upgraded.\n")
        if not simulating:
            output += ("Need to get 11 MB/12 MB of archives.\n"
                       "After this operation, 30 MB of additional disk space will be used.\n"
                       "Do you want to continue? [Y/n] N\nAbort.\n")
        return subprocess.CompletedProcess(args, 0 if simulating else 1, output, "")

    def test_native_transport_finishes_verified_fetch_before_no_download_install(self):
        import proot_package_fetch
        helper=self.prefix/'lib/apt/apt-helper';helper.parent.mkdir(parents=True);helper.touch()
        with (self.root/'var/lib/dpkg/status').open('a') as stream:stream.write('\n\nPackage: ca-certificates\nStatus: install ok installed\nArchitecture: all\nVersion: 1\n')
        records={'lxde-core':dict(Package='lxde-core',Version='1:48+2',Architecture='all',Filename='pool/lxde-core_48+2_all.deb',Size='1',SHA256='a'*64)}
        order=[]
        def runner(argv,**kw):
            if '--print-uris' in argv:
                return subprocess.CompletedProcess(argv,0,"'https://example.invalid/pool/lxde-core_48+2_all.deb' lxde-core_1%3a48+2_all.deb 1 SHA256:"+'a'*64+'\n','')
            if '-y' in argv:order.append('apt');self.assertIn('--no-download',argv)
            return self.fake_runner(argv,**kw)
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement,'_assert_idle'),mock.patch.object(subprocess,'run',runner),mock.patch.object(proot_package_fetch,'metadata',return_value=(records,{'index':'b'*64})),mock.patch.object(proot_desktop_setup.proot_fresh_setup,'_native_ca_bundle',return_value=(self.prefix/'ca.pem','c'*64)),mock.patch.object(proot_package_fetch,'fetch',side_effect=lambda *a,**k:order.append('verified-fetch')):
            plan=proot_desktop_setup.preview(prefix=str(self.prefix),home=str(self.home),state_dir=str(self.state),selected=['lxde'],runner=runner)
            self.assertEqual(plan['operation']['native_fetch']['archives'][0]['sha256'],'a'*64)
            result=proot_desktop_setup.apply(prefix=str(self.prefix),home=str(self.home),state_dir=str(self.state),plan_id=plan['plan_id'],confirmed=True,runner=runner)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(order,['verified-fetch','apt'])

    def test_missing_guest_ca_is_explicitly_included_before_approval(self):
        import proot_package_fetch
        helper=self.prefix/'lib/apt/apt-helper';helper.parent.mkdir(parents=True);helper.touch()
        records={name:dict(Package=name,Version=version,Architecture='all',Filename='pool/'+name+'.deb',Size='1',SHA256=digest*64) for name,version,digest in (('lxde-core','1:48+2','a'),('ca-certificates','2026','b'))}
        def runner(argv,**kw):
            return subprocess.CompletedProcess(argv,0,"'https://example.invalid/pool/lxde-core.deb' lxde-core_1%3a48+2_all.deb 1 SHA256:"+'a'*64+"\n'https://example.invalid/pool/ca-certificates.deb' ca-certificates_2026_all.deb 1 SHA256:"+'b'*64+'\n','')
        transaction=dict(new_packages=[['lxde-core','1:48+2'],['ca-certificates','2026']],new_package_count=2,upgraded=0,removed=0,not_upgraded=0,download=dict(value=1,unit='MB'),disk=dict(value=2,unit='MB'))
        before=(self.root/'var/lib/dpkg/status').read_bytes()
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement,'_assert_idle'),mock.patch.object(subprocess,'run',runner),mock.patch.object(proot_desktop_setup,'_run_guest',return_value=transaction),mock.patch.object(proot_package_fetch,'metadata',return_value=(records,{'index':'c'*64})),mock.patch.object(proot_desktop_setup.proot_fresh_setup,'_native_ca_bundle',return_value=(self.prefix/'ca','d'*64)):
            plan=proot_desktop_setup.preview(prefix=str(self.prefix),home=str(self.home),state_dir=str(self.state),selected=['lxde'],runner=runner)
        self.assertIn('ca-certificates',plan['operation']['requested_packages'])
        self.assertEqual((self.root/'var/lib/dpkg/status').read_bytes(),before)

    def test_preview_pins_transaction_without_changing_guest_and_apply_checks_exact_delta(self):
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["lxde"], runner=self.fake_runner)
            self.assertEqual(plan["status"], "preview")
            self.assertEqual(plan["transaction"]["new_package_count"], 1)
            self.assertEqual(plan["transaction"]["disk"], {"value": 30.0, "unit": "MB"})
            self.assertEqual(plan["transaction"]["download"], {"value": 11.0, "unit": "MB"})
            self.assertIn("Acquire::https::User-Agent=curl/8", self.calls[0])
            self.assertIn("Acquire::https::Pipeline-Depth=0", self.calls[0])
            self.assertNotIn("lxde-core", (self.root / "var/lib/dpkg/status").read_text())
            result = proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id=plan["plan_id"], confirmed=True, runner=self.fake_runner)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["desktop_environments"], ["lxde"])
        self.assertTrue(any("lxde-core=1:48+2" in call for call in self.calls))

    def test_preview_repairs_a_missing_required_plasma_x11_package(self):
        status = self.root / "var/lib/dpkg/status"
        with status.open("a", encoding="utf-8") as stream:
            stream.write("\n\nPackage: kde-plasma-desktop\nStatus: install ok installed\nArchitecture: all\nVersion: 5:162\n")

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
            proot_desktop_setup._run_guest(str(self.prefix), ["lxde-core"], apply=False, runner=fake)

    def test_resume_preview_pins_pending_dpkg_records_and_repair_archive(self):
        import json
        import proot_fresh_setup
        identity = proot_desktop_setup._rootfs(str(self.prefix))[1]
        status = self.root / "var/lib/dpkg/status"
        status.write_text(status.read_text() + "\n\nPackage: lxde-core\nStatus: install ok unpacked\nVersion: 1:48+2\nArchitecture: all\n")
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
                 "transaction_packages": [["lxde-core", "1:48+2"], ["broken-theme", "1.2-3"]],
                 "desktop_environments": ["lxde"]}
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
                 "transaction_packages": [["lxde-core", "1:48+2"]], "desktop_environments": ["lxde"]}
        proot_fresh_setup._private_write(state_root / "previews" / f"desktop-{failed_id}.json", saved)
        proot_fresh_setup._private_write(state_root / f"desktop-{failed_id}.journal.json",
                                         {"plan_id": failed_id, "state": "failed"})
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "unexpected package"):
                proot_desktop_setup.resume_preview(prefix=str(self.prefix), home=str(self.home),
                    state_dir=str(self.state), failed_plan_id=failed_id)

    def test_existing_ubuntu_writer_addon_preserves_installed_xfce_and_pins_apply(self):
        container = self.root.parent
        target = container.with_name("ubuntu")
        container.rename(target)
        self.root = target / "rootfs"
        (self.root / "etc/os-release").write_text("ID=ubuntu\nVERSION_CODENAME=noble\n")

        def runner(args, **kwargs):
            self.calls.append(args)
            self.assertIn("ubuntu", args)
            self.assertNotIn("debian", args)
            if "-y" in args:
                self.assertIn("libreoffice-writer=1.0", args)
                with (self.root / "var/lib/dpkg/status").open("a") as stream:
                    stream.write("\n\nPackage: libreoffice-writer\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1.0\n")
                return subprocess.CompletedProcess(args, 0, "0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n", "")
            output = "Inst libreoffice-writer (1.0 Ubuntu:noble [arm64])\n0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n"
            return subprocess.CompletedProcess(args, 0, output, "")

        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["xfce"], alias="ubuntu", apps=["writer"], runner=runner)
            self.assertEqual(plan["operation"]["alias"], "ubuntu")
            self.assertEqual(plan["operation"]["apps"], ["writer"])
            self.assertNotIn("libreoffice-calc", plan["operation"]["requested_packages"])
            result = proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id=plan["plan_id"], confirmed=True, runner=runner)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["desktop_environments"], ["xfce"])

    def test_repeated_existing_desktop_selection_is_a_readonly_noop(self):
        def runner(args, **kwargs):
            self.assertNotIn("-y", args)
            return subprocess.CompletedProcess(args, 0, "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n", "")
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"):
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["xfce"], runner=runner)
        self.assertEqual(plan["status"], "already_installed")

    def test_headless_graphics_addon_reuses_pinned_turnip_installer_after_exact_package_apply(self):
        import proot_software
        packages = proot_software.packages("debian", ["graphics-runtime"])

        def runner(args, **kwargs):
            if "-y" in args:
                with (self.root / "var/lib/dpkg/status").open("a") as stream:
                    for package in packages:
                        stream.write(f"\n\nPackage: {package}\nStatus: install ok installed\nArchitecture: arm64\nVersion: 1.0\n")
                output = f"0 upgraded, {len(packages)} newly installed, 0 to remove and 0 not upgraded.\n"
            else:
                output = "".join(f"Inst {package} (1.0 Debian:13/stable [arm64])\n" for package in packages)
                output += f"0 upgraded, {len(packages)} newly installed, 0 to remove and 0 not upgraded.\n"
            return subprocess.CompletedProcess(args, 0, output, "")

        fresh = proot_desktop_setup.proot_fresh_setup
        with mock.patch.object(proot_desktop_setup.proot_guest_retirement, "_assert_idle"), \
             mock.patch.object(fresh, "_kgsl_accessible", return_value=True), \
             mock.patch.object(fresh, "_stage_turnip", return_value=(Path("driver"), Path("icd"))) as stage, \
             mock.patch.object(fresh, "_guest_turnip_install") as install:
            plan = proot_desktop_setup.preview(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), selected=["none"], apps=["graphics-runtime"], runner=runner)
            self.assertTrue(plan["operation"]["graphics_runtime"]["kgsl_accessible"])
            self.assertEqual(plan["operation"]["desktop_environments"], [])
            result = proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id=plan["plan_id"], confirmed=True, runner=runner)
        self.assertEqual(result["status"], "complete")
        stage.assert_called_once()
        install.assert_called_once()

    def test_failed_or_unconfirmed_apply_is_refused(self):
        with self.assertRaisesRegex(proot_desktop_setup.DesktopSetupError, "requires --yes"):
            proot_desktop_setup.apply(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), plan_id="0" * 64, confirmed=False, runner=self.fake_runner)


if __name__ == "__main__":
    unittest.main()
