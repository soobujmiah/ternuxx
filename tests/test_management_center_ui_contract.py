from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "apps/management-center/management-center.c").read_text()
BRIDGE = (ROOT / "scripts/management_desktop_bridge.py").read_text()


class ManagementCenterNativeUiContractTests(unittest.TestCase):
    def test_gtk_client_exposes_guest_status_and_broker_terminal_without_arbitrary_shell(self):
        self.assertIn("proot.debian.workloads", SOURCE)
        self.assertIn("proot-status", SOURCE)
        self.assertIn("Launch Debian app", SOURCE)
        self.assertIn("Preview shortcut add", SOURCE)
        self.assertIn("Preview shortcut remove", SOURCE)
        self.assertIn("Preview session stop", SOURCE)
        self.assertIn("Inspect/reconcile exited session", SOURCE)
        self.assertIn('g_regex_match_simple("^plan-[0-9a-f]{64}$", f[1], 0, 0)', SOURCE)
        self.assertIn("proot.recovery.reconcile.preview", BRIDGE)
        self.assertIn("Ternuxx-owned session ID (proot-…)", SOURCE)
        self.assertIn("proot-session-list", SOURCE)
        for contract in ("proot.interactive-terminal-broker", "terminal-service-prepare",
                         "terminal-service-apply", "vte_terminal_spawn_async",
                         '"terminal", "start"', "closing this window also detaches"):
            with self.subTest(contract=contract):
                self.assertIn(contract.lower(), SOURCE.lower())
        for unsafe in ("/bin/sh", "terminal_cli"):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, SOURCE)

    def test_native_desktop_selector_is_exposed_in_gtk(self):
        for contract in ("desktop_choice", "XFCE (default)", "KDE Plasma", "start-desktop", "desktop_id"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)
        self.assertIn("start-desktop", BRIDGE)

    def test_gtk_managed_guest_desktop_picker_is_a_multi_select_checkbox_group(self):
        for contract in ("proot_desktop_checks[7]", "gtk_check_button_new_with_label",
                         "gtk_check_button_get_active", "Desktop environments (select one or more)",
                         '"install", "debian", "--desktops", desktops->str'):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)
        self.assertNotIn("proot_desktop_entry", SOURCE)

    def test_review_instance_remains_available(self):
        self.assertIn('g_strcmp0(argv[1], "--review") == 0', SOURCE)
        self.assertIn('"dev.ternuxx.management-center.review"', SOURCE)

    def test_native_cpu_inference_controls_share_model_preview_and_stdin_prompt(self):
        for contract in ("cpu-model-preview", "cpu-model-apply", "run_bridge_input",
                         "G_SUBPROCESS_FLAGS_STDIN_PIPE", "inference.cpu.local"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_native_vulkan_inference_has_explicit_status_and_run_controls(self):
        for contract in ("inference.gpu.local", "ai_gpu_status_button", "gpu-status",
                         "ai_gpu_run_button", "gpu-run", "Run on Vulkan",
                         "verified GPU-layer offload", "CPU fallback is disabled", "gpu-device-entry",
                         "Exact ID from List Vulkan inference devices"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_native_hexagon_inference_has_preview_confirmation_status_and_explicit_run(self):
        for contract in ("inference.npu.local", "ai_npu_status_button", "npu-status",
                         "npu-runtime-preview", "npu-runtime-apply", "Type INSTALL exactly",
                         "ai_npu_run_button", "npu-run", "CPU fallback is disabled"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE + BRIDGE)

    def test_graphics_selection_warns_about_experimental_candidate_and_future_scope(self):
        self.assertIn("KGSL option is experimental", SOURCE)
        self.assertIn("must already be extracted", SOURCE)
        self.assertIn("Ternuxx does not install it", SOURCE)
        self.assertIn("Experimental KGSL (already present)", SOURCE)

    def test_gtk_termux_boot_cron_has_exact_preview_confirmation_controls(self):
        for contract in ("boot.termux.cron", "Manage Termux:Boot Cron startup",
                         "boot-cron-status", "boot-cron-validate", "boot-cron-preview",
                         "boot-cron-apply", "^[0-9a-f]{64}$", "Apply exact change"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE + BRIDGE)

    def test_gtk_boot_helpers_selects_exact_helper_and_rollback_snapshot(self):
        for contract in ("boot-helpers-status", "boot-helpers-snapshots", "boot-helpers-preview",
                         "boot-helpers-apply", "boot_helpers_button", "Select the exact rollback snapshot",
                         "Review the exact boot-helper target, contents, and hashes"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE + BRIDGE)

    def test_curated_native_app_client_uses_saved_preview_and_exact_confirmation(self):
        for contract in ("software.curated-apps", "software-preview", "software-apply",
                         "software-run", "HOME-relative file or directory path",
                         "^[0-9a-f]{64}$", "Review exact Native Termux APT transaction",
                         "Browse Native Termux apps"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_gtk_cron_update_form_supports_name_and_enabled_fields(self):
        for contract in ('cron-update-field', '"name"', '"enabled"',
                         'g_strcmp0(name_value, "true")', 'g_strcmp0(name_value, "false")',
                         'run_bridge(c, "cron-preview", "update", job_id, field_value, name_value, NULL)'):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_gtk_cron_create_supports_every_schedule_type_via_typed_bridge(self):
        for contract in ("cron-schedule-type", "cron-schedule-extra", "cron-timezone",
                         'g_strcmp0(type_value, "cron")', 'g_strcmp0(type_value, "interval")',
                         'g_strcmp0(type_value, "calendar")', 'g_strcmp0(type_value, "one_time")',
                         'run_bridge_full(c, "cron-preview", "create"',
                         '"Optional IANA timezone for cron/daily; blank uses preference"',
                         '"Cron expression, interval seconds, HH:MM or ISO datetime"'):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_gtk_cron_read_details_use_typed_bridge_references(self):
        for contract in ("cron_target_entry", "Inspect saved job", "Preview next five runs",
                         "Inspect execution record", "inspect_cron_reference", "cron-inspect-kind"):
            self.assertIn(contract, SOURCE)
        for contract in ('action == "cron-inspect" and len(argv) == 3', 'job-[0-9a-f]{32}',
                         'exec-[0-9a-f]{32}', '"cron.jobs.next_runs"'):
            self.assertIn(contract, BRIDGE)

    def test_gtk_recovery_create_and_restore_use_confirmed_plan_dialogs(self):
        for contract in ("backup-create-preview", "backup-create-apply", "restore-apply-preview",
                         "restore-apply", "recovery-resolve-preview", "recovery-resolve-apply",
                         "recovery-rollback-apply-preview", "recovery-rollback-apply", "ask_recovery_confirmation",
                         "Create backup from name above", "Restore from backup ID above", "Apply restore rollback",
                         "Reconcile unresolved operation", "Review this exact %s plan"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)
        for contract in ('action == "backup-create-preview"', 'action == "backup-create-apply"',
                         'action in {"restore-apply-preview", "restore-apply"}',
                         'recovery_preview_actions = {"recovery-resolve-preview"',
                         'action in {"recovery-resolve-apply", "recovery-rollback-apply"}'):
            with self.subTest(contract=contract):
                self.assertIn(contract, BRIDGE)

    def test_gtk_recovery_controls_are_read_only_and_bridge_ids_are_typed(self):
        for contract in ("List verified configuration backups", "Preview restore (read-only)",
                         "Preview restore rollback (read-only)", "inspect_recovery_reference",
                         "recovery_target_entry", "recovery-action"):
            self.assertIn(contract, SOURCE)
        for contract in ('action in {"recovery-status", "backup-list", "continuity-status"}',
                         '"restore-preview"', '"recovery-rollback-preview"',
                         '"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"'):
            self.assertIn(contract, BRIDGE)

    def test_gtk_reboot_qualification_uses_shared_preview_and_apply_actions(self):
        for contract in ("reboot_test_prepare_button", "reboot_test_verify_button",
                         "Prepare reboot qualification", "Verify reboot qualification",
                         "reboot-test-prepare-preview", "reboot-test-verify-preview",
                         "reboot-test-prepare-apply", "reboot-test-verify-apply",
                         "private NOT_READY evidence record", "does not reboot"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE + BRIDGE)
        for contract in ('"continuity.prepare-reboot-test.preview"',
                         '"continuity.verify-reboot-test.preview"',
                         '"continuity.prepare-reboot-test"', '"continuity.verify-reboot-test"'):
            with self.subTest(operation=contract):
                self.assertIn(contract, BRIDGE)

    def test_cron_scheduler_controls_use_explicit_confirmation_and_shared_bridge(self):
        for contract in ("cron_start_button", "cron_stop_button", "ask_cron_scheduler_confirmation",
                         "cron-scheduler-start", "cron-scheduler-stop", '"cron-scheduler", "start", "10"',
                         '"cron-scheduler", "stop"'):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)

    def test_catalog_is_the_source_for_visible_resources(self):
        self.assertIn('script, "catalog", NULL', SOURCE)
        self.assertIn('Connected to Native Termux shared management service', SOURCE)

    def test_gtk_proot_shortcut_sync_and_rollback_are_preview_confirmed(self):
        for contract in ("Preview app and desktop shortcut synchronization", "List prior shortcut syncs",
                         "Preview shortcut sync restore", "proot-shortcut-sync-preview",
                         "proot-shortcut-rollback-preview", "proot-shortcut-sync-apply",
                         "proot-shortcut-rollback-apply"):
            self.assertIn(contract, SOURCE)
        for contract in ('action == "proot-shortcut-sync-preview"',
                         'action == "proot-shortcut-rollback-preview"',
                         'action == "proot-shortcut-sync-apply"',
                         'action == "proot-shortcut-rollback-apply"'):
            self.assertIn(contract, BRIDGE)

    def test_gtk_proot_setup_launches_guided_installer_with_desktop_selection(self):
        self.assertIn("Install managed Debian", SOURCE)
        self.assertIn("proot_desktop_checks[7]", SOURCE)
        self.assertIn("gtk_check_button_get_active", SOURCE)
        self.assertIn('"install", "debian", "--desktops", desktops->str', SOURCE)
        self.assertIn("Existing guests are preserved", SOURCE)

    def test_gtk_replay_guest_retirement_and_restore_use_inline_exact_plan_review(self):
        for contract in ("proot.replay-guests", "Preview replay guest retirement",
                         "Preview replay guest restore", "proot_replay_review_box",
                         "proot_replay_cancel_button", "proot_replay_apply_button",
                         "No guest files are deleted", 'g_strcmp0(c->selected_resource_id, "proot.replay-guests")'):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)
        for contract in ('action == "proot-replay-retire-preview"',
                         'action == "proot-replay-restore-preview"',
                         '"proot-replay-retire-apply"', '"proot-replay-restore-apply"',
                         '"proot.setup.retire.preview"', '"proot.setup.restore.preview"'):
            with self.subTest(contract=contract):
                self.assertIn(contract, BRIDGE)

    def test_gtk_ssh_definition_deploy_and_rollback_use_exact_preview_plans(self):
        for contract in ("ssh_deploy_button", "ssh_deploy_rollback_button",
                         "Review and deploy SSH service definition",
                         "Restore previous SSH service definition",
                         "ssh-deploy-preview", "ssh-deploy-apply",
                         "ssh-deploy-rollback-list", "ssh-deploy-rollback-preview",
                         "ssh-deploy-rollback-apply", "^[0-9a-f]{64}$",
                         "The current sshd process will keep running"):
            with self.subTest(contract=contract):
                self.assertIn(contract, SOURCE)
        for contract in ('action == "ssh-deploy-preview"',
                         'action == "ssh-deploy-apply"',
                         'action == "ssh-deploy-rollback-list"',
                         'action == "ssh-deploy-rollback-preview"',
                         'action == "ssh-deploy-rollback-apply"',
                         '"ssh.service.deploy.rollback.apply"'):
            with self.subTest(contract=contract):
                self.assertIn(contract, BRIDGE)


if __name__ == "__main__":
    unittest.main()
