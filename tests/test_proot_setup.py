from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_setup


class ProotSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.prefix = self.base / "prefix"
        self.root = self.prefix / "var/lib/proot-distro/containers/debian/rootfs"
        (self.root / "etc").mkdir(parents=True)
        (self.root / "usr/lib").mkdir(parents=True)
        release = "\n".join(["ID=debian", "VERSION_ID=13", "VERSION_CODENAME=trixie", ""])
        (self.root / "usr/lib/os-release").write_text(release, encoding="utf-8")
        (self.root / "etc/os-release").symlink_to("../usr/lib/os-release")
        passwd = "\n".join([
            "root:x:0:0:root:/root:/bin/bash",
            "sbj:x:1000:1000:Owner:/home/sbj:/bin/bash",
            "",
        ])
        (self.root / "etc/passwd").write_text(passwd, encoding="utf-8")
        status = self.root / "var/lib/dpkg/status"
        status.parent.mkdir(parents=True)
        status.write_text("\n\n".join([
            "Package: ca-certificates\nStatus: install ok installed\nArchitecture: all\nVersion: 2025.1",
            "Package: libgl1-mesa-dri:arm64\nStatus: hold ok installed\nArchitecture: arm64\nVersion: 25.0.7-2",
            "Package: mesa-vulkan-drivers\nStatus: deinstall ok config-files\nArchitecture: arm64\nVersion: 25.0.7-2",
            "",
        ]), encoding="utf-8")
        self.repo = self.base / "repo"
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "config/proot/debian-trixie.json", manifest)
        self.state = self.home / ".local/share/ternuxx"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _guest_digest(self) -> str:
        digest = hashlib.sha256()
        for path in sorted((self.root / "etc").iterdir()):
            digest.update(path.name.encode())
            if path.is_symlink():
                digest.update(os.readlink(path).encode())
            else:
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def test_adoption_preview_and_apply_only_write_native_state(self) -> None:
        before = self._guest_digest()
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                                                home=str(self.home), state_dir=str(self.state), user="sbj")
        operation = preview["operation"]
        self.assertEqual(operation["guest_mutations"], [])
        self.assertEqual(operation["package_changes"], [])
        base_packages = operation["observed_package_groups"]["base"]
        self.assertEqual(base_packages["installed"], 2)
        self.assertEqual(base_packages["held"], ["libgl1-mesa-dri"])
        self.assertIn("libvulkan1", base_packages["missing"])
        self.assertRegex(operation["dpkg_status_sha256"], r"^[0-9a-f]{64}$")
        result = proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                                            home=str(self.home), state_dir=str(self.state), user="sbj",
                                            plan_id=preview["plan_id"], confirmed=True)
        self.assertFalse(result["guest_mutations"])
        current = proot_setup.status(repo_root=str(self.repo), prefix=str(self.prefix),
                                     home=str(self.home), state_dir=str(self.state))
        self.assertEqual(current["status"], "adopted")
        self.assertEqual(current["package_baseline"]["status"], "matches")
        record = self.state / "proot-setup/provider.json"
        self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        self.assertEqual(self._guest_digest(), before)

    def test_apply_requires_confirmation_and_unchanged_preview(self) -> None:
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                                                home=str(self.home), state_dir=str(self.state), user="sbj")
        with self.assertRaisesRegex(proot_setup.SetupError, "explicit confirmation"):
            proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                                       state_dir=str(self.state), user="sbj", plan_id=preview["plan_id"],
                                       confirmed=False)
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(proot_setup.SetupError, "differs from the reviewed preview"):
            proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                                       state_dir=str(self.state), user="sbj", plan_id=preview["plan_id"],
                                       confirmed=True)

    def test_adoption_status_reports_selected_package_drift_without_repair(self) -> None:
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=preview["plan_id"], confirmed=True)
        status_file = self.root / "var/lib/dpkg/status"
        original = status_file.read_bytes()
        record_file = self.state / "proot-setup/provider.json"
        receipt_before = record_file.read_bytes()
        status_file.write_text(status_file.read_text().replace("25.0.7-2", "25.0.8-1"), encoding="utf-8")
        result = proot_setup.status(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state))
        self.assertEqual(result["package_baseline"]["status"], "changed")
        self.assertEqual(result["package_baseline"]["changed_groups"], ["base"])
        self.assertEqual(record_file.read_bytes(), receipt_before)
        status_file.write_bytes(original)

    def test_stale_adoption_record_is_bound_to_preview_and_never_overwritten(self) -> None:
        record = self.state / "proot-setup/provider.json"
        record.parent.mkdir(parents=True, mode=0o700)
        original = b'{"schema_version":1,"profile_id":"ternuxx-debian-trixie-workstation","manifest_sha256":"old"}\n'
        record.write_bytes(original)
        record.chmod(0o600)
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        self.assertTrue(preview["operation"]["apply_blocked_reason"])
        with self.assertRaisesRegex(proot_setup.SetupError, "different rootfs identity"):
            proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=preview["plan_id"], confirmed=True)
        self.assertEqual(record.read_bytes(), original)

    def test_stale_same_rootfs_adoption_refresh_has_exact_rollback(self):
        original_preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=original_preview["plan_id"], confirmed=True)
        record = self.state / "proot-setup/provider.json"
        original_bytes = record.read_bytes()
        before_guest = self._guest_digest()
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")

        refresh = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        operation = refresh["operation"]
        self.assertTrue(operation["refresh_existing_record"])
        self.assertIsNone(operation["apply_blocked_reason"])
        backup_id = operation["rollback_backup_id"]
        result = proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=refresh["plan_id"], confirmed=True)
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["record"]["rollback_backup_id"], backup_id)
        backup = self.state / "proot-setup/adoption-backups" / f"{backup_id}.record"
        self.assertEqual(backup.read_bytes(), original_bytes)
        self.assertNotEqual(record.read_bytes(), original_bytes)
        self.assertEqual(self._guest_digest(), before_guest)

        rollback = proot_setup.preview_adoption_rollback(prefix=str(self.prefix), home=str(self.home),
            state_dir=str(self.state), backup_id=backup_id)
        rolled_back = proot_setup.apply_adoption_rollback(prefix=str(self.prefix), home=str(self.home),
            state_dir=str(self.state), backup_id=backup_id, plan_id=rollback["plan_id"], confirmed=True)
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertEqual(record.read_bytes(), original_bytes)
        self.assertEqual(self._guest_digest(), before_guest)

    def test_rollback_refuses_a_changed_current_record_after_preview(self):
        first = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=first["plan_id"], confirmed=True)
        original = (self.state / "proot-setup/provider.json").read_bytes()
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
        refresh = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=refresh["plan_id"], confirmed=True)
        backup_id = refresh["operation"]["rollback_backup_id"]
        rollback = proot_setup.preview_adoption_rollback(prefix=str(self.prefix), home=str(self.home),
            state_dir=str(self.state), backup_id=backup_id)
        record = self.state / "proot-setup/provider.json"
        changed = record.read_bytes() + b" "
        record.write_bytes(changed)
        record.chmod(0o600)
        with self.assertRaisesRegex(proot_setup.SetupError, "differs from the reviewed rollback preview"):
            proot_setup.apply_adoption_rollback(prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), backup_id=backup_id, plan_id=rollback["plan_id"], confirmed=True)
        self.assertEqual(record.read_bytes(), changed)
        self.assertNotEqual(record.read_bytes(), original)

    def test_symlinked_adoption_backup_directory_is_refused(self):
        first = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj",
            plan_id=first["plan_id"], confirmed=True)
        record = self.state / "proot-setup/provider.json"
        original = record.read_bytes()
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
        refresh = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        backup_dir = self.state / "proot-setup/adoption-backups"
        outside = self.base / "outside-backups"
        outside.mkdir(mode=0o700)
        backup_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(proot_setup.SetupError, "backup directory is a symbolic link"):
            proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj",
                plan_id=refresh["plan_id"], confirmed=True)
        self.assertEqual(record.read_bytes(), original)
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_change_is_reported_without_claiming_guest_drift_or_mutating_it(self) -> None:
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                                                home=str(self.home), state_dir=str(self.state), user="sbj")
        proot_setup.apply_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                                   home=str(self.home), state_dir=str(self.state), user="sbj",
                                   plan_id=preview["plan_id"], confirmed=True)
        before = self._guest_digest()
        record = self.state / "proot-setup/provider.json"
        record_before = record.read_bytes()
        manifest = self.repo / "config/proot/debian-trixie.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
        result = proot_setup.status(repo_root=str(self.repo), prefix=str(self.prefix),
                                    home=str(self.home), state_dir=str(self.state))
        self.assertEqual(result["status"], "profile_changed")
        self.assertNotEqual(result["manifest_sha256"], result["recorded_manifest_sha256"])
        self.assertIn("guest drift is not inferred", result["detail"])
        self.assertIn("does not refresh adoption metadata", result["next_action"])
        self.assertEqual(self._guest_digest(), before)
        self.assertEqual(record.read_bytes(), record_before)

    def test_adoption_checks_manifest_icd_path_and_reports_other_config_separately(self) -> None:
        graphics = self.root / "usr/local/share/vulkan/icd.d"
        graphics.mkdir(parents=True)
        (graphics / "ternux_freedreno_icd.json").write_text("legacy icd", encoding="utf-8")
        driver = self.root / "usr/local/lib/aarch64-linux-gnu/libvulkan_freedreno.so"
        driver.parent.mkdir(parents=True)
        driver.write_bytes(b"driver")
        preview = proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
            home=str(self.home), state_dir=str(self.state), user="sbj")
        operation = preview["operation"]
        graphics_state = operation["observed_graphics_files"]
        self.assertEqual(graphics_state["turnip_driver"]["status"], "present")
        self.assertEqual(graphics_state["turnip_icd"]["path"],
            "/usr/local/share/vulkan/icd.d/ternuxx_freedreno_icd.json")
        self.assertEqual(graphics_state["turnip_icd"]["status"], "missing")
        self.assertEqual(operation["observed_other_icd_configs"][0]["name"], "ternux_freedreno_icd.json")

    def test_manifest_graphics_symlink_is_refused_without_following_it(self) -> None:
        graphics = self.root / "usr/local/share/vulkan"
        graphics.mkdir(parents=True)
        outside = self.base / "outside-icd"
        outside.mkdir()
        (graphics / "icd.d").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(proot_setup.SetupError, "symlink"):
            proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")

    def test_package_status_database_symlink_is_refused(self) -> None:
        status = self.root / "var/lib/dpkg/status"
        saved = self.base / "status-saved"
        status.rename(saved)
        status.symlink_to(saved)
        with self.assertRaisesRegex(proot_setup.SetupError, "status database is unsafe"):
            proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix),
                home=str(self.home), state_dir=str(self.state), user="sbj")

    def test_wrong_release_or_user_is_rejected(self) -> None:
        release = self.root / "usr/lib/os-release"
        release.write_text("\n".join(["ID=ubuntu", "VERSION_ID=24.04", "VERSION_CODENAME=noble", ""]),
                           encoding="utf-8")
        with self.assertRaisesRegex(proot_setup.SetupError, "not the Debian Trixie profile"):
            proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                                         state_dir=str(self.state), user="sbj")
        release.write_text("\n".join(["ID=debian", "VERSION_ID=13", "VERSION_CODENAME=trixie", ""]),
                           encoding="utf-8")
        with self.assertRaisesRegex(proot_setup.SetupError, "selected guest account is missing"):
            proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                                         state_dir=str(self.state), user="missing")

    def test_legacy_icd_move_is_exact_previewed_and_reversible(self) -> None:
        guest_dir = self.root / "usr/local/share/vulkan/icd.d"
        guest_dir.mkdir(parents=True)
        source = guest_dir / "ternux_freedreno_icd.json"
        target = guest_dir / "ternuxx_freedreno_icd.json"
        original = json.dumps({
            "file_format_version": "1.0.1",
            "ICD": {"api_version": "1.4.359", "library_arch": "64",
                    "library_path": "/usr/local/lib/aarch64-linux-gnu/libvulkan_freedreno.so"},
        }, indent=2).encode()
        source.write_bytes(original)
        source.chmod(0o644)
        with patch.object(proot_setup, "_assert_guest_icd_idle"), \
             patch("proot_guest_retirement._container_lock", return_value=nullcontext()):
            preview = proot_setup.preview_icd_migration(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), alias="debian")
            operation = preview["operation"]
            self.assertEqual(operation["source_path"], "/usr/local/share/vulkan/icd.d/ternux_freedreno_icd.json")
            self.assertEqual(operation["target_path"], "/usr/local/share/vulkan/icd.d/ternuxx_freedreno_icd.json")
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(target.exists())
            applied = proot_setup.apply_icd_migration(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), alias="debian", plan_id=preview["plan_id"], confirmed=True)
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target.stat().st_ino, operation["source_inode"])
            backup = Path(applied["receipt"]["backup_path"])
            self.assertEqual(backup.read_bytes(), original)
            rollback = proot_setup.preview_icd_rollback(
                prefix=str(self.prefix), home=str(self.home), state_dir=str(self.state),
                plan_id=preview["plan_id"])
            result = proot_setup.apply_icd_rollback(
                prefix=str(self.prefix), home=str(self.home), state_dir=str(self.state),
                migration_id=preview["plan_id"], plan_id=rollback["plan_id"], confirmed=True)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(target.exists())

    def test_legacy_icd_migration_refuses_conflicts_and_unexpected_content(self) -> None:
        guest_dir = self.root / "usr/local/share/vulkan/icd.d"
        guest_dir.mkdir(parents=True)
        source = guest_dir / "ternux_freedreno_icd.json"
        target = guest_dir / "ternuxx_freedreno_icd.json"
        source.write_text("{}", encoding="utf-8")
        with patch.object(proot_setup, "_assert_guest_icd_idle"), \
             patch("proot_guest_retirement._container_lock", return_value=nullcontext()):
            with self.assertRaisesRegex(proot_setup.SetupError, "does not match"):
                proot_setup.preview_icd_migration(
                    repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                    state_dir=str(self.state), alias="debian")
        source.unlink()
        source.write_text(json.dumps({"file_format_version": "1.0.1", "ICD": {
            "api_version": "1.4.359", "library_arch": "64",
            "library_path": "/usr/local/lib/aarch64-linux-gnu/libvulkan_freedreno.so"}}), encoding="utf-8")
        target.write_text("preserve", encoding="utf-8")
        with patch.object(proot_setup, "_assert_guest_icd_idle"), \
             patch("proot_guest_retirement._container_lock", return_value=nullcontext()), \
             self.assertRaisesRegex(proot_setup.SetupError, "destination already exists"):
            proot_setup.preview_icd_migration(
                repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                state_dir=str(self.state), alias="debian")
        self.assertEqual(source.read_text(), json.dumps({"file_format_version": "1.0.1", "ICD": {
            "api_version": "1.4.359", "library_arch": "64",
            "library_path": "/usr/local/lib/aarch64-linux-gnu/libvulkan_freedreno.so"}}))
        self.assertEqual(target.read_text(), "preserve")

    def test_fresh_preview_cli_forwards_provider_and_package_group_selection(self) -> None:
        preview = {"status": "preview", "plan_id": "a" * 64}
        argv = ["proot_setup.py", "fresh-preview", "--repo-root", str(self.repo),
                "--prefix", str(self.prefix), "--home", str(self.home),
                "--state-dir", str(self.state), "--user", "sbj",
                "--alias", "ternuxx-replay-cli", "--groups", "base,fonts"]
        with patch.object(sys, "argv", argv), \
             patch.object(proot_setup.proot_fresh_setup, "preview", return_value=preview) as fresh_preview, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(proot_setup.main(), 0)
        self.assertEqual(fresh_preview.call_args.kwargs["alias"], "ternuxx-replay-cli")
        self.assertEqual(fresh_preview.call_args.kwargs["groups"], ["base", "fonts"])
        self.assertNotIn("resume_plan_id", fresh_preview.call_args.kwargs)

    def test_fresh_apply_cli_uses_preview_bound_account_and_alias(self) -> None:
        plan_id = "d" * 64
        result = {"status": "installed", "record": {"guest_user": "workuser"}}
        argv = ["proot_setup.py", "fresh-install", "--repo-root", str(self.repo),
                "--prefix", str(self.prefix), "--home", str(self.home),
                "--state-dir", str(self.state), "--plan-id", plan_id, "--yes"]
        with patch.object(sys, "argv", argv), \
             patch.object(proot_setup.getpass, "getpass", side_effect=["private-passphrase", "private-passphrase"]), \
             patch.object(proot_setup.proot_fresh_setup, "apply", return_value=result) as fresh_apply, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(proot_setup.main(), 0)
        self.assertIsNone(fresh_apply.call_args.kwargs["user"])
        self.assertIsNone(fresh_apply.call_args.kwargs["alias"])
        self.assertEqual(fresh_apply.call_args.kwargs["plan_id"], plan_id)
        self.assertEqual(fresh_apply.call_args.kwargs["password"], "private-passphrase")
        self.assertNotIn("private-passphrase", output.getvalue())

    def test_fresh_resume_preview_cli_forwards_failed_plan_and_groups(self) -> None:
        failed_id = "b" * 64
        preview = {"status": "preview", "plan_id": "c" * 64}
        argv = ["proot_setup.py", "fresh-resume-preview", "--repo-root", str(self.repo),
                "--prefix", str(self.prefix), "--home", str(self.home),
                "--state-dir", str(self.state), "--user", "sbj",
                "--plan-id", failed_id, "--groups", "base,development"]
        with patch.object(sys, "argv", argv), \
             patch.object(proot_setup.proot_fresh_setup, "preview", return_value=preview) as fresh_preview, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(proot_setup.main(), 0)
        self.assertEqual(fresh_preview.call_args.kwargs["resume_plan_id"], failed_id)
        self.assertEqual(fresh_preview.call_args.kwargs["groups"], ["base", "development"])

    def test_rootfs_symlink_is_rejected(self) -> None:
        original = self.root
        saved = self.base / "rootfs-real"
        original.rename(saved)
        original.symlink_to(saved, target_is_directory=True)
        with self.assertRaisesRegex(proot_setup.SetupError, "regular directory tree"):
            proot_setup.preview_adoption(repo_root=str(self.repo), prefix=str(self.prefix), home=str(self.home),
                                         state_dir=str(self.state), user="sbj")


if __name__ == "__main__":
    unittest.main()
