#include <gtk/gtk.h>
#include <vte/vte.h>
#include <string.h>

typedef struct { gchar *id, *category, *name, *status, *availability, *description, *operations; } Resource;
typedef struct { gchar *id, *name, *routes; } InstallDesktop;
typedef struct { gchar *alias, *label; GPtrArray *desktops; } InstallProfile;
typedef struct { GtkWidget *window, *category_list, *resource_list, *details, *notice, *search, *action_scroll;
                 GtkWidget *desktop_choice, *start_button, *stop_button, *ssh_restart_button, *ssh_keys_button, *ssh_enroll_button, *ssh_revoke_button, *ssh_rollback_button, *ssh_generate_button, *ssh_autostart_button, *ssh_deploy_button, *ssh_deploy_rollback_button, *ssh_wakelock_button, *boot_cron_button, *boot_helpers_button, *graphics_select_button, *graphics_api_button, *history_button, *logs_button, *audit_logs_button, *desktop_log_button, *cron_button, *cron_history_button, *cron_manage_button, *cron_start_button, *cron_stop_button, *cron_target_entry, *cron_inspect_button, *cron_next_button, *cron_execution_button, *recovery_target_entry, *backup_list_button, *recovery_status_button, *continuity_status_button, *continuity_prepare_button, *continuity_verify_button, *reboot_test_prepare_button, *reboot_test_verify_button, *backup_inspect_button, *restore_preview_button, *backup_create_button, *restore_apply_button, *operation_inspect_button, *rollback_preview_button, *rollback_apply_button, *recovery_resolve_button, *timezone_set_button, *software_button, *ai_model_install_button, *ai_model_remove_button, *ai_run_button, *ai_auto_run_button, *ai_gpu_status_button, *ai_gpu_run_button, *ai_npu_status_button, *ai_npu_install_button, *ai_npu_run_button, *terminal_service_button, *terminal_open_button, *monitor_box, *monitor_enabled,
                 *monitor_interval, *monitor_unit, *monitor_focus, *monitor_launch,
                 *proot_box, *proot_help, *proot_setup_help, *proot_setup_button, *proot_desktop_box, *proot_distro, *proot_app_entry, *proot_shortcut_entry, *proot_sync_rollback_entry, *proot_session_entry,
                 *proot_replay_alias_entry, *proot_replay_backup_entry, *proot_replay_retire_button,
                 *proot_replay_restore_button, *proot_replay_review_box, *proot_replay_review_label,
                 *proot_replay_apply_button, *proot_replay_cancel_button,
                 *proot_app_button, *proot_shortcut_list_button, *proot_shortcut_add_button,
                 *proot_shortcut_remove_button, *proot_shortcut_sync_button, *proot_shortcut_rollback_list_button,
                 *proot_shortcut_rollback_preview_button, *proot_session_stop_button, *proot_session_reconcile_button; GPtrArray *proot_desktop_checks, *install_profiles, *categories,
                 *resources; gchar *selected_category, *selected_resource_id, *replay_review_action,
                 *replay_review_alias, *replay_review_backup, *replay_review_plan; guint category_count; } Center;
typedef struct { Center *center; gchar *action; gchar *resource_id; gchar *detail_id; gchar *plan_id; gchar *extra_id; } Request;
typedef struct { Center *center; GPtrArray *ids; GPtrArray *labels; gchar *helper_id; } BootHelperChoice;
static Center *app_center;
static void run_bridge(Center *c, const gchar *action, const gchar *arg1, const gchar *arg2,
                       const gchar *arg3, const gchar *arg4, const gchar *arg5);
static void run_bridge_full(Center *c, const gchar *action, const gchar *arg1, const gchar *arg2,
                            const gchar *arg3, const gchar *arg4, const gchar *arg5,
                            const gchar *arg6, const gchar *arg7);
static void ask_ssh_confirmation(Center *c, const gchar *preview_action, const gchar *plan_id, const gchar *impact);
static void ask_ssh_rollback_confirmation(Center *c, const gchar *rollback_id, const gchar *plan_id, const gchar *effect);
static void ask_ssh_deploy_confirmation(Center *c, const gchar *plan_id, const gchar *summary);
static void ask_ssh_deploy_rollback_confirmation(Center *c, const gchar *operation_id, const gchar *plan_id, const gchar *summary);
static void ssh_deploy_rollback_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void choose_graphics_api(GtkButton *button, gpointer data);
static void ask_terminal_service_confirmation(Center *c, const gchar *plan_id, const gchar *action, const gchar *impact);
static void open_debian_terminal(GtkButton *button, gpointer data);
static void open_debian_setup(GtkButton *button, gpointer data);
static void ask_shortcut_confirmation(Center *c, const gchar *action, const gchar *app_id, const gchar *plan_id, const gchar *target, const gchar *transition);
static void proot_app_clicked(GtkButton *button, gpointer data);
static void proot_shortcut_list_clicked(GtkButton *button, gpointer data);
static void proot_shortcut_clicked(GtkButton *button, gpointer data);
static void proot_shortcut_sync_clicked(GtkButton *button, gpointer data);
static void proot_shortcut_rollback_list_clicked(GtkButton *button, gpointer data);
static void proot_shortcut_rollback_preview_clicked(GtkButton *button, gpointer data);
static void proot_session_stop_clicked(GtkButton *button, gpointer data);
static void proot_replay_retire_clicked(GtkButton *button, gpointer data);
static void proot_replay_restore_clicked(GtkButton *button, gpointer data);
static void proot_replay_apply_clicked(GtkButton *button, gpointer data);
static void proot_replay_cancel_clicked(GtkButton *button, gpointer data);
static void clear_replay_review(Center *c);
static void ask_proot_confirmation(Center *c, const gchar *action, const gchar *resource_id,
                                   const gchar *detail_id, const gchar *plan_id, const gchar *summary);
static void ask_cron_confirmation(Center *c, const gchar *plan_id, const gchar *summary);
static void ask_cron_scheduler_confirmation(Center *c, gboolean start);
static void confirmed_action(GObject *source, GAsyncResult *result, gpointer user_data);
static void install_profile_changed(GObject *object, GParamSpec *pspec, gpointer user_data);
static void ask_recovery_confirmation(Center *c, const gchar *action, const gchar *resource_id, const gchar *plan_id, const gchar *summary);
static void ask_cpu_model_confirmation(Center *c, const gchar *action, const gchar *plan_id, const gchar *summary);
static void show_npu_install_confirmation(Center *c, const gchar *plan_id, const gchar *summary);
static void show_management_log(GtkButton *button, gpointer data);
static void show_ssh_keys(GtkButton *button, gpointer data);
static void enroll_ssh_key(GtkButton *button, gpointer data);
static void revoke_ssh_key(GtkButton *button, gpointer data);
static void restore_ssh_key(GtkButton *button, gpointer data);
static void ssh_rollback_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void generate_ssh_key(GtkButton *button, gpointer data);
static void ssh_client_key_preview(GtkButton *button, gpointer data);
static void ask_ssh_client_key_confirmation(Center *c, const gchar *name, const gchar *plan_id, const gchar *path, const gchar *impact);
static void change_ssh_autostart(GtkButton *button, gpointer data);
static void deploy_ssh_definition(GtkButton *button, gpointer data);
static void rollback_ssh_definition(GtkButton *button, gpointer data);
static void change_ssh_wakelock(GtkButton *button, gpointer data);
static void manage_boot_cron(GtkButton *button, gpointer data);
static void boot_cron_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void manage_boot_helpers(GtkButton *button, gpointer data);
static void boot_helpers_name_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void boot_helpers_action_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void boot_helpers_snapshot_choice(GObject *source, GAsyncResult *result, gpointer user_data);
static void ask_ssh_wakelock_confirmation(Center *c, const gchar *enabled, const gchar *plan_id, const gchar *effect);
static void change_ssh_wakelock(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-wakelock-status", NULL, NULL, NULL, NULL, NULL);
}
static void boot_cron_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    Center *c = user_data; GError *error = NULL;
    gint choice = gtk_alert_dialog_choose_finish(GTK_ALERT_DIALOG(source), result, &error);
    if (error) { gtk_label_set_text(GTK_LABEL(c->notice), error->message); g_clear_error(&error); return; }
    if (choice == 0) run_bridge(c, "boot-cron-status", NULL, NULL, NULL, NULL, NULL);
    else if (choice == 1) run_bridge(c, "boot-cron-validate", NULL, NULL, NULL, NULL, NULL);
    else if (choice == 2) run_bridge(c, "boot-cron-preview", "enable", NULL, NULL, NULL, NULL);
    else if (choice == 3) run_bridge(c, "boot-cron-preview", "disable", NULL, NULL, NULL, NULL);
}
static void manage_boot_cron(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const char *choices[] = {"Check status", "Validate setup", "Enable at boot…", "Disable at boot…", "Cancel", NULL};
    GtkAlertDialog *dialog = gtk_alert_dialog_new("Termux:Boot Cron startup");
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 4);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, boot_cron_choice, c);
    g_object_unref(dialog);
}
static void boot_helper_choice_free(BootHelperChoice *choice) {
    if (!choice) return;
    if (choice->ids) g_ptr_array_unref(choice->ids);
    if (choice->labels) g_ptr_array_unref(choice->labels);
    g_free(choice->helper_id); g_free(choice);
}
static void boot_helpers_snapshot_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    BootHelperChoice *choice = user_data; GError *error = NULL;
    gint selected = gtk_alert_dialog_choose_finish(GTK_ALERT_DIALOG(source), result, &error);
    if (error) { gtk_label_set_text(GTK_LABEL(choice->center->notice), error->message); g_clear_error(&error); }
    else if (selected >= 0 && (guint)selected < choice->ids->len)
        run_bridge_full(choice->center, "boot-helpers-preview", choice->helper_id, "rollback",
                        g_ptr_array_index(choice->ids, (guint)selected), NULL, NULL, NULL, NULL);
    boot_helper_choice_free(choice);
}
static void boot_helpers_action_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    BootHelperChoice *choice = user_data; GError *error = NULL;
    gint selected = gtk_alert_dialog_choose_finish(GTK_ALERT_DIALOG(source), result, &error);
    if (error) { gtk_label_set_text(GTK_LABEL(choice->center->notice), error->message); g_clear_error(&error); }
    else if (selected == 0)
        run_bridge_full(choice->center, "boot-helpers-preview", choice->helper_id, "deploy", "-", NULL, NULL, NULL, NULL);
    else if (selected == 1)
        run_bridge(choice->center, "boot-helpers-snapshots", choice->helper_id, NULL, NULL, NULL, NULL);
    boot_helper_choice_free(choice);
}
static void boot_helpers_name_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    BootHelperChoice *choice = user_data; GError *error = NULL;
    gint selected = gtk_alert_dialog_choose_finish(GTK_ALERT_DIALOG(source), result, &error);
    if (error) { gtk_label_set_text(GTK_LABEL(choice->center->notice), error->message); g_clear_error(&error); }
    else if (selected >= 0 && (guint)selected < choice->ids->len) {
        choice->helper_id = g_strdup(g_ptr_array_index(choice->ids, (guint)selected));
        gchar *title = g_strdup_printf("Manage the %s boot helper", choice->helper_id);
        GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", title);
        const char *actions[] = {"Deploy current repository version…", "Roll back to a saved snapshot…", "Cancel", NULL};
        gtk_alert_dialog_set_buttons(dialog, actions); gtk_alert_dialog_set_default_button(dialog, 2);
        gtk_alert_dialog_choose(dialog, GTK_WINDOW(choice->center->window), NULL, boot_helpers_action_choice, choice);
        g_object_unref(dialog); g_free(title); return;
    }
    boot_helper_choice_free(choice);
}
static void manage_boot_helpers(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "boot-helpers-status", NULL, NULL, NULL, NULL, NULL);
}
static void ask_ssh_wakelock_confirmation(Center *c, const gchar *enabled,
                                          const gchar *plan_id, const gchar *effect) {
    gboolean desired = g_strcmp0(enabled, "true") == 0;
    gchar *message = g_strdup_printf("%s the managed SSH keep-awake preference?\n\n%s\n\nThe current SSH process and Wake Lock lease will remain unchanged.",
        desired ? "Enable" : "Disable", effect);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", desired ? "Keep SSH awake" : "Do not keep SSH awake", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-wakelock-apply"); request->resource_id = g_strdup(enabled);
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing managed SSH Wake Lock preference");
    g_object_unref(dialog); g_free(message);
}

static void ask_ssh_autostart_confirmation(Center *c, const gchar *enabled, const gchar *plan_id, const gchar *effect);
static void ask_ssh_key_confirmation(Center *c, const gchar *action, const gchar *subject, const gchar *plan_id, const gchar *fingerprint);
static void show_cron_log(GtkButton *button, gpointer data);
static void show_desktop_log(GtkButton *button, gpointer data);
static gchar *python_path(void);

static gchar *bridge_path(void) {
    const gchar *root = g_getenv("TERNUXX_CHECKOUT");
    if (!root || !*root) return NULL;
    return g_build_filename(root, "scripts", "management_desktop_bridge.py", NULL);
}
static gchar *python_path(void) {
    const gchar *prefix = g_getenv("PREFIX");
    return g_build_filename(prefix && *prefix ? prefix : "/data/data/com.termux/files/usr", "bin", "python", NULL);
}
static void set_text(Center *c, const gchar *text) {
    GtkTextBuffer *buffer = gtk_text_view_get_buffer(GTK_TEXT_VIEW(c->details));
    gtk_text_buffer_set_text(buffer, text ? text : "", -1);
}
static void clear_replay_review(Center *c) {
    g_clear_pointer(&c->replay_review_action, g_free);
    g_clear_pointer(&c->replay_review_alias, g_free);
    g_clear_pointer(&c->replay_review_backup, g_free);
    g_clear_pointer(&c->replay_review_plan, g_free);
    if (c->proot_replay_review_box) gtk_widget_set_visible(c->proot_replay_review_box, FALSE);
}
static void show_replay_review(Center *c, const gchar *action, const gchar *alias,
                               const gchar *backup_id, const gchar *plan_id, const gchar *impact) {
    clear_replay_review(c);
    c->replay_review_action = g_strdup(action);
    c->replay_review_alias = g_strdup(alias);
    c->replay_review_backup = g_strdup(backup_id);
    c->replay_review_plan = g_strdup(plan_id);
    gchar *summary = g_strdup_printf("Review exact replay guest: %s\nPlan: %.16s…\nBackup ID: %s\n\n%s\n\n%s",
        alias, plan_id, backup_id ? backup_id : "not applicable", impact,
        g_strcmp0(action, "proot-replay-retire-apply") == 0
            ? "This moves the same guest directory into private Ternuxx state. No guest files are deleted."
            : "This restores the same guest directory to the exact alias.");
    gtk_label_set_text(GTK_LABEL(c->proot_replay_review_label), summary);
    gtk_button_set_label(GTK_BUTTON(c->proot_replay_apply_button),
        g_strcmp0(action, "proot-replay-retire-apply") == 0 ? "Retire this replay guest" : "Restore this replay guest");
    gtk_widget_set_visible(c->proot_replay_review_box, TRUE);
    gtk_label_set_text(GTK_LABEL(c->notice), "Review the exact replay guest plan; Cancel remains available.");
    g_free(summary);
}
static void install_desktop_free(gpointer data) {
    InstallDesktop *desktop = data; if (!desktop) return;
    g_free(desktop->id); g_free(desktop->name); g_free(desktop->routes); g_free(desktop);
}
static void install_profile_free(gpointer data) {
    InstallProfile *profile = data; if (!profile) return;
    g_free(profile->alias); g_free(profile->label);
    if (profile->desktops) g_ptr_array_unref(profile->desktops);
    g_free(profile);
}
static void install_profile_changed(GObject *object, GParamSpec *pspec, gpointer user_data) {
    (void)object; (void)pspec; Center *c = user_data;
    GtkWidget *note = gtk_widget_get_next_sibling(c->proot_distro);
    if (!note) return;
    GtkWidget *child = gtk_widget_get_next_sibling(note);
    while (child) {
        GtkWidget *next = gtk_widget_get_next_sibling(child);
        gtk_box_remove(GTK_BOX(c->proot_desktop_box), child); child = next;
    }
    g_ptr_array_set_size(c->proot_desktop_checks, 0);
    guint selected = gtk_drop_down_get_selected(GTK_DROP_DOWN(c->proot_distro));
    if (!c->install_profiles || selected >= c->install_profiles->len) return;
    InstallProfile *profile = g_ptr_array_index(c->install_profiles, selected);
    for (guint i = 0; i < profile->desktops->len; i++) {
        InstallDesktop *desktop = g_ptr_array_index(profile->desktops, i);
        gchar *label = g_strcmp0(desktop->routes, "unverified") == 0
            ? g_strdup_printf("%s (launch route unverified)", desktop->name)
            : g_strdup_printf("%s (%s)", desktop->name, desktop->routes);
        GtkWidget *check = gtk_check_button_new_with_label(label); g_free(label);
        g_object_set_data_full(G_OBJECT(check), "install-desktop-id", g_strdup(desktop->id), g_free);
        gtk_check_button_set_active(GTK_CHECK_BUTTON(check), i == 0);
        gtk_box_append(GTK_BOX(c->proot_desktop_box), check);
        g_ptr_array_add(c->proot_desktop_checks, check);
    }
    gtk_widget_set_sensitive(c->proot_setup_button, profile->desktops->len > 0);
}
static void load_install_catalog(Center *c, const gchar *output) {
    GPtrArray *profiles = g_ptr_array_new_with_free_func(install_profile_free);
    gchar **lines = g_strsplit(output ? output : "", "\n", -1);
    gboolean valid = TRUE;
    for (guint i = 0; lines[i] && valid; i++) {
        gchar **f = g_strsplit(lines[i], "\t", 6);
        if (g_strcmp0(f[0], "D") == 0 && f[1] && f[2]
                && g_regex_match_simple("^[a-z0-9][a-z0-9-]{0,31}$", f[1], 0, 0)) {
            InstallProfile *profile = g_new0(InstallProfile, 1);
            profile->alias = g_strdup(f[1]); profile->label = g_strdup(f[2]);
            profile->desktops = g_ptr_array_new_with_free_func(install_desktop_free);
            g_ptr_array_add(profiles, profile);
        } else if (g_strcmp0(f[0], "E") == 0 && f[1] && f[2] && f[3] && f[4]
                && g_regex_match_simple("^[a-z0-9][a-z0-9-]{0,31}$", f[2], 0, 0)) {
            InstallProfile *profile = NULL;
            for (guint j = 0; j < profiles->len; j++) {
                InstallProfile *candidate = g_ptr_array_index(profiles, j);
                if (g_strcmp0(candidate->alias, f[1]) == 0) { profile = candidate; break; }
            }
            if (!profile) valid = FALSE;
            else {
                InstallDesktop *desktop = g_new0(InstallDesktop, 1);
                desktop->id = g_strdup(f[2]); desktop->name = g_strdup(f[3]); desktop->routes = g_strdup(f[4]);
                g_ptr_array_add(profile->desktops, desktop);
            }
        } else if (*lines[i]) valid = FALSE;
        g_strfreev(f);
    }
    g_strfreev(lines);
    if (!valid || !profiles->len) {
        gtk_widget_set_sensitive(c->proot_distro, FALSE);
        gtk_widget_set_sensitive(c->proot_setup_button, FALSE);
        gtk_label_set_text(GTK_LABEL(c->notice), "Managed distro catalog failed validation; installation choices are disabled.");
        g_ptr_array_unref(profiles); return;
    }
    if (c->install_profiles) g_ptr_array_unref(c->install_profiles);
    c->install_profiles = profiles;
    GtkStringList *model = gtk_string_list_new(NULL);
    for (guint i = 0; i < profiles->len; i++) {
        InstallProfile *profile = g_ptr_array_index(profiles, i);
        gtk_string_list_append(model, profile->label);
    }
    gtk_drop_down_set_model(GTK_DROP_DOWN(c->proot_distro), G_LIST_MODEL(model));
    g_object_unref(model);
    gtk_drop_down_set_selected(GTK_DROP_DOWN(c->proot_distro), 0);
    gtk_widget_set_sensitive(c->proot_distro, TRUE);
    install_profile_changed(G_OBJECT(c->proot_distro), NULL, c);
    gtk_label_set_text(GTK_LABEL(c->notice), "Managed distro and desktop choices loaded from the verified profile catalog.");
}

static void request_done(GObject *source, GAsyncResult *result, gpointer user_data) {
    Request *request = user_data; Center *c = request->center; GError *error = NULL;
    gchar *stdout_text = NULL, *stderr_text = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(G_SUBPROCESS(source), result,
        &stdout_text, &stderr_text, &error);
    if (g_strcmp0(request->action, "inspect") == 0
            && g_strcmp0(request->resource_id, c->selected_resource_id) != 0) {
        g_clear_error(&error);
        g_free(stdout_text); g_free(stderr_text);
        g_free(request->action); g_free(request->resource_id);
        g_free(request->detail_id); g_free(request->plan_id); g_free(request->extra_id); g_free(request);
        return;
    }
    if (!ok) {
        gtk_label_set_text(GTK_LABEL(c->notice), error ? error->message : "Request failed");
        g_clear_error(&error);
    } else {
        gboolean success = g_subprocess_get_successful(G_SUBPROCESS(source));
        if (g_strcmp0(request->action, "proot-install-catalog") == 0) {
            if (success && stdout_text) load_install_catalog(c, stdout_text);
            else {
                gtk_widget_set_sensitive(c->proot_distro, FALSE);
                gtk_widget_set_sensitive(c->proot_setup_button, FALSE);
                gtk_label_set_text(GTK_LABEL(c->notice), "Managed distro catalog is unavailable; installation choices are disabled.");
            }
        } else if ((g_strcmp0(request->action, "proot-replay-retire-preview") == 0
                    || g_strcmp0(request->action, "proot-replay-restore-preview") == 0)
                && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gboolean restore = g_strcmp0(request->action, "proot-replay-restore-preview") == 0;
            gchar **f = g_strsplit(stdout_text, "\t", restore ? 5 : 4);
            gboolean valid = g_strcmp0(c->selected_resource_id, "proot.replay-guests") == 0
                && f[1] && g_regex_match_simple("^[0-9a-f]{64}$", f[1], 0, 0)
                && f[2] && g_strcmp0(f[2], request->resource_id) == 0
                && g_regex_match_simple("^ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}$", f[2], 0, 0)
                && ((!restore && f[3]) || (restore && f[3]
                    && g_strcmp0(f[3], request->detail_id) == 0
                    && g_regex_match_simple("^[0-9a-f]{32}$", f[3], 0, 0) && f[4]));
            if (valid) {
                g_strchomp(f[restore ? 4 : 3]);
                show_replay_review(c, restore ? "proot-replay-restore-apply" : "proot-replay-retire-apply",
                    f[2], restore ? f[3] : NULL, f[1], restore ? f[4] : f[3]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Replay guest preview was invalid or the selected resource changed; no change was made.");
            g_strfreev(f);
        } else if ((g_strcmp0(request->action, "backup-create-preview") == 0 || g_strcmp0(request->action, "restore-apply-preview") == 0
             || g_strcmp0(request->action, "recovery-resolve-preview") == 0 || g_strcmp0(request->action, "recovery-rollback-apply-preview") == 0
             || g_strcmp0(request->action, "continuity-prepare-preview") == 0 || g_strcmp0(request->action, "continuity-verify-preview") == 0
             || g_strcmp0(request->action, "reboot-test-prepare-preview") == 0 || g_strcmp0(request->action, "reboot-test-verify-preview") == 0)
                && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gboolean recovery_record = g_str_has_prefix(request->action, "recovery-");
            gchar **f = g_strsplit(stdout_text, "\t", recovery_record ? 4 : 3);
            gboolean backup = g_strcmp0(request->action, "backup-create-preview") == 0;
            gboolean resolve = g_strcmp0(request->action, "recovery-resolve-preview") == 0;
            gboolean continuity_prepare = g_strcmp0(request->action, "continuity-prepare-preview") == 0;
            gboolean continuity_verify = g_strcmp0(request->action, "continuity-verify-preview") == 0;
            gboolean reboot_test_prepare = g_strcmp0(request->action, "reboot-test-prepare-preview") == 0;
            gboolean reboot_test_verify = g_strcmp0(request->action, "reboot-test-verify-preview") == 0;
            const gchar *operation_id = recovery_record ? f[2] : request->resource_id;
            const gchar *summary = recovery_record ? f[3] : f[2];
            if (f[1] && g_regex_match_simple("^[0-9a-f]{64}$", f[1], 0, 0) && summary
                    && (!recovery_record || (operation_id && g_regex_match_simple("^[0-9a-f]{32}$", operation_id, 0, 0)))) {
                g_strchomp((gchar *)summary);
                ask_recovery_confirmation(c, backup ? "backup-create-apply" :
                    (g_strcmp0(request->action, "restore-apply-preview") == 0 ? "restore-apply" :
                    (resolve ? "recovery.resolve" : (continuity_prepare ? "continuity-prepare-apply" :
                    (continuity_verify ? "continuity-verify-apply" : (reboot_test_prepare ? "reboot-test-prepare-apply" :
                    (reboot_test_verify ? "reboot-test-verify-apply" : "recovery.rollback.apply")))))), operation_id, f[1], summary);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Recovery preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "software-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 6);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{64}$", f[1], 0, 0) && f[2] && f[3] && f[4]) {
                g_strchomp(f[4]);
                gchar *message = g_strdup_printf("Review exact Native Termux APT transaction for %s (%s):\n\n%s\n\nApply this exact preview?", f[2], f[3], f[4]);
                GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
                gchar *label = g_strdup_printf("Apply %s", f[3]); const char *choices[] = {"Cancel", label, NULL};
                gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
                Request *next = g_new0(Request, 1); next->center = c; next->action = g_strdup("software-apply");
                next->resource_id = g_strdup(f[2]); next->detail_id = g_strdup(f[3]); next->plan_id = g_strdup(f[1]);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, next);
                gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact Native app package plan");
                g_free(label); g_free(message); g_object_unref(dialog);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Native app preview response was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "cpu-model-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 3);
            if (f[1] && strlen(f[1]) == 24 && g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0) && f[2]) {
                g_strchomp(f[2]); ask_cpu_model_confirmation(c, request->resource_id, f[1], f[2]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "CPU model preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "npu-runtime-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 3);
            if (f[1] && strlen(f[1]) == 24 && g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0) && f[2]) {
                g_strchomp(f[2]); show_npu_install_confirmation(c, f[1], f[2]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "NPU runtime preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "cron-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 3);
            if (f[1] && f[2] && strlen(f[1]) == 32) {
                g_strchomp(f[2]);
                ask_cron_confirmation(c, f[1], f[2]);
            } else {
                gtk_label_set_text(GTK_LABEL(c->notice), "Cron preview response was invalid.");
            }
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-wakelock-status") == 0 && stdout_text && g_str_has_prefix(stdout_text, "S\t")) {
            gchar *value = g_strdup(stdout_text + 2); g_strchomp(value);
            if (g_strcmp0(value, "true") == 0 || g_strcmp0(value, "false") == 0)
                run_bridge(c, "ssh-wakelock-preview", g_strcmp0(value, "true") == 0 ? "disabled" : "enabled", NULL, NULL, NULL, NULL);
            else gtk_label_set_text(GTK_LABEL(c->notice), "Managed SSH Wake Lock status was invalid.");
            g_free(value);
        } else if (g_strcmp0(request->action, "ssh-wakelock-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0) && f[2]
                    && (g_strcmp0(f[2], "true") == 0 || g_strcmp0(f[2], "false") == 0) && f[3]) {
                g_strchomp(f[3]); ask_ssh_wakelock_confirmation(c, f[2], f[1], f[3]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Managed SSH Wake Lock preview was invalid.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-autostart-status") == 0 && stdout_text && g_str_has_prefix(stdout_text, "S\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 2);
            if (f[1]) { g_strchomp(f[1]); if (g_strcmp0(f[1], "true") == 0 || g_strcmp0(f[1], "false") == 0)
                run_bridge(c, "ssh-autostart-preview", g_strcmp0(f[1], "true") == 0 ? "disabled" : "enabled", NULL, NULL, NULL, NULL);
                else gtk_label_set_text(GTK_LABEL(c->notice), "SSH startup preference response was invalid."); }
            else gtk_label_set_text(GTK_LABEL(c->notice), "SSH startup preference response was incomplete.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-autostart-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0) && f[2]
                    && (g_strcmp0(f[2], "true") == 0 || g_strcmp0(f[2], "false") == 0) && f[3]) {
                g_strchomp(f[3]); ask_ssh_autostart_confirmation(c, f[2], f[1], f[3]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "SSH startup preference preview was invalid.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-deploy-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 3);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{64}$", f[1], 0, 0) && f[2]) {
                g_strchomp(f[2]); ask_ssh_deploy_confirmation(c, f[1], f[2]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "SSH definition preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-deploy-rollback-list") == 0 && stdout_text) {
            gchar **lines = g_strsplit(stdout_text, "\n", -1);
            GPtrArray *ids = g_ptr_array_new_with_free_func(g_free);
            GPtrArray *labels = g_ptr_array_new_with_free_func(g_free);
            for (guint i = 0; lines[i]; i++) {
                gchar **f = g_strsplit(lines[i], "\t", 4);
                if (g_strcmp0(f[0], "R") == 0 && f[1] && f[2]
                        && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)) {
                    g_ptr_array_add(ids, g_strdup(f[1]));
                    g_ptr_array_add(labels, g_strdup_printf("%s · %s", f[2], f[3] ? f[3] : ""));
                }
                g_strfreev(f);
            }
            g_strfreev(lines);
            if (ids->len == 0) {
                gtk_label_set_text(GTK_LABEL(c->notice), "No completed SSH definition deployments are available to restore.");
            } else {
                gchar **choices = g_new0(gchar *, labels->len + 2);
                choices[0] = g_strdup("Cancel");
                GString *message = g_string_new("Choose a saved SSH service-definition deployment:");
                GString *joined = g_string_new(NULL);
                for (guint i = 0; i < ids->len; i++) {
                    choices[i + 1] = g_strdup_printf("%u. %s", i + 1, (gchar *)g_ptr_array_index(labels, i));
                    g_string_append_printf(message, "\n\n%u. %s", i + 1, (gchar *)g_ptr_array_index(labels, i));
                    if (i) g_string_append_c(joined, ',');
                    g_string_append(joined, g_ptr_array_index(ids, i));
                }
                GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message->str);
                gtk_alert_dialog_set_buttons(dialog, (const char * const *)choices);
                gtk_alert_dialog_set_default_button(dialog, 0);
                Request *select = g_new0(Request, 1); select->center = c;
                select->action = g_strdup("ssh-deploy-rollback-select");
                select->resource_id = g_string_free(joined, FALSE);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, ssh_deploy_rollback_choice, select);
                gtk_label_set_text(GTK_LABEL(c->notice), "Choose the exact saved SSH definition to review.");
                g_object_unref(dialog); g_string_free(message, TRUE); g_strfreev(choices);
            }
            g_ptr_array_unref(ids); g_ptr_array_unref(labels);
        } else if (g_strcmp0(request->action, "ssh-deploy-rollback-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)
                    && f[2] && g_regex_match_simple("^[0-9a-f]{64}$", f[2], 0, 0) && f[3]) {
                g_strchomp(f[3]); ask_ssh_deploy_rollback_confirmation(c, f[1], f[2], f[3]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "SSH definition rollback preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-key-rollback-list") == 0 && stdout_text && g_str_has_prefix(stdout_text, "R\t")) {
            gchar **lines = g_strsplit(stdout_text, "\n", -1);
            GPtrArray *ids = g_ptr_array_new_with_free_func(g_free);
            GPtrArray *labels = g_ptr_array_new_with_free_func(g_free);
            for (guint i = 0; lines[i]; i++) {
                gchar **f = g_strsplit(lines[i], "\t", 5);
                if (f[0] && g_strcmp0(f[0], "R") == 0 && f[1] && g_strcmp0(f[1], "-") != 0
                        && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)) {
                    g_ptr_array_add(ids, g_strdup(f[1]));
                    g_ptr_array_add(labels, g_strdup_printf("%s key %s (%s)", f[3] ? f[3] : "changed",
                        f[2] ? f[2] : "fingerprint unavailable", f[4] ? f[4] : "saved"));
                }
                g_strfreev(f);
            }
            g_strfreev(lines);
            if (ids->len == 0) {
                gtk_label_set_text(GTK_LABEL(c->notice), "No saved SSH key changes are available to restore.");
            } else {
                gchar **choices = g_new0(gchar *, labels->len + 2); choices[0] = g_strdup("Cancel");
                GString *message = g_string_new("Choose a saved authorized-key change to restore:");
                GString *joined = g_string_new(NULL);
                for (guint i = 0; i < ids->len; i++) {
                    choices[i + 1] = g_strdup_printf("%u. %s", i + 1, (gchar *)g_ptr_array_index(labels, i));
                    g_string_append_printf(message, "\n\n%u. %s", i + 1, (gchar *)g_ptr_array_index(labels, i));
                    if (i) g_string_append_c(joined, ',');
                    g_string_append(joined, g_ptr_array_index(ids, i));
                }
                GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message->str);
                gtk_alert_dialog_set_buttons(dialog, (const char * const *)choices);
                gtk_alert_dialog_set_default_button(dialog, 0);
                Request *request = g_new0(Request, 1); request->center = c;
                request->action = g_strdup("ssh-key-rollback-select"); request->resource_id = g_string_free(joined, FALSE);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, ssh_rollback_choice, request);
                gtk_label_set_text(GTK_LABEL(c->notice), "Choose an exact saved SSH key state to review.");
                g_object_unref(dialog); g_string_free(message, TRUE);
                g_strfreev(choices);
            }
            g_ptr_array_unref(ids); g_ptr_array_unref(labels);
        } else if (g_strcmp0(request->action, "ssh-key-rollback-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0) && f[2]
                    && g_regex_match_simple("^[0-9a-f]{32}$", f[2], 0, 0) && f[3]) {
                g_strchomp(f[3]); ask_ssh_rollback_confirmation(c, f[2], f[1], f[3]);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "SSH recovery preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "ssh-client-key-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 5);
            gchar *expected_path = f[2] ? g_strdup_printf("~/.ssh/ternuxx-keys/%s", f[2]) : NULL;
            gboolean valid = f[1] && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)
                && f[2] && g_regex_match_simple("^[a-z0-9][a-z0-9_-]{0,31}$", f[2], 0, 0)
                && f[3] && expected_path && g_strcmp0(f[3], expected_path) == 0 && f[4];
            if (valid) { g_strchomp(f[4]); ask_ssh_client_key_confirmation(c, f[2], f[1], f[3], f[4]); }
            else gtk_label_set_text(GTK_LABEL(c->notice), "Native SSH key preview was invalid; no key was created.");
            g_free(expected_path); g_strfreev(f);
        } else if ((g_strcmp0(request->action, "ssh-key-add-preview") == 0 || g_strcmp0(request->action, "ssh-key-remove-preview") == 0)
                && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            gboolean valid = f[1] && strlen(f[1]) == 24 && f[2]
                && g_regex_match_simple("^SHA256:[A-Za-z0-9+/]{43}$", f[2], 0, 0) && f[3];
            if (valid) ask_ssh_key_confirmation(c, request->action, request->resource_id, f[1], f[2]);
            else gtk_label_set_text(GTK_LABEL(c->notice), "SSH key preview incomplete; no change was made.");
            g_strfreev(f);
        } else if ((g_strcmp0(request->action, "proot-shortcut-preview") == 0
                    || g_strcmp0(request->action, "proot-stop-preview") == 0
                    || g_strcmp0(request->action, "proot-reconcile-preview") == 0)
                   && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 5);
            gboolean shortcut = g_strcmp0(request->action, "proot-shortcut-preview") == 0;
            gboolean reconcile = g_strcmp0(request->action, "proot-reconcile-preview") == 0;
            gboolean valid = f[1] && f[2] && (shortcut
                ? g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0)
                : g_regex_match_simple("^plan-[0-9a-f]{64}$", f[1], 0, 0));
            if (valid) {
                g_strchomp(f[shortcut ? 3 : 2]);
                gchar *summary = shortcut
                    ? g_strdup_printf("Guest app: %s\nLauncher: %s", f[2], f[3] ? f[3] : "")
                    : g_strdup(f[2]);
                ask_proot_confirmation(c, shortcut ? "proot-shortcut-apply" :
                    (reconcile ? "proot-reconcile-apply" : "proot-stop-apply"),
                    request->resource_id, request->detail_id, f[1], summary);
                g_free(summary);
            } else {
                gtk_label_set_text(GTK_LABEL(c->notice), "Debian preview was invalid; no change was made.");
            }
            g_strfreev(f);
        } else if ((g_strcmp0(request->action, "proot-shortcut-preview") == 0
                    || g_strcmp0(request->action, "proot-stop-preview") == 0)
                   && stdout_text && g_str_has_prefix(stdout_text, "R\t")) {
            set_text(c, "The requested guest shortcut state is already active.");
            gtk_label_set_text(GTK_LABEL(c->notice), "No shortcut change needed");
        } else if ((g_strcmp0(request->action, "proot-shortcut-sync-preview") == 0
                    || g_strcmp0(request->action, "proot-shortcut-rollback-preview") == 0)
                   && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 6);
            gboolean valid = f[1] && g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0);
            if (valid && g_strcmp0(request->action, "proot-shortcut-sync-preview") == 0
                    && f[2] && f[3] && f[4]) {
                g_strchomp(f[4]);
                gchar *summary = g_strdup_printf("Discovered guest apps: %s\nLauncher changes: %s\nPreserved conflicts: %s", f[2], f[3], f[4]);
                ask_proot_confirmation(c, "proot-shortcut-sync-apply", f[1], NULL, f[1], summary);
                g_free(summary);
            } else if (valid && g_strcmp0(request->action, "proot-shortcut-rollback-preview") == 0
                       && f[2] && g_regex_match_simple("^[0-9a-f]{32}$", f[2], 0, 0) && f[3]) {
                g_strchomp(f[3]);
                gchar *summary = g_strdup_printf("Restore saved shortcut sync %s\nLauncher entries: %s", f[2], f[3]);
                ask_proot_confirmation(c, "proot-shortcut-rollback-apply", f[2], NULL, f[1], summary);
                g_free(summary);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Shortcut sync preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "proot-shortcut-rollback-preview") == 0
                   && stdout_text && g_str_has_prefix(stdout_text, "Q\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 5);
            if (f[1] && g_regex_match_simple("^[0-9a-f]{24}$", f[1], 0, 0)
                    && f[2] && g_regex_match_simple("^[0-9a-f]{32}$", f[2], 0, 0) && f[3]) {
                g_strchomp(f[3]);
                gchar *summary = g_strdup_printf("Restore saved shortcut sync %s\nLauncher entries: %s", f[2], f[3]);
                ask_proot_confirmation(c, "proot-shortcut-rollback-apply", f[2], NULL, f[1], summary);
                g_free(summary);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Shortcut rollback preview was invalid; no change was made.");
            g_strfreev(f);
        } else if ((g_strcmp0(request->action, "proot-shortcut-sync-preview") == 0
                    || g_strcmp0(request->action, "proot-shortcut-rollback-preview") == 0)
                   && stdout_text && g_str_has_prefix(stdout_text, "R\t")) {
            set_text(c, stdout_text);
            gtk_label_set_text(GTK_LABEL(c->notice), "No shortcut synchronization changes needed");
        } else if (g_strcmp0(request->action, "shortcut-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 6);
            if (f[1] && f[2] && f[3] && f[4] && g_strcmp0(f[2], "true") == 0
                    && g_strcmp0(f[1], "-") != 0 && strlen(f[1]) == 24) {
                g_strchomp(f[4]);
                ask_shortcut_confirmation(c, request->resource_id, request->detail_id, f[1], f[3], f[4]);
            } else {
                set_text(c, "Shortcut is already in the requested state. No change was made.");
                gtk_label_set_text(GTK_LABEL(c->notice), "No shortcut change needed");
            }
            g_strfreev(f);
        } else if ((g_strcmp0(request->action, "ssh-preview-start") == 0 || g_strcmp0(request->action, "ssh-preview-stop") == 0 || g_strcmp0(request->action, "ssh-preview-restart") == 0)
                && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            if (f[1] && f[2] && f[3] && g_strcmp0(f[2], "true") == 0 && g_strcmp0(f[1], "-") != 0) {
                g_strchomp(f[3]); ask_ssh_confirmation(c, request->action, f[1], f[3]);
            } else {
                set_text(c, "Managed SSH 8023 is already in the requested state. No change was made.");
                gtk_label_set_text(GTK_LABEL(c->notice), "No service change needed");
            }
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "terminal-service-prepare") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 5);
            if (f[1] && f[2] && f[3] && g_strcmp0(f[2], "install") != 0 && g_strcmp0(f[2], "start") != 0) {
                set_text(c, "The broker service preview was invalid; no change was applied.");
                gtk_label_set_text(GTK_LABEL(c->notice), "Invalid broker service preview");
            } else if (f[1] && f[2] && f[3] && g_str_has_suffix(f[3], "\n")) {
                g_strchomp(f[3]); ask_terminal_service_confirmation(c, f[1], f[2], f[3]);
            } else if (f[1] && f[2] && f[3]) {
                ask_terminal_service_confirmation(c, f[1], f[2], f[3]);
            } else {
                set_text(c, "The broker service preview was incomplete; no change was applied.");
                gtk_label_set_text(GTK_LABEL(c->notice), "Invalid broker service preview");
            }
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "terminal-service-prepare") == 0 && stdout_text && g_str_has_prefix(stdout_text, "R\t")) {
            set_text(c, "The fixed Ternuxx terminal broker is already running. No guest was started.");
            gtk_label_set_text(GTK_LABEL(c->notice), "Terminal broker is running");
        } else if (g_strcmp0(request->action, "boot-cron-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 4);
            gboolean valid = f[1] && g_regex_match_simple("^[0-9a-f]{64}$", f[1], 0, 0)
                && f[2] && (g_strcmp0(f[2], "enable") == 0 || g_strcmp0(f[2], "disable") == 0) && f[3];
            if (valid) {
                g_strchomp(f[3]);
                gchar *message = g_strdup_printf("Review this exact Termux:Boot Cron change:\n\n%s\n\nApply this preview?", f[3]);
                GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
                const char *choices[] = {"Cancel", "Apply exact change", NULL};
                gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
                Request *next = g_new0(Request, 1); next->center = c;
                next->action = g_strdup("boot-cron-apply"); next->resource_id = g_strdup(f[2]); next->plan_id = g_strdup(f[1]);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, next);
                gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact Termux:Boot Cron preview");
                g_object_unref(dialog); g_free(message);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Termux:Boot preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "boot-helpers-status") == 0 && stdout_text) {
            set_text(c, stdout_text);
            BootHelperChoice *choice = g_new0(BootHelperChoice, 1); choice->center = c;
            choice->ids = g_ptr_array_new_with_free_func(g_free); choice->labels = g_ptr_array_new_with_free_func(g_free);
            gchar **lines = g_strsplit(stdout_text, "\n", -1);
            for (guint i = 0; lines[i]; i++) {
                gchar **f = g_strsplit(lines[i], "\t", 6);
                if (g_strcmp0(f[0], "H") == 0 && f[1] && f[2]
                        && (g_strcmp0(f[1], "services") == 0 || g_strcmp0(f[1], "recovery") == 0)) {
                    g_ptr_array_add(choice->ids, g_strdup(f[1]));
                    g_ptr_array_add(choice->labels, g_strdup_printf("%s · %s", f[1], f[2]));
                }
                g_strfreev(f);
            }
            g_strfreev(lines);
            if (choice->ids->len) {
                gchar **buttons = g_new0(gchar *, choice->labels->len + 2);
                for (guint i = 0; i < choice->labels->len; i++) buttons[i] = g_ptr_array_index(choice->labels, i);
                buttons[choice->labels->len] = "Cancel";
                GtkAlertDialog *dialog = gtk_alert_dialog_new("Choose a fixed Ternuxx-owned Termux:Boot helper");
                gtk_alert_dialog_set_buttons(dialog, (const char * const *)buttons);
                gtk_alert_dialog_set_default_button(dialog, (gint)choice->labels->len);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, boot_helpers_name_choice, choice);
                g_object_unref(dialog); g_free(buttons);
            } else {
                boot_helper_choice_free(choice);
                gtk_label_set_text(GTK_LABEL(c->notice), "No recognized Ternuxx boot helpers were returned.");
            }
        } else if (g_strcmp0(request->action, "boot-helpers-snapshots") == 0 && stdout_text) {
            set_text(c, stdout_text);
            BootHelperChoice *choice = g_new0(BootHelperChoice, 1); choice->center = c;
            choice->helper_id = g_strdup(request->resource_id);
            choice->ids = g_ptr_array_new_with_free_func(g_free); choice->labels = g_ptr_array_new_with_free_func(g_free);
            gchar **lines = g_strsplit(stdout_text, "\n", -1);
            for (guint i = 0; lines[i]; i++) {
                gchar **f = g_strsplit(lines[i], "\t", 5);
                if (g_strcmp0(f[0], "S") == 0 && f[1]
                        && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)) {
                    g_ptr_array_add(choice->ids, g_strdup(f[1]));
                    g_ptr_array_add(choice->labels, g_strdup_printf("%s · %s · %s", f[2] ? f[2] : "unknown", f[3] ? f[3] : "", f[1]));
                }
                g_strfreev(f);
            }
            g_strfreev(lines);
            if (choice->ids->len) {
                gchar **buttons = g_new0(gchar *, choice->labels->len + 2);
                for (guint i = 0; i < choice->labels->len; i++) buttons[i] = g_ptr_array_index(choice->labels, i);
                buttons[choice->labels->len] = "Cancel";
                GtkAlertDialog *dialog = gtk_alert_dialog_new("Select the exact rollback snapshot for %s", choice->helper_id);
                gtk_alert_dialog_set_buttons(dialog, (const char * const *)buttons);
                gtk_alert_dialog_set_default_button(dialog, (gint)choice->labels->len);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, boot_helpers_snapshot_choice, choice);
                g_object_unref(dialog); g_free(buttons);
            } else {
                boot_helper_choice_free(choice);
                gtk_label_set_text(GTK_LABEL(c->notice), "No rollback snapshot is available for this helper.");
            }
        } else if (g_strcmp0(request->action, "boot-helpers-preview") == 0 && stdout_text && g_str_has_prefix(stdout_text, "P\t")) {
            gchar **f = g_strsplit(stdout_text, "\t", 6);
            gboolean valid = f[1] && g_regex_match_simple("^[0-9a-f]{32}$", f[1], 0, 0)
                && f[2] && g_strcmp0(f[2], request->resource_id) == 0
                && f[3] && g_strcmp0(f[3], request->detail_id) == 0 && f[4]
                && g_strcmp0(f[4], request->plan_id) == 0 && f[5];
            if (valid) {
                g_strchomp(f[5]);
                gchar *message = g_strdup_printf("Review the exact boot-helper target, contents, and hashes:\n\n%s\n\nApply this plan?", f[5]);
                GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
                const char *buttons[] = {"Cancel", g_strcmp0(f[3], "deploy") == 0 ? "Deploy exact helper" : "Restore exact snapshot", NULL};
                gtk_alert_dialog_set_buttons(dialog, buttons); gtk_alert_dialog_set_default_button(dialog, 0);
                Request *next = g_new0(Request, 1); next->center = c; next->action = g_strdup("boot-helpers-apply");
                next->resource_id = g_strdup(f[2]); next->detail_id = g_strdup(f[3]); next->plan_id = g_strdup(f[1]); next->extra_id = g_strdup(f[4]);
                gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, next);
                gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact boot-helper plan");
                g_object_unref(dialog); g_free(message);
            } else gtk_label_set_text(GTK_LABEL(c->notice), "Boot-helper preview was invalid; no change was made.");
            g_strfreev(f);
        } else if (g_strcmp0(request->action, "monitor") == 0 && stdout_text && g_str_has_prefix(stdout_text,"M\t")) {
            gchar **f=g_strsplit(stdout_text,"\t",5);
            if(f[1]&&f[2]&&f[3]&&f[4]) {
                g_strchomp(f[4]);
                gtk_check_button_set_active(GTK_CHECK_BUTTON(c->monitor_enabled),g_strcmp0(f[1],"True")==0||g_strcmp0(f[1],"true")==0);
                gtk_spin_button_set_value(GTK_SPIN_BUTTON(c->monitor_interval),g_ascii_strtod(f[2],NULL)); gtk_drop_down_set_selected(GTK_DROP_DOWN(c->monitor_unit),0);
                gtk_check_button_set_active(GTK_CHECK_BUTTON(c->monitor_focus),g_strcmp0(f[3],"True")==0||g_strcmp0(f[3],"true")==0);
                gtk_check_button_set_active(GTK_CHECK_BUTTON(c->monitor_launch),g_strcmp0(f[4],"True")==0||g_strcmp0(f[4],"true")==0);
            }
            g_strfreev(f); set_text(c,"Android Activity/focus monitoring policy\n\nLinux GUI health is inspected separately. Status reads do not launch Termux:X11.");
        } else {
            const gchar *message = (stderr_text && *stderr_text) ? stderr_text :
                ((stdout_text && *stdout_text) ? stdout_text : "Request completed.");
            set_text(c, message);
        }
        const gchar *notice = success ? "Shared management service request completed"
            : ((stderr_text && *stderr_text) ? stderr_text : "Operation failed; inspect the result details.");
        gtk_label_set_text(GTK_LABEL(c->notice), notice);
        gtk_widget_set_sensitive(c->start_button, TRUE); gtk_widget_set_sensitive(c->stop_button, TRUE); gtk_widget_set_sensitive(c->ssh_restart_button, TRUE);
        if (success && (g_strcmp0(request->action,"start-desktop")==0 || g_strcmp0(request->action,"stop-desktop")==0))
            run_bridge(c,"inspect","native.desktop.session",NULL,NULL,NULL,NULL);
        else if (success && (g_strcmp0(request->action,"ssh-apply-start")==0 || g_strcmp0(request->action,"ssh-apply-stop")==0 || g_strcmp0(request->action,"ssh-apply-restart")==0))
            run_bridge(c,"inspect","network.ssh.managed-8023",NULL,NULL,NULL,NULL);
        else if (success && (g_strcmp0(request->action,"ssh-key-add-apply")==0 || g_strcmp0(request->action,"ssh-key-remove-apply")==0))
            run_bridge(c,"ssh-keys-list",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"ssh-client-key-apply")==0)
            gtk_label_set_text(GTK_LABEL(c->notice), "Native recovery key created. Review the public-key path in the result, then enroll it separately if needed.");
        else if (success && g_strcmp0(request->action,"ssh-autostart-apply")==0)
            run_bridge(c,"ssh-autostart-status",NULL,NULL,NULL,NULL,NULL);
        else if (success && (g_strcmp0(request->action,"ssh-deploy-apply")==0 || g_strcmp0(request->action,"ssh-deploy-rollback-apply")==0))
            run_bridge(c,"inspect","network.ssh.managed-8023",NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"ssh-wakelock-apply")==0)
            run_bridge(c,"ssh-wakelock-status",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"boot-cron-apply")==0)
            run_bridge(c,"boot-cron-status",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"boot-helpers-apply")==0)
            run_bridge(c,"boot-helpers-status",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"set-monitor")==0)
            run_bridge(c,"monitor",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"cron-apply")==0)
            run_bridge(c,"cron-jobs",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"terminal-service-apply")==0)
            run_bridge(c,"terminal-service-status",NULL,NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"cpu-model-apply")==0)
            run_bridge(c,"inspect","inference.cpu.local",NULL,NULL,NULL,NULL);
        else if (success && g_strcmp0(request->action,"software-apply")==0)
            run_bridge(c,"inspect","software.curated-apps",NULL,NULL,NULL,NULL);
    }
    g_free(stdout_text); g_free(stderr_text); g_free(request->action); g_free(request->resource_id); g_free(request->detail_id); g_free(request->plan_id); g_free(request->extra_id); g_free(request);
}
static void run_bridge_full(Center *c, const gchar *action, const gchar *arg1, const gchar *arg2,
                            const gchar *arg3, const gchar *arg4, const gchar *arg5,
                            const gchar *arg6, const gchar *arg7) {
    gchar *script = bridge_path(), *python = python_path();
    if (!script || !g_file_test(script, G_FILE_TEST_IS_REGULAR)) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Management bridge is unavailable; check TERNUXX_CHECKOUT.");
        g_free(script); g_free(python); return;
    }
    gboolean lifecycle = g_strcmp0(action,"start-desktop")==0 || g_strcmp0(action,"stop-desktop")==0
        || g_str_has_prefix(action,"ssh-preview-") || g_str_has_prefix(action,"ssh-apply-");
    if (lifecycle) { gtk_widget_set_sensitive(c->start_button,FALSE); gtk_widget_set_sensitive(c->stop_button,FALSE); gtk_widget_set_sensitive(c->ssh_restart_button,FALSE); }
    GPtrArray *argv = g_ptr_array_new(); g_ptr_array_add(argv, python); g_ptr_array_add(argv, script);
    g_ptr_array_add(argv, (gpointer)action);
    if (arg1) g_ptr_array_add(argv, (gpointer)arg1); if (arg2) g_ptr_array_add(argv, (gpointer)arg2);
    if (arg3) g_ptr_array_add(argv, (gpointer)arg3); if (arg4) g_ptr_array_add(argv, (gpointer)arg4); if (arg5) g_ptr_array_add(argv, (gpointer)arg5);
    if (arg6) g_ptr_array_add(argv, (gpointer)arg6); if (arg7) g_ptr_array_add(argv, (gpointer)arg7);
    g_ptr_array_add(argv, NULL);
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv((const gchar * const *)argv->pdata,
        G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, &error);
    gtk_label_set_text(GTK_LABEL(c->notice), "Working…");
    if (!process) {
        gtk_label_set_text(GTK_LABEL(c->notice), error ? error->message : "Could not start management request");
        g_clear_error(&error);
    } else {
        Request *request = g_new0(Request, 1); request->center = c;
        request->action = g_strdup(action); request->resource_id = g_strdup(arg1); request->detail_id = g_strdup(arg2); request->plan_id = g_strdup(arg3); request->extra_id = g_strdup(arg4);
        g_subprocess_communicate_utf8_async(process, NULL, NULL, request_done, request);
        g_object_unref(process);
    }
    g_ptr_array_unref(argv); g_free(script); g_free(python);
}
static void run_bridge(Center *c, const gchar *action, const gchar *arg1, const gchar *arg2,
                       const gchar *arg3, const gchar *arg4, const gchar *arg5) {
    run_bridge_full(c, action, arg1, arg2, arg3, arg4, arg5, NULL, NULL);
}
static void run_bridge_input_full(Center *c, const gchar *action, const gchar *input, const gchar *device_id) {
    gchar *script = bridge_path(), *python = python_path();
    if (!script || !g_file_test(script, G_FILE_TEST_IS_REGULAR)) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Management bridge is unavailable; check TERNUXX_CHECKOUT.");
        g_free(script); g_free(python); return;
    }
    const gchar *argv[5] = {python, script, action, NULL, NULL};
    if (device_id && *device_id) { argv[3] = device_id; argv[4] = NULL; }
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_STDIN_PIPE |
        G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, &error);
    gtk_label_set_text(GTK_LABEL(c->notice), g_strcmp0(action, "gpu-run") == 0
        ? "Running bounded Vulkan inference with offload verification…"
        : g_strcmp0(action, "auto-run") == 0
        ? "Selecting HTP, Vulkan, or CPU for bounded inference…"
        : "Running bounded local CPU inference…");
    if (!process) {
        gtk_label_set_text(GTK_LABEL(c->notice), error ? error->message : "Could not start local inference");
        g_clear_error(&error);
    } else {
        Request *request = g_new0(Request, 1); request->center = c; request->action = g_strdup(action);
        g_subprocess_communicate_utf8_async(process, input, NULL, request_done, request);
        g_object_unref(process);
    }
    g_free(script); g_free(python);
}
static void run_bridge_input(Center *c, const gchar *action, const gchar *input) {
    run_bridge_input_full(c, action, input, NULL);
}

static void resource_free(gpointer ptr) {
    Resource *r = ptr; if (!r) return; g_free(r->id); g_free(r->category); g_free(r->name);
    g_free(r->status); g_free(r->availability); g_free(r->description); g_free(r->operations); g_free(r);
}
static void clear_rows(GtkWidget *list) {
    GtkWidget *child; while ((child = gtk_widget_get_first_child(list)) != NULL) gtk_list_box_remove(GTK_LIST_BOX(list), child);
}
static const gchar *status_label(const gchar *status) {
    if (!status) return "Unknown";
    if (!g_strcmp0(status,"implemented")) return "Implemented";
    if (!g_strcmp0(status,"partial")) return "Partial";
    if (!g_strcmp0(status,"external")) return "Externally managed";
    if (!g_strcmp0(status,"unverified")) return "Unverified";
    if (!g_strcmp0(status,"unavailable")) return "Unavailable";
    if (!g_strcmp0(status,"planned")) return "Planned";
    if (!g_strcmp0(status,"unknown")) return "Unknown";
    return status;
}
static void show_resource(Center *c, Resource *r) {
    if (!r) return;
    const gchar *gui_actions = "Status and details only.";
    if (g_strcmp0(r->id, "native.desktop.session") == 0)
        gui_actions = "Check status · Start or stop desktop";
    else if (g_strcmp0(r->id, "graphics.native") == 0)
        gui_actions = "Check status · Verify OpenGL, GLES, Vulkan · Select backend";
    else if (g_strcmp0(r->id, "network.ssh.managed-8023") == 0)
        gui_actions = "Check status · Generate a Native recovery key · Enroll, revoke, or restore public keys · Set SSH automatic start · Start, stop, or restart managed SSH (8023)";
    else if (g_strcmp0(r->id, "native.wakelock") == 0)
        gui_actions = "Inspect Wake Lock leases · Set managed SSH keep-awake preference";
    else if (g_strcmp0(r->id, "boot.termux.cron") == 0)
        gui_actions = "Check status · Validate · Preview and confirm Termux:Boot Cron startup changes";
    else if (g_strcmp0(r->id, "boot.termux.profile") == 0)
        gui_actions = "Inspect startup profile and fixed boot helpers · Preview and confirm helper deploy or rollback";
    else if (g_strcmp0(r->id, "native.gui.activity-monitor") == 0)
        gui_actions = "Review or update monitoring settings";
    else if (g_strcmp0(r->id, "recovery.native-state") == 0)
        gui_actions = "View history · Create verified backups · Restore profiles · Reconcile operations and apply restore rollback";
    else if (g_strcmp0(r->id, "automation.cron-registry") == 0)
        gui_actions = "Manage scheduler and jobs · View run history";
    else if (g_strcmp0(r->id, "native.timezone") == 0)
        gui_actions = "View or change Ternuxx timezone";
    else if (g_strcmp0(r->id, "inference.auto.local") == 0)
        gui_actions = "Run on the highest-priority available backend: HTP0, then Vulkan, then CPU; selected backend is reported and inference errors do not silently retry";
    else if (g_strcmp0(r->id, "inference.cpu.local") == 0)
        gui_actions = "Check runtime · Preview model download/removal · Run a bounded local CPU prompt";
    else if (g_strcmp0(r->id, "inference.gpu.local") == 0)
        gui_actions = "List Vulkan inference devices · Run a bounded Vulkan prompt with verified GPU offload and no silent CPU fallback";
    else if (g_strcmp0(r->id, "inference.npu.local") == 0)
        gui_actions = "Check HTP0 · Preview and confirm a pinned Snapdragon runtime · Run an experimental HTP prompt with verified offload and no CPU fallback";
    else if (g_strcmp0(r->id, "proot.debian.workloads") == 0)
        gui_actions = "Install a managed Debian or Ubuntu guest · Inspect status · List profiles and owned sessions";
    else if (g_strcmp0(r->id, "proot.replay-guests") == 0)
        gui_actions = "Preview exact receipt-verified replay guest retirement or restore · Review exact target and reversible impact before applying";
    else if (g_strcmp0(r->id, "proot.interactive-terminal-broker") == 0)
        gui_actions = "Inspect broker status · Preview and confirm its fixed Runit service · Open the fixed Debian login in a Native GTK terminal";
    gchar *availability = g_strdup(r->availability && *r->availability ? r->availability : "unknown");
    g_strdelimit(availability, "-_", ' ');
    availability[0] = g_ascii_toupper(availability[0]);
    gchar *summary = g_strdup_printf("%s\n\nCapability: %s\nAvailability: %s\n\n%s\n\nIn this app\n%s",
        r->name, status_label(r->status), availability, r->description, gui_actions);
    set_text(c, summary); g_free(summary); g_free(availability);
    g_free(c->selected_resource_id); c->selected_resource_id = g_strdup(r->id);
    gboolean graphics = g_str_has_prefix(r->id, "graphics.");
    gboolean desktop = g_strcmp0(r->id, "native.desktop.session") == 0;
    gboolean managed_ssh = g_strcmp0(r->id, "network.ssh.managed-8023") == 0;
    gboolean wakelock = g_strcmp0(r->id, "native.wakelock") == 0;
    gboolean monitor = g_strcmp0(r->id, "native.gui.activity-monitor") == 0;
    gboolean history = g_strcmp0(r->id, "recovery.native-state") == 0;
    gboolean system_health = g_strcmp0(r->id, "native.system.health") == 0;
    gboolean cron = g_strcmp0(r->id, "automation.cron-registry") == 0;
    gboolean timezone = g_strcmp0(r->id, "native.timezone") == 0;
    gboolean auto_inference = g_strcmp0(r->id, "inference.auto.local") == 0;
    gboolean cpu_inference = g_strcmp0(r->id, "inference.cpu.local") == 0;
    gboolean gpu_inference = g_strcmp0(r->id, "inference.gpu.local") == 0;
    gboolean npu_inference = g_strcmp0(r->id, "inference.npu.local") == 0;
    gboolean proot_workloads = g_strcmp0(r->id, "proot.debian.workloads") == 0;
    gboolean proot_replay = g_strcmp0(r->id, "proot.replay-guests") == 0;
    gboolean terminal_broker = g_strcmp0(r->id, "proot.interactive-terminal-broker") == 0;
    gtk_widget_set_visible(c->history_button, history);
    gtk_widget_set_visible(c->desktop_log_button, system_health);
    gtk_widget_set_visible(c->logs_button, system_health);
    gtk_widget_set_visible(c->audit_logs_button, system_health);
    gtk_widget_set_visible(c->cron_button, cron);
    gtk_widget_set_visible(c->cron_history_button, cron);
    gtk_widget_set_visible(c->cron_manage_button, cron);
    gtk_widget_set_visible(c->cron_start_button, cron);
    gtk_widget_set_visible(c->cron_stop_button, cron);
    gtk_widget_set_visible(c->cron_target_entry, cron);
    gtk_widget_set_visible(c->cron_inspect_button, cron);
    gtk_widget_set_visible(c->cron_next_button, cron);
    gtk_widget_set_visible(c->cron_execution_button, cron);
    gboolean recovery = g_strcmp0(r->id, "recovery.native-state") == 0;
    gtk_widget_set_visible(c->backup_list_button, recovery);
    gtk_widget_set_visible(c->recovery_status_button, recovery);
    gtk_widget_set_visible(c->continuity_status_button, recovery);
    gtk_widget_set_visible(c->continuity_prepare_button, recovery);
    gtk_widget_set_visible(c->continuity_verify_button, recovery);
    gtk_widget_set_visible(c->reboot_test_prepare_button, recovery);
    gtk_widget_set_visible(c->reboot_test_verify_button, recovery);
    gtk_widget_set_visible(c->recovery_target_entry, recovery);
    gtk_widget_set_visible(c->backup_inspect_button, recovery);
    gtk_widget_set_visible(c->restore_preview_button, recovery);
    gtk_widget_set_visible(c->backup_create_button, recovery);
    gtk_widget_set_visible(c->restore_apply_button, recovery);
    gtk_widget_set_visible(c->rollback_apply_button, recovery);
    gtk_widget_set_visible(c->recovery_resolve_button, recovery);
    gtk_widget_set_visible(c->operation_inspect_button, recovery);
    gtk_widget_set_visible(c->rollback_preview_button, recovery);
    gtk_widget_set_visible(c->timezone_set_button, timezone);
    gboolean curated_software = g_strcmp0(r->id, "software.curated-apps") == 0;
    gtk_widget_set_visible(c->software_button, curated_software);
    gtk_widget_set_visible(c->ai_auto_run_button, auto_inference);
    gtk_widget_set_visible(c->ai_model_install_button, cpu_inference);
    gtk_widget_set_visible(c->ai_model_remove_button, cpu_inference);
    gtk_widget_set_visible(c->ai_run_button, cpu_inference);
    gtk_widget_set_visible(c->ai_auto_run_button, auto_inference);
    gtk_widget_set_visible(c->ai_gpu_status_button, gpu_inference);
    gtk_widget_set_visible(c->ai_gpu_run_button, gpu_inference);
    gtk_widget_set_visible(c->ai_npu_status_button, npu_inference);
    gtk_widget_set_visible(c->ai_npu_install_button, npu_inference);
    gtk_widget_set_visible(c->ai_npu_run_button, npu_inference);
    gtk_widget_set_visible(c->terminal_service_button, terminal_broker);
    gtk_widget_set_visible(c->terminal_open_button, terminal_broker);
    gtk_widget_set_visible(c->proot_box, proot_workloads || proot_replay);
    gtk_widget_set_visible(c->proot_help, proot_workloads);
    gtk_widget_set_visible(c->proot_setup_help, proot_workloads);
    gtk_widget_set_visible(c->proot_setup_button, proot_workloads);
    GtkWidget *workload_widgets[] = {c->proot_setup_button, c->proot_desktop_box, c->proot_app_entry, c->proot_app_button, c->proot_shortcut_entry,
        c->proot_shortcut_list_button, c->proot_shortcut_add_button, c->proot_shortcut_remove_button,
        c->proot_shortcut_sync_button, c->proot_shortcut_rollback_list_button, c->proot_sync_rollback_entry,
        c->proot_shortcut_rollback_preview_button, c->proot_session_entry, c->proot_session_stop_button,
        c->proot_session_reconcile_button};
    for (guint i = 0; i < G_N_ELEMENTS(workload_widgets); i++) gtk_widget_set_visible(workload_widgets[i], proot_workloads);
    gtk_widget_set_visible(c->proot_replay_alias_entry, proot_replay);
    gtk_widget_set_visible(c->proot_replay_backup_entry, proot_replay);
    gtk_widget_set_visible(c->proot_replay_retire_button, proot_replay);
    gtk_widget_set_visible(c->proot_replay_restore_button, proot_replay);
    if (!proot_replay) clear_replay_review(c);
    gtk_widget_set_visible(c->graphics_api_button, graphics);
    gtk_button_set_label(GTK_BUTTON(c->start_button), managed_ssh ? "Start managed SSH (8023)" : "Start desktop");
    gtk_button_set_label(GTK_BUTTON(c->stop_button), managed_ssh ? "Stop managed SSH (8023)" : "Stop desktop");
    gtk_widget_set_visible(c->start_button, desktop || managed_ssh || graphics || proot_workloads); gtk_widget_set_visible(c->desktop_choice, desktop); gtk_widget_set_visible(c->stop_button, desktop || managed_ssh || graphics || proot_workloads);
    gtk_button_set_label(GTK_BUTTON(c->ssh_restart_button), "Restart managed SSH (8023)");
    gtk_widget_set_visible(c->ssh_restart_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_keys_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_enroll_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_revoke_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_rollback_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_generate_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_autostart_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_deploy_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_deploy_rollback_button, managed_ssh);
    gtk_widget_set_visible(c->ssh_wakelock_button, wakelock);
    gtk_widget_set_visible(c->boot_cron_button, g_strcmp0(r->id, "boot.termux.cron") == 0);
    gtk_widget_set_visible(c->boot_helpers_button, g_strcmp0(r->id, "boot.termux.profile") == 0);
    gtk_widget_set_visible(c->graphics_select_button, g_strcmp0(r->id, "graphics.native") == 0);
    if (graphics) { gtk_button_set_label(GTK_BUTTON(c->start_button), "Graphics status"); gtk_button_set_label(GTK_BUTTON(c->stop_button), "Verify OpenGL"); }
    else if (proot_workloads) { gtk_button_set_label(GTK_BUTTON(c->start_button), "Debian status"); gtk_button_set_label(GTK_BUTTON(c->stop_button), "Guest sessions"); }
    else { gtk_button_set_label(GTK_BUTTON(c->start_button), managed_ssh ? "Start managed SSH (8023)" : "Start desktop"); gtk_button_set_label(GTK_BUTTON(c->stop_button), managed_ssh ? "Stop managed SSH (8023)" : "Stop desktop"); }
    gtk_widget_set_visible(c->monitor_box, monitor);
    GtkWidget *action_buttons[] = {c->start_button, c->stop_button, c->ssh_restart_button, c->ssh_keys_button, c->ssh_enroll_button, c->ssh_revoke_button, c->ssh_rollback_button, c->ssh_generate_button, c->ssh_autostart_button, c->ssh_deploy_button, c->ssh_deploy_rollback_button, c->ssh_wakelock_button, c->boot_cron_button, c->boot_helpers_button, c->graphics_select_button,
        c->graphics_api_button, c->history_button, c->desktop_log_button, c->logs_button,
        c->audit_logs_button, c->cron_button, c->cron_history_button, c->cron_manage_button,
        c->cron_start_button, c->cron_stop_button, c->timezone_set_button, c->software_button, c->ai_model_install_button, c->ai_model_remove_button, c->ai_run_button, c->ai_auto_run_button, c->ai_gpu_status_button, c->ai_gpu_run_button, c->ai_npu_status_button, c->ai_npu_install_button, c->ai_npu_run_button, c->terminal_service_button, c->terminal_open_button,
        c->proot_box};
    gboolean has_actions = FALSE;
    for (guint i = 0; i < G_N_ELEMENTS(action_buttons); i++)
        has_actions = has_actions || gtk_widget_get_visible(action_buttons[i]);
    gtk_widget_set_visible(c->action_scroll, has_actions);
    if (desktop || graphics) run_bridge(c, "inspect", r->id, NULL, NULL, NULL, NULL);
    else if (monitor) run_bridge(c, "monitor", NULL, NULL, NULL, NULL, NULL);
    else run_bridge(c, "inspect", r->id, NULL, NULL, NULL, NULL);
}
static void resource_selected(GtkListBox *box, GtkListBoxRow *row, gpointer data) {
    (void)box; Center *c = data; if (!row) return;
    Resource *r = g_object_get_data(G_OBJECT(row), "resource"); show_resource(c, r);
}
static gint resource_name_compare(gconstpointer a, gconstpointer b, gpointer data) {
    (void)data;
    const Resource *left = *(Resource * const *)a;
    const Resource *right = *(Resource * const *)b;
    return g_utf8_collate(left->name, right->name);
}
static void fill_resource_rows(Center *c) {
    clear_rows(c->resource_list); const gchar *query=gtk_editable_get_text(GTK_EDITABLE(c->search));
    gchar *needle=g_utf8_strdown(query?query:"",-1);
    GPtrArray *visible = g_ptr_array_new();
    for (guint i = 0; i < c->resources->len; i++) {
        Resource *r = g_ptr_array_index(c->resources, i); if (g_strcmp0(r->category, c->selected_category)) continue;
        gchar *raw=g_strconcat(r->name," ",r->description,NULL); gchar *haystack=g_utf8_strdown(raw,-1); g_free(raw);
        gboolean match=!needle||!*needle||g_strstr_len(haystack,-1,needle)!=NULL; g_free(haystack); if(!match) continue;
        g_ptr_array_add(visible, r);
    }
    g_ptr_array_sort_with_data(visible, (GCompareDataFunc)resource_name_compare, NULL);
    for (guint i = 0; i < visible->len; i++) {
        Resource *r = g_ptr_array_index(visible, i);
        GtkWidget *line = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3); gchar *numbered = g_strdup_printf("%02u  %s", i + 1, r->name); GtkWidget *title = gtk_label_new(numbered); g_free(numbered);
        GtkWidget *meta = gtk_label_new(status_label(r->status)); gtk_label_set_wrap(GTK_LABEL(title),TRUE); gtk_label_set_wrap_mode(GTK_LABEL(title),PANGO_WRAP_WORD_CHAR); gtk_label_set_max_width_chars(GTK_LABEL(title),22); gtk_widget_set_hexpand(title,TRUE); gtk_widget_set_halign(title,GTK_ALIGN_FILL);
        gtk_widget_set_halign(meta, GTK_ALIGN_START); gtk_widget_add_css_class(meta, "dim-label");
        gtk_box_append(GTK_BOX(line), title); gtk_box_append(GTK_BOX(line), meta);
        GtkWidget *listrow = gtk_list_box_row_new(); gtk_list_box_row_set_child(GTK_LIST_BOX_ROW(listrow), line);
        g_object_set_data(G_OBJECT(listrow), "resource", r); gtk_list_box_append(GTK_LIST_BOX(c->resource_list), listrow);
    }
    g_ptr_array_unref(visible);
    GtkListBoxRow *first = gtk_list_box_get_row_at_index(GTK_LIST_BOX(c->resource_list), 0);
    if (first) gtk_list_box_select_row(GTK_LIST_BOX(c->resource_list), first);
    g_free(needle);
}
static void category_selected(GtkListBox *box, GtkListBoxRow *row, gpointer data) {
    (void)box; Center *c = data; if (!row) return;
    const gchar *id = g_object_get_data(G_OBJECT(row), "category-id");
    g_free(c->selected_category); c->selected_category = g_strdup(id); fill_resource_rows(c);
}
static void search_changed(GtkEditable *entry, gpointer data) {
    (void)entry; Center *c=data; if(c->selected_category) fill_resource_rows(c);
}
static void append_category(Center *c, gchar **fields) {
    GtkWidget *row = gtk_list_box_row_new(); gchar *numbered = g_strdup_printf("%u. %s", ++c->category_count, fields[2]); GtkWidget *label = gtk_label_new(numbered); g_free(numbered);
    gtk_label_set_wrap(GTK_LABEL(label),TRUE); gtk_label_set_wrap_mode(GTK_LABEL(label),PANGO_WRAP_WORD_CHAR); gtk_label_set_max_width_chars(GTK_LABEL(label),22); gtk_widget_set_hexpand(label,TRUE); gtk_widget_set_halign(label,GTK_ALIGN_FILL); gtk_list_box_row_set_child(GTK_LIST_BOX_ROW(row), label);
    g_object_set_data_full(G_OBJECT(row), "category-id", g_strdup(fields[1]), g_free);
    gtk_list_box_append(GTK_LIST_BOX(c->category_list), row);
}
static void append_resource(Center *c, gchar **f) {
    Resource *r = g_new0(Resource, 1); r->id=g_strdup(f[1]); r->category=g_strdup(f[2]);
    r->name=g_strdup(f[3]); r->status=g_strdup(f[4]); r->availability=g_strdup(f[5]); r->description=g_strdup(f[6]); r->operations=g_strdup(f[7] ? f[7] : "");
    g_ptr_array_add(c->resources, r);
}
static void load_catalog(Center *c) {
    gchar *script = bridge_path(), *python = python_path(), *out = NULL, *err = NULL; gint status = 0; GError *error = NULL;
    if (!script || !g_file_test(script, G_FILE_TEST_IS_REGULAR)) { gtk_label_set_text(GTK_LABEL(c->notice), "Set TERNUXX_CHECKOUT to the Native Termux checkout."); goto done; }
    gchar *argv[] = {python, script, "catalog", NULL};
    if (!g_spawn_sync(NULL, argv, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, &out, &err, &status, &error) || status != 0) {
        gtk_label_set_text(GTK_LABEL(c->notice), error ? error->message : (err && *err ? err : "Catalog request failed")); goto done;
    }
    gchar **lines = g_strsplit(out, "\n", -1);
    for (guint i=0; lines[i]; i++) {
        gchar **f=g_strsplit(lines[i], "\t", 8);
        if (f[0] && g_strcmp0(f[0],"C")==0 && f[1] && f[2]) append_category(c,f);
        else if (f[0] && g_strcmp0(f[0],"R")==0 && f[6]) append_resource(c,f);
        g_strfreev(f);
    }
    g_strfreev(lines); GtkListBoxRow *first=gtk_list_box_get_row_at_index(GTK_LIST_BOX(c->category_list),0);
    if (first) gtk_list_box_select_row(GTK_LIST_BOX(c->category_list), first);
    gtk_label_set_text(GTK_LABEL(c->notice), "Connected to Native Termux shared management service");
done:
    g_free(script); g_free(python); g_free(out); g_free(err); g_clear_error(&error);
}
static void confirmed_action(GObject *source, GAsyncResult *result, gpointer user_data) {
    GtkAlertDialog *dialog = GTK_ALERT_DIALOG(source); Request *request = user_data; GError *error = NULL;
    int choice = gtk_alert_dialog_choose_finish(dialog, result, &error);
    if (!error && choice == 1) {
        if (g_str_has_prefix(request->action, "ssh-apply-"))
            run_bridge(request->center, request->action, "confirmed", request->resource_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-key-add-apply") == 0 || g_strcmp0(request->action, "ssh-key-remove-apply") == 0)
            run_bridge(request->center, request->action, "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-key-rollback-apply") == 0)
            run_bridge(request->center, "ssh-key-rollback-apply", request->resource_id, request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-client-key-apply") == 0)
            run_bridge(request->center, "ssh-client-key-apply", "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-autostart-apply") == 0)
            run_bridge(request->center, "ssh-autostart-apply", "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-deploy-apply") == 0)
            run_bridge(request->center, "ssh-deploy-apply", "confirmed", request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-deploy-rollback-apply") == 0)
            run_bridge(request->center, "ssh-deploy-rollback-apply", request->resource_id, request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "ssh-wakelock-apply") == 0)
            run_bridge(request->center, "ssh-wakelock-apply", "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "boot-cron-apply") == 0)
            run_bridge(request->center, "boot-cron-apply", request->resource_id, request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "boot-helpers-apply") == 0)
            run_bridge_full(request->center, "boot-helpers-apply", request->resource_id, request->detail_id,
                request->plan_id, request->extra_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "shortcut-apply") == 0)
            run_bridge(request->center, "shortcut-apply", request->resource_id, request->detail_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "proot-shortcut-apply") == 0)
            run_bridge(request->center, "proot-shortcut-apply", request->resource_id, request->detail_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "proot-shortcut-sync-apply") == 0)
            run_bridge(request->center, "proot-shortcut-sync-apply", "confirmed", request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "proot-shortcut-rollback-apply") == 0)
            run_bridge(request->center, "proot-shortcut-rollback-apply", "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "proot-stop-apply") == 0)
            run_bridge(request->center, "proot-stop-apply", request->resource_id, request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "proot-reconcile-apply") == 0)
            run_bridge(request->center, "proot-reconcile-apply", request->resource_id, request->plan_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "cron-apply") == 0)
            run_bridge(request->center, "cron-apply", request->plan_id, NULL, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "cron-scheduler-start") == 0)
            run_bridge(request->center, "cron-scheduler", "start", "10", NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "cron-scheduler-stop") == 0)
            run_bridge(request->center, "cron-scheduler", "stop", NULL, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "terminal-service-apply") == 0)
            run_bridge(request->center, "terminal-service-apply", "confirmed", request->resource_id, request->plan_id, NULL, NULL);
        else if (g_strcmp0(request->action, "cpu-model-apply") == 0)
            run_bridge(request->center, "cpu-model-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "recovery.resolve") == 0)
            run_bridge(request->center, "recovery-resolve-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "recovery.rollback.apply") == 0)
            run_bridge(request->center, "recovery-rollback-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "backup-create-apply") == 0)
            run_bridge(request->center, "backup-create-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "restore-apply") == 0)
            run_bridge(request->center, "restore-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "continuity-prepare-apply") == 0)
            run_bridge(request->center, "continuity-prepare-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "continuity-verify-apply") == 0)
            run_bridge(request->center, "continuity-verify-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "reboot-test-prepare-apply") == 0)
            run_bridge(request->center, "reboot-test-prepare-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "reboot-test-verify-apply") == 0)
            run_bridge(request->center, "reboot-test-verify-apply", request->resource_id, request->plan_id, "confirmed", NULL, NULL);
        else if (g_strcmp0(request->action, "start-desktop") == 0)
            run_bridge(request->center, request->action, "confirmed", request->resource_id, NULL, NULL, NULL);
        else if (g_strcmp0(request->action, "software-apply") == 0) {
            gchar *confirmation = g_ascii_strup(request->detail_id, -1);
            run_bridge(request->center, "software-apply", request->resource_id, request->detail_id,
                       request->plan_id, confirmation, NULL);
            g_free(confirmation);
        }
        else
            run_bridge(request->center, request->action, "confirmed", NULL, NULL, NULL, NULL);
    }
    else if (error) { gtk_label_set_text(GTK_LABEL(request->center->notice), error->message); g_clear_error(&error); }
    else gtk_label_set_text(GTK_LABEL(request->center->notice), "Action cancelled");
    g_free(request->action); g_free(request->resource_id); g_free(request->detail_id); g_free(request->plan_id); g_free(request->extra_id); g_free(request);
}
static void ask_terminal_service_confirmation(Center *c, const gchar *plan_id,
                                              const gchar *action, const gchar *impact) {
    const gboolean install = g_strcmp0(action, "install") == 0;
    gchar *message = g_strdup_printf("Review this exact Ternuxx terminal broker service plan:\n\n%s\n\n%s? This does not start a Debian guest.",
        impact, install ? "Register the fixed Runit service" : "Start the fixed Runit service");
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", install ? "Install broker service" : "Start broker service", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("terminal-service-apply");
    request->resource_id = g_strdup(action); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact terminal broker service plan");
    g_object_unref(dialog); g_free(message);
}

static void terminal_service_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "terminal-service-prepare", NULL, NULL, NULL, NULL, NULL);
}


static void terminal_spawn_done(VteTerminal *terminal, GPid pid, GError *error, gpointer user_data) {
    (void)terminal; (void)pid;
    Center *c = user_data;
    if (error) gtk_label_set_text(GTK_LABEL(c->notice), error->message);
    else gtk_label_set_text(GTK_LABEL(c->notice), "Debian terminal attached. Closing the terminal detaches; the guest session continues.");
}

static void open_debian_terminal(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *prefix = g_getenv("PREFIX");
    if (!prefix || g_strcmp0(prefix, "/data/data/com.termux/files/usr") != 0) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Native Termux is required to open the managed Debian terminal.");
        return;
    }
    gchar *tx = g_build_filename(prefix, "bin", "tx", NULL);
    if (!g_file_test(tx, G_FILE_TEST_IS_EXECUTABLE)) {
        gtk_label_set_text(GTK_LABEL(c->notice), "The installed Native `tx` command is unavailable.");
        g_free(tx); return;
    }
    GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Ternuxx — Debian terminal");
    gtk_window_set_default_size(GTK_WINDOW(window), 900, 600);
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window));
    gtk_window_set_destroy_with_parent(GTK_WINDOW(window), TRUE);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    GtkWidget *note = gtk_label_new("Fixed Debian login profile. Ctrl-] detaches; closing this window also detaches without stopping the guest.");
    gtk_label_set_wrap(GTK_LABEL(note), TRUE); gtk_box_append(GTK_BOX(box), note);
    VteTerminal *terminal = VTE_TERMINAL(vte_terminal_new());
    vte_terminal_set_scrollback_lines(terminal, 10000);
    gtk_widget_set_vexpand(GTK_WIDGET(terminal), TRUE); gtk_widget_set_hexpand(GTK_WIDGET(terminal), TRUE);
    gtk_box_append(GTK_BOX(box), GTK_WIDGET(terminal));
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_window_present(GTK_WINDOW(window));
    gchar *argv[] = {tx, "terminal", "start", NULL};
    vte_terminal_spawn_async(terminal, VTE_PTY_DEFAULT, NULL, argv, NULL,
        G_SPAWN_DEFAULT, NULL, NULL, NULL, -1, NULL, terminal_spawn_done, c);
    g_free(tx);
}

static void guest_setup_spawn_done(VteTerminal *terminal, GPid pid, GError *error, gpointer user_data) {
    (void)terminal; (void)pid;
    Center *c = user_data;
    if (error) gtk_label_set_text(GTK_LABEL(c->notice), error->message);
    else gtk_label_set_text(GTK_LABEL(c->notice), "Guided managed guest installer finished or was cancelled. Existing guests remain preserved.");
}

static void open_debian_setup(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *prefix = g_getenv("PREFIX");
    if (!prefix || g_strcmp0(prefix, "/data/data/com.termux/files/usr") != 0) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Native Termux is required to install a managed proot guest.");
        return;
    }
    gchar *tx = g_build_filename(prefix, "bin", "tx", NULL);
    if (!g_file_test(tx, G_FILE_TEST_IS_EXECUTABLE)) {
        gtk_label_set_text(GTK_LABEL(c->notice), "The installed Native `tx` command is unavailable.");
        g_free(tx); return;
    }
    guint distro_index = gtk_drop_down_get_selected(GTK_DROP_DOWN(c->proot_distro));
    if (!c->install_profiles || distro_index >= c->install_profiles->len) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Managed distro catalog is unavailable; refresh the management center.");
        g_free(tx); return;
    }
    InstallProfile *profile = g_ptr_array_index(c->install_profiles, distro_index);
    GString *desktops = g_string_new(NULL);
    for (guint i = 0; i < profile->desktops->len; i++) {
        if (i >= c->proot_desktop_checks->len) continue;
        GtkWidget *check = g_ptr_array_index(c->proot_desktop_checks, i);
        if (!gtk_check_button_get_active(GTK_CHECK_BUTTON(check))) continue;
        const gchar *desktop_id = g_object_get_data(G_OBJECT(check), "install-desktop-id");
        if (!desktop_id) continue;
        if (desktops->len) g_string_append_c(desktops, ',');
        g_string_append(desktops, desktop_id);
    }
    if (!desktops->len) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Select at least one desktop environment.");
        g_string_free(desktops, TRUE);
        g_free(tx); return;
    }
    GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Ternuxx — Managed proot setup");
    gtk_window_set_default_size(GTK_WINDOW(window), 820, 520);
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window));
    gtk_window_set_destroy_with_parent(GTK_WINDOW(window), TRUE);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    GtkWidget *note = gtk_label_new("Guided Ternuxx-managed distro install. Review the pinned target and confirm in this terminal; passwords are hidden. Existing guests are preserved.");
    gtk_label_set_wrap(GTK_LABEL(note), TRUE); gtk_box_append(GTK_BOX(box), note);
    VteTerminal *terminal = VTE_TERMINAL(vte_terminal_new());
    vte_terminal_set_scrollback_lines(terminal, 5000);
    gtk_widget_set_vexpand(GTK_WIDGET(terminal), TRUE); gtk_widget_set_hexpand(GTK_WIDGET(terminal), TRUE);
    gtk_box_append(GTK_BOX(box), GTK_WIDGET(terminal));
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_window_present(GTK_WINDOW(window));
    gchar *argv[] = {tx, "install", profile->alias, "--desktops", desktops->str, NULL};
    vte_terminal_spawn_async(terminal, VTE_PTY_DEFAULT, NULL, argv, NULL,
        G_SPAWN_DEFAULT, NULL, NULL, NULL, -1, NULL, guest_setup_spawn_done, c);
    g_string_free(desktops, TRUE);
    g_free(tx);
}

static void ask_recovery_confirmation(Center *c, const gchar *action, const gchar *resource_id,
                                      const gchar *plan_id, const gchar *summary) {
    gboolean backup = g_strcmp0(action, "backup-create-apply") == 0;
    gboolean restore = g_strcmp0(action, "restore-apply") == 0;
    gboolean checkpoint_prepare = g_strcmp0(action, "continuity-prepare-apply") == 0;
    gboolean checkpoint_verify = g_strcmp0(action, "continuity-verify-apply") == 0;
    gboolean reboot_test_prepare = g_strcmp0(action, "reboot-test-prepare-apply") == 0;
    gboolean reboot_test_verify = g_strcmp0(action, "reboot-test-verify-apply") == 0;
    const gchar *what = backup ? "Native configuration backup" : restore ? "Native boot-profile restore" :
        checkpoint_prepare ? "Native continuity checkpoint" : checkpoint_verify ? "Continuity boot observation" :
        reboot_test_prepare ? "Native reboot qualification baseline" : reboot_test_verify ? "Reboot qualification verification" :
        g_strcmp0(action, "recovery.resolve") == 0 ? "Native operation reconciliation" : "Native restore rollback";
    const gchar *effect = backup ? "Create this backup" : restore ? "Apply this restore and create its rollback snapshot" :
        checkpoint_prepare ? "Write this private checkpoint without rebooting or resuming work" :
        checkpoint_verify ? "Write this observation report without rebooting or resuming work" :
        reboot_test_prepare ? "Write this private NOT_READY evidence record; this does not reboot the device" :
        reboot_test_verify ? "Record this evidence-only verification; this does not reboot or resume work" :
        g_strcmp0(action, "recovery.resolve") == 0 ? "Reconcile this operation record" : "Restore the reviewed rollback snapshot";
    const gchar *button = backup ? "Create backup" : restore ? "Restore profile" :
        checkpoint_prepare ? "Create checkpoint" : checkpoint_verify ? "Record observation" :
        reboot_test_prepare ? "Create NOT_READY record" : reboot_test_verify ? "Record verification" :
        g_strcmp0(action, "recovery.resolve") == 0 ? "Reconcile record" : "Apply rollback";
    gchar *message = g_strdup_printf("Review this exact %s plan:\n\n%s\n\n%s?", what, summary, effect);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", button, NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c; request->action = g_strdup(action);
    request->resource_id = g_strdup(resource_id); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact Native backup or restore plan");
    g_object_unref(dialog); g_free(message);
}

static void ask_cpu_model_confirmation(Center *c, const gchar *action,
                                        const gchar *plan_id, const gchar *summary) {
    gboolean install = g_strcmp0(action, "install") == 0;
    gchar *message = g_strdup_printf("Review this exact pinned CPU model plan:\n\n%s\n\n%s only this Ternuxx-owned model file?",
        summary, install ? "Download" : "Remove");
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", install ? "Download model" : "Remove model", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("cpu-model-apply"); request->resource_id = g_strdup(action);
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact pinned CPU model change");
    g_object_unref(dialog); g_free(message);
}

static void software_preview_clicked(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data); Center *c = g_object_get_data(G_OBJECT(window), "software-center");
    GtkWidget *app = g_object_get_data(G_OBJECT(window), "software-app");
    GtkWidget *action = g_object_get_data(G_OBJECT(window), "software-action");
    GtkWidget *path = g_object_get_data(G_OBJECT(window), "software-path");
    const gchar *apps[] = {"process-monitor", "terminal-multiplexer", "directory-tree"};
    const gchar *actions[] = {"install", "update", "remove", "run"};
    guint ai = gtk_drop_down_get_selected(GTK_DROP_DOWN(app)); guint xi = gtk_drop_down_get_selected(GTK_DROP_DOWN(action));
    if (ai >= G_N_ELEMENTS(apps) || xi >= G_N_ELEMENTS(actions)) return;
    if (xi == 3) {
        const gchar *selected_path = gtk_editable_get_text(GTK_EDITABLE(path));
        if (ai != 2 || !selected_path || !*selected_path) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Choose directory-tree and a HOME-relative path."); return;
        }
        run_bridge(c, "software-run", selected_path, NULL, NULL, NULL, NULL);
    } else {
        run_bridge(c, "software-preview", apps[ai], actions[xi], NULL, NULL, NULL);
    }
    gtk_window_destroy(GTK_WINDOW(window));
}
static void software_apps(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Native Termux optional apps"); gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window));
    gtk_window_set_modal(GTK_WINDOW(window), TRUE); gtk_window_set_default_size(GTK_WINDOW(window), 360, 220);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8); gtk_widget_set_margin_top(box, 16); gtk_widget_set_margin_bottom(box, 16); gtk_widget_set_margin_start(box, 16); gtk_widget_set_margin_end(box, 16);
    gtk_box_append(GTK_BOX(box), gtk_label_new("Choose a curated app and transaction. The shared service validates current installed state and APT origin."));
    const char *apps[] = {"process-monitor", "terminal-multiplexer", "directory-tree", NULL}; GtkWidget *app = gtk_drop_down_new_from_strings(apps);
    const char *actions[] = {"install", "update", "remove", "run (directory-tree only)", NULL}; GtkWidget *action = gtk_drop_down_new_from_strings(actions);
    GtkWidget *path = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(path), "HOME-relative file or directory path");
    gtk_box_append(GTK_BOX(box), app); gtk_box_append(GTK_BOX(box), action); gtk_box_append(GTK_BOX(box), path);
    GtkWidget *preview = gtk_button_new_with_label("Preview package changes or run selected path"); gtk_box_append(GTK_BOX(box), preview);
    g_object_set_data(G_OBJECT(window), "software-center", c); g_object_set_data(G_OBJECT(window), "software-app", app); g_object_set_data(G_OBJECT(window), "software-action", action); g_object_set_data(G_OBJECT(window), "software-path", path);
    g_signal_connect(preview, "clicked", G_CALLBACK(software_preview_clicked), window); gtk_window_set_child(GTK_WINDOW(window), box); gtk_window_present(GTK_WINDOW(window));
}

static void cpu_model_install(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "cpu-model-preview", "install", NULL, NULL, NULL, NULL);
}
static void cpu_model_remove(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "cpu-model-preview", "remove", NULL, NULL, NULL, NULL);
}
static void cpu_prompt_submit(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data);
    Center *c = g_object_get_data(G_OBJECT(window), "cpu-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "cpu-entry");
    const gchar *prompt = gtk_editable_get_text(GTK_EDITABLE(entry));
    if (!prompt || !*prompt || strlen(prompt) > 4096 || strchr(prompt, '\n') || strchr(prompt, '\r')) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Use one non-empty prompt line under 4096 UTF-8 bytes.");
        return;
    }
    run_bridge_input(c, "cpu-run", prompt);
    gtk_window_destroy(GTK_WINDOW(window));
}
static void cpu_prompt_dialog(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    GtkWidget *window = gtk_window_new(); gtk_window_set_title(GTK_WINDOW(window), "Run local CPU prompt");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 440, 180);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_box_append(GTK_BOX(box), gtk_label_new("Runs on this device: CPU only, 4 threads, 512-token context, up to 64 output tokens. Prompt is sent only to the local shared service."));
    GtkWidget *entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "One-line prompt (up to 4096 UTF-8 bytes)");
    gtk_box_append(GTK_BOX(box), entry); GtkWidget *run = gtk_button_new_with_label("Run on CPU"); gtk_box_append(GTK_BOX(box), run);
    g_object_set_data(G_OBJECT(window), "cpu-center", c); g_object_set_data(G_OBJECT(window), "cpu-entry", entry);
    g_signal_connect(run, "clicked", G_CALLBACK(cpu_prompt_submit), window); gtk_window_present(GTK_WINDOW(window));
}

static void auto_prompt_submit(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data);
    Center *c = g_object_get_data(G_OBJECT(window), "auto-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "auto-entry");
    GtkWidget *model = g_object_get_data(G_OBJECT(window), "auto-model");
    const gchar *prompt = gtk_editable_get_text(GTK_EDITABLE(entry));
    const gchar *models[] = {"qwen2.5-1.5b-instruct-q4_k_m", "qwen2.5-1.5b-instruct-q4_0"};
    guint selected = gtk_drop_down_get_selected(GTK_DROP_DOWN(model));
    if (!prompt || !*prompt || strlen(prompt) > 4096 || strchr(prompt, '\n') || strchr(prompt, '\r')) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Use one non-empty prompt line under 4096 UTF-8 bytes.");
        return;
    }
    if (selected >= G_N_ELEMENTS(models)) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Choose a supported local model.");
        return;
    }
    run_bridge_input_full(c, "auto-run", prompt, models[selected]);
    gtk_window_destroy(GTK_WINDOW(window));
}
static void auto_prompt_dialog(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Run automatic local inference");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 460, 230);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_box_append(GTK_BOX(box), gtk_label_new("Select a local model. Routing prefers configured HTP, then Vulkan, then CPU; the actual backend is reported."));
    const char *models[] = {"qwen2.5-1.5b-instruct-q4_k_m", "qwen2.5-1.5b-instruct-q4_0", NULL};
    GtkWidget *model = gtk_drop_down_new_from_strings(models); gtk_box_append(GTK_BOX(box), model);
    GtkWidget *entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "One-line prompt (up to 4096 UTF-8 bytes)"); gtk_box_append(GTK_BOX(box), entry);
    GtkWidget *run = gtk_button_new_with_label("Run automatically"); gtk_box_append(GTK_BOX(box), run);
    g_object_set_data(G_OBJECT(window), "auto-center", c); g_object_set_data(G_OBJECT(window), "auto-entry", entry);
    g_object_set_data(G_OBJECT(window), "auto-model", model);
    g_signal_connect(run, "clicked", G_CALLBACK(auto_prompt_submit), window); gtk_window_present(GTK_WINDOW(window));
}

static void gpu_prompt_submit(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data);
    Center *c = g_object_get_data(G_OBJECT(window), "gpu-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "gpu-entry");
    GtkWidget *device_entry = g_object_get_data(G_OBJECT(window), "gpu-device-entry");
    const gchar *prompt = gtk_editable_get_text(GTK_EDITABLE(entry));
    const gchar *device_id = gtk_editable_get_text(GTK_EDITABLE(device_entry));
    if (!prompt || !*prompt || strlen(prompt) > 4096 || strchr(prompt, '\n') || strchr(prompt, '\r')) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Use one non-empty prompt line under 4096 UTF-8 bytes.");
        return;
    }
    if (device_id && strlen(device_id) > 64) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Vulkan device ID is too long."); return;
    }
    run_bridge_input_full(c, "gpu-run", prompt, device_id);
    gtk_window_destroy(GTK_WINDOW(window));
}
static void gpu_prompt_dialog(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Run local Vulkan prompt");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 440, 180);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_box_append(GTK_BOX(box), gtk_label_new("Explicit Vulkan inference requires a listed device and verified GPU-layer offload; CPU fallback is disabled. Leave the device ID blank only when one Vulkan device is listed."));
    GtkWidget *device_entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(device_entry), "Exact ID from List Vulkan inference devices (e.g. Vulkan0)");
    gtk_box_append(GTK_BOX(box), device_entry);
    GtkWidget *entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "One-line prompt (up to 4096 UTF-8 bytes)");
    gtk_box_append(GTK_BOX(box), entry); GtkWidget *run = gtk_button_new_with_label("Run on Vulkan"); gtk_box_append(GTK_BOX(box), run);
    g_object_set_data(G_OBJECT(window), "gpu-center", c); g_object_set_data(G_OBJECT(window), "gpu-entry", entry);
    g_object_set_data(G_OBJECT(window), "gpu-device-entry", device_entry);
    g_signal_connect(run, "clicked", G_CALLBACK(gpu_prompt_submit), window); gtk_window_present(GTK_WINDOW(window));
}
static void gpu_status_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "gpu-status", NULL, NULL, NULL, NULL, NULL);
}
static void npu_status_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "npu-status", NULL, NULL, NULL, NULL, NULL);
}
static void npu_install_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "npu-runtime-preview", NULL, NULL, NULL, NULL, NULL);
}
static void npu_run_submit(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data);
    Center *c = g_object_get_data(G_OBJECT(window), "npu-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "npu-entry");
    const gchar *prompt = gtk_editable_get_text(GTK_EDITABLE(entry));
    if (!prompt || !*prompt || strlen(prompt) > 4096 || strchr(prompt, '\n') || strchr(prompt, '\r')) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Use one non-empty prompt line under 4096 UTF-8 bytes.");
        return;
    }
    run_bridge_input(c, "npu-run", prompt);
    gtk_window_destroy(GTK_WINDOW(window));
}
static void npu_run_dialog(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Run experimental HTP prompt");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 460, 220);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(window), box);
    GtkWidget *help = gtk_label_new("Experimental Native HTP0 inference. Requires verified full layer offload and fails closed; CPU fallback is disabled. The local shared service checks HTP0 availability before running.");
    gtk_label_set_wrap(GTK_LABEL(help), TRUE); gtk_label_set_xalign(GTK_LABEL(help), 0.0f); gtk_box_append(GTK_BOX(box), help);
    GtkWidget *entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "One-line local prompt (up to 4096 UTF-8 bytes)"); gtk_box_append(GTK_BOX(box), entry);
    GtkWidget *run = gtk_button_new_with_label("Run on HTP0"); gtk_box_append(GTK_BOX(box), run);
    g_object_set_data(G_OBJECT(window), "npu-center", c); g_object_set_data(G_OBJECT(window), "npu-entry", entry);
    g_signal_connect(run, "clicked", G_CALLBACK(npu_run_submit), window); gtk_window_present(GTK_WINDOW(window));
}
static void npu_install_submit(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = GTK_WIDGET(data);
    Center *c = g_object_get_data(G_OBJECT(window), "npu-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "npu-install-entry");
    const gchar *confirmation = gtk_editable_get_text(GTK_EDITABLE(entry));
    const gchar *plan_id = g_object_get_data(G_OBJECT(window), "npu-plan-id");
    if (!confirmation || g_strcmp0(confirmation, "INSTALL") != 0 || !plan_id) {
        if (c) gtk_label_set_text(GTK_LABEL(c->notice), "Type INSTALL exactly to apply this preview; no change was made.");
        return;
    }
    run_bridge(c, "npu-runtime-apply", plan_id, "INSTALL", NULL, NULL, NULL);
    gtk_window_destroy(GTK_WINDOW(window));
}
static void show_npu_install_confirmation(Center *c, const gchar *plan_id, const gchar *summary) {
    GtkWidget *window = gtk_window_new(); gtk_window_set_title(GTK_WINDOW(window), "Review experimental Snapdragon runtime");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 480, 300);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    GtkWidget *help = gtk_label_new(NULL);
    gchar *message = g_strdup_printf("Review this exact pinned MIT Snapdragon runtime preview. It is stored only in Ternuxx private app storage. No Android system/vendor files are copied or changed.\n\n%s", summary);
    gtk_label_set_text(GTK_LABEL(help), message); gtk_label_set_wrap(GTK_LABEL(help), TRUE); gtk_label_set_xalign(GTK_LABEL(help), 0.0f); gtk_box_append(GTK_BOX(box), help);
    GtkWidget *entry = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "Type INSTALL exactly to apply this preview"); gtk_box_append(GTK_BOX(box), entry);
    GtkWidget *apply = gtk_button_new_with_label("Apply exact preview"); gtk_box_append(GTK_BOX(box), apply);
    g_object_set_data(G_OBJECT(window), "npu-center", c); g_object_set_data_full(G_OBJECT(window), "npu-plan-id", g_strdup(plan_id), g_free);
    g_object_set_data(G_OBJECT(window), "npu-install-entry", entry);
    g_signal_connect(apply, "clicked", G_CALLBACK(npu_install_submit), window);
    gtk_window_set_child(GTK_WINDOW(window), box); gtk_window_present(GTK_WINDOW(window));
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact pinned experimental NPU runtime preview");
    g_free(message);
}

static void proot_shortcut_list_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "proot-shortcut-list", NULL, NULL, NULL, NULL, NULL);
}
static void proot_app_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *app_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_app_entry));
    if (!app_id || !*app_id) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter a Debian app ID first."); return; }
    run_bridge(c, "proot-app-launch", app_id, NULL, NULL, NULL, NULL);
}
static void proot_shortcut_clicked(GtkButton *button, gpointer data) {
    Center *c = data;
    const gchar *app_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_shortcut_entry));
    const gchar *action = g_object_get_data(G_OBJECT(button), "proot-shortcut-action");
    if (!app_id || !*app_id || !action) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter a Debian app ID first."); return; }
    run_bridge(c, "proot-shortcut-preview", action, app_id, NULL, NULL, NULL);
}
static void proot_shortcut_sync_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "proot-shortcut-sync-preview", NULL, NULL, NULL, NULL, NULL);
}
static void proot_shortcut_rollback_list_clicked(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "proot-shortcut-rollback-list", NULL, NULL, NULL, NULL, NULL);
}
static void proot_shortcut_rollback_preview_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *rollback_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_sync_rollback_entry));
    if (!rollback_id || !*rollback_id) { gtk_label_set_text(GTK_LABEL(c->notice), "List prior syncs and enter an applied rollback ID first."); return; }
    run_bridge(c, "proot-shortcut-rollback-preview", rollback_id, NULL, NULL, NULL, NULL);
}
static void proot_session_stop_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *session_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_session_entry));
    if (!session_id || !*session_id) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter a Ternuxx-owned session ID first."); return; }
    run_bridge(c, "proot-stop-preview", session_id, NULL, NULL, NULL, NULL);
}
static void proot_session_reconcile_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *session_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_session_entry));
    if (!session_id || !*session_id) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter a Ternuxx-owned session ID first."); return; }
    run_bridge(c, "proot-reconcile-preview", session_id, NULL, NULL, NULL, NULL);
}
static void proot_replay_retire_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    if (g_strcmp0(c->selected_resource_id, "proot.replay-guests") != 0) return;
    const gchar *alias = gtk_editable_get_text(GTK_EDITABLE(c->proot_replay_alias_entry));
    run_bridge(c, "proot-replay-retire-preview", alias, NULL, NULL, NULL, NULL);
}
static void proot_replay_restore_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    if (g_strcmp0(c->selected_resource_id, "proot.replay-guests") != 0) return;
    const gchar *alias = gtk_editable_get_text(GTK_EDITABLE(c->proot_replay_alias_entry));
    const gchar *backup_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_replay_backup_entry));
    run_bridge(c, "proot-replay-restore-preview", alias, backup_id, NULL, NULL, NULL);
}
static void proot_replay_cancel_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; clear_replay_review(c);
    gtk_label_set_text(GTK_LABEL(c->notice), "Replay guest plan cancelled; no change was made.");
}
static void proot_replay_apply_clicked(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    gboolean retire = g_strcmp0(c->replay_review_action, "proot-replay-retire-apply") == 0;
    gboolean restore = g_strcmp0(c->replay_review_action, "proot-replay-restore-apply") == 0;
    const gchar *alias = gtk_editable_get_text(GTK_EDITABLE(c->proot_replay_alias_entry));
    const gchar *backup_id = gtk_editable_get_text(GTK_EDITABLE(c->proot_replay_backup_entry));
    gboolean exact_target = c->replay_review_alias && g_strcmp0(alias, c->replay_review_alias) == 0
        && c->replay_review_plan && g_regex_match_simple("^[0-9a-f]{64}$", c->replay_review_plan, 0, 0)
        && ((retire && !c->replay_review_backup)
            || (restore && c->replay_review_backup && g_strcmp0(backup_id, c->replay_review_backup) == 0));
    if (g_strcmp0(c->selected_resource_id, "proot.replay-guests") != 0 || !exact_target) {
        gtk_label_set_text(GTK_LABEL(c->notice), "The reviewed target changed. Create a fresh replay guest preview.");
        clear_replay_review(c); return;
    }
    gchar *action = g_strdup(c->replay_review_action);
    gchar *target_alias = g_strdup(c->replay_review_alias);
    gchar *target_backup = g_strdup(c->replay_review_backup);
    gchar *plan_id = g_strdup(c->replay_review_plan);
    clear_replay_review(c);
    if (retire) run_bridge(c, action, target_alias, plan_id, NULL, NULL, NULL);
    else run_bridge(c, action, target_alias, target_backup, plan_id, NULL, NULL);
    g_free(action); g_free(target_alias); g_free(target_backup); g_free(plan_id);
}
static void ask_proot_confirmation(Center *c, const gchar *action, const gchar *resource_id,
                                   const gchar *detail_id, const gchar *plan_id, const gchar *summary) {
    const gchar *subject = g_strcmp0(action, "proot-stop-apply") == 0
        ? "Stop this verified Ternuxx guest session?"
        : g_strcmp0(action, "proot-reconcile-apply") == 0
            ? "Reconcile this exited Ternuxx session record? No process will be signaled."
        : g_strcmp0(action, "proot-shortcut-sync-apply") == 0
            ? "Synchronize these Debian app and desktop shortcuts?"
        : g_strcmp0(action, "proot-shortcut-rollback-apply") == 0
            ? "Restore this previous Debian shortcut sync?"
            : "Change this Debian shortcut?";
    gchar *message = g_strdup_printf("%s\n\n%s\n\nThe shared service will recheck this exact plan before applying it.", subject, summary);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Confirm", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c; request->action = g_strdup(action);
    request->resource_id = g_strdup(resource_id); request->detail_id = g_strdup(detail_id);
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact Debian change");
    g_object_unref(dialog); g_free(message);
}

static void ask_shortcut_confirmation(Center *c, const gchar *action, const gchar *app_id,
                                      const gchar *plan_id, const gchar *target, const gchar *transition) {
    (void)app_id;
    gchar *message = g_strdup_printf("Confirm %s shortcut change?\n\nTarget: %s\nChange: %s\n\nOnly this exact Ternuxx-owned launcher will change.", action, target, transition);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Confirm", NULL}; gtk_alert_dialog_set_buttons(dialog, choices);
    gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("shortcut-apply"); request->resource_id = g_strdup(action);
    request->detail_id = g_strdup(app_id); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact Native shortcut change");
    g_object_unref(dialog); g_free(message);
}
static void ask_ssh_confirmation(Center *c, const gchar *preview_action, const gchar *plan_id, const gchar *impact) {
    gboolean start = g_strcmp0(preview_action, "ssh-preview-start") == 0;
    gboolean restart = g_strcmp0(preview_action, "ssh-preview-restart") == 0;
    const gchar *verb = start ? "start" : restart ? "restart" : "stop";
    gchar *message = g_strdup_printf("Confirm %s of the Ternuxx-managed SSH service on 127.0.0.1:8023?\n\n%s\n\nOther Native SSH configurations are excluded.", verb, impact);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Confirm", NULL}; gtk_alert_dialog_set_buttons(dialog, choices);
    gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup(start ? "ssh-apply-start" : restart ? "ssh-apply-restart" : "ssh-apply-stop"); request->resource_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing managed SSH service impact");
    g_object_unref(dialog); g_free(message);
}
static void confirm_action(GtkButton *button, gpointer data) {
    Center *c=data; gboolean start=GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button),"start"));
    if (g_str_has_prefix(c->selected_resource_id ? c->selected_resource_id : "", "graphics.")) {
        const gchar *provider = "native";
        if (start) run_bridge(c, "inspect", c->selected_resource_id, NULL, NULL, NULL, NULL);
        else run_bridge(c, "graphics-verify", provider, "opengl", NULL, NULL, NULL);
        return;
    }
    if (g_strcmp0(c->selected_resource_id, "proot.debian.workloads") == 0) {
        run_bridge(c, start ? "proot-status" : "proot-session-list", NULL, NULL, NULL, NULL, NULL);
        return;
    }
    if (g_strcmp0(c->selected_resource_id, "network.ssh.managed-8023") == 0) {
        const gchar *action = button == GTK_BUTTON(c->ssh_restart_button) ? "restart" : start ? "start" : "stop";
        gchar *preview = g_strdup_printf("ssh-preview-%s", action);
        run_bridge(c, preview, NULL, NULL, NULL, NULL, NULL);
        g_free(preview);
        return;
    }
    GtkAlertDialog *dialog=gtk_alert_dialog_new("Confirm native desktop %s?",start?"start":"stop");
    const char *choices[]={"Cancel","Confirm",NULL}; gtk_alert_dialog_set_buttons(dialog,choices);
    gtk_alert_dialog_set_default_button(dialog,0); Request *request=g_new0(Request,1);
    request->center=c; request->action=g_strdup(start?"start-desktop":"stop-desktop");
    if (start) {
        static const char *desktop_ids[] = {"xfce", "lxqt", "mate", "cinnamon", "plasma"};
        guint selected = gtk_drop_down_get_selected(GTK_DROP_DOWN(c->desktop_choice));
        request->resource_id = g_strdup(selected < G_N_ELEMENTS(desktop_ids) ? desktop_ids[selected] : "xfce");
    }
    gtk_alert_dialog_choose(dialog,GTK_WINDOW(c->window),NULL,confirmed_action,request); g_object_unref(dialog);
}
static void graphics_select_done(GObject *source, GAsyncResult *result, gpointer user_data) {
    GtkAlertDialog *dialog=GTK_ALERT_DIALOG(source); Center *c=user_data; GError *error=NULL;
    int choice=gtk_alert_dialog_choose_finish(dialog,result,&error);
    if (!error && choice == 1) run_bridge(c,"graphics-select","termux-zink",NULL,NULL,NULL,NULL);
    else if (!error && choice == 2) run_bridge(c,"graphics-select","kgsl-freedreno",NULL,NULL,NULL,NULL);
    else if (!error && choice == 3) run_bridge(c,"graphics-select","system",NULL,NULL,NULL,NULL);
    else if (error) { gtk_label_set_text(GTK_LABEL(c->notice),error->message); g_clear_error(&error); }
}
static void select_graphics(GtkButton *button, gpointer data) {
    (void)button; Center *c=data;
    GtkAlertDialog *dialog=gtk_alert_dialog_new("Choose a graphics stack for future desktop starts. Termux Zink requires the Native graphical package profile and available Freedreno ICD; it uses stock Termux Mesa. The KGSL option is experimental, device-specific, and must already be extracted; Ternuxx does not install it. Choices affect future desktop starts only.");
    const char *choices[]={"Cancel","Termux Mesa Zink + Freedreno ICD","Experimental KGSL (already present)","Termux system stack",NULL}; gtk_alert_dialog_set_buttons(dialog,choices);
    gtk_alert_dialog_set_default_button(dialog,0); gtk_alert_dialog_choose(dialog,GTK_WINDOW(c->window),NULL,graphics_select_done,c); g_object_unref(dialog);
}
static void graphics_api_done(GObject *source, GAsyncResult *result, gpointer user_data) {
    GtkAlertDialog *dialog = GTK_ALERT_DIALOG(source); Request *request = user_data; GError *error = NULL;
    int choice = gtk_alert_dialog_choose_finish(dialog, result, &error);
    if (!error && choice > 0) {
        const gchar *api = choice == 1 ? "opengl" : choice == 2 ? "gles" : "vulkan";
        run_bridge(request->center, "graphics-verify", request->resource_id, api, NULL, NULL, NULL);
    } else if (error) {
        gtk_label_set_text(GTK_LABEL(request->center->notice), error->message); g_clear_error(&error);
    }
    g_free(request->action); g_free(request->resource_id); g_free(request);
}
static void choose_graphics_api(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    const gchar *provider = "native";
    GtkAlertDialog *dialog = gtk_alert_dialog_new("Choose the graphics API to verify.");
    const char *choices[] = {"Cancel", "OpenGL", "OpenGL ES", "Vulkan", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("graphics-verify"); request->resource_id = g_strdup(provider);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, graphics_api_done, request);
    g_object_unref(dialog);
}
static void show_history(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "history", NULL, NULL, NULL, NULL, NULL);
}
static void cron_form_submit(GtkButton *button, gpointer data) {
    (void)data;
    Center *c = g_object_get_data(G_OBJECT(button), "cron-center");
    GtkWidget *mode = g_object_get_data(G_OBJECT(button), "cron-mode");
    GtkWidget *id = g_object_get_data(G_OBJECT(button), "cron-id");
    GtkWidget *name = g_object_get_data(G_OBJECT(button), "cron-name");
    GtkWidget *update_field = g_object_get_data(G_OBJECT(button), "cron-update-field");
    GtkWidget *action = g_object_get_data(G_OBJECT(button), "cron-action");
    GtkWidget *schedule_type = g_object_get_data(G_OBJECT(button), "cron-schedule-type");
    GtkWidget *schedule_extra = g_object_get_data(G_OBJECT(button), "cron-schedule-extra");
    GtkWidget *timezone = g_object_get_data(G_OBJECT(button), "cron-timezone");
    GtkWidget *expr = g_object_get_data(G_OBJECT(button), "cron-expr");
    const gchar *kind = gtk_editable_get_text(GTK_EDITABLE(mode));
    const gchar *job_id = gtk_editable_get_text(GTK_EDITABLE(id));
    const gchar *name_value = gtk_editable_get_text(GTK_EDITABLE(name));
    const gchar *field_value = gtk_editable_get_text(GTK_EDITABLE(update_field));
    const gchar *action_id = gtk_editable_get_text(GTK_EDITABLE(action));
    const gchar *type_value = gtk_editable_get_text(GTK_EDITABLE(schedule_type));
    const gchar *extra_value = gtk_editable_get_text(GTK_EDITABLE(schedule_extra));
    const gchar *timezone_value = gtk_editable_get_text(GTK_EDITABLE(timezone));
    const gchar *cron_expr = gtk_editable_get_text(GTK_EDITABLE(expr));
    if (g_strcmp0(kind, "create") == 0) {
        gboolean supported_type = g_strcmp0(type_value, "cron") == 0 || g_strcmp0(type_value, "interval") == 0
            || g_strcmp0(type_value, "calendar") == 0 || g_strcmp0(type_value, "one_time") == 0;
        gboolean interval = g_strcmp0(type_value, "interval") == 0;
        gboolean calendar = g_strcmp0(type_value, "calendar") == 0;
        gboolean daily_calendar = calendar && g_strcmp0(extra_value, "daily") == 0;
        gboolean specific_calendar = calendar && g_strcmp0(extra_value, "specific") == 0;
        gboolean needs_extra = interval || calendar;
        gboolean bad_extra = (g_strcmp0(type_value, "cron") == 0 && *extra_value)
            || (calendar && !daily_calendar && !specific_calendar)
            || (g_strcmp0(type_value, "one_time") == 0 && *extra_value);
        gboolean bad_timezone = *timezone_value && g_strcmp0(type_value, "cron") != 0 && !daily_calendar;
        if (!*name_value || !*action_id || !*cron_expr || !supported_type
            || (needs_extra && !*extra_value) || bad_extra || bad_timezone) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Check the schedule type, value, optional anchor/calendar mode, and timezone fields.");
            return;
        }
        run_bridge_full(c, "cron-preview", "create", name_value, action_id, type_value,
                        cron_expr, extra_value, timezone_value);
    } else if (g_strcmp0(kind, "update") == 0) {
        if (!*job_id || !*name_value
            || (g_strcmp0(field_value, "enabled") == 0
                && g_strcmp0(name_value, "true") != 0 && g_strcmp0(name_value, "false") != 0)
            || (g_strcmp0(field_value, "name") != 0 && g_strcmp0(field_value, "enabled") != 0)) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Update needs a saved job ID and a valid name or true/false enabled value.");
            return;
        }
        run_bridge(c, "cron-preview", "update", job_id, field_value, name_value, NULL);
    } else if (g_strcmp0(kind, "remove") == 0) {
        if (!*job_id) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Remove needs a saved job ID.");
            return;
        }
        run_bridge(c, "cron-preview", "remove", job_id, NULL, NULL, NULL);
    } else {
        gtk_label_set_text(GTK_LABEL(c->notice), "Choose create, update, or remove.");
    }
}

static void show_cron_form(GtkButton *button, gpointer data) {
    (void)button;
    Center *c = data;
    GtkWidget *win = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(win), "Manage Cron job");
    gtk_window_set_transient_for(GTK_WINDOW(win), GTK_WINDOW(c->window));
    gtk_window_set_modal(GTK_WINDOW(win), TRUE);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14);
    gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14);
    gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(win), box);
    gtk_box_append(GTK_BOX(box), gtk_label_new("Preview is saved first; a separate confirmation applies that exact plan."));
    GtkWidget *mode = gtk_entry_new();
    gtk_editable_set_text(GTK_EDITABLE(mode), "create");
    gtk_entry_set_placeholder_text(GTK_ENTRY(mode), "create, update, or remove");
    gtk_box_append(GTK_BOX(box), mode);
    GtkWidget *id = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(id), "Saved job ID (update/remove)");
    gtk_box_append(GTK_BOX(box), id);
    GtkWidget *name = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(name), "Job name; for enabled updates use true or false");
    gtk_box_append(GTK_BOX(box), name);
    GtkWidget *update_field = gtk_entry_new();
    gtk_editable_set_text(GTK_EDITABLE(update_field), "name");
    gtk_entry_set_placeholder_text(GTK_ENTRY(update_field), "Update field: name or enabled");
    gtk_box_append(GTK_BOX(box), update_field);
    GtkWidget *action = gtk_entry_new();
    gtk_editable_set_text(GTK_EDITABLE(action), "diagnostics.doctor");
    gtk_entry_set_placeholder_text(GTK_ENTRY(action), "Registered safe action ID");
    gtk_box_append(GTK_BOX(box), action);
    GtkWidget *schedule_type = gtk_entry_new();
    gtk_editable_set_text(GTK_EDITABLE(schedule_type), "cron");
    gtk_entry_set_placeholder_text(GTK_ENTRY(schedule_type), "Schedule type: cron, interval, calendar, one_time");
    gtk_box_append(GTK_BOX(box), schedule_type);
    GtkWidget *expr = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(expr), "Cron expression, interval seconds, HH:MM or ISO datetime");
    gtk_box_append(GTK_BOX(box), expr);
    GtkWidget *schedule_extra = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(schedule_extra), "Interval anchor ISO datetime, or calendar mode daily/specific");
    gtk_box_append(GTK_BOX(box), schedule_extra);
    GtkWidget *timezone = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(timezone), "Optional IANA timezone for cron/daily; blank uses preference");
    gtk_box_append(GTK_BOX(box), timezone);
    GtkWidget *submit = gtk_button_new_with_label("Preview Cron change");
    g_object_set_data(G_OBJECT(submit), "cron-center", c);
    g_object_set_data(G_OBJECT(submit), "cron-mode", mode);
    g_object_set_data(G_OBJECT(submit), "cron-id", id);
    g_object_set_data(G_OBJECT(submit), "cron-name", name);
    g_object_set_data(G_OBJECT(submit), "cron-update-field", update_field);
    g_object_set_data(G_OBJECT(submit), "cron-action", action);
    g_object_set_data(G_OBJECT(submit), "cron-schedule-type", schedule_type);
    g_object_set_data(G_OBJECT(submit), "cron-schedule-extra", schedule_extra);
    g_object_set_data(G_OBJECT(submit), "cron-timezone", timezone);
    g_object_set_data(G_OBJECT(submit), "cron-expr", expr);
    g_signal_connect(submit, "clicked", G_CALLBACK(cron_form_submit), NULL);
    gtk_box_append(GTK_BOX(box), submit);
    gtk_window_present(GTK_WINDOW(win));
}

static void ask_cron_confirmation(Center *c, const gchar *plan_id, const gchar *summary) {
    gchar *message = g_strdup_printf("Review this saved Cron change and confirm only if it matches your request:\n\n%s", summary);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Apply exact plan", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices);
    gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1);
    request->center = c;
    request->action = g_strdup("cron-apply");
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    g_object_unref(dialog);
    g_free(message);
}
static void ask_cron_scheduler_confirmation(Center *c, gboolean start) {
    GtkAlertDialog *dialog = gtk_alert_dialog_new(start
        ? "Start the Ternuxx Cron scheduler with a 10-second poll? It may run enabled registered actions; shell commands are not accepted."
        : "Stop only the Ternuxx Cron scheduler? Other services will remain unchanged.");
    const char *choices[] = {"Cancel", start ? "Start scheduler" : "Stop scheduler", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup(start ? "cron-scheduler-start" : "cron-scheduler-stop");
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing Ternuxx Cron scheduler action");
    g_object_unref(dialog);
}
static void cron_scheduler_start(GtkButton *button, gpointer data) {
    (void)button; ask_cron_scheduler_confirmation(data, TRUE);
}
static void cron_scheduler_stop(GtkButton *button, gpointer data) {
    (void)button; ask_cron_scheduler_confirmation(data, FALSE);
}
static void show_cron_jobs(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "cron-jobs", NULL, NULL, NULL, NULL, NULL);
}
static void show_desktop_log(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "logs-read", "native-desktop", NULL, NULL, NULL, NULL);
}
static void show_ssh_keys(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-keys-list", NULL, NULL, NULL, NULL, NULL);
}

static void ssh_key_dialog_cancel(GtkButton *button, gpointer data) {
    (void)button; gtk_window_destroy(GTK_WINDOW(data));
}
static void ssh_key_preview_clicked(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = data;
    Center *c = g_object_get_data(G_OBJECT(window), "ssh-key-center");
    const gchar *action = g_object_get_data(G_OBJECT(window), "ssh-key-action");
    GtkWidget *field = g_object_get_data(G_OBJECT(window), "ssh-key-field");
    gchar *subject = NULL;
    if (g_strcmp0(action, "ssh-key-add-preview") == 0) {
        GtkTextBuffer *buffer = gtk_text_view_get_buffer(GTK_TEXT_VIEW(field));
        GtkTextIter start, end; gtk_text_buffer_get_bounds(buffer, &start, &end);
        subject = gtk_text_buffer_get_text(buffer, &start, &end, FALSE); g_strstrip(subject);
        if (!*subject || strchr(subject, '\n') || strchr(subject, '\r') || strlen(subject) > 16384) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Paste exactly one public-key line. Private keys are not accepted.");
            g_free(subject); return;
        }
    } else {
        subject = g_strdup(gtk_editable_get_text(GTK_EDITABLE(field))); g_strstrip(subject);
        if (!g_regex_match_simple("^SHA256:[A-Za-z0-9+/]{43}$", subject, 0, 0)) {
            gtk_label_set_text(GTK_LABEL(c->notice), "Use a SHA256 fingerprint from the shared key inventory.");
            g_free(subject); return;
        }
    }
    run_bridge(c, action, subject, NULL, NULL, NULL, NULL);
    gtk_window_destroy(GTK_WINDOW(window)); g_free(subject);
}
static void ssh_key_dialog(Center *c, gboolean enroll) {
    GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), enroll ? "Enroll SSH public key" : "Revoke SSH public key");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window));
    gtk_window_set_modal(GTK_WINDOW(window), TRUE); gtk_window_set_default_size(GTK_WINDOW(window), 520, enroll ? 330 : 220);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14); gtk_window_set_child(GTK_WINDOW(window), box);
    GtkWidget *hint = gtk_label_new(enroll
        ? "Paste one SSH public-key line for the Ternuxx-managed SSH service. It does not change external SSH configuration. Never paste a private key."
        : "Enter the SHA256 fingerprint shown in the Ternuxx SSH key inventory. Revocation removes only that service's key; the final valid key cannot be removed.");
    gtk_label_set_wrap(GTK_LABEL(hint), TRUE); gtk_box_append(GTK_BOX(box), hint);
    GtkWidget *field;
    if (enroll) {
        field = gtk_text_view_new(); gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(field), GTK_WRAP_NONE);
        GtkWidget *scroll = gtk_scrolled_window_new(); gtk_widget_set_vexpand(scroll, TRUE);
        gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(scroll), field); gtk_box_append(GTK_BOX(box), scroll);
    } else {
        field = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(field), "SHA256 fingerprint"); gtk_box_append(GTK_BOX(box), field);
    }
    GtkWidget *buttons = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    GtkWidget *cancel = gtk_button_new_with_label("Cancel");
    GtkWidget *preview = gtk_button_new_with_label(enroll ? "Preview enrollment" : "Preview revocation");
    gtk_box_append(GTK_BOX(buttons), cancel); gtk_box_append(GTK_BOX(buttons), preview); gtk_box_append(GTK_BOX(box), buttons);
    g_object_set_data(G_OBJECT(window), "ssh-key-center", c);
    g_object_set_data_full(G_OBJECT(window), "ssh-key-action", g_strdup(enroll ? "ssh-key-add-preview" : "ssh-key-remove-preview"), g_free);
    g_object_set_data(G_OBJECT(window), "ssh-key-field", field);
    g_signal_connect(cancel, "clicked", G_CALLBACK(ssh_key_dialog_cancel), window);
    g_signal_connect(preview, "clicked", G_CALLBACK(ssh_key_preview_clicked), window);
    gtk_window_present(GTK_WINDOW(window));
}
static void enroll_ssh_key(GtkButton *button, gpointer data) {
    (void)button; ssh_key_dialog(data, TRUE);
}
static void revoke_ssh_key(GtkButton *button, gpointer data) {
    (void)button; ssh_key_dialog(data, FALSE);
}
static void ssh_client_key_preview(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = data;
    Center *c = g_object_get_data(G_OBJECT(window), "ssh-client-key-center");
    GtkWidget *field = g_object_get_data(G_OBJECT(window), "ssh-client-key-name");
    gchar *name = g_strdup(gtk_editable_get_text(GTK_EDITABLE(field))); g_strstrip(name);
    if (!g_regex_match_simple("^[a-z0-9][a-z0-9_-]{0,31}$", name, 0, 0)) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Use 1–32 lowercase letters, numbers, dashes, or underscores; start with a letter or number.");
        g_free(name); return;
    }
    run_bridge(c, "ssh-client-key-preview", name, NULL, NULL, NULL, NULL);
    gtk_window_destroy(GTK_WINDOW(window)); g_free(name);
}
static void generate_ssh_key(GtkButton *button, gpointer data) {
    (void)button; Center *c = data; GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Create Native SSH recovery key");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window)); gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 440, 210);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_margin_top(box, 14); gtk_widget_set_margin_bottom(box, 14);
    gtk_widget_set_margin_start(box, 14); gtk_widget_set_margin_end(box, 14);
    gtk_window_set_child(GTK_WINDOW(window), box);
    GtkWidget *hint = gtk_label_new("Creates an unencrypted Ed25519 keypair in the private Native .ssh/ternuxx-keys directory. The private key is mode 0600. Creating it does not enroll it; enrollment is a separate action and grants access to the applicable SSH configurations.");
    gtk_label_set_wrap(GTK_LABEL(hint), TRUE); gtk_box_append(GTK_BOX(box), hint);
    GtkWidget *field = gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(field), "Recovery key name (for example: phone-recovery)");
    gtk_editable_set_text(GTK_EDITABLE(field), "recovery8023"); gtk_box_append(GTK_BOX(box), field);
    GtkWidget *buttons = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    GtkWidget *cancel = gtk_button_new_with_label("Cancel"), *preview = gtk_button_new_with_label("Review key creation");
    gtk_box_append(GTK_BOX(buttons), cancel); gtk_box_append(GTK_BOX(buttons), preview); gtk_box_append(GTK_BOX(box), buttons);
    g_object_set_data(G_OBJECT(window), "ssh-client-key-center", c); g_object_set_data(G_OBJECT(window), "ssh-client-key-name", field);
    g_signal_connect(cancel, "clicked", G_CALLBACK(ssh_key_dialog_cancel), window);
    g_signal_connect(preview, "clicked", G_CALLBACK(ssh_client_key_preview), window);
    gtk_window_present(GTK_WINDOW(window));
}
static void ask_ssh_client_key_confirmation(Center *c, const gchar *name, const gchar *plan_id,
                                            const gchar *path, const gchar *impact) {
    gchar *message = g_strdup_printf("Create Native SSH recovery key ‘%s’?\\n\\nPrivate key: %s\\n\\n%s\\n\\nThe key will not be enrolled automatically. Keep the private key private; use the separate public-key enrollment action when ready.", name, path, impact);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Create key", NULL}; gtk_alert_dialog_set_buttons(dialog, choices);
    gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-client-key-apply"); request->resource_id = g_strdup(name); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing Native SSH key creation");
    g_object_unref(dialog); g_free(message);
}
static void change_ssh_autostart(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-autostart-status", NULL, NULL, NULL, NULL, NULL);
}
static void ask_ssh_autostart_confirmation(Center *c, const gchar *enabled,
                                           const gchar *plan_id, const gchar *effect) {
    gboolean desired = g_strcmp0(enabled, "true") == 0;
    gchar *message = g_strdup_printf("%s managed SSH automatic start?\n\n%s\n\nThis preference applies when the Runit supervisor next starts. The current SSH process will not be stopped or started.", desired ? "Enable" : "Disable", effect);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", desired ? "Enable at startup" : "Disable at startup", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-autostart-apply"); request->resource_id = g_strdup(enabled);
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing SSH automatic-start preference");
    g_object_unref(dialog); g_free(message);
}
static void ask_ssh_deploy_confirmation(Center *c, const gchar *plan_id, const gchar *summary) {
    gchar *message = g_strdup_printf("Review this exact SSH service-definition deployment?\n\n%s\n\nOnly the fixed Ternuxx Runit run definition will be atomically replaced. The current sshd process will keep running; external SSH configurations are untouched.", summary);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Deploy definition", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-deploy-apply"); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact SSH service definition and backup");
    g_object_unref(dialog); g_free(message);
}
static void ask_ssh_deploy_rollback_confirmation(Center *c, const gchar *operation_id,
                                                  const gchar *plan_id, const gchar *summary) {
    gchar *message = g_strdup_printf("Review this exact SSH service-definition rollback?\n\n%s\n\nOnly the prior fixed Runit run definition will be restored. The current sshd process will keep running; external SSH configurations are untouched.", summary);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Restore definition", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-deploy-rollback-apply");
    request->resource_id = g_strdup(operation_id); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact SSH definition rollback");
    g_object_unref(dialog); g_free(message);
}
static void ask_ssh_key_confirmation(Center *c, const gchar *action, const gchar *subject,
                                     const gchar *plan_id, const gchar *fingerprint) {
    gboolean enroll = g_strcmp0(action, "ssh-key-add-preview") == 0;
    gchar *message = g_strdup_printf("Confirm %s of SSH key %s?\n\nThis changes the Ternuxx-managed SSH authorized-key file only. External SSH configuration and key files remain untouched. The exact preview will be revalidated before writing.",
        enroll ? "enrollment" : "revocation", fingerprint);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", enroll ? "Enroll key" : "Revoke key", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup(enroll ? "ssh-key-add-apply" : "ssh-key-remove-apply");
    request->resource_id = g_strdup(subject); request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing shared SSH key change");
    g_object_unref(dialog); g_free(message);
}

static void ssh_rollback_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    GtkAlertDialog *dialog = GTK_ALERT_DIALOG(source); Request *request = user_data; GError *error = NULL;
    int choice = gtk_alert_dialog_choose_finish(dialog, result, &error);
    if (!error && choice > 0) {
        gchar **ids = g_strsplit(request->resource_id ? request->resource_id : "", ",", -1);
        guint index = (guint)(choice - 1);
        if (ids[index] && g_regex_match_simple("^[0-9a-f]{32}$", ids[index], 0, 0))
            run_bridge(request->center, "ssh-key-rollback-preview", ids[index], NULL, NULL, NULL, NULL);
        else gtk_label_set_text(GTK_LABEL(request->center->notice), "Selected SSH recovery record is invalid.");
        g_strfreev(ids);
    } else if (error) { gtk_label_set_text(GTK_LABEL(request->center->notice), error->message); g_clear_error(&error); }
    else gtk_label_set_text(GTK_LABEL(request->center->notice), "SSH recovery cancelled.");
    g_free(request->action); g_free(request->resource_id); g_free(request->detail_id); g_free(request->plan_id); g_free(request);
}
static void restore_ssh_key(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-key-rollback-list", NULL, NULL, NULL, NULL, NULL);
}
static void ssh_deploy_rollback_choice(GObject *source, GAsyncResult *result, gpointer user_data) {
    GtkAlertDialog *dialog = GTK_ALERT_DIALOG(source); Request *request = user_data; GError *error = NULL;
    int choice = gtk_alert_dialog_choose_finish(dialog, result, &error);
    if (!error && choice > 0) {
        gchar **ids = g_strsplit(request->resource_id ? request->resource_id : "", ",", -1);
        guint index = (guint)(choice - 1);
        if (index < g_strv_length(ids) && g_regex_match_simple("^[0-9a-f]{32}$", ids[index], 0, 0))
            run_bridge(request->center, "ssh-deploy-rollback-preview", ids[index], NULL, NULL, NULL, NULL);
        else gtk_label_set_text(GTK_LABEL(request->center->notice), "Selected SSH definition record is invalid.");
        g_strfreev(ids);
    } else if (error) { gtk_label_set_text(GTK_LABEL(request->center->notice), error->message); g_clear_error(&error); }
    else gtk_label_set_text(GTK_LABEL(request->center->notice), "SSH definition rollback cancelled.");
    g_free(request->action); g_free(request->resource_id); g_free(request->detail_id); g_free(request->plan_id); g_free(request);
}
static void deploy_ssh_definition(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-deploy-preview", NULL, NULL, NULL, NULL, NULL);
}
static void rollback_ssh_definition(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "ssh-deploy-rollback-list", NULL, NULL, NULL, NULL, NULL);
}
static void ask_ssh_rollback_confirmation(Center *c, const gchar *rollback_id,
                                          const gchar *plan_id, const gchar *effect) {
    gchar *message = g_strdup_printf("Restore the exact previous authorized_keys file?\n\n%s\n\nThis restores only the Ternuxx-managed SSH authorized-key file. External SSH configuration and key files remain untouched. Restore is refused if the file changed since this snapshot.", effect);
    GtkAlertDialog *dialog = gtk_alert_dialog_new("%s", message);
    const char *choices[] = {"Cancel", "Restore saved key state", NULL};
    gtk_alert_dialog_set_buttons(dialog, choices); gtk_alert_dialog_set_default_button(dialog, 0);
    Request *request = g_new0(Request, 1); request->center = c;
    request->action = g_strdup("ssh-key-rollback-apply"); request->resource_id = g_strdup(rollback_id);
    request->plan_id = g_strdup(plan_id);
    gtk_alert_dialog_choose(dialog, GTK_WINDOW(c->window), NULL, confirmed_action, request);
    gtk_label_set_text(GTK_LABEL(c->notice), "Reviewing exact SSH key recovery");
    g_object_unref(dialog); g_free(message);
}
static void show_management_log(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "logs-read", "management-api", NULL, NULL, NULL, NULL);
}
static void show_cron_log(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "logs-read", "cron-scheduler", NULL, NULL, NULL, NULL);
}
static void show_cron_history(GtkButton *button, gpointer data) {
    (void)button; run_bridge(data, "cron-history", NULL, NULL, NULL, NULL, NULL);
}
static void inspect_recovery_reference(GtkButton *button, gpointer data) {
    Center *c = data;
    const gchar *action = g_object_get_data(G_OBJECT(button), "recovery-action");
    const gchar *reference = gtk_editable_get_text(GTK_EDITABLE(c->recovery_target_entry));
    if (!action) return;
    if (g_strcmp0(action, "continuity-prepare-preview") == 0 || g_strcmp0(action, "continuity-verify-preview") == 0
            || g_strcmp0(action, "reboot-test-prepare-preview") == 0 || g_strcmp0(action, "reboot-test-verify-preview") == 0) {
        if (!reference || !*reference) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter the checkpoint or reboot-test ID first."); return; }
        run_bridge(c, action, reference, NULL, NULL, NULL, NULL); return;
    }
    if (g_strcmp0(action, "backup-create-preview") == 0) {
        if (!reference || !*reference) { gtk_label_set_text(GTK_LABEL(c->notice), "Enter a backup name first."); return; }
        run_bridge(c, action, reference, NULL, NULL, NULL, NULL); return;
    }
    if (g_strcmp0(action, "backup-list") == 0 || g_strcmp0(action, "recovery-status") == 0
            || g_strcmp0(action, "continuity-status") == 0) {
        run_bridge(c, action, NULL, NULL, NULL, NULL, NULL);
        return;
    }
    if (!reference || !*reference) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Enter a backup name, backup ID, or operation ID first.");
        return;
    }
    run_bridge(c, action, reference, NULL, NULL, NULL, NULL);
}
static void inspect_cron_reference(GtkButton *button, gpointer data) {
    Center *c = data;
    const gchar *kind = g_object_get_data(G_OBJECT(button), "cron-inspect-kind");
    const gchar *item_id = gtk_editable_get_text(GTK_EDITABLE(c->cron_target_entry));
    if (!kind || !item_id || !*item_id) {
        gtk_label_set_text(GTK_LABEL(c->notice), "Enter a job or execution ID from the list/history first.");
        return;
    }
    run_bridge(c, "cron-inspect", kind, item_id, NULL, NULL, NULL);
}
static void timezone_save_clicked(GtkButton *button, gpointer data) {
    (void)button; GtkWidget *window = data;
    Center *c = g_object_get_data(G_OBJECT(window), "timezone-center");
    GtkWidget *entry = g_object_get_data(G_OBJECT(window), "timezone-entry");
    const gchar *zone = gtk_editable_get_text(GTK_EDITABLE(entry));
    if (zone && *zone) run_bridge(c, "timezone-set", zone, NULL, NULL, NULL, NULL);
    else gtk_label_set_text(GTK_LABEL(c->notice), "Enter an IANA timezone name.");
    gtk_window_destroy(GTK_WINDOW(window));
}
static void timezone_cancel_clicked(GtkButton *button, gpointer data) {
    (void)button; gtk_window_destroy(GTK_WINDOW(data));
}
static void set_timezone(GtkButton *button, gpointer data) {
    (void)button; Center *c = data;
    GtkWidget *window = gtk_window_new();
    gtk_window_set_title(GTK_WINDOW(window), "Set Ternuxx timezone preference");
    gtk_window_set_transient_for(GTK_WINDOW(window), GTK_WINDOW(c->window));
    gtk_window_set_modal(GTK_WINDOW(window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(window), 420, 150);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_widget_set_margin_top(box, 16); gtk_widget_set_margin_bottom(box, 16);
    gtk_widget_set_margin_start(box, 16); gtk_widget_set_margin_end(box, 16);
    gtk_window_set_child(GTK_WINDOW(window), box);
    gtk_box_append(GTK_BOX(box), gtk_label_new("This changes Ternuxx scheduling preference only, not Android system time."));
    GtkWidget *entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "IANA name, for example Asia/Dhaka");
    gtk_box_append(GTK_BOX(box), entry);
    GtkWidget *buttons = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    GtkWidget *cancel = gtk_button_new_with_label("Cancel");
    GtkWidget *save = gtk_button_new_with_label("Save preference");
    gtk_box_append(GTK_BOX(buttons), cancel); gtk_box_append(GTK_BOX(buttons), save);
    gtk_box_append(GTK_BOX(box), buttons);
    g_object_set_data(G_OBJECT(window), "timezone-center", c);
    g_object_set_data(G_OBJECT(window), "timezone-entry", entry);
    g_signal_connect(cancel, "clicked", G_CALLBACK(timezone_cancel_clicked), window);
    g_signal_connect(save, "clicked", G_CALLBACK(timezone_save_clicked), window);
    gtk_window_present(GTK_WINDOW(window));
}
static void save_monitor(GtkButton *button, gpointer data) {
    (void)button; Center *c=data; gchar interval[16];
    g_snprintf(interval,sizeof interval,"%d",gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(c->monitor_interval)));
    const gchar *unit=gtk_string_object_get_string(GTK_STRING_OBJECT(gtk_drop_down_get_selected_item(GTK_DROP_DOWN(c->monitor_unit))));
    const gchar *effective_unit=unit?unit:"seconds"; gint value=gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(c->monitor_interval));
    gint factor=!g_strcmp0(effective_unit,"hours")?3600:(!g_strcmp0(effective_unit,"minutes")?60:1);
    if(value*factor<30||value*factor>86400) { gtk_label_set_text(GTK_LABEL(c->notice),"Use an interval between 30 seconds and 24 hours."); return; }
    run_bridge(c,"set-monitor",gtk_check_button_get_active(GTK_CHECK_BUTTON(c->monitor_enabled))?"true":"false",
        interval,effective_unit,gtk_check_button_get_active(GTK_CHECK_BUTTON(c->monitor_focus))?"true":"false",
        gtk_check_button_get_active(GTK_CHECK_BUTTON(c->monitor_launch))?"true":"false");
}
static void open_shared_installer(GtkButton *button, gpointer data) {
    Center *c = data;
    const gchar *target = g_object_get_data(G_OBJECT(button), "installer-target");
    run_bridge(c, "installer-open", target, NULL, NULL, NULL, NULL);
}

static gboolean active(GtkApplication *app, gpointer user_data) {
    (void)user_data; Center *c=g_new0(Center,1); app_center=c;
    c->categories=g_ptr_array_new_with_free_func(g_free); c->resources=g_ptr_array_new_with_free_func(resource_free);
    c->window=gtk_application_window_new(app);
    gtk_window_set_title(GTK_WINDOW(c->window), "Ternuxx Management Center");
    gtk_window_set_default_size(GTK_WINDOW(c->window),720,980);
    GtkCssProvider *theme=gtk_css_provider_new();
    gtk_css_provider_load_from_string(theme,"window{background:#0c1511;color:#e6f1e9;} list,row{background:#111e18;color:#e6f1e9;} list row:selected{background:#245638;} button{background:#17271f;color:#e6f1e9;border:1px solid #2b4034;border-radius:9px;padding:8px;} button:hover{border-color:#62d58a;} label.dim-label{color:#9eb2a3;} textview,textview text{background-color:#111e18;color:#e6f1e9;}");
    gtk_style_context_add_provider_for_display(gdk_display_get_default(),GTK_STYLE_PROVIDER(theme),GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(theme);
    GtkWidget *root=gtk_box_new(GTK_ORIENTATION_VERTICAL,10); gtk_widget_set_margin_top(root,8); gtk_widget_set_margin_bottom(root,8); gtk_widget_set_margin_start(root,8); gtk_widget_set_margin_end(root,8); gtk_window_set_child(GTK_WINDOW(c->window),root);
    GtkWidget *heading=gtk_label_new("TERNUXX  ·  MANAGEMENT CENTER"); gtk_widget_add_css_class(heading,"title-1"); gtk_widget_set_halign(heading,GTK_ALIGN_START); gtk_box_append(GTK_BOX(root),heading);
    GtkWidget *setup_actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
    GtkWidget *setup_button=gtk_button_new_with_label("Install / extend workstation");
    GtkWidget *gpu_setup_button=gtk_button_new_with_label("Graphics / sound setup");
    g_object_set_data(G_OBJECT(setup_button),"installer-target","workstation");
    g_object_set_data(G_OBJECT(gpu_setup_button),"installer-target","gpu");
    g_signal_connect(setup_button,"clicked",G_CALLBACK(open_shared_installer),c);
    g_signal_connect(gpu_setup_button,"clicked",G_CALLBACK(open_shared_installer),c);
    gtk_box_append(GTK_BOX(setup_actions),setup_button); gtk_box_append(GTK_BOX(setup_actions),gpu_setup_button);
    gtk_box_append(GTK_BOX(root),setup_actions);
    GtkWidget *paned=gtk_paned_new(GTK_ORIENTATION_HORIZONTAL); gtk_widget_set_vexpand(paned,TRUE); gtk_box_append(GTK_BOX(root),paned);
    c->category_list=gtk_list_box_new(); gtk_widget_set_size_request(c->category_list,155,-1); gtk_list_box_set_selection_mode(GTK_LIST_BOX(c->category_list),GTK_SELECTION_SINGLE); gtk_paned_set_start_child(GTK_PANED(paned),c->category_list);
    GtkWidget *middle=gtk_paned_new(GTK_ORIENTATION_VERTICAL); GtkWidget *center=gtk_box_new(GTK_ORIENTATION_VERTICAL,8); gtk_widget_set_size_request(center,-1,180); c->search=gtk_search_entry_new(); gtk_search_entry_set_placeholder_text(GTK_SEARCH_ENTRY(c->search),"Search resources"); gtk_box_append(GTK_BOX(center),c->search); c->resource_list=gtk_list_box_new(); gtk_list_box_set_selection_mode(GTK_LIST_BOX(c->resource_list),GTK_SELECTION_SINGLE); GtkWidget *scroll=gtk_scrolled_window_new(); gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(scroll),c->resource_list); gtk_widget_set_vexpand(scroll,TRUE); gtk_box_append(GTK_BOX(center),scroll); gtk_paned_set_start_child(GTK_PANED(middle),center);
    GtkWidget *right=gtk_box_new(GTK_ORIENTATION_VERTICAL,8); c->details=gtk_text_view_new(); gtk_text_view_set_editable(GTK_TEXT_VIEW(c->details),FALSE); gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(c->details),GTK_WRAP_WORD_CHAR); GtkWidget *detail_scroll=gtk_scrolled_window_new(); gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(detail_scroll),c->details); gtk_widget_set_vexpand(detail_scroll,TRUE);
    GtkWidget *actions=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);
    c->history_button=gtk_button_new_with_label("View operation history"); gtk_widget_set_visible(c->history_button,FALSE);
    c->desktop_log_button=gtk_button_new_with_label("Read Native desktop log (may include app output)"); gtk_widget_set_visible(c->desktop_log_button,FALSE);
    c->logs_button=gtk_button_new_with_label("Read Cron scheduler log"); gtk_widget_set_visible(c->logs_button,FALSE);
    c->audit_logs_button=gtk_button_new_with_label("Read management audit log"); gtk_widget_set_visible(c->audit_logs_button,FALSE);
    const char *native_desktops[] = {"XFCE (default)", "LXQt", "MATE", "Cinnamon", "KDE Plasma", NULL};
    c->desktop_choice=gtk_drop_down_new_from_strings(native_desktops); gtk_widget_set_visible(c->desktop_choice,FALSE);
    c->start_button=gtk_button_new_with_label("Start desktop"); c->stop_button=gtk_button_new_with_label("Stop desktop");
    c->ssh_restart_button=gtk_button_new_with_label("Restart managed SSH (8023)"); gtk_widget_set_visible(c->ssh_restart_button,FALSE);
    c->ssh_keys_button=gtk_button_new_with_label("View shared SSH key fingerprints"); gtk_widget_set_visible(c->ssh_keys_button,FALSE);
    c->ssh_enroll_button=gtk_button_new_with_label("Enroll public key..."); gtk_widget_set_visible(c->ssh_enroll_button,FALSE);
    c->ssh_revoke_button=gtk_button_new_with_label("Revoke public key..."); gtk_widget_set_visible(c->ssh_revoke_button,FALSE);
    c->ssh_rollback_button=gtk_button_new_with_label("Restore previous SSH key change..."); gtk_widget_set_visible(c->ssh_rollback_button,FALSE);
    c->ssh_generate_button=gtk_button_new_with_label("Create Native recovery key..."); gtk_widget_set_visible(c->ssh_generate_button,FALSE);
    c->ssh_autostart_button=gtk_button_new_with_label("Set SSH start with Termux services..."); gtk_widget_set_visible(c->ssh_autostart_button,FALSE);
    c->ssh_deploy_button=gtk_button_new_with_label("Review and deploy SSH service definition..."); gtk_widget_set_visible(c->ssh_deploy_button,FALSE);
    c->ssh_deploy_rollback_button=gtk_button_new_with_label("Restore previous SSH service definition..."); gtk_widget_set_visible(c->ssh_deploy_rollback_button,FALSE);
    c->ssh_wakelock_button=gtk_button_new_with_label("Set managed SSH keep-awake preference..."); gtk_widget_set_visible(c->ssh_wakelock_button,FALSE);
    c->boot_cron_button=gtk_button_new_with_label("Manage Termux:Boot Cron startup..."); gtk_widget_set_visible(c->boot_cron_button,FALSE);
    c->boot_helpers_button=gtk_button_new_with_label("Inspect or reconcile Termux:Boot helpers..."); gtk_widget_set_visible(c->boot_helpers_button,FALSE);
    c->graphics_select_button=gtk_button_new_with_label("Select backend (KGSL experimental)"); gtk_widget_set_visible(c->graphics_select_button,FALSE);
    c->graphics_api_button=gtk_button_new_with_label("Verify graphics API…"); gtk_widget_set_visible(c->graphics_api_button,FALSE);
    g_object_set_data(G_OBJECT(c->start_button),"start",GINT_TO_POINTER(TRUE)); g_object_set_data(G_OBJECT(c->stop_button),"start",GINT_TO_POINTER(FALSE));
    gtk_widget_set_visible(c->start_button,FALSE); gtk_widget_set_visible(c->stop_button,FALSE);
    GtkWidget *base_actions[]={c->start_button,c->stop_button,c->ssh_restart_button,c->ssh_keys_button,c->ssh_enroll_button,c->ssh_revoke_button,c->ssh_rollback_button,c->ssh_generate_button,c->ssh_autostart_button,c->ssh_deploy_button,c->ssh_deploy_rollback_button,c->ssh_wakelock_button,c->boot_cron_button,c->boot_helpers_button,c->graphics_select_button,c->graphics_api_button,c->history_button,c->desktop_log_button,c->logs_button,c->audit_logs_button};
    for (guint i=0;i<G_N_ELEMENTS(base_actions);i++) gtk_box_append(GTK_BOX(actions),base_actions[i]);
    c->cron_button=gtk_button_new_with_label("View saved Cron jobs"); gtk_widget_set_visible(c->cron_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_button);
    c->cron_history_button=gtk_button_new_with_label("View Cron execution history"); gtk_widget_set_visible(c->cron_history_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_history_button);
    c->cron_manage_button=gtk_button_new_with_label("Manage Cron jobs…"); gtk_widget_set_visible(c->cron_manage_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_manage_button);
    c->cron_start_button=gtk_button_new_with_label("Start Cron scheduler…"); gtk_widget_set_visible(c->cron_start_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_start_button);
    c->cron_stop_button=gtk_button_new_with_label("Stop Cron scheduler…"); gtk_widget_set_visible(c->cron_stop_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_stop_button);
    c->cron_target_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->cron_target_entry), "Paste job-… or exec-… ID"); gtk_widget_set_visible(c->cron_target_entry,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_target_entry);
    c->cron_inspect_button=gtk_button_new_with_label("Inspect saved job"); gtk_widget_set_visible(c->cron_inspect_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_inspect_button); g_object_set_data(G_OBJECT(c->cron_inspect_button), "cron-inspect-kind", "job");
    c->cron_next_button=gtk_button_new_with_label("Preview next five runs"); gtk_widget_set_visible(c->cron_next_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_next_button); g_object_set_data(G_OBJECT(c->cron_next_button), "cron-inspect-kind", "next");
    c->cron_execution_button=gtk_button_new_with_label("Inspect execution record"); gtk_widget_set_visible(c->cron_execution_button,FALSE); gtk_box_append(GTK_BOX(actions),c->cron_execution_button); g_object_set_data(G_OBJECT(c->cron_execution_button), "cron-inspect-kind", "execution");
    c->recovery_status_button=gtk_button_new_with_label("View recovery operation history"); gtk_widget_set_visible(c->recovery_status_button,FALSE); gtk_box_append(GTK_BOX(actions),c->recovery_status_button); g_object_set_data(G_OBJECT(c->recovery_status_button), "recovery-action", "recovery-status");
    c->backup_list_button=gtk_button_new_with_label("List verified configuration backups"); gtk_widget_set_visible(c->backup_list_button,FALSE); gtk_box_append(GTK_BOX(actions),c->backup_list_button); g_object_set_data(G_OBJECT(c->backup_list_button), "recovery-action", "backup-list");
    c->continuity_status_button=gtk_button_new_with_label("Check reboot-continuity status"); gtk_widget_set_visible(c->continuity_status_button,FALSE); gtk_box_append(GTK_BOX(actions),c->continuity_status_button); g_object_set_data(G_OBJECT(c->continuity_status_button), "recovery-action", "continuity-status");
    c->continuity_prepare_button=gtk_button_new_with_label("Prepare continuity checkpoint…"); gtk_widget_set_visible(c->continuity_prepare_button,FALSE); gtk_box_append(GTK_BOX(actions),c->continuity_prepare_button); g_object_set_data(G_OBJECT(c->continuity_prepare_button), "recovery-action", "continuity-prepare-preview");
    c->continuity_verify_button=gtk_button_new_with_label("Verify checkpoint…"); gtk_widget_set_visible(c->continuity_verify_button,FALSE); gtk_box_append(GTK_BOX(actions),c->continuity_verify_button); g_object_set_data(G_OBJECT(c->continuity_verify_button), "recovery-action", "continuity-verify-preview");
    c->reboot_test_prepare_button=gtk_button_new_with_label("Prepare reboot qualification…"); gtk_widget_set_visible(c->reboot_test_prepare_button,FALSE); gtk_box_append(GTK_BOX(actions),c->reboot_test_prepare_button); g_object_set_data(G_OBJECT(c->reboot_test_prepare_button), "recovery-action", "reboot-test-prepare-preview");
    c->reboot_test_verify_button=gtk_button_new_with_label("Verify reboot qualification…"); gtk_widget_set_visible(c->reboot_test_verify_button,FALSE); gtk_box_append(GTK_BOX(actions),c->reboot_test_verify_button); g_object_set_data(G_OBJECT(c->reboot_test_verify_button), "recovery-action", "reboot-test-verify-preview");
    c->recovery_target_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->recovery_target_entry), "Backup name, checkpoint/reboot-test ID, backup ID, or operation ID"); gtk_widget_set_visible(c->recovery_target_entry,FALSE); gtk_box_append(GTK_BOX(actions),c->recovery_target_entry);
    c->backup_inspect_button=gtk_button_new_with_label("Inspect backup"); gtk_widget_set_visible(c->backup_inspect_button,FALSE); gtk_box_append(GTK_BOX(actions),c->backup_inspect_button); g_object_set_data(G_OBJECT(c->backup_inspect_button), "recovery-action", "backup-inspect");
    c->restore_preview_button=gtk_button_new_with_label("Preview restore (read-only)"); gtk_widget_set_visible(c->restore_preview_button,FALSE); gtk_box_append(GTK_BOX(actions),c->restore_preview_button); g_object_set_data(G_OBJECT(c->restore_preview_button), "recovery-action", "restore-preview");
    c->backup_create_button=gtk_button_new_with_label("Create backup from name above…"); gtk_widget_set_visible(c->backup_create_button,FALSE); gtk_box_append(GTK_BOX(actions),c->backup_create_button); g_object_set_data(G_OBJECT(c->backup_create_button), "recovery-action", "backup-create-preview");
    c->restore_apply_button=gtk_button_new_with_label("Restore from backup ID above…"); gtk_widget_set_visible(c->restore_apply_button,FALSE); gtk_box_append(GTK_BOX(actions),c->restore_apply_button); g_object_set_data(G_OBJECT(c->restore_apply_button), "recovery-action", "restore-apply-preview");
    c->operation_inspect_button=gtk_button_new_with_label("Inspect operation record"); gtk_widget_set_visible(c->operation_inspect_button,FALSE); gtk_box_append(GTK_BOX(actions),c->operation_inspect_button); g_object_set_data(G_OBJECT(c->operation_inspect_button), "recovery-action", "recovery-inspect");
    c->rollback_preview_button=gtk_button_new_with_label("Preview restore rollback (read-only)"); gtk_widget_set_visible(c->rollback_preview_button,FALSE); gtk_box_append(GTK_BOX(actions),c->rollback_preview_button); g_object_set_data(G_OBJECT(c->rollback_preview_button), "recovery-action", "recovery-rollback-preview");
    c->rollback_apply_button=gtk_button_new_with_label("Apply restore rollback…"); gtk_widget_set_visible(c->rollback_apply_button,FALSE); gtk_box_append(GTK_BOX(actions),c->rollback_apply_button); g_object_set_data(G_OBJECT(c->rollback_apply_button), "recovery-action", "recovery-rollback-apply-preview");
    c->recovery_resolve_button=gtk_button_new_with_label("Reconcile unresolved operation…"); gtk_widget_set_visible(c->recovery_resolve_button,FALSE); gtk_box_append(GTK_BOX(actions),c->recovery_resolve_button); g_object_set_data(G_OBJECT(c->recovery_resolve_button), "recovery-action", "recovery-resolve-preview");
    c->timezone_set_button=gtk_button_new_with_label("Set Ternuxx timezone preference…"); gtk_widget_set_visible(c->timezone_set_button,FALSE); gtk_box_append(GTK_BOX(actions),c->timezone_set_button);
    c->software_button=gtk_button_new_with_label("Browse Native Termux apps…"); gtk_widget_set_visible(c->software_button,FALSE); gtk_box_append(GTK_BOX(actions),c->software_button);
    c->ai_model_install_button=gtk_button_new_with_label("Preview or download pinned CPU model…"); gtk_widget_set_visible(c->ai_model_install_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_model_install_button);
    c->ai_model_remove_button=gtk_button_new_with_label("Preview model removal…"); gtk_widget_set_visible(c->ai_model_remove_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_model_remove_button);
    c->ai_run_button=gtk_button_new_with_label("Run bounded CPU prompt…"); gtk_widget_set_visible(c->ai_run_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_run_button);
    c->ai_auto_run_button=gtk_button_new_with_label("Run using preferred AI backend…"); gtk_widget_set_visible(c->ai_auto_run_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_auto_run_button);
    c->ai_gpu_status_button=gtk_button_new_with_label("List Vulkan inference devices"); gtk_widget_set_visible(c->ai_gpu_status_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_gpu_status_button);
    c->ai_gpu_run_button=gtk_button_new_with_label("Run bounded Vulkan prompt…"); gtk_widget_set_visible(c->ai_gpu_run_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_gpu_run_button);
    c->ai_npu_status_button=gtk_button_new_with_label("Check HTP0 runtime and device"); gtk_widget_set_visible(c->ai_npu_status_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_npu_status_button);
    c->ai_npu_install_button=gtk_button_new_with_label("Preview or install pinned Snapdragon runtime…"); gtk_widget_set_visible(c->ai_npu_install_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_npu_install_button);
    c->ai_npu_run_button=gtk_button_new_with_label("Run bounded experimental HTP prompt…"); gtk_widget_set_visible(c->ai_npu_run_button,FALSE); gtk_box_append(GTK_BOX(actions),c->ai_npu_run_button);
    c->terminal_service_button=gtk_button_new_with_label("Check or start terminal broker…"); gtk_widget_set_visible(c->terminal_service_button,FALSE); gtk_box_append(GTK_BOX(actions),c->terminal_service_button);
    c->terminal_open_button=gtk_button_new_with_label("Open Debian terminal"); gtk_widget_set_visible(c->terminal_open_button,FALSE); gtk_box_append(GTK_BOX(actions),c->terminal_open_button);
    c->proot_box=gtk_expander_new("Managed guest tools"); gtk_widget_set_visible(c->proot_box,FALSE);
    GtkWidget *proot_actions=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);
    c->proot_help=gtk_label_new("Use an installed guest app ID. Shortcut edits and session stops show an exact preview first."); gtk_label_set_wrap(GTK_LABEL(c->proot_help),TRUE); gtk_label_set_xalign(GTK_LABEL(c->proot_help),0.0f); gtk_box_append(GTK_BOX(proot_actions),c->proot_help);
    c->proot_setup_help=gtk_label_new("Choose one or more desktop IDs, then start the guided installer here. Review and confirm its pinned target in the embedded terminal; Ternuxx applies available graphics/audio integration. Existing guests are preserved."); gtk_label_set_wrap(GTK_LABEL(c->proot_setup_help),TRUE); gtk_label_set_xalign(GTK_LABEL(c->proot_setup_help),0.0f); gtk_box_append(GTK_BOX(proot_actions),c->proot_setup_help);
    c->proot_desktop_box=gtk_box_new(GTK_ORIENTATION_VERTICAL,2); gtk_box_append(GTK_BOX(proot_actions),c->proot_desktop_box);
    GtkWidget *distro_note=gtk_label_new("Managed guest distribution"); gtk_widget_set_halign(distro_note,GTK_ALIGN_START); gtk_box_append(GTK_BOX(c->proot_desktop_box),distro_note);
    c->proot_distro=gtk_drop_down_new_from_strings(NULL); gtk_widget_set_sensitive(c->proot_distro,FALSE); gtk_box_append(GTK_BOX(c->proot_desktop_box),c->proot_distro);
    g_signal_connect(c->proot_distro,"notify::selected",G_CALLBACK(install_profile_changed),c);
    GtkWidget *desktop_note=gtk_label_new("Desktop environments (select one or more; routes shown per profile)"); gtk_widget_set_halign(desktop_note,GTK_ALIGN_START); gtk_box_append(GTK_BOX(c->proot_desktop_box),desktop_note);
    c->install_profiles=g_ptr_array_new(); c->proot_desktop_checks=g_ptr_array_new();
    c->proot_setup_button=gtk_button_new_with_label("Install managed proot distro…"); gtk_widget_set_sensitive(c->proot_setup_button,FALSE); gtk_box_append(GTK_BOX(proot_actions),c->proot_setup_button);
    c->proot_app_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_app_entry), "Debian app ID (for example: firefox)"); gtk_box_append(GTK_BOX(proot_actions),c->proot_app_entry);
    c->proot_app_button=gtk_button_new_with_label("Launch Debian app"); gtk_box_append(GTK_BOX(proot_actions),c->proot_app_button);
    c->proot_shortcut_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_shortcut_entry), "Debian app ID for shortcut add/remove"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_entry);
    c->proot_shortcut_list_button=gtk_button_new_with_label("List Debian shortcuts"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_list_button);
    c->proot_shortcut_add_button=gtk_button_new_with_label("Preview shortcut add…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_add_button); g_object_set_data(G_OBJECT(c->proot_shortcut_add_button), "proot-shortcut-action", "add");
    c->proot_shortcut_remove_button=gtk_button_new_with_label("Preview shortcut remove…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_remove_button); g_object_set_data(G_OBJECT(c->proot_shortcut_remove_button), "proot-shortcut-action", "remove");
    c->proot_shortcut_sync_button=gtk_button_new_with_label("Preview app and desktop shortcut synchronization…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_sync_button);
    c->proot_shortcut_rollback_list_button=gtk_button_new_with_label("List prior shortcut syncs"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_rollback_list_button);
    c->proot_sync_rollback_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_sync_rollback_entry), "Applied shortcut sync rollback ID"); gtk_box_append(GTK_BOX(proot_actions),c->proot_sync_rollback_entry);
    c->proot_shortcut_rollback_preview_button=gtk_button_new_with_label("Preview shortcut sync restore…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_shortcut_rollback_preview_button);
    c->proot_session_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_session_entry), "Ternuxx-owned session ID (proot-…)"); gtk_box_append(GTK_BOX(proot_actions),c->proot_session_entry);
    c->proot_session_stop_button=gtk_button_new_with_label("Preview session stop…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_session_stop_button);
    c->proot_session_reconcile_button=gtk_button_new_with_label("Inspect/reconcile exited session…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_session_reconcile_button);
    c->proot_replay_alias_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_replay_alias_entry), "Exact receipt-backed alias: ternuxx-replay-NAME"); gtk_box_append(GTK_BOX(proot_actions),c->proot_replay_alias_entry);
    c->proot_replay_backup_entry=gtk_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(c->proot_replay_backup_entry), "Retired replay backup ID (32 lowercase hex characters)"); gtk_box_append(GTK_BOX(proot_actions),c->proot_replay_backup_entry);
    c->proot_replay_retire_button=gtk_button_new_with_label("Preview replay guest retirement…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_replay_retire_button);
    c->proot_replay_restore_button=gtk_button_new_with_label("Preview replay guest restore…"); gtk_box_append(GTK_BOX(proot_actions),c->proot_replay_restore_button);
    c->proot_replay_review_box=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);
    c->proot_replay_review_label=gtk_label_new(""); gtk_label_set_wrap(GTK_LABEL(c->proot_replay_review_label),TRUE); gtk_label_set_xalign(GTK_LABEL(c->proot_replay_review_label),0.0f); gtk_box_append(GTK_BOX(c->proot_replay_review_box),c->proot_replay_review_label);
    GtkWidget *replay_review_buttons=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4);
    c->proot_replay_cancel_button=gtk_button_new_with_label("Cancel replay guest change"); gtk_box_append(GTK_BOX(replay_review_buttons),c->proot_replay_cancel_button);
    c->proot_replay_apply_button=gtk_button_new_with_label("Apply reviewed replay guest change"); gtk_box_append(GTK_BOX(replay_review_buttons),c->proot_replay_apply_button);
    gtk_box_append(GTK_BOX(c->proot_replay_review_box),replay_review_buttons); gtk_widget_set_visible(c->proot_replay_review_box,FALSE); gtk_box_append(GTK_BOX(proot_actions),c->proot_replay_review_box);
    gtk_expander_set_child(GTK_EXPANDER(c->proot_box),proot_actions); gtk_box_append(GTK_BOX(actions),c->proot_box);
    c->action_scroll=gtk_scrolled_window_new(); gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(c->action_scroll),actions); gtk_scrolled_window_set_max_content_height(GTK_SCROLLED_WINDOW(c->action_scroll),190); gtk_scrolled_window_set_propagate_natural_height(GTK_SCROLLED_WINDOW(c->action_scroll),TRUE); gtk_widget_set_size_request(c->action_scroll,-1,1); gtk_box_append(GTK_BOX(right),c->action_scroll); gtk_box_append(GTK_BOX(right),detail_scroll);
    c->monitor_box=gtk_box_new(GTK_ORIENTATION_VERTICAL,4); c->monitor_enabled=gtk_check_button_new_with_label("Enable Activity/focus monitoring"); c->monitor_interval=gtk_spin_button_new_with_range(1,86400,1); const gchar *units[]={"seconds","minutes","hours",NULL}; c->monitor_unit=gtk_drop_down_new_from_strings(units); c->monitor_focus=gtk_check_button_new_with_label("Check Android Activity focus"); c->monitor_launch=gtk_check_button_new_with_label("Request Activity when background"); gtk_box_append(GTK_BOX(c->monitor_box),c->monitor_enabled); gtk_box_append(GTK_BOX(c->monitor_box),gtk_label_new("Polling interval")); gtk_box_append(GTK_BOX(c->monitor_box),c->monitor_interval); gtk_box_append(GTK_BOX(c->monitor_box),c->monitor_unit); gtk_box_append(GTK_BOX(c->monitor_box),c->monitor_focus); gtk_box_append(GTK_BOX(c->monitor_box),c->monitor_launch); GtkWidget *save=gtk_button_new_with_label("Save monitoring policy"); gtk_box_append(GTK_BOX(c->monitor_box),save); gtk_widget_set_visible(c->monitor_box,FALSE); gtk_box_append(GTK_BOX(right),c->monitor_box);
    gtk_paned_set_end_child(GTK_PANED(middle),right); gtk_paned_set_end_child(GTK_PANED(paned),middle); gtk_paned_set_position(GTK_PANED(paned),165); gtk_paned_set_position(GTK_PANED(middle),190);
    c->notice=gtk_label_new("Loading resource catalog…"); gtk_widget_set_halign(c->notice,GTK_ALIGN_START); gtk_box_append(GTK_BOX(root),c->notice);
    GtkWidget *brand=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4); GtkWidget *tagline=gtk_label_new("Workstation in your pocket — by Sobuj Miah");
    gtk_widget_set_halign(tagline,GTK_ALIGN_START); gtk_widget_add_css_class(tagline,"dim-label");
    GtkWidget *portfolio=gtk_link_button_new_with_label("https://soobujmiah.github.io/","soobujmiah.github.io");
    gtk_box_append(GTK_BOX(brand),tagline); gtk_box_append(GTK_BOX(brand),portfolio); gtk_box_append(GTK_BOX(root),brand);
    g_signal_connect(c->software_button,"clicked",G_CALLBACK(software_apps),c); g_signal_connect(c->ai_auto_run_button,"clicked",G_CALLBACK(auto_prompt_dialog),c); g_signal_connect(c->ai_model_install_button,"clicked",G_CALLBACK(cpu_model_install),c); g_signal_connect(c->ai_model_remove_button,"clicked",G_CALLBACK(cpu_model_remove),c); g_signal_connect(c->ai_run_button,"clicked",G_CALLBACK(cpu_prompt_dialog),c);
    g_signal_connect(c->ai_gpu_status_button,"clicked",G_CALLBACK(gpu_status_clicked),c); g_signal_connect(c->ai_gpu_run_button,"clicked",G_CALLBACK(gpu_prompt_dialog),c);
    g_signal_connect(c->ai_npu_status_button,"clicked",G_CALLBACK(npu_status_clicked),c); g_signal_connect(c->ai_npu_install_button,"clicked",G_CALLBACK(npu_install_clicked),c); g_signal_connect(c->ai_npu_run_button,"clicked",G_CALLBACK(npu_run_dialog),c);
    g_signal_connect(c->terminal_service_button,"clicked",G_CALLBACK(terminal_service_clicked),c);
    g_signal_connect(c->terminal_open_button,"clicked",G_CALLBACK(open_debian_terminal),c);
    g_signal_connect(c->proot_setup_button,"clicked",G_CALLBACK(open_debian_setup),c);
    run_bridge(c,"proot-install-catalog",NULL,NULL,NULL,NULL,NULL);
    g_signal_connect(c->proot_app_button,"clicked",G_CALLBACK(proot_app_clicked),c);
    g_signal_connect(c->proot_shortcut_list_button,"clicked",G_CALLBACK(proot_shortcut_list_clicked),c);
    g_signal_connect(c->proot_shortcut_add_button,"clicked",G_CALLBACK(proot_shortcut_clicked),c);
    g_signal_connect(c->proot_shortcut_remove_button,"clicked",G_CALLBACK(proot_shortcut_clicked),c);
    g_signal_connect(c->proot_shortcut_sync_button,"clicked",G_CALLBACK(proot_shortcut_sync_clicked),c);
    g_signal_connect(c->proot_shortcut_rollback_list_button,"clicked",G_CALLBACK(proot_shortcut_rollback_list_clicked),c);
    g_signal_connect(c->proot_shortcut_rollback_preview_button,"clicked",G_CALLBACK(proot_shortcut_rollback_preview_clicked),c);
    g_signal_connect(c->proot_session_stop_button,"clicked",G_CALLBACK(proot_session_stop_clicked),c);
    g_signal_connect(c->proot_session_reconcile_button,"clicked",G_CALLBACK(proot_session_reconcile_clicked),c);
    g_signal_connect(c->proot_replay_retire_button,"clicked",G_CALLBACK(proot_replay_retire_clicked),c);
    g_signal_connect(c->proot_replay_restore_button,"clicked",G_CALLBACK(proot_replay_restore_clicked),c);
    g_signal_connect(c->proot_replay_cancel_button,"clicked",G_CALLBACK(proot_replay_cancel_clicked),c);
    g_signal_connect(c->proot_replay_apply_button,"clicked",G_CALLBACK(proot_replay_apply_clicked),c);
    g_signal_connect(c->boot_cron_button,"clicked",G_CALLBACK(manage_boot_cron),c);
    g_signal_connect(c->boot_helpers_button,"clicked",G_CALLBACK(manage_boot_helpers),c);
    g_signal_connect(c->category_list,"row-selected",G_CALLBACK(category_selected),c); g_signal_connect(c->resource_list,"row-selected",G_CALLBACK(resource_selected),c); g_signal_connect(c->search,"search-changed",G_CALLBACK(search_changed),c); g_signal_connect(c->start_button,"clicked",G_CALLBACK(confirm_action),c); g_signal_connect(c->stop_button,"clicked",G_CALLBACK(confirm_action),c); g_signal_connect(c->ssh_restart_button,"clicked",G_CALLBACK(confirm_action),c); g_signal_connect(c->ssh_keys_button,"clicked",G_CALLBACK(show_ssh_keys),c); g_signal_connect(c->ssh_enroll_button,"clicked",G_CALLBACK(enroll_ssh_key),c); g_signal_connect(c->ssh_revoke_button,"clicked",G_CALLBACK(revoke_ssh_key),c); g_signal_connect(c->ssh_rollback_button,"clicked",G_CALLBACK(restore_ssh_key),c); g_signal_connect(c->ssh_generate_button,"clicked",G_CALLBACK(generate_ssh_key),c); g_signal_connect(c->ssh_autostart_button,"clicked",G_CALLBACK(change_ssh_autostart),c); g_signal_connect(c->ssh_deploy_button,"clicked",G_CALLBACK(deploy_ssh_definition),c); g_signal_connect(c->ssh_deploy_rollback_button,"clicked",G_CALLBACK(rollback_ssh_definition),c); g_signal_connect(c->ssh_wakelock_button,"clicked",G_CALLBACK(change_ssh_wakelock),c); g_signal_connect(c->graphics_select_button,"clicked",G_CALLBACK(select_graphics),c); g_signal_connect(c->graphics_api_button,"clicked",G_CALLBACK(choose_graphics_api),c); g_signal_connect(c->history_button,"clicked",G_CALLBACK(show_history),c); g_signal_connect(c->desktop_log_button,"clicked",G_CALLBACK(show_desktop_log),c); g_signal_connect(c->logs_button,"clicked",G_CALLBACK(show_cron_log),c); g_signal_connect(c->audit_logs_button,"clicked",G_CALLBACK(show_management_log),c); g_signal_connect(c->cron_button,"clicked",G_CALLBACK(show_cron_jobs),c); g_signal_connect(c->cron_history_button,"clicked",G_CALLBACK(show_cron_history),c); g_signal_connect(c->cron_manage_button,"clicked",G_CALLBACK(show_cron_form),c); g_signal_connect(c->cron_start_button,"clicked",G_CALLBACK(cron_scheduler_start),c); g_signal_connect(c->cron_stop_button,"clicked",G_CALLBACK(cron_scheduler_stop),c); g_signal_connect(c->cron_inspect_button,"clicked",G_CALLBACK(inspect_cron_reference),c); g_signal_connect(c->cron_next_button,"clicked",G_CALLBACK(inspect_cron_reference),c); g_signal_connect(c->cron_execution_button,"clicked",G_CALLBACK(inspect_cron_reference),c); g_signal_connect(c->recovery_status_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->backup_list_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->continuity_status_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->continuity_prepare_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->continuity_verify_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->reboot_test_prepare_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->reboot_test_verify_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->backup_inspect_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->backup_create_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->restore_apply_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->restore_preview_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->operation_inspect_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->rollback_preview_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->rollback_apply_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->recovery_resolve_button,"clicked",G_CALLBACK(inspect_recovery_reference),c); g_signal_connect(c->timezone_set_button,"clicked",G_CALLBACK(set_timezone),c); g_signal_connect(save,"clicked",G_CALLBACK(save_monitor),c);
    load_catalog(c); gtk_window_present(GTK_WINDOW(c->window));
    return TRUE;
}
int main(int argc, char **argv) {
    if (argc == 2 && g_strcmp0(argv[1], "--version") == 0) { g_print("Ternuxx Management Center 0.1\n"); return 0; }
    if (argc == 2 && g_strcmp0(argv[1], "--self-check") == 0) {
        g_print("GTK %u.%u.%u; Native management client build is available\n",
                gtk_get_major_version(), gtk_get_minor_version(), gtk_get_micro_version()); return 0;
    }
    gboolean review_instance = argc == 2 && g_strcmp0(argv[1], "--review") == 0;
    const gchar *app_id = review_instance ? "dev.ternuxx.management-center.review" : "dev.ternuxx.management-center";
    GtkApplication *app=gtk_application_new(app_id,
        review_instance ? G_APPLICATION_NON_UNIQUE : G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(app,"activate",G_CALLBACK(active),NULL);
    int run_argc = review_instance ? 1 : argc;
    int status=g_application_run(G_APPLICATION(app),run_argc,argv);
    g_object_unref(app); return status;
}
