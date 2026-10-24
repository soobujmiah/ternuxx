from __future__ import annotations

from pathlib import Path
import os
import stat
import threading
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_service  # noqa: E402
import proot_shortcuts  # noqa: E402


class ProotShortcutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-proot-shortcuts-")
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.repo = Path(self.temp.name) / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "scripts" / "proot-x11-app.sh").touch()
        (self.repo / "scripts" / "proot-x11-shortcut-manager.sh").touch()
        (self.repo / "tx").touch()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_guest_executable(self, prefix, guest_path="/usr/bin/editor"):
        rootfs = Path(prefix) / "var/lib/proot-distro/containers/debian/rootfs"
        executable = rootfs / guest_path.lstrip("/")
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        return executable

    def preview(self, action="add", app_id="terminal"):
        return proot_shortcuts.preview(
            action, app_id, home=str(self.home), prefix="/termux",
            repo_root=str(self.repo), path="/bin",
        )

    def test_x11_launch_wrappers_use_the_supported_checkout_entrypoint(self) -> None:
        for name in ("proot-x11-app.sh", "proot-x11-shortcut-manager.sh", "proot-x11-shortcuts.sh"):
            source = (ROOT / "scripts" / name).read_text()
            self.assertIn('"$ROOT/tx"', source, name)
            self.assertNotIn('"$ROOT/ternuxx"', source, name)

    def test_list_reports_provider_and_does_not_claim_guest_app_availability(self) -> None:
        result = proot_shortcuts.list_shortcuts(home=str(self.home), prefix="/termux", repo_root=str(self.repo))
        self.assertEqual(result["resource_id"], "proot.x11.shortcuts")
        terminal = next(item for item in result["items"] if item["id"] == "terminal")
        self.assertEqual(terminal["provider"], "proot_debian")
        self.assertEqual(terminal["shortcut_owner"], "native_termux")
        self.assertEqual(terminal["shortcut_state"], "absent")
        self.assertEqual(terminal["application_availability"], "unknown")
        self.assertTrue(result["read_only"])

    def test_add_preview_requires_exact_confirmation_then_writes_owned_file(self) -> None:
        with patch.object(proot_shortcuts, "_available", return_value=True):
            plan = self.preview()
            self.assertTrue(plan["requires_confirmation"])
            self.assertEqual(plan["provider"], "proot_debian")
            self.assertEqual(plan["storage_provider"], "native_termux")
            self.assertEqual(proot_shortcuts.apply(
                "add", "terminal", home=str(self.home), prefix="/termux",
                repo_root=str(self.repo), confirmed=False, plan_id=None,
                path="/bin",
            )["status"], "confirmation_required")
            with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "plan ID"):
                proot_shortcuts.apply(
                    "add", "terminal", home=str(self.home), prefix="/termux",
                    repo_root=str(self.repo), confirmed=True, plan_id="wrong",
                    path="/bin",
                )
            applied = proot_shortcuts.apply(
                "add", "terminal", home=str(self.home), prefix="/termux",
                repo_root=str(self.repo), confirmed=True, plan_id=plan["plan_id"],
                path="/bin",
            )
        self.assertEqual(applied["status"], "complete")
        target = self.home / ".local" / "share" / "applications" / "ternuxx-proot-terminal.desktop"
        text = target.read_text()
        self.assertIn("X-Ternuxx-Managed=true", text)
        self.assertIn("X-Ternuxx-App-ID=terminal", text)
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        self.assertIn('management app launch terminal', text)
        self.assertIn(str(self.repo / "tx"), text)
        self.assertNotIn(str(self.repo / "ternuxx"), text)
        self.assertNotIn('proot-x11-app.sh', text)

    def test_dynamic_shortcut_add_remove_uses_exact_preview_and_managed_file(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        rootfs = prefix / "var/lib/proot-distro/containers/debian/rootfs"
        app_dir = rootfs / "usr/share/applications"
        app_dir.mkdir(parents=True)
        self.make_guest_executable(prefix)
        (app_dir / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor %f\n"
        )
        data = self.home / "xfce-data"
        kwargs = {"home": str(self.home), "prefix": str(prefix), "repo_root": str(self.repo),
                  "xdg_data_home": str(data)}
        plan = proot_shortcuts.preview("add", desktop_id="org.example.Editor.desktop", **kwargs)
        self.assertEqual(plan["name"], "Editor")
        self.assertTrue(plan["requires_confirmation"])
        applied = proot_shortcuts.apply("add", desktop_id="org.example.Editor.desktop",
            confirmed=True, plan_id=plan["plan_id"], state_dir=str(self.home / ".local/share/ternuxx"), **kwargs)
        self.assertEqual(applied["status"], "complete")
        target = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        self.assertIn("X-Ternuxx-Generated=proot-app-v2", target.read_text())
        inventory = proot_shortcuts.list_shortcuts(home=str(self.home), prefix=str(prefix),
                                                    xdg_data_home=str(data), repo_root=str(self.repo))
        item = next(row for row in inventory["desktop_applications"]["items"]
                    if row["desktop_id"] == "org.example.Editor.desktop")
        self.assertEqual(item["shortcut_state"], "installed")
        remove = proot_shortcuts.preview("remove", desktop_id="org.example.Editor.desktop", **kwargs)
        removed = proot_shortcuts.apply("remove", desktop_id="org.example.Editor.desktop",
            confirmed=True, plan_id=remove["plan_id"], state_dir=str(self.home / ".local/share/ternuxx"), **kwargs)
        self.assertEqual(removed["status"], "complete")
        self.assertFalse(target.exists())

    def test_dynamic_shortcut_can_remove_owned_launcher_when_app_command_is_unavailable(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        rootfs = prefix / "var/lib/proot-distro/containers/debian/rootfs"
        app_dir = rootfs / "usr/share/applications"
        app_dir.mkdir(parents=True)
        executable = self.make_guest_executable(prefix)
        (app_dir / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor\n"
        )
        data = self.home / "xfce-data"
        kwargs = {"home": str(self.home), "prefix": str(prefix), "repo_root": str(self.repo),
                  "xdg_data_home": str(data)}
        added = proot_shortcuts.preview("add", desktop_id="org.example.Editor.desktop", **kwargs)
        proot_shortcuts.apply("add", desktop_id="org.example.Editor.desktop", confirmed=True,
            plan_id=added["plan_id"], state_dir=str(self.home / ".local/share/ternuxx"), **kwargs)
        executable.chmod(0o644)
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "no longer available"):
            proot_shortcuts.preview("add", desktop_id="org.example.Editor.desktop", **kwargs)
        removal = proot_shortcuts.preview("remove", desktop_id="org.example.Editor.desktop", **kwargs)
        result = proot_shortcuts.apply("remove", desktop_id="org.example.Editor.desktop", confirmed=True,
            plan_id=removal["plan_id"], state_dir=str(self.home / ".local/share/ternuxx"), **kwargs)
        self.assertEqual(result["status"], "complete")
        self.assertFalse((data / "applications/ternuxx-proot-app-org.example.Editor.desktop").exists())

    def test_dynamic_shortcut_preserves_modified_generated_launcher(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        rootfs = prefix / "var/lib/proot-distro/containers/debian/rootfs"
        app_dir = rootfs / "usr/share/applications"
        app_dir.mkdir(parents=True)
        self.make_guest_executable(prefix)
        (app_dir / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor\n"
        )
        data = self.home / "xfce-data"
        target = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        target.parent.mkdir(parents=True)
        target.write_text("[Desktop Entry]\nName=User edit\n")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "modified or not Ternuxx-owned"):
            proot_shortcuts.preview("remove", desktop_id="org.example.Editor.desktop",
                home=str(self.home), prefix=str(prefix), repo_root=str(self.repo), xdg_data_home=str(data))
        self.assertEqual(target.read_text(), "[Desktop Entry]\nName=User edit\n")

    def test_individual_shortcut_apply_waits_for_shared_sync_lock(self) -> None:
        with patch.object(proot_shortcuts, "_available", return_value=True):
            plan = self.preview()
            state_dir = self.home / ".local" / "share" / "ternuxx"
            state = proot_shortcuts._sync_state_root(str(self.home), str(state_dir), create=True)
            held = proot_shortcuts._sync_lock(state)
            attempted, done = threading.Event(), threading.Event()
            outcomes = []

            def apply_shortcut():
                try:
                    outcomes.append(proot_shortcuts.apply(
                        "add", "terminal", home=str(self.home), prefix="/termux",
                        repo_root=str(self.repo), confirmed=True, plan_id=plan["plan_id"],
                        path="/bin", state_dir=str(state_dir)))
                except Exception as exc:
                    outcomes.append(exc)
                finally:
                    done.set()

            original_lock = proot_shortcuts._sync_lock

            def tracked_lock(path):
                attempted.set()
                return original_lock(path)

            worker = threading.Thread(target=apply_shortcut)
            with patch.object(proot_shortcuts, "_sync_lock", side_effect=tracked_lock):
                worker.start()
                try:
                    self.assertTrue(attempted.wait(2))
                    self.assertFalse(done.wait(0.15), "individual apply bypassed the bulk-sync lock")
                finally:
                    os.close(held)
                self.assertTrue(done.wait(2))
                worker.join(timeout=2)
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], dict)
        self.assertEqual(outcomes[0]["status"], "complete")

    def test_stale_preview_is_rejected_and_existing_unowned_file_is_preserved(self) -> None:
        with patch.object(proot_shortcuts, "_available", return_value=True):
            plan = self.preview()
        target = self.home / ".local" / "share" / "applications" / "ternuxx-proot-terminal.desktop"
        target.parent.mkdir(parents=True)
        target.write_text("[Desktop Entry]\nName=My launcher\n")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "non-Ternuxx"):
            proot_shortcuts.apply(
                "add", "terminal", home=str(self.home), prefix="/termux",
                repo_root=str(self.repo), confirmed=True, plan_id=plan["plan_id"],
                path="/bin",
            )
        self.assertEqual(target.read_text(), "[Desktop Entry]\nName=My launcher\n")

    def test_exact_legacy_launcher_is_adopted_but_edits_are_not(self) -> None:
        app_dir = self.home / ".local" / "share" / "applications"
        app_dir.mkdir(parents=True)
        target = app_dir / "ternuxx-proot-shortcut-manager.desktop"
        target.write_bytes(proot_shortcuts._legacy_entry(
            "shortcut-manager", prefix="/termux", repo_root=str(self.repo),
        ))
        listed = proot_shortcuts.list_shortcuts(home=str(self.home), prefix="/termux", repo_root=str(self.repo))
        item = next(row for row in listed["items"] if row["id"] == "shortcut-manager")
        self.assertEqual(item["shortcut_state"], "installed")
        with patch.object(proot_shortcuts, "_available", return_value=True):
            plan = self.preview(app_id="shortcut-manager")
        self.assertTrue(plan["changed"])
        target.write_bytes(target.read_bytes() + b"# user edit\n")
        item = next(row for row in proot_shortcuts.list_shortcuts(
            home=str(self.home), prefix="/termux", repo_root=str(self.repo),
        )["items"] if row["id"] == "shortcut-manager")
        self.assertEqual(item["shortcut_state"], "conflict")
        with self.assertRaises(proot_shortcuts.ShortcutError):
            self.preview(app_id="shortcut-manager")

    def test_remove_only_deletes_owned_shortcut_and_never_stops_apps(self) -> None:
        with patch.object(proot_shortcuts, "_available", return_value=True):
            add = self.preview()
            proot_shortcuts.apply(
                "add", "terminal", home=str(self.home), prefix="/termux",
                repo_root=str(self.repo), confirmed=True, plan_id=add["plan_id"], path="/bin",
            )
        remove = self.preview("remove")
        with self.assertRaises(proot_shortcuts.ShortcutError):
            proot_shortcuts.apply(
                "remove", "terminal", home=str(self.home), prefix="/termux",
                repo_root=str(self.repo), confirmed=True, plan_id="stale", path="/bin",
            )
        result = proot_shortcuts.apply(
            "remove", "terminal", home=str(self.home), prefix="/termux",
            repo_root=str(self.repo), confirmed=True, plan_id=remove["plan_id"], path="/bin",
        )
        self.assertFalse((self.home / ".local" / "share" / "applications" / "ternuxx-proot-terminal.desktop").exists())
        self.assertFalse(result["safety"]["running_apps_stopped"])

    def test_symlinked_target_and_external_xdg_directory_fail_closed(self) -> None:
        app_dir = self.home / ".local" / "share" / "applications"
        app_dir.mkdir(parents=True)
        outside = Path(self.temp.name) / "owned-by-user.desktop"
        outside.write_text("keep")
        (app_dir / "ternuxx-proot-files.desktop").symlink_to(outside)
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "symbolic link"):
            proot_shortcuts.list_shortcuts(home=str(self.home), prefix="/termux")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "inside"):
            proot_shortcuts.list_shortcuts(home=str(self.home), prefix="/termux", xdg_data_home=self.temp.name)
        self.assertEqual(outside.read_text(), "keep")

    def test_launch_uses_only_named_catalog_entries_and_reports_visibility_unknown(self) -> None:
        with patch.object(proot_shortcuts.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()) as run:
            result = proot_shortcuts.launch(
                "files", prefix="/termux", repo_root=str(self.repo), env={"DISPLAY": ":1"},
            )
        self.assertEqual(result["resource_id"], "proot.x11.app.files")
        self.assertEqual(result["provider"], "proot_debian")
        self.assertEqual(result["gui_visible"], "unknown")
        self.assertEqual(run.call_args.args[0][1], str(self.repo / "scripts" / "proot-x11-app.sh"))
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "unknown"):
            proot_shortcuts.launch("../../shell", prefix="/termux", repo_root=str(self.repo), env={})

    def test_management_service_exposes_shortcut_operations_with_typed_provider_data(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr", "HOME": str(self.home), "PATH": "/bin"}
        request = {"api_version": 1, "request_id": "request-shortcuts-01",
                   "operation": "proot.shortcuts.list", "args": {}}
        result = management_service.dispatch(request, env=env)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["resource_id"], "proot.x11.shortcuts")
        self.assertEqual({item["provider"] for item in result["data"]["items"]}, {"proot_debian"})

    def test_management_launch_routes_explicit_ternuxx_display(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin"}
        request = {"api_version": 1, "request_id": "request-proot-ternuxx-01",
                   "operation": "proot.app.launch", "args": {"app_id": "files", "display": ":1"}}
        with patch.object(proot_shortcuts, "launch", return_value={"status": "process_exited"}) as launch:
            result = management_service.dispatch(request, env=env)
        self.assertTrue(result["ok"])
        self.assertEqual(launch.call_args.kwargs["display"], ":1")
        self.assertNotIn("session_owner", launch.call_args.kwargs)

    def test_management_launch_routes_guest_desktop_id(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin"}
        request = {"api_version": 1, "request_id": "request-proot-desktop-id-01",
                   "operation": "proot.app.launch", "args": {"desktop_id": "thunar.desktop"}}
        with patch.object(proot_shortcuts, "launch_desktop_application",
                          return_value={"status": "process_exited"}) as launch:
            result = management_service.dispatch(request, env=env)
        self.assertTrue(result["ok"])
        self.assertEqual(launch.call_args.args[0], "thunar.desktop")

    def test_standalone_display_zero_is_forwarded_to_app_wrapper(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin"}
        prefix = Path(self.temp.name) / "prefix"
        app_dir = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        app_dir.mkdir(parents=True)
        (app_dir / "xfce4-about.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=About Xfce\nExec=xfce4-about\n",
            encoding="utf-8",
        )
        with patch.object(proot_shortcuts.subprocess, "run",
                          return_value=type("Result", (), {"returncode": 0})()) as run:
            result = proot_shortcuts.launch_desktop_application(
                "xfce4-about.desktop", prefix=str(prefix), repo_root=str(self.repo),
                env=env, display=":0",
            )
        self.assertEqual(result["provider"], "proot_debian")
        command = run.call_args.args[0]
        self.assertIn("--display", command)
        self.assertEqual(command[command.index("--display") + 1], ":0")

    def test_shortcut_sync_preview_and_apply_are_typed_shared_operations(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin",
               "TERNUXX_STATE_DIR": str(self.home / ".local/share/ternuxx")}
        preview_request = {"api_version": 1, "request_id": "request-proot-sync-preview-01",
                           "operation": "proot.shortcuts.sync.preview", "args": {}}
        with patch.object(proot_shortcuts, "preview_desktop_application_sync",
                          return_value={"status": "preview", "changed": True}) as preview:
            result = management_service.dispatch(preview_request, env=env)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["status"], "preview")
        self.assertEqual(preview.call_args.kwargs["home"], str(self.home))
        self.assertEqual(preview.call_args.kwargs["xdg_data_home"],
                         str(self.home / ".local/share/ternuxx/xfce/data"))

        apply_request = {"api_version": 1, "request_id": "request-proot-sync-apply-01",
                         "operation": "proot.shortcuts.sync.apply",
                         "args": {"confirmed": True, "plan_id": "a" * 24}}
        with patch.object(proot_shortcuts, "apply_desktop_application_sync",
                          return_value={"status": "complete"}) as apply:
            result = management_service.dispatch(apply_request, env=env)
        self.assertTrue(result["ok"])
        self.assertEqual(apply.call_args.kwargs["plan_id"], "a" * 24)
        self.assertTrue(apply.call_args.kwargs["confirmed"])

    def test_management_launch_rejects_legacy_ternux_session_owner(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin"}
        request = {"api_version": 1, "request_id": "request-proot-legacy-owner-01",
                   "operation": "proot.app.launch",
                   "args": {"app_id": "files", "session_owner": "ternux", "display": ":1"}}
        result = management_service.dispatch(request, env=env)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_arguments")

    def test_management_launch_rejects_malformed_display(self) -> None:
        env = {"TERMUX_VERSION": "test", "PREFIX": "/data/data/com.termux/files/usr",
               "HOME": str(self.home), "PATH": "/bin"}
        request = {"api_version": 1, "request_id": "request-proot-display-01",
                   "operation": "proot.app.launch", "args": {"app_id": "files", "display": "$(bad)"}}
        result = management_service.dispatch(request, env=env)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_arguments")


    def test_sync_discovers_visible_guest_apps_and_adds_separate_menu_category(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        root = prefix / "var/lib/proot-distro/containers/debian/rootfs"
        apps = root / "usr/share/applications"
        apps.mkdir(parents=True)
        self.make_guest_executable(prefix)
        (apps / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor %f\nIcon=editor\n")
        (apps / "hidden.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Hidden\nExec=hidden\nNoDisplay=true\n")
        config = self.home / "xfce-config"
        data = self.home / "xfce-data"
        result = proot_shortcuts._sync_desktop_applications_mutate(
            home=str(self.home), prefix=str(prefix), repo_root=str(self.repo),
            xdg_data_home=str(data), xdg_config_home=str(config),
        )
        self.assertEqual(result["discovered"], 1)
        launcher = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        self.assertIn("Categories=X-Ternuxx-PRoot;", launcher.read_text())
        self.assertIn("--desktop-id", launcher.read_text())
        self.assertIn(str(self.repo / "tx"), launcher.read_text())
        self.assertIn("PRoot Apps", (config / "menus/xfce-applications.menu").read_text())
        self.assertIn("MergeFile type=\"parent\"", (config / "menus/xfce-applications.menu").read_text())
        self.assertTrue((data / "desktop-directories/ternuxx-proot-apps.directory").is_file())

    def test_sync_rollback_state_allows_shared_ancestors_under_umask_022(self) -> None:
        import os
        home = Path(self.temp.name) / "ordinary-home"
        home.mkdir(mode=0o755)
        old_mask = os.umask(0o022)
        try:
            state = proot_shortcuts._sync_state_root(
                str(home), str(home / ".local/share/ternuxx"), create=True)
            self.assertEqual(stat.S_IMODE((home / ".local").stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((home / ".local/share").stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            self.assertEqual(proot_shortcuts._sync_state_root(
                str(home), str(home / ".local/share/ternuxx"), create=False), state)
        finally:
            os.umask(old_mask)

    def test_bulk_sync_preview_requires_confirmation_and_applies_exact_plan(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        apps = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        apps.mkdir(parents=True)
        self.make_guest_executable(prefix)
        (apps / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor %f\n")
        data = self.home / "xfce-data"
        config = self.home / "xfce-config"
        kwargs = {"home": str(self.home), "prefix": str(prefix), "repo_root": str(self.repo),
                  "xdg_data_home": str(data), "xdg_config_home": str(config)}
        plan = proot_shortcuts.preview_desktop_application_sync(**kwargs)
        self.assertTrue(plan["read_only"])
        self.assertTrue(plan["requires_confirmation"])
        self.assertEqual(plan["changes"][0]["action"], "create")
        self.assertFalse((data / "applications").exists())
        self.assertEqual(proot_shortcuts.apply_desktop_application_sync(
            **kwargs, confirmed=False, plan_id=None)["status"], "confirmation_required")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "state changed"):
            proot_shortcuts.apply_desktop_application_sync(
                **kwargs, confirmed=True, plan_id="0" * 24)
        applied = proot_shortcuts.apply_desktop_application_sync(
            **kwargs, confirmed=True, plan_id=plan["plan_id"])
        self.assertEqual(applied["status"], "complete")
        self.assertTrue((data / "applications/ternuxx-proot-app-org.example.Editor.desktop").is_file())
        self.assertTrue((config / "menus/xfce-applications.menu").is_file())
        self.assertRegex(applied["rollback_id"], r"^[0-9a-f]{32}$")
        rollback_list = proot_shortcuts.list_desktop_application_sync_rollbacks(
            home=str(self.home), state_dir=str(self.home / ".local/share/ternuxx"))
        self.assertEqual(rollback_list["rollbacks"][0]["status"], "applied")
        rollback_preview = proot_shortcuts.preview_desktop_application_sync_rollback(
            applied["rollback_id"], home=str(self.home), state_dir=str(self.home / ".local/share/ternuxx"))
        self.assertTrue(rollback_preview["requires_confirmation"])
        rolled_back = proot_shortcuts.apply_desktop_application_sync_rollback(
            applied["rollback_id"], home=str(self.home), state_dir=str(self.home / ".local/share/ternuxx"),
            confirmed=True, plan_id=rollback_preview["plan_id"])
        self.assertEqual(rolled_back["status"], "complete")
        self.assertFalse((data / "applications/ternuxx-proot-app-org.example.Editor.desktop").exists())
        self.assertFalse((config / "menus/xfce-applications.menu").exists())
        self.assertEqual(proot_shortcuts.list_desktop_application_sync_rollbacks(
            home=str(self.home), state_dir=str(self.home / ".local/share/ternuxx"))["rollbacks"][0]["status"],
            "rolled_back")

    def test_bulk_sync_restores_prior_files_when_apply_fails_midway(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        apps = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        apps.mkdir(parents=True)
        (apps / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\\nType=Application\\nName=Editor\\nExec=/usr/bin/editor\\n")
        data = self.home / "xfce-data"
        config = self.home / "xfce-config"
        kwargs = {"home": str(self.home), "prefix": str(prefix), "repo_root": str(self.repo),
                  "xdg_data_home": str(data), "xdg_config_home": str(config)}
        plan = proot_shortcuts.preview_desktop_application_sync(**kwargs)
        menu = config / "menus/xfce-applications.menu"
        original_write = proot_shortcuts._atomic_write

        def fail_menu(path, payload):
            if Path(path) == menu:
                raise OSError("injected menu write failure")
            return original_write(path, payload)

        with patch.object(proot_shortcuts, "_atomic_write", side_effect=fail_menu):
            with self.assertRaisesRegex(OSError, "injected menu write failure"):
                proot_shortcuts.apply_desktop_application_sync(
                    **kwargs, confirmed=True, plan_id=plan["plan_id"])
        launcher = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        self.assertFalse(launcher.exists())
        self.assertFalse(menu.exists())

    def test_bulk_sync_preview_preserves_unmanaged_conflicts(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        apps = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        apps.mkdir(parents=True)
        self.make_guest_executable(prefix)
        (apps / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor\n")
        data = self.home / "xfce-data"
        target = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        target.parent.mkdir(parents=True)
        original = b"[Desktop Entry]\nName=Owner launcher\n"
        target.write_bytes(original)
        plan = proot_shortcuts.preview_desktop_application_sync(
            home=str(self.home), prefix=str(prefix), repo_root=str(self.repo),
            xdg_data_home=str(data), xdg_config_home=str(self.home / "xfce-config"))
        self.assertIn("ternuxx-proot-app-org.example.Editor.desktop", plan["conflicts"])
        self.assertNotIn(str(target.relative_to(self.home)), {change["path"] for change in plan["changes"]})
        self.assertEqual(target.read_bytes(), original)

    def test_desktop_app_catalog_reports_localization_executable_and_shortcut_ownership(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        rootfs = prefix / "var/lib/proot-distro/containers/debian/rootfs"
        apps = rootfs / "usr/share/applications"
        apps.mkdir(parents=True)
        self.make_guest_executable(prefix)
        entry = apps / "org.example.Editor.desktop"
        entry.write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nName[bn]=সম্পাদক\n"
            "Comment=Edit documents\nCategories=Utility;TextEditor;\n"
            "Exec=/usr/bin/editor %f\nTryExec=editor\nIcon=editor-icon\n")
        data = self.home / "xfce-data"
        inventory = proot_shortcuts.inspect_desktop_apps(prefix=str(prefix))
        item = inventory["items"][0]
        self.assertEqual(inventory["status"], "available")
        self.assertEqual(item["desktop_id"], "org.example.Editor.desktop")
        self.assertEqual(item["localized_names"]["bn"], "সম্পাদক")
        self.assertEqual(item["categories"], ["Utility", "TextEditor"])
        self.assertTrue(item["executable_available"])
        self.assertEqual(proot_shortcuts.discover_desktop_apps(prefix=str(prefix))[0]["desktop_id"],
                         "org.example.Editor.desktop")

        listed = proot_shortcuts.list_shortcuts(
            home=str(self.home), prefix=str(prefix), repo_root=str(self.repo),
            xdg_data_home=str(data))
        dynamic = listed["desktop_applications"]["items"][0]
        self.assertEqual(dynamic["shortcut_state"], "absent")
        launcher = data / "applications/ternuxx-proot-app-org.example.Editor.desktop"
        launcher.parent.mkdir(parents=True)
        launcher.write_bytes(proot_shortcuts._dynamic_entry(
            dynamic["desktop_id"], dynamic, cli=str(self.repo / "tx")))
        installed = proot_shortcuts.list_shortcuts(
            home=str(self.home), prefix=str(prefix), repo_root=str(self.repo),
            xdg_data_home=str(data))["desktop_applications"]["items"][0]
        self.assertEqual(installed["shortcut_state"], "installed")
        launcher.write_text(launcher.read_text() + "# local edit\n")
        modified = proot_shortcuts.list_shortcuts(
            home=str(self.home), prefix=str(prefix), repo_root=str(self.repo),
            xdg_data_home=str(data))["desktop_applications"]["items"][0]
        self.assertEqual(modified["shortcut_state"], "modified")

    def test_discovery_explains_unavailable_and_unsafe_desktop_entries(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        apps = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        apps.mkdir(parents=True)
        (apps / "missing.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Missing\n"
            "Exec=/usr/bin/missing\nTryExec=missing\n")
        (apps / "unsafe.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Unsafe\nExec=sh -c false\n")
        (apps / "hidden.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Hidden\nExec=missing\nHidden=true\n")
        inventory = proot_shortcuts.inspect_desktop_apps(prefix=str(prefix))
        states = {item["desktop_id"]: item["status"] for item in inventory["items"]}
        self.assertEqual(states["missing.desktop"], "unavailable")
        self.assertIn("missing.desktop", {item["desktop_id"] for item in inventory["items"]})
        diagnostics = {item["desktop_id"]: item for item in inventory["diagnostics"]}
        self.assertEqual(diagnostics["unsafe.desktop"]["status"], "unsupported")
        self.assertIn("interpreter", diagnostics["unsafe.desktop"]["reason"])
        self.assertEqual(diagnostics["hidden.desktop"]["status"], "hidden")
        self.assertEqual(proot_shortcuts.discover_desktop_apps(prefix=str(prefix)), [])

    def test_dynamic_launch_reads_desktop_exec_without_shell(self) -> None:
        prefix = Path(self.temp.name) / "termux"
        apps = prefix / "var/lib/proot-distro/containers/debian/rootfs/usr/share/applications"
        apps.mkdir(parents=True)
        (apps / "org.example.Editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\nExec=/usr/bin/editor --title=\"My Editor\" %f\n")
        with patch.object(proot_shortcuts.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()) as run:
            proot_shortcuts.launch_desktop_application(
                "org.example.Editor.desktop", prefix=str(prefix), repo_root=str(self.repo),
                env={"DISPLAY": ":1"}, display=":1",
            )
        self.assertEqual(run.call_args.args[0][-2:], ["/usr/bin/editor", "--title=My Editor"])
        (apps / "unsafe.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Unsafe\nExec=sh -c 'false'\n")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "interpreter command"):
            proot_shortcuts.launch_desktop_application(
                "unsafe.desktop", prefix=str(prefix), repo_root=str(self.repo), env={})
        (apps / "wrapped-unsafe.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Wrapped\nExec=env sh -c 'false'\n")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "interpreter command"):
            proot_shortcuts.launch_desktop_application(
                "wrapped-unsafe.desktop", prefix=str(prefix), repo_root=str(self.repo), env={})
        (apps / "xfce4-session-logout.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Log out\nExec=xfce4-session-logout\n")
        with self.assertRaisesRegex(proot_shortcuts.ShortcutError, "allowed visible"):
            proot_shortcuts.launch_desktop_application(
                "xfce4-session-logout.desktop", prefix=str(prefix), repo_root=str(self.repo), env={})


if __name__ == "__main__":
    unittest.main()
