"""Tests for isolated, preview-bound fresh Debian provisioning."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_fresh_setup
import proot_desktops
import proot_profiles


class FreshProotSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-fresh-proot-")
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.prefix = self.base / "prefix"
        self.containers = self.prefix / "var/lib/proot-distro/containers"
        self.containers.mkdir(parents=True)
        ca = self.prefix / "etc/tls/cert.pem"
        ca.parent.mkdir(parents=True)
        ca.write_bytes(b"-----BEGIN CERTIFICATE-----\n" + b"A" * 2048 + b"\n-----END CERTIFICATE-----\n")
        self.repo = self.base / "repo"
        (self.repo / "config/proot").mkdir(parents=True)
        shutil.copyfile(ROOT / "config/proot/debian-trixie.json",
                        self.repo / "config/proot/debian-trixie.json")
        shutil.copyfile(ROOT / "config/proot/ubuntu-noble.json",
                        self.repo / "config/proot/ubuntu-noble.json")
        self.state = self.home / ".local/share/ternuxx"
        self.state.mkdir(parents=True, mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def test_release_identity_accepts_safe_in_root_os_release_symlink(self):
        rootfs = self.base / "release-rootfs"
        (rootfs / "etc").mkdir(parents=True)
        (rootfs / "usr/lib").mkdir(parents=True)
        (rootfs / "usr/lib/os-release").write_text("ID=ubuntu\nVERSION_CODENAME=noble\n")
        (rootfs / "etc/os-release").symlink_to("../usr/lib/os-release")
        self.assertEqual(proot_fresh_setup._read_guest_release_identity(rootfs),
                         {"ID": "ubuntu", "VERSION_CODENAME": "noble"})

    def test_release_identity_rejects_os_release_symlink_outside_rootfs(self):
        rootfs = self.base / "release-rootfs"
        (rootfs / "etc").mkdir(parents=True)
        external = self.base / "external-os-release"
        external.write_text("ID=ubuntu\nVERSION_CODENAME=noble\n")
        (rootfs / "etc/os-release").symlink_to(external)
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "identity is unsafe"):
            proot_fresh_setup._read_guest_release_identity(rootfs)

    def test_fresh_plan_binds_multiple_desktop_choices_and_required_packages(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sobuj",
                desktops=["lxqt", "mate"])
        operation = plan["operation"]
        self.assertEqual(operation["desktop_environments"], ["lxqt", "mate"])
        self.assertIn("lxqt", operation["packages"])
        self.assertIn("mate-desktop-environment-core", operation["packages"])
        self.assertNotIn("startlxqt", operation["packages"])

    def test_fresh_plan_rejects_unknown_or_duplicate_desktops(self):
        for choices in (["invalid"], ["xfce", "xfce"], []):
            with self.subTest(choices=choices), patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
                 self.assertRaises(proot_fresh_setup.FreshSetupError):
                proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sobuj", desktops=choices)

    def test_guest_password_accepts_user_selected_four_character_credential(self):
        proot_fresh_setup._validate_guest_password("1234")

    def test_fresh_preview_supports_package_installed_without_runtime_store(self):
        shutil.rmtree(self.prefix / "var")
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        self.assertEqual(plan["operation"]["rootfs_target"],
                         str(self.prefix / "var/lib/proot-distro/containers/debian/rootfs"))
        self.assertFalse((self.prefix / "var").exists())
        self.assertGreater(plan["operation"]["free_bytes_at_preview"], 0)

    def _write_fixture_package_database(self, alias="debian"):
        provider = proot_profiles.profile_for_alias(alias)
        manifest = json.loads((self.repo / "config/proot" / proot_profiles.PROFILE_FILES[provider]).read_text())
        raw = self._version_output(alias)
        records = []
        for line in raw.splitlines():
            _status, separator, entry = line.partition("\t")
            name, equals, version = entry.partition("=")
            if separator and equals:
                records.append(f"Package: {name}\nStatus: install ok installed\nArchitecture: arm64\nVersion: {version}")
        status = self.containers / alias / "rootfs/var/lib/dpkg/status"
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text("\n\n".join(records) + "\n")

    def _fixture_runner(self, calls):
        def run(args, **kwargs):
            calls.append(args)
            if args[1] == "install":
                alias = args[args.index("--name") + 1]
                root = self.containers / alias / "rootfs"
                (root / "etc").mkdir(parents=True)
                provider = proot_profiles.profile_for_alias(alias)
                manifest_path = self.repo / "config/proot" / proot_profiles.PROFILE_FILES[provider]
                manifest = json.loads(manifest_path.read_text())
                (root / "etc/os-release").write_text(
                    f"ID={manifest['release_id']}\nVERSION_CODENAME={manifest['codename']}\n")
                spec = manifest["fresh_install"]
                (root.parent / "manifest.json").write_text(json.dumps({
                    "image_ref": proot_fresh_setup._pinned_image_reference(spec), "arch": "aarch64",
                    "manifest": {"config": {"digest": spec["config_digest"], "size": spec["config_size"]},
                                 "layers": [{"digest": spec["layer_digest"], "size": spec["layer_size"]}]},
                    "image_config": {"architecture": "arm64", "created": spec["image_created"]}}))
            if "/bin/bash" in args:
                alias = args[args.index("--user") + 2]
                self._write_fixture_package_database(alias)
            return SimpleNamespace(returncode=0)
        return run

    def _version_output(self, alias="debian"):
        provider = proot_profiles.profile_for_alias(alias)
        manifest = json.loads((self.repo / "config/proot" / proot_profiles.PROFILE_FILES[provider]).read_text())
        packages = proot_fresh_setup._packages(manifest)
        packages.extend(proot_desktops.packages_for(provider))
        return "".join("ii \t" + p + "=1.0\n" for p in packages)

    def test_ubuntu_noble_preview_binds_its_image_snapshot_and_xfce_route(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            result = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sobuj", alias="ubuntu")
        plan = result["operation"]
        self.assertEqual(plan["profile_id"], "ubuntu-noble")
        self.assertEqual(plan["distro"], "ubuntu")
        self.assertEqual(plan["release"], "Ubuntu 24.04 LTS (Noble)")
        self.assertEqual(plan["desktop_environments"], ["xfce"])
        self.assertEqual(plan["image"], "ubuntu:noble-20260930.1@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac")
        self.assertIn("xserver-xephyr", plan["packages"])
        self.assertIn("mesa-vulkan-drivers", plan["packages"])
        self.assertEqual(plan["apt_snapshot"]["snapshot_id"], "20261001T000000Z")

    def test_ubuntu_noble_apply_uses_its_pinned_root_and_records_profile(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sobuj", alias="ubuntu",
                sudo_mode="passwordless")
            result = proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sobuj", alias="ubuntu",
                plan_id=plan["plan_id"], confirmed=True, sudo_mode="passwordless",
                runner=self._fixture_runner([]))
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["record"]["profile_id"], "ternuxx-ubuntu-noble-workstation")
        self.assertEqual(result["record"]["distro"], "ubuntu")
        self.assertEqual(result["record"]["release"], "Ubuntu 24.04 LTS (Noble)")

    def test_fresh_apply_requires_password_for_the_selected_guest_account(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="workuser")
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "requires a sudo password"):
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="workuser",
                plan_id=plan["plan_id"], confirmed=True,
                runner=lambda *_a, **_k: self.fail("must reject before touching the guest"))

    def test_unowned_destination_does_not_become_resumable_after_refusal(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
            (self.containers / "debian/rootfs").mkdir(parents=True)
            marker = self.containers / "debian/rootfs/owner-data"
            marker.write_text("preserve")
            with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
                 patch.object(proot_fresh_setup, "_verify_base_image"):
                for attempt in range(2):
                    with self.subTest(attempt=attempt), self.assertRaises(proot_fresh_setup.FreshSetupError):
                        proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                            home=str(self.home), state_dir=str(self.state), user="sbj",
                            plan_id=plan["plan_id"], confirmed=True, password="example-passphrase",
                            runner=lambda *_a, **_k: self.fail("must never enter unowned guest"))
            self.assertEqual(marker.read_text(), "preserve")

    def test_apt_failure_cannot_fall_through_to_user_creation(self):
        calls = []
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=plan["plan_id"], confirmed=True, password="example-passphrase", runner=self._fixture_runner(calls))
        script = next(args[-1] for args in calls if "/bin/bash" in args)
        # Run only the package/user tail, with every external command stubbed.
        # The guest APT source edits are never executed on the host.
        tail = script[script.index("apt-get -o Acquire::https::CaInfo=/tmp/ternuxx-native-ca.pem -o Acquire::Check-Valid-Until=false update"):]
        tail = tail.replace("/etc/locale.gen", str(self.base / "locale.gen"))
        stub = self.base / "stub"
        stub.mkdir()
        for command in ("apt-get", "getent", "useradd", "usermod", "update-locale", "locale-gen"):
            path = stub / command
            body = "#!/bin/sh\n"
            if command == "apt-get": body += "exit 37\n"
            elif command == "getent": body += "exit 1\n"
            elif command == "useradd": body += 'touch "$FRESH_TEST_MARKER"\n'
            else: body += "exit 0\n"
            path.write_text(body);path.chmod(0o700)
        marker = self.base / "user-created"
        result = subprocess.run(["bash", "-c", "set -eu\n" + tail],
            env=dict(os.environ, PATH=str(stub)+":"+os.environ["PATH"], FRESH_TEST_MARKER=str(marker)))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_replay_alias_coexists_with_working_debian_and_rejects_arbitrary_names(self):
        existing = self.containers / "debian/rootfs"
        existing.mkdir(parents=True)
        marker = existing / "owner-data"
        marker.write_text("preserve")
        calls = []
        alias = "ternuxx-replay-test"
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="workuser", alias=alias)
            result = proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state),
                plan_id=plan["plan_id"], confirmed=True, password="example-passphrase", runner=self._fixture_runner(calls))
        self.assertEqual(result["record"]["alias"], alias)
        self.assertEqual(result["record"]["guest_user"], "workuser")
        self.assertEqual(marker.read_text(), "preserve")
        self.assertFalse((self.state / "proot-setup/fresh-provider.json").exists())
        for bad in ("../debian", "ternuxx-replay-", "ternuxx-replay-../debian", "debian/other"):
            with self.subTest(alias=bad), self.assertRaises(proot_fresh_setup.FreshSetupError):
                proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj", alias=bad)

    def test_root_replacement_after_failed_packages_is_not_resumed(self):
        calls = []
        base_runner = self._fixture_runner(calls)
        def fail_packages(args, **kwargs):
            if args[1] == "login":
                return SimpleNamespace(returncode=1)
            return base_runner(args, **kwargs)
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
            with self.assertRaises(proot_fresh_setup.FreshSetupError):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=plan["plan_id"], confirmed=True, password="example-passphrase", runner=fail_packages)
            root = self.containers / "debian/rootfs"
            root.rename(self.containers / "debian/original-rootfs")
            root.mkdir()
            (root / "owner-data").write_text("preserve")
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "identity"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=plan["plan_id"], confirmed=True, password="example-passphrase",
                    runner=lambda *_a, **_k: self.fail("must not enter replacement"))

    def test_different_previews_for_same_alias_share_install_lock(self):
        calls = []
        base_runner = self._fixture_runner(calls)
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            first = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
            second = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="other")
            def runner(args, **kwargs):
                if args[1] == "install":
                    with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "another"):
                        proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                            home=str(self.home), state_dir=str(self.state), user="other",
                            plan_id=second["plan_id"], confirmed=True, password="example-passphrase", runner=base_runner)
                return base_runner(args, **kwargs)
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=first["plan_id"], confirmed=True, password="example-passphrase", runner=runner)

    def test_parent_symlink_is_refused_and_package_inventory_is_complete(self):
        for output in ("bash=1.0\n", "bash=1.0\\n", "bash=\n", "rc \tbash=1.0\nii \tlocales=2.41\n"):
            with self.subTest(output=output), self.assertRaises(proot_fresh_setup.FreshSetupError):
                proot_fresh_setup._version_inventory(output, ["bash", "locales"])
        proot_fresh_setup._version_inventory("ii \tbash=1:5.2-1+deb13u1\nhi \tlocales=2.41\n", ["bash", "locales"])
        outside = self.base / "outside"
        outside.mkdir(mode=0o700)
        (self.home / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "symbolic"):
            proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.home / "linked/state"), user="sbj")
        self.assertEqual(list(outside.iterdir()), [])

    def test_fresh_turnip_install_uses_manifest_paths_and_rejects_conflicts(self):
        import subprocess
        manifest = json.loads((self.repo / "config/proot/debian-trixie.json").read_text())
        manifest["graphics"]["managed_install_paths"] = {
            "driver": "/usr/local/lib/ternuxx-test/libvulkan_freedreno.so",
            "icd": "/usr/local/share/vulkan/icd.d/ternuxx-test.json",
        }
        driver = self.base / "driver.so"
        icd = self.base / "icd.json"
        driver.write_bytes(b"verified-driver")
        icd.write_text('{"ICD":{"library_path":"unused"}}', encoding="utf-8")
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0)
        proot_fresh_setup._guest_turnip_install(
            ["mesa-vulkan-drivers"], driver, icd, "/fixture/proot-distro",
            "ternuxx-replay-test", runner, manifest)
        script = calls[-1][0][-1]
        self.assertIn("/usr/local/lib/ternuxx-test/libvulkan_freedreno.so", script)
        self.assertIn("/usr/local/share/vulkan/icd.d/ternuxx-test.json", script)
        self.assertNotIn("/usr/local/share/vulkan/icd.d/ternux_freedreno_icd.json", script)
        self.assertIn("[ -L /usr/local/lib/ternuxx-test/libvulkan_freedreno.so ]", script)
        self.assertEqual(subprocess.run(["bash", "-n", "-c", script], check=False).returncode, 0)
        manifest["graphics"]["managed_install_paths"]["icd"] = "/usr/local/share/vulkan/icd.d/../../etc/passwd"
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "path is invalid"):
            proot_fresh_setup._managed_turnip_paths(manifest)

    def test_graphics_artifacts_never_follow_symlinks_or_overwrite_other_bytes(self):
        outside = self.base / "owner-data"
        outside.write_bytes(b"preserve")
        target = self.base / "artifact"
        target.symlink_to(outside)
        with self.assertRaises(proot_fresh_setup.FreshSetupError):
            proot_fresh_setup._store_artifact(target, b"replacement")
        self.assertEqual(outside.read_bytes(), b"preserve")
        target.unlink()
        proot_fresh_setup._store_artifact(target, b"verified")
        proot_fresh_setup._store_artifact(target, b"verified")
        with self.assertRaises(proot_fresh_setup.FreshSetupError):
            proot_fresh_setup._store_artifact(target, b"different")
        self.assertEqual(proot_fresh_setup._artifact_bytes(target), b"verified")

    def test_preview_is_private_and_targets_separate_alias(self):
        preview = proot_fresh_setup.preview(
            repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
            state_dir=str(self.state), user="sbj")
        self.assertEqual(preview["operation"]["alias"], "debian")
        self.assertFalse(preview["operation"]["existing_debian_rootfs_changed"])
        self.assertEqual(preview["operation"]["image_pin"], "sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5")
        self.assertEqual(preview["operation"]["image"], "debian:trixie-20261005@sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5")
        saved = self.state / "proot-setup/previews" / f"fresh-{preview['plan_id']}.json"
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.containers / "debian/rootfs").exists())

    def test_apply_creates_only_new_alias_and_records_package_evidence(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            preview = proot_fresh_setup.preview(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), user="sbj")
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[1] == "install":
                root = self.containers / "debian/rootfs"
                (root / "etc").mkdir(parents=True)
                (root / "etc/os-release").write_text(
                    "ID=debian\nVERSION_CODENAME=trixie\n")
                (root.parent / "manifest.json").write_text(json.dumps({
                    "image_ref": "debian:trixie-20261005@sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5", "arch": "aarch64",
                    "manifest": {"config": {"digest": "sha256:4bb08c595249772893799a9189839e5a94900e8deaa14885896307e562b51e88",
                                              "size": 466},
                                 "layers": [{"digest": "sha256:df9831efb49cab24dec437e8482f2a9ddbd9e239131fa3ffe095dc1492081e1d",
                                             "size": 49761105}]},
                    "image_config": {"architecture": "arm64", "created": "2026-10-05T00:00:00Z"}}))
                return SimpleNamespace(returncode=0)
            if "/bin/bash" in args:
                alias = args[args.index("--user") + 2]
                self._write_fixture_package_database(alias)
            return SimpleNamespace(returncode=0)
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            result = proot_fresh_setup.apply(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), user="sbj", plan_id=preview["plan_id"],
                confirmed=True, password="example-passphrase", runner=runner)
        self.assertEqual(result["status"], "installed")
        self.assertTrue(result["record"]["package_versions_recorded"])
        self.assertFalse(result["record"]["turnip_runtime_verified"])
        self.assertTrue(result["record"]["package_versions_file"].endswith("debian-package-versions.txt"))
        self.assertEqual(calls[0][0:6], ["/prefix/bin/proot-distro", "install", "--name",
                                         "debian", "--architecture", "aarch64"])
        self.assertEqual(calls[0][-1], "debian:trixie-20261005@sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5")
        self.assertIn("--isolated", calls[2])
        self.assertIn("apt-get -o Acquire::https::CaInfo=/tmp/ternuxx-native-ca.pem install -y --no-install-recommends", calls[2][-1])
        self.assertIn("snapshot-cloudflare.debian.org/archive/debian/20261020T000000Z", calls[2][-1])
        self.assertEqual(calls[2][-3:], ["/bin/bash", "-lc", calls[2][-1]])
        syntax = subprocess.run(["bash", "-n", "-c", calls[2][-1]], check=False)
        self.assertEqual(syntax.returncode, 0)

    def test_failed_package_setup_can_resume_only_with_matching_journal(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            preview = proot_fresh_setup.preview(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), user="sbj")
        install_count = 0
        fail_once = True
        def runner(args, **kwargs):
            nonlocal install_count, fail_once
            if args[1] == "install":
                install_count += 1
                root = self.containers / "debian/rootfs"
                (root / "etc").mkdir(parents=True)
                (root / "etc/os-release").write_text("ID=debian\nVERSION_CODENAME=trixie\n")
                (root.parent / "manifest.json").write_text(json.dumps({
                    "image_ref": "debian:trixie-20261005@sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5", "arch": "aarch64",
                    "manifest": {"config": {"digest": "sha256:4bb08c595249772893799a9189839e5a94900e8deaa14885896307e562b51e88", "size": 466},
                                 "layers": [{"digest": "sha256:df9831efb49cab24dec437e8482f2a9ddbd9e239131fa3ffe095dc1492081e1d", "size": 49761105}]},
                    "image_config": {"architecture": "arm64", "created": "2026-10-05T00:00:00Z"}}))
            elif "/bin/bash" in args and fail_once:
                fail_once = False
                return SimpleNamespace(returncode=1)
            elif "/bin/bash" in args:
                self._write_fixture_package_database("debian")
            return SimpleNamespace(returncode=0)
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "package setup failed"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=preview["plan_id"], confirmed=True, password="example-passphrase", runner=runner)
            result = proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=preview["plan_id"], confirmed=True, password="example-passphrase", runner=runner)
        self.assertEqual(install_count, 1)
        self.assertEqual(result["status"], "installed")

    def test_failed_partial_setup_can_resume_after_mirror_only_change(self):
        manifest_path = self.repo / "config/proot/debian-trixie.json"
        initial_manifest = json.loads(manifest_path.read_text())
        initial_manifest["fresh_install"]["apt_snapshot"]["main_archive"] = "http://snapshot.debian.org/archive/debian/20261020T000000Z/"
        initial_manifest["fresh_install"]["apt_snapshot"]["security_archive"] = "http://snapshot.debian.org/archive/debian-security/20261020T000000Z/"
        initial_manifest["fresh_install"]["apt_snapshot"].pop("mirror", None)
        manifest_path.write_text(json.dumps(initial_manifest, indent=2) + "\n")
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            first = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        calls = []
        fail_once = True
        def runner(args, **kwargs):
            nonlocal fail_once
            calls.append(args)
            if args[1] == "install":
                root = self.containers / "debian/rootfs"
                (root / "etc").mkdir(parents=True)
                (root / "etc/os-release").write_text("ID=debian\nVERSION_CODENAME=trixie\n")
                spec = json.loads((self.repo / "config/proot/debian-trixie.json").read_text())["fresh_install"]
                (root.parent / "manifest.json").write_text(json.dumps({
                    "image_ref": proot_fresh_setup._pinned_image_reference(spec), "arch": "aarch64",
                    "manifest": {"config": {"digest": spec["config_digest"], "size": spec["config_size"]},
                                 "layers": [{"digest": spec["layer_digest"], "size": spec["layer_size"]}]},
                    "image_config": {"architecture": "arm64", "created": spec["image_created"]}}))
            elif "/bin/bash" in args and fail_once:
                fail_once = False
                return SimpleNamespace(returncode=1)
            elif "/bin/bash" in args:
                self._write_fixture_package_database("debian")
            return SimpleNamespace(returncode=0)
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "package setup failed"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=first["plan_id"], confirmed=True, password="example-passphrase", runner=runner)
            manifest = json.loads(manifest_path.read_text())
            manifest["fresh_install"]["apt_snapshot"]["main_archive"] = "https://snapshot-cloudflare.debian.org/archive/debian/20261020T000000Z/"
            manifest["fresh_install"]["apt_snapshot"]["security_archive"] = "https://snapshot-cloudflare.debian.org/archive/debian-security/20261020T000000Z/"
            manifest["fresh_install"]["apt_snapshot"]["mirror"] = "snapshot-cloudflare.debian.org"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            resumed = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj", resume_plan_id=first["plan_id"])
            self.assertEqual(resumed["operation"]["operation"], "resume-fresh-debian-trixie")
            self.assertEqual(resumed["operation"]["resume_from_plan_id"], first["plan_id"])
            result = proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=resumed["plan_id"], confirmed=True, password="example-passphrase", runner=runner)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(sum(call[1] == "install" for call in calls), 1)
        self.assertEqual(sum("apt-get -o Acquire::https::CaInfo=/tmp/ternuxx-native-ca.pem install -y" in call[-1] for call in calls if "/bin/bash" in call), 2)

    def test_turnip_package_selection_is_previewed_and_hardware_drift_is_rejected(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=True):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        operation = plan["operation"]
        self.assertTrue(operation["graphics"]["kgsl_accessible_at_preview"])
        self.assertTrue(operation["graphics"]["turnip_install_planned"])
        manifest = json.loads(self.repo.joinpath("config/proot/debian-trixie.json").read_text())
        self.assertTrue(set(manifest["graphics"]["hold_packages"]).issubset(set(operation["packages"])))
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "KGSL capability changed"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=plan["plan_id"], confirmed=True, password="example-passphrase", runner=lambda *_a, **_k: self.fail("must not execute"))

    def test_image_content_mismatch_stops_before_package_configuration(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            preview = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[1] == "install":
                root = self.containers / "debian/rootfs"
                (root / "etc").mkdir(parents=True)
                (root / "etc/os-release").write_text("ID=debian\nVERSION_CODENAME=trixie\n")
                (root.parent / "manifest.json").write_text(json.dumps({
                    "image_ref": "debian:trixie-20261005@sha256:913f6706df59a68922d1dd08f78c2476560a8d367897200a6005b00e5f67c2d5", "arch": "aarch64",
                    "manifest": {"config": {"digest": "sha256:4bb08c595249772893799a9189839e5a94900e8deaa14885896307e562b51e88",
                                              "size": 466},
                                 "layers": [{"digest": "sha256:wrong",
                                             "size": 49761105}]},
                    "image_config": {"architecture": "arm64", "created": "2026-10-05T00:00:00Z"}}))
            return SimpleNamespace(returncode=0)
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "does not match the pinned"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=preview["plan_id"], confirmed=True, password="example-passphrase", runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertIn("install", calls[0])

    def test_existing_debian_rootfs_is_never_overwritten(self):
        root = self.containers / "debian/rootfs"
        root.mkdir(parents=True)
        marker = root / "preserve-me"
        marker.write_text("legacy")
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "already exists"):
            proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        self.assertEqual(marker.read_text(), "legacy")

    def test_package_groups_are_selectable_but_base_is_required(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            default_plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
            self.assertEqual(default_plan["operation"]["package_groups"], ["base"])
            manifest = json.loads((self.repo / "config/proot/debian-trixie.json").read_text())
            self.assertEqual(default_plan["operation"]["packages"], manifest["packages"]["base"])
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj", groups=["base", "fonts"])
            operation = plan["operation"]
            self.assertEqual(operation["package_groups"], ["base", "fonts"])
            manifest = json.loads((self.repo / "config/proot/debian-trixie.json").read_text())
            expected = manifest["packages"]["base"] + manifest["packages"]["fonts"]
            self.assertEqual(operation["packages"], expected)
            for invalid in (["fonts"], ["base", "unknown"], ["base", "base"], [], [{"group": "base"}]):
                with self.subTest(groups=invalid), self.assertRaises(proot_fresh_setup.FreshSetupError):
                    proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                        home=str(self.home), state_dir=str(self.state), user="sbj", groups=invalid)

    def test_native_ca_bundle_change_invalidates_the_reviewed_preview(self):
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            preview = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")
        ca = self.prefix / "etc/tls/cert.pem"
        ca.write_bytes(ca.read_bytes() + b"changed")
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "CA bundle or HTTPS trust policy changed"):
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=preview["plan_id"], confirmed=True, password="example-passphrase",
                runner=lambda *_a, **_k: self.fail("CA drift must fail before any install command"))

    def test_passwordless_sudo_mode_is_plan_bound_and_never_prompts_or_sets_a_password(self):
        calls = []
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="chosen-user", sudo_mode="passwordless")
            result = proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="chosen-user",
                plan_id=plan["plan_id"], confirmed=True, runner=self._fixture_runner(calls))
        script = next(args[-1] for args in calls if "/bin/bash" in args)
        self.assertIn("chosen-user ALL=(ALL:ALL) NOPASSWD: ALL", script)
        self.assertFalse(any(args[-1] == "/usr/sbin/chpasswd" for args in calls))
        self.assertEqual(result["record"]["sudo_mode"], "passwordless")
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "do not provide a password"):
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="chosen-user",
                plan_id=plan["plan_id"], confirmed=True, password="ignored-secret",
                sudo_mode="passwordless", runner=lambda *_a, **_k: self.fail("must reject password input"))

    def test_password_is_stdin_only_and_never_persisted(self):
        calls = []
        received = {}
        base_runner = self._fixture_runner(calls)
        def runner(args, **kwargs):
            if args[-1] == "/usr/sbin/chpasswd":
                received.update(kwargs)
                calls.append(args)
                return SimpleNamespace(returncode=0)
            return base_runner(args, **kwargs)
        secret = "S3cure-Guest-Pass"
        with patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False), \
             patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"):
            plan = proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="chosen-user")
            proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="chosen-user",
                plan_id=plan["plan_id"], confirmed=True, runner=runner, password=secret)
        command = next(args for args in calls if args[-1] == "/usr/sbin/chpasswd")
        self.assertNotIn(secret, " ".join(command))
        self.assertEqual(received["input"], f"chosen-user:{secret}\n")
        persisted = "".join(path.read_text(errors="ignore") for path in self.state.rglob("*") if path.is_file())
        self.assertNotIn(secret, persisted)

    def test_changed_manifest_and_existing_unowned_alias_fail_closed(self):
        preview = proot_fresh_setup.preview(
            repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
            state_dir=str(self.state), user="sbj")
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text() + " ")
        with patch.object(proot_fresh_setup.shutil, "which", return_value="/prefix/bin/proot-distro"), \
             patch.object(proot_fresh_setup, "_kgsl_accessible", return_value=False):
            with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "differs"):
                proot_fresh_setup.apply(repo_root=str(self.repo), prefix=str(self.prefix),
                    home=str(self.home), state_dir=str(self.state), user="sbj",
                    plan_id=preview["plan_id"], confirmed=True, password="example-passphrase")
        occupied = self.containers / "debian/rootfs"
        occupied.mkdir(parents=True)
        with self.assertRaisesRegex(proot_fresh_setup.FreshSetupError, "already exists"):
            proot_fresh_setup.preview(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")


if __name__ == "__main__":
    unittest.main()
