"""Typed, truthful inventory of Native Termux and optional PRoot domains/resources."""
from __future__ import annotations

from typing import Literal, TypedDict

import management_authorization


CapabilityStatus = Literal["implemented", "partial", "external", "unverified", "unavailable", "planned"]


class Category(TypedDict):
    id: str
    name: str
    description: str
    status: CapabilityStatus


class Resource(TypedDict):
    id: str
    category_id: str
    name: str
    description: str
    status: CapabilityStatus
    availability: str
    provider: str
    environment: str
    ownership: dict[str, str]
    state: dict[str, str]
    configuration: dict[str, object]
    supported_operations: list[str]
    planned_operations: list[str]
    dependencies: list[str]
    dependants: list[str]
    background: dict[str, object]
    boot: dict[str, object]
    logs: dict[str, str]
    diagnostics: list[str]
    recovery: list[str]
    identity: dict[str, str]
    security: dict[str, object]
    operation_capabilities: dict[str, str | None]
    unavailable_operations: list[str]


PROVIDERS = [
    {"id": "native-termux", "kind": "local-runtime", "status": "active", "secret_policy": "local state only"},
    {"id": "proot-distro", "kind": "optional-isolated-guest-runtime", "status": "installed-live-acceptance-passed", "secret_policy": "guest credentials remain guest-owned"},
    {"id": "runit", "kind": "service-manager", "status": "active-for-managed-sshd", "secret_policy": "no credentials stored"},
    {"id": "hermes-agent", "kind": "optional-agent-provider", "status": "read-only-status-adapter", "secret_policy": "does not return task/configuration contents"},
    {"id": "cloud-api", "kind": "remote-backend", "status": "planned-disabled", "secret_policy": "future secret references only; no credentials or network calls"},
]

DOMAINS = [
    {"id":"graphics-management", "status":"partial", "providers":["native-termux"], "operations":["graphics.provider.status","graphics.provider.verify","graphics.provider.select"]},
    {"id":"native-desktop", "status":"implemented", "providers":["native-termux"], "operations":["desktop.status","desktop.start","desktop.stop","desktop.restart","desktop.monitor.status","desktop.monitor.configure"]},
    {"id":"sshd-servers", "status":"implemented", "providers":["native-termux","runit"], "operations":["ssh.inspect","ssh.keys.list","ssh.service.start","ssh.service.stop","ssh.service.restart","ssh.service.deploy","ssh.service.deploy.rollback.preview","ssh.service.deploy.rollback.apply","remote.access.preview"]},
    {
        'id': 'proot-runtime',
        'status': 'installed-live-acceptance-passed',
        'providers': ['native-termux', 'proot-distro'],
        'operations': [
            'proot.status', 'proot.profiles.list', 'proot.profiles.show',
            'proot.sessions.list', 'proot.sessions.show', 'proot.sessions.health',
            'proot.recovery.inspect', 'proot.recovery.reconcile.preview',
            'proot.recovery.reconcile', 'proot.start.preview', 'proot.start',
            'proot.stop.preview', 'proot.stop', 'proot.guest.verify',
            'proot.setup.retire.preview', 'proot.setup.retire.apply',
            'proot.setup.restore.preview', 'proot.setup.restore.apply',
            'proot.setup.icd-migrate.preview', 'proot.setup.icd-migrate.apply',
            'proot.setup.icd-migrate.rollback.preview',
            'proot.setup.icd-migrate.rollback.apply', 'proot.app.launch',
            'proot.shortcuts.list', 'proot.shortcuts.preview', 'proot.shortcuts.apply',
            'proot.shortcuts.sync.preview', 'proot.shortcuts.sync.apply',
            'proot.shortcuts.sync.rollback.list', 'proot.shortcuts.sync.rollback.preview',
            'proot.shortcuts.sync.rollback.apply', 'terminal.broker.status',
            'terminal.broker.service.status', 'terminal.broker.service.install.preview',
            'terminal.broker.service.install.apply', 'terminal.broker.service.start.preview',
            'terminal.broker.service.start.apply', 'terminal.start.preview', 'terminal.start',
            'terminal.attach', 'terminal.input', 'terminal.resize', 'terminal.output',
            'terminal.detach', 'terminal.close.preview', 'terminal.close',
        ],
    },
    {"id":"doctor-diagnostics", "status":"implemented", "providers":["native-termux"], "operations":["doctor.report","management.catalog","management.logs.list","management.logs.read"]},
    {"id":"timezone-settings", "status":"implemented", "providers":["native-termux"], "operations":["timezone.status","timezone.list","timezone.set"]},
    {"id":"cron-registry", "status":"scheduler-runtime-available-not-autostarted", "providers":["native-termux"], "operations":["cron.status","cron.scheduler.start","cron.scheduler.stop","cron.executor.self_test","cron.jobs.list","cron.jobs.show","cron.jobs.validate","cron.jobs.next_runs","cron.jobs.mutation.preview","cron.jobs.mutation.apply","cron.executions.list","cron.executions.show"], "planned":["cron.device-boot.deliver","cron.scheduler-recovery.deliver","cron.execution.cancel","cron.retry","cron.queue-one"]},
    {"id":"hermes-agent", "status":"read-only-inspection", "providers":["hermes-agent"], "operations":["agent.hermes.status"], "planned":["agent.hermes.tasks.list","agent.hermes.task.validate","agent.hermes.execution.preview","agent.hermes.execution.run","agent.hermes.execution.cancel"]},
    {"id":"autoboot-background", "status":"implemented", "providers":["native-termux","runit"], "operations":["boot.status","boot.profile.status","boot.profile.preview","boot.enable","boot.disable","wakelock.status","wakelock.acquire","wakelock.release"]},
    {"id":"backup-recovery-continuity", "status":"implemented", "providers":["native-termux"], "operations":["backup.create","backup.list","backup.inspect","restore.preview","restore.apply","recovery.status","recovery.resolve","recovery.inspect","recovery.rollback.preview","recovery.rollback.apply","continuity.status","continuity.prepare.preview","continuity.prepare","continuity.verify.preview","continuity.verify","continuity.prepare-reboot-test.preview","continuity.prepare-reboot-test","continuity.verify-reboot-test.preview","continuity.verify-reboot-test","continuity.resume-info"]},
    {"id":"addons-plugins-tools", "status":"catalog-and-cli-tools-partial", "providers":["native-termux"], "operations":[], "planned":["addon.list","addon.preview","addon.apply","plugin.list","plugin.preview","plugin.apply","tool.catalog"]},
    {"id":"native-cpu-inference", "status":"partial", "providers":["native-termux"], "operations":["inference.cpu.status","inference.cpu.model.preview","inference.cpu.model.apply","inference.cpu.run"]},
    {"id":"native-vulkan-inference", "status":"partial", "providers":["native-termux"], "operations":["inference.gpu.status","inference.gpu.run"]},
    {"id":"native-hexagon-inference", "status":"partial", "providers":["native-termux"], "operations":["inference.npu.status","inference.npu.runtime.preview","inference.npu.runtime.apply","inference.npu.run"]},
    {"id":"native-curated-software", "status":"implemented", "providers":["native-termux"], "operations":["software.apps.list","software.app.preview","software.app.apply","software.app.run"]},
    {"id":"api-backends", "status":"planned-disabled", "providers":["cloud-api"], "operations":[], "planned":["backend.list","backend.health","backend.select","backend.credentials.reference"]},
]

CATEGORIES: list[Category] = [
    {"id":"system-health", "name":"System & health", "description":"Device, runtime, resource use, and overall health.", "status":"partial"},
    {"id":"services", "name":"Services & background", "description":"Managed services, supervisors, and background work.", "status":"partial"},
    {"id":"networking", "name":"Networking & remote access", "description":"SSH ownership, listener policy, and approved remote workflows.", "status":"partial"},
    {'id': 'proot', 'name': 'Debian PRoot & applications', 'description': 'Installed Debian PRoot profile with preview-confirmed diagnostic sessions, bounded health reads, and a foreground terminal login verified on-device; clean-device setup replay, concurrent rootfs use, and cold-boot GUI/workstation supervision remain unqualified.', 'status': 'partial'},
    {"id":"desktop-audio", "name":"Desktop & multimedia", "description":"Display, GUI sessions, audio, and graphical dependencies.", "status":"partial"},
    {"id":"graphics-acceleration", "name":"Graphics acceleration", "description":"Provider-specific GPU, Vulkan, and software-rendering diagnostics.", "status":"partial"},
    {"id":"boot-automation", "name":"Boot & automation", "description":"Termux:Boot profiles, service startup, and scheduled work.", "status":"partial"},
    {"id":"security-recovery", "name":"Configuration, security & recovery", "description":"Validated state, backups, access policy, and recovery actions.", "status":"partial"},
    {"id":"observability", "name":"Diagnostics & observability", "description":"Doctor findings, health evidence, logs, and operational events.", "status":"partial"},
    {"id":"software", "name":"Software & dependencies", "description":"Native Termux package management and dependencies.", "status":"partial"},
    {"id":"ai-providers", "name":"AI runtime & providers", "description":"Local runtimes, models, hardware capabilities, and API providers.", "status":"partial"},
    {"id":"deployments", "name":"Server & application deployment", "description":"Server templates, deployments, ports, versions, and rollback.", "status":"planned"},
    {"id":"extensions", "name":"Extensions & integrations", "description":"Future provider adapters with explicit lifecycle contracts.", "status":"planned"},
]

# `state.current` is deliberately not a live health claim. The linked operation
# must be called to obtain current state; discovery itself has no side effects.
RESOURCES: list[Resource] = [
    {'id': 'graphics.debian',
 'category_id': 'graphics-acceleration',
 'name': 'Debian PRoot graphics',
 'description': 'The Debian guest is installed, but Ternuxx graphics verification currently supports only '
                'Native Termux. Guest rendering remains external and unverified.',
 'status': 'external',
 'availability': 'guest-graphics-not-managed-or-verified',
 'provider': 'proot-debian',
 'environment': 'debian-glibc-guest',
 'ownership': {'authority': 'existing-guest-owner',
               'status': 'external; read-only diagnostics',
               'evidence': 'graphics.provider.status'},
 'state': {'current': 'external-unverified',
           'desired': 'existing-guest-settings',
           'readiness': 'guest-side-verification-required',
           'source_operation': 'management.catalog'},
 'configuration': {'schema_id': 'existing-ternux-graphics',
                   'defaults': {'backend': 'zink'},
                   'contains_secrets': False},
 'supported_operations': [],
 'planned_operations': [],
 'dependencies': [],
 'dependants': [],
 'background': {'supported': 'external', 'status': 'existing-guest'},
 'boot': {'configurable': False, 'status': 'external'},
 'logs': {'status': 'not-read', 'path': ''},
 'diagnostics': [],
 'recovery': [],
 'identity': {'source': 'fixed read-only guest verifier',
              'installed': 'existing Ternux PRoot',
              'version': 'device-probe'},
 'security': {'read_only': True, 'disruptive_operations': [], 'secret_values_returned': False}} ,
    {'id': 'proot.debian.workloads',
 'category_id': 'proot',
 'name': 'Existing Debian PRoot',
 'description': 'Debian PRoot profile, setup, session, recovery, app launch, and shortcut lifecycle. Native PRoot and Debian Trixie are installed; supported guest actions use preview and verified session identity.',
 'status': 'partial',
 'availability': 'installed-native-proot-debian-guest',
 'provider': 'proot-debian',
 'environment': 'debian-glibc-guest',
 'ownership': {'authority': 'Ternuxx-created-session-records-only; existing-guest-sessions-external',
               'status': 'ternuxx-session-identities-verified; external-host-processes-unverified',
               'evidence': 'proot.status'},
 'state': {'current': 'not-queried',
           'desired': 'owner-configured',
           'readiness': 'profile-preflight-query-required',
           'source_operation': 'proot.status'},
 'configuration': {'schema_id': 'proot-session-registry.schema-v3',
                   'defaults': {'distro': 'debian'},
                   'contains_secrets': False},
 'supported_operations': ['proot.status',
                          'proot.profiles.list',
                          'proot.profiles.show',
                          'proot.sessions.list',
                          'proot.sessions.show',
                          'proot.sessions.health',
                          'proot.recovery.inspect',
                          'proot.recovery.reconcile.preview',
                          'proot.recovery.reconcile',
                          'proot.start.preview',
                          'proot.start',
                          'proot.stop.preview',
                          'proot.stop',
                          'proot.guest.verify',
                          'proot.setup.icd-migrate.preview',
                          'proot.setup.icd-migrate.apply',
                          'proot.setup.icd-migrate.rollback.preview',
                          'proot.setup.icd-migrate.rollback.apply',
                          'proot.app.launch',
                          'proot.shortcuts.list',
                          'proot.shortcuts.preview',
                          'proot.shortcuts.apply',
                          'proot.shortcuts.sync.preview',
                          'proot.shortcuts.sync.apply',
                          'proot.shortcuts.sync.rollback.list',
                          'proot.shortcuts.sync.rollback.preview',
                          'proot.shortcuts.sync.rollback.apply'],
 'planned_operations': ['guest.desktop.supervision', 'guest.service.dependencies'],
 'dependencies': ['native.desktop.session'],
 'dependants': [],
 'background': {'supported': 'partial',
                'status': 'previewed-headless-probe-and-brokered-foreground-tty'},
 'boot': {'configurable': False, 'status': 'not-in-boot-profile'},
 'logs': {'status': 'unavailable', 'path': ''},
 'diagnostics': ['proot.status', 'proot.profiles.list', 'proot.sessions.list', 'proot.guest.verify'],
 'recovery': ['proot.sessions.show'],
 'identity': {'source': 'private versioned session registry plus PID start, isolated SID/PGRP, marker, '
                        'launcher and rootfs identities',
              'installed': 'source-backed-shared-api',
              'version': 'session-schema-v3'},
 'security': {'read_only': False,
              'disruptive_operations': ['proot.start',
                                        'proot.stop',
                                        'proot.app.launch',
                                        'proot.shortcuts.apply',
                                        'proot.shortcuts.sync.apply',
                                        'proot.shortcuts.sync.rollback.apply'],
              'secret_values_returned': False}} ,
    {'id': 'proot.replay-guests',
 'category_id': 'proot',
 'name': 'Ternuxx replay guests',
 'description': 'Exact-alias replay guest retirement and restore previews. The owner reports a backup; its '
                'contents have not been inspected.',
 'status': 'partial',
 'availability': 'source-restored-backup-unverified',
 'provider': 'proot-distro',
 'environment': 'native-termux-control-of-optional-proot',
 'ownership': {'authority': 'Ternuxx fresh-guest receipt',
               'status': 'receipt-and-rootfs-identity-required',
               'evidence': 'proot.setup.retire.preview'},
 'state': {'current': 'not-queried',
           'desired': 'owner-configured',
           'readiness': 'alias-and-receipt-required',
           'source_operation': 'proot.status'},
 'configuration': {'schema_id': 'fresh-proot-provider-receipt-v1', 'defaults': {}, 'contains_secrets': False},
 'supported_operations': ['proot.status',
                          'proot.setup.retire.preview',
                          'proot.setup.retire.apply',
                          'proot.setup.restore.preview',
                          'proot.setup.restore.apply'],
 'planned_operations': [],
 'dependencies': [],
 'dependants': [],
 'background': {'supported': False, 'status': 'must-be-idle'},
 'boot': {'configurable': False, 'status': 'test-guest-only'},
 'logs': {'status': 'private-journal', 'path': '$TERNUXX_STATE_DIR/proot-setup/retired'},
 'diagnostics': ['proot.status'],
 'recovery': ['proot.setup.restore.preview', 'proot.setup.restore.apply'],
 'identity': {'source': 'fresh install receipt and exact rootfs device/inode',
              'installed': 'source-backed-shared-api',
              'version': 'receipt-v1'},
 'security': {'read_only': False,
              'disruptive_operations': ['proot.setup.retire.apply', 'proot.setup.restore.apply'],
              'secret_values_returned': False}} ,
    {'id': 'proot.interactive-terminal-broker',
 'category_id': 'proot',
 'name': 'Optional Debian terminal',
 'description': 'Private Native terminal broker for preview-confirmed Debian sessions; live interactive TTY and clean session exit are verified on this device.',
 'status': 'partial',
 'availability': 'installed-running-broker-service',
 'provider': 'native-termux',
 'environment': 'native-termux-control-of-optional-proot',
 'ownership': {'authority': 'ternuxx-terminal-broker',
               'status': 'exact-session-identity-checked',
               'evidence': 'terminal.broker.status'},
 'state': {'current': 'not-queried',
           'desired': 'owner-started-optional-broker',
           'readiness': 'query-required',
           'source_operation': 'terminal.broker.status'},
 'configuration': {'schema_id': 'terminal-broker-request-v1', 'defaults': {}, 'contains_secrets': False},
 'supported_operations': ['terminal.broker.status',
                          'terminal.broker.service.status',
                          'terminal.broker.service.install.preview',
                          'terminal.broker.service.install.apply',
                          'terminal.broker.service.start.preview',
                          'terminal.broker.service.start.apply',
                          'terminal.start.preview',
                          'terminal.start',
                          'terminal.attach',
                          'terminal.input',
                          'terminal.resize',
                          'terminal.output',
                          'terminal.detach',
                          'terminal.close.preview',
                          'terminal.close'],
 'planned_operations': [],
 'dependencies': [],
 'dependants': [],
 'background': {'supported': True, 'status': 'optional-previewed-runit-service'},
 'boot': {'configurable': False, 'status': 'follows-Termux-services-lifecycle'},
 'logs': {'status': 'broker-errors-only', 'path': '$TERNUXX_STATE_DIR/log/terminal-broker-runit.log'},
 'diagnostics': ['terminal.broker.status'],
 'recovery': [],
 'identity': {'source': 'fixed-profile private Unix socket and Linux peer credentials',
              'installed': 'preview-confirmed-runit-service',
              'version': 'protocol-v1'},
 'security': {'read_only': False,
              'disruptive_operations': ['terminal.start', 'terminal.input', 'terminal.close'],
              'secret_values_returned': False}} ,
    {"id":"graphics.native", "category_id":"graphics-acceleration", "name":"Native Termux graphics", "description":"Native Bionic graphics probes and backend selection. The graphical package profile installs Termux Mesa Freedreno Vulkan ICD; termux-zink selects it for future Native X11 starts. KGSL candidate is experimental, device-specific, and has no Ternuxx installer. Status, context, and enumeration do not prove a rendered workload.", "status":"partial", "availability":"live-probe", "provider":"native-termux", "environment":"native-termux-bionic", "ownership":{"authority":"ternuxx-native-graphics-selector","status":"managed-preference","evidence":"graphics.provider.status"}, "state":{"current":"not-queried","desired":"existing-device-setting","readiness":"probe-required","source_operation":"graphics.provider.status"}, "configuration":{"schema_id":"native-graphics-selector-v1","defaults":{},"contains_secrets":False}, "supported_operations":["graphics.provider.status","graphics.provider.verify","graphics.provider.select"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":False,"status":"no-service-lifecycle-control"}, "boot":{"configurable":False,"status":"desktop-environment-only"}, "logs":{"status":"not-recorded","path":""}, "diagnostics":["graphics.provider.status","graphics.provider.verify"], "recovery":[], "identity":{"source":"native process renderer and tool output","installed":"device-probe","version":"runtime"}, "security":{"read_only":False,"disruptive_operations":["graphics.provider.select"],"secret_values_returned":False}},
    {"id":"inference.cpu.local", "category_id":"ai-providers", "name":"Native CPU inference", "description":"Run bounded local llama.cpp inference with the pinned checksum-verified model on CPU. Network-isolated/offline execution has not been verified.", "status":"partial", "availability":"native-cpu-local-runtime", "provider":"native-termux", "environment":"native-termux-bionic", "ownership":{"authority":"termux-package-manager-and-ternux-model-state", "status":"runtime-external-model-managed", "evidence":"inference.cpu.status"}, "state":{"current":"not-queried", "desired":"bounded-local-cpu", "readiness":"runtime-and-model-probe-required", "source_operation":"inference.cpu.status"}, "configuration":{"schema_id":"pinned-cpu-model-v1", "defaults":{"model_id":"qwen3-0.6b-q4_0", "gpu_layers":0, "max_output_tokens":64}, "contains_secrets":False}, "supported_operations":["inference.cpu.status","inference.cpu.model.preview","inference.cpu.model.apply","inference.cpu.run"], "planned_operations":[], "dependencies":["Termux llama-cpp package", "Qwen3 0.6B Q4_0 model (Apache-2.0)"], "dependants":[], "background":{"supported":False,"status":"foreground-bounded-run"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"not-recorded","path":""}, "diagnostics":["inference.cpu.status"], "recovery":["interrupted-download-temporary-file-cleanup"], "identity":{"source":"Termux package metadata and pinned Hugging Face file hash","installed":"runtime-external-model-state-managed","version":"runtime-queried-at-status"}, "security":{"read_only":False,"disruptive_operations":["inference.cpu.model.apply","inference.cpu.run"],"secret_values_returned":False}},
    {"id":"inference.gpu.local", "category_id":"ai-providers", "name":"Native Vulkan inference", "description":"Run a bounded pinned-model prompt on an explicitly selected Vulkan llama.cpp device; status is based on runtime-reported devices and successful runs require GPU-layer offload proof.", "status":"partial", "availability":"native-vulkan-runtime-probe", "provider":"native-termux", "environment":"native-termux-bionic", "ownership":{"authority":"termux-package-manager-and-ternux-model-state", "status":"runtime-external-model-managed", "evidence":"inference.gpu.status"}, "state":{"current":"not-queried", "desired":"verified-vulkan-inference", "readiness":"package-device-and-model-probe-required", "source_operation":"inference.gpu.status"}, "configuration":{"schema_id":"pinned-vulkan-inference-v1", "defaults":{"model_id":"qwen3-0.6b-q4_0","max_output_tokens":64}, "contains_secrets":False}, "supported_operations":["inference.gpu.status","inference.gpu.run"], "planned_operations":[], "dependencies":["Termux llama-cpp package","Termux llama-cpp-backend-vulkan package","Vulkan-capable device","Qwen3 0.6B Q4_0 model (Apache-2.0)"], "dependants":[], "background":{"supported":False,"status":"foreground-bounded-run"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"not-recorded","path":""}, "diagnostics":["inference.gpu.status"], "recovery":[], "identity":{"source":"llama.cpp --list-devices and per-run offload log","installed":"runtime-probed","version":"queried-at-status"}, "security":{"read_only":False,"disruptive_operations":["inference.gpu.run"],"secret_values_returned":False}},
    {"id":"inference.npu.local", "category_id":"ai-providers", "name":"Native Hexagon NPU inference", "description":"Experimental Native llama.cpp HTP0 inference using a pinned MIT upstream Snapdragon artifact. The live path is verified only on SM8735, requires explicit runtime installation, and fails without full HTP layer delegation; CPU fallback is disabled. Current one-model measurements show offload but not a speedup over CPU.", "status":"partial", "availability":"experimental-sm8735-htp0", "provider":"native-termux", "environment":"native-termux-bionic", "ownership":{"authority":"ternuxx-pinned-upstream-artifact-cache", "status":"release-sha256-and-per-run-offload-checked", "evidence":"inference.npu.status"}, "state":{"current":"not-queried", "desired":"verified-htp-inference", "readiness":"runtime-device-model-and-offload-probe-required", "source_operation":"inference.npu.status"}, "configuration":{"schema_id":"native-hexagon-htp-v1", "defaults":{"model_id":"qwen3-0.6b-q4_0","device_id":"HTP0","max_output_tokens":64,"experimental":True}, "contains_secrets":False}, "supported_operations":["inference.npu.status","inference.npu.runtime.preview","inference.npu.runtime.apply","inference.npu.run"], "planned_operations":[], "dependencies":["SM8735 device","pinned llama.cpp b11849 Android Snapdragon release (MIT)","pinned Qwen3 0.6B Q4_0 model"], "dependants":[], "background":{"supported":False,"status":"foreground-bounded-run"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"not-recorded","path":""}, "diagnostics":["inference.npu.status"], "recovery":[], "identity":{"source":"GitHub release asset SHA-256, runtime device list, HTP layer and buffer logs","installed":"private-app-state-verified-release","version":"b11849"}, "security":{"read_only":False,"disruptive_operations":["inference.npu.runtime.apply","inference.npu.run"],"secret_values_returned":False}},
    {"id":"native.acceleration.qualification", "category_id":"system-health", "name":"CPU / GPU / NPU qualification", "description":"Read-only CPU baseline and context-separated accelerator diagnostics. Device/library presence is not workload acceleration; Native Termux remains the only supported execution environment.", "status":"partial", "availability":"diagnostics-available-workload-integrations-unqualified", "provider":"native-termux", "environment":"native-termux-evidence", "ownership":{"authority":"ternuxx-diagnostics", "status":"read-only-evidence", "evidence":"doctor.report"}, "state":{"current":"not-queried", "desired":"verified-per-workload", "readiness":"named-runtime-and-workload-required", "source_operation":"doctor.report"}, "configuration":{"schema_id":"doctor-report.schema.json", "defaults":{"graphics":True}, "contains_secrets":False}, "supported_operations":["doctor.report"], "planned_operations":["compute.runtime.inventory","compute.workload.preview","compute.workload.run"], "dependencies":[], "dependants":[], "background":{"supported":False, "status":"not-applicable"}, "boot":{"configurable":False, "status":"not-applicable"}, "logs":{"status":"not-catalogued", "path":""}, "diagnostics":["doctor.report"], "recovery":[], "identity":{"source":"repository-owned read-only diagnostics", "installed":"not-checked", "version":"unknown"}, "security":{"read_only":True, "disruptive_operations":[], "secret_values_returned":False}},
    {"id":"native.system.health", "category_id":"system-health", "name":"Native Termux health", "description":"Read-only device and capability diagnostics.", "status":"implemented", "availability":"available", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-diagnostics", "status":"verified-contract", "evidence":"doctor.report"}, "state":{"current":"not-queried", "desired":"observe", "readiness":"query-required", "source_operation":"doctor.report"}, "configuration":{"schema_id":"doctor-report.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["doctor.report","management.logs.list","management.logs.read"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":False, "status":"not-applicable"}, "boot":{"configurable":False, "status":"not-applicable"}, "logs":{"status":"bounded-owned-sources", "path":""}, "diagnostics":["doctor.report","management.logs.list","management.logs.read"], "recovery":[], "identity":{"source":"repository-owned diagnostic code", "installed":"not-checked", "version":"unknown"}, "security":{"read_only":True, "disruptive_operations":[], "secret_values_returned":False}},
    {"id":"native.timezone", "category_id":"system-health", "name":"System timezone", "description":"Persistent IANA timezone preference backed by the installed system timezone database.", "status":"implemented", "availability":"runtime-timezone-data-checked-by-status", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-timezone-preference", "status":"private-atomic-config", "evidence":"timezone.status"}, "state":{"current":"not-queried", "desired":"Asia/Dhaka-by-default", "readiness":"query-required", "source_operation":"timezone.status"}, "configuration":{"schema_id":"timezone-config-v1.schema.json", "defaults":{"timezone":"Asia/Dhaka"}, "contains_secrets":False}, "supported_operations":["timezone.status","timezone.list","timezone.set"], "planned_operations":["timezone.installation-suggestion"], "dependencies":[], "dependants":["automation.cron-registry"], "background":{"supported":False,"status":"not-applicable"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"not-available","path":""}, "diagnostics":["timezone.status","timezone.list"], "recovery":[], "identity":{"source":"Android packed tzdata or system TZif files", "installed":"runtime-detected", "version":"queried-at-status"}, "security":{"read_only":False,"disruptive_operations":["timezone.set"],"secret_values_returned":False}},
    {"id":"native.desktop.session", "category_id":"desktop-audio", "name":"Native GUI session", "description":"Ternuxx-owned Termux:X11 session with provider-specific selectable desktop launchers; XFCE remains the default.", "status":"implemented", "availability":"available", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-session-supervisor", "status":"identity-checked", "evidence":"desktop.status"}, "state":{"current":"not-queried", "desired":"owner-configured", "readiness":"query-required", "source_operation":"desktop.status"}, "configuration":{"schema_id":"desktop-session-recovery.schema.json", "defaults":{"display":":1"}, "contains_secrets":False}, "supported_operations":["desktop.status","desktop.start","desktop.stop","desktop.restart"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":True, "status":"supervisor-managed"}, "boot":{"configurable":True, "status":"profile-controlled-delivery-unverified"}, "logs":{"status":"available", "path":"$TERNUXX_STATE_DIR/desktop.log"}, "diagnostics":["desktop.status","doctor.report"], "recovery":["desktop.start"], "identity":{"source":"session record and proc identities", "installed":"source-backed-cli", "version":"unknown"}, "security":{"read_only":False, "disruptive_operations":["desktop.stop","desktop.restart"], "secret_values_returned":False}},
    {"id":"native.gui.activity-monitor", "category_id":"desktop-audio", "name":"Android Activity monitoring policy", "description":"Optional Termux:X11 Activity and focus checks; disabled by default.", "status":"partial", "availability":"available", "provider":"native-termux", "environment":"android-host-via-termux", "ownership":{"authority":"ternuxx-monitor-policy", "status":"configuration-managed", "evidence":"desktop.monitor.status"}, "state":{"current":"not-queried", "desired":"disabled-by-default", "readiness":"query-required", "source_operation":"desktop.monitor.status"}, "configuration":{"schema_id":"gui-monitoring-policy.schema.json", "defaults":{"enabled":False,"interval_seconds":300,"activity_launch":False,"focus_check":False}, "contains_secrets":False}, "supported_operations":["desktop.monitor.status","desktop.monitor.configure"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"query-required"}, "boot":{"configurable":False,"status":"not-enabled"}, "logs":{"status":"not-recorded","path":""}, "diagnostics":["desktop.monitor.status"], "recovery":[], "identity":{"source":"schema-validated private policy", "installed":"source-hash-match", "version":"1"}, "security":{"read_only":False,"disruptive_operations":[],"secret_values_returned":False}},
    {"id":"native.audio.pulseaudio", "category_id":"desktop-audio", "name":"Native audio server", "description":"Ternuxx identity-manages Native PulseAudio; Native applications consume its authenticated loopback endpoint. UI lifecycle parity and audible output remain unqualified.", "status":"partial", "availability":"native-cli-managed-ui-actions-unavailable", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-native-pulse-lifecycle", "status":"identity-checked-lifecycle-protocol-verified", "evidence":"tx.audio.status; tx.db.pactl"}, "state":{"current":"not-queried", "desired":"ternuxx-native-protocol-server", "readiness":"explicit-authenticated-probe-required", "source_operation":"doctor.report"}, "configuration":{"schema_id":"private-managed-pulse-config", "defaults":{"server":"tcp:127.0.0.1:4713","auth":"native-cookie"}, "contains_secrets":False}, "supported_operations":["doctor.report"], "planned_operations":["audio.server.status","audio.server.start","audio.server.stop","audio.server.restart","audio.client.inspect"], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"identity-managed-native-process"}, "boot":{"configurable":False,"status":"not-enabled"}, "logs":{"status":"available","path":"$TERNUXX_STATE_DIR/audio/pulseaudio.log"}, "diagnostics":["doctor.report"], "recovery":[], "identity":{"source":"private record and process identity plus authenticated TCP readiness", "installed":"Native PulseAudio package", "version":"17.0-dirty"}, "security":{"read_only":True,"disruptive_operations":[],"secret_values_returned":False}},
    {"id":"network.ssh.external-native", "category_id":"networking", "name":"External Native SSH configuration", "description":"Owner-started development access; visible for diagnostics only.", "status":"external", "availability":"available", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"owner-manual", "status":"external-do-not-manage", "evidence":"ssh.inspect"}, "state":{"current":"not-queried", "desired":"externally-managed", "readiness":"query-required", "source_operation":"ssh.inspect"}, "configuration":{"schema_id":"native-ssh-config.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["ssh.inspect"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"owner-managed"}, "boot":{"configurable":False,"status":"owner-managed"}, "logs":{"status":"external-unverified","path":""}, "diagnostics":["ssh.inspect"], "recovery":[], "identity":{"source":"listener-to-process mapping restricted", "installed":"system sshd/config visible", "version":"unknown"}, "security":{"read_only":True,"disruptive_operations":[],"secret_values_returned":False}},
    {"id":"network.ssh.managed-8023", "category_id":"services", "name":"Ternuxx SSH service · 8023", "description":"Runit-managed loopback OpenSSH service; public-key login only. Ternuxx authorized keys are isolated from owner-managed SSH configuration.", "status":"implemented", "availability":"available", "provider":"runit", "environment":"native-termux", "ownership":{"authority":"ternuxx-sshd", "status":"query-required", "evidence":"ssh.inspect"}, "state":{"current":"not-queried", "desired":"owner-configured", "readiness":"query-required", "source_operation":"ssh.inspect"}, "configuration":{"schema_id":"native-ssh-service-action.schema.json", "defaults":{"port":8023,"bind":"127.0.0.1"}, "contains_secrets":False}, "supported_operations":["ssh.inspect","ssh.keys.list","ssh.keys.add.preview","ssh.keys.add.apply","ssh.keys.remove.preview","ssh.keys.remove.apply","ssh.keys.rollback.list","ssh.keys.rollback.preview","ssh.keys.rollback.apply","ssh.client-key.create.preview","ssh.client-key.create.apply","ssh.service.autostart.status","ssh.service.autostart.preview","ssh.service.autostart.apply","ssh.service.start","ssh.service.stop","ssh.service.restart","ssh.service.deploy","ssh.service.deploy.rollback.preview","ssh.service.deploy.rollback.apply"], "planned_operations":["ssh.service.enable","ssh.service.disable","ssh.service.logs"], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"runit-supervised"}, "boot":{"configurable":True,"status":"Runit down marker controls next supervisor startup; Android cold-boot readiness unverified"}, "logs":{"status":"not-recorded", "path":""}, "diagnostics":["ssh.inspect"], "recovery":["ssh.keys.rollback.list","ssh.keys.rollback.preview","ssh.keys.rollback.apply","ssh.service.deploy.rollback.preview","ssh.service.deploy.rollback.apply"], "identity":{"source":"runit service definition", "installed":"query-required", "version":"unknown"}, "security":{"read_only":False,"disruptive_operations":["ssh.service.stop","ssh.service.restart","ssh.service.deploy","ssh.service.deploy.rollback.apply","ssh.keys.add.apply","ssh.keys.remove.apply","ssh.keys.rollback.apply","ssh.client-key.create.apply","ssh.service.autostart.apply"],"secret_values_returned":False}},
    {"id":"boot.termux.profile", "category_id":"boot-automation", "name":"Termux:Boot profile", "description":"Ternuxx-owned boot profile and script delivery.", "status":"partial", "availability":"available", "provider":"native-termux", "environment":"android-host-via-termux", "ownership":{"authority":"ternuxx-boot-profile", "status":"managed-generated-script-identity-queried", "evidence":"boot.profile.status"}, "state":{"current":"not-queried", "desired":"owner-configured", "readiness":"cold-boot-unverified", "source_operation":"boot.profile.status"}, "configuration":{"schema_id":"boot-profile.schema.json", "defaults":{"profile":"cli-only"}, "contains_secrets":False}, "supported_operations":["boot.status","boot.profile.status","boot.profile.preview","boot.helpers.status","boot.helpers.preview","boot.helpers.apply","boot.enable","boot.disable"], "planned_operations":["boot.service.catalog","boot.service.autostart.configure"], "dependencies":[], "dependants":["network.ssh.managed-8023","native.desktop.session"], "background":{"supported":True,"status":"boot-script-managed"}, "boot":{"configurable":True,"status":"delivery-and-cold-boot-unverified"}, "logs":{"status":"available", "path":"$HOME/.termux/boot"}, "diagnostics":["boot.status","boot.profile.status"], "recovery":["recovery.status"], "identity":{"source":"profile-specific script generated by boot profile planner", "installed":"live-query-required", "version":"profile-schema-v2"}, "security":{"read_only":False,"disruptive_operations":["boot.helpers.apply","boot.enable","boot.disable"],"secret_values_returned":False}},
    {"id":"boot.termux.cron", "category_id":"boot-automation", "name":"Termux:Boot Cron startup", "description":"Opt-in official Termux:Boot script that starts only the Ternuxx Cron daemon through tx mng cron start.", "status":"partial", "availability":"opt-in-not-configured", "provider":"official-termux-boot", "environment":"native-termux", "ownership":{"authority":"ternuxx-cron-boot-entrypoint", "status":"create-only-owned-script", "evidence":"boot.cron.status"}, "state":{"current":"not-configured", "desired":"owner-opt-in", "readiness":"device-boot-delivery-unverified", "source_operation":"boot.cron.status"}, "configuration":{"schema_id":"termux-boot-cron.schema.json", "defaults":{"enabled":False}, "contains_secrets":False}, "supported_operations":["boot.cron.status","boot.cron.validate","boot.cron.preview","boot.cron.enable","boot.cron.disable"], "planned_operations":[], "dependencies":["automation.cron-registry","official-termux-boot-app"], "dependants":[], "background":{"supported":True,"status":"cron-daemon-only; runtime duplicate guard uses scheduler lease"}, "boot":{"configurable":True,"status":"opt-in; actual device-boot delivery not verified"}, "logs":{"status":"bounded-private-script-result", "path":"$TERNUXX_STATE_DIR/cron/boot/termux-boot-cron.jsonl"}, "diagnostics":["boot.cron.status","boot.cron.validate"], "recovery":[], "identity":{"source":"generated dedicated Termux:Boot script", "installed":"not-configured", "version":"1"}, "security":{"read_only":False,"disruptive_operations":["boot.cron.enable","boot.cron.disable"],"secret_values_returned":False}},
    {"id":"recovery.native-state", "category_id":"security-recovery", "name":"Native state backup & recovery", "description":"Previewed backup, restore, operation recovery, task checkpoints, and detailed reboot qualification.", "status":"partial", "availability":"available", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-private-state", "status":"path-checked", "evidence":"recovery.status"}, "state":{"current":"not-queried", "desired":"preserve", "readiness":"query-required", "source_operation":"recovery.status"}, "configuration":{"schema_id":"config-backup.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["backup.create","backup.list","backup.inspect","restore.preview","restore.apply","recovery.status","recovery.resolve","recovery.inspect","recovery.rollback.preview","recovery.rollback.apply","continuity.status","continuity.prepare.preview","continuity.prepare","continuity.verify.preview","continuity.verify","continuity.prepare-reboot-test.preview","continuity.prepare-reboot-test","continuity.verify-reboot-test.preview","continuity.verify-reboot-test","continuity.resume-info"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":False,"status":"operation-scoped"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"available", "path":"$TERNUXX_STATE_DIR/operations"}, "diagnostics":["recovery.status","backup.list"], "recovery":["recovery.inspect","recovery.rollback.preview","recovery.rollback.apply"], "identity":{"source":"repository recovery modules", "installed":"source-backed-cli", "version":"unknown"}, "security":{"read_only":False,"disruptive_operations":["restore.apply","recovery.resolve","recovery.rollback.apply"],"secret_values_returned":False}},
    {"id":"native.wakelock", "category_id":"services", "name":"Termux Wake Lock", "description":"Owner-scoped Android Wake Lock leases; Native managed SSH persistent-lease policy applies on its next service start.", "status":"implemented", "availability":"available", "provider":"native-termux", "environment":"android-host-via-termux", "ownership":{"authority":"ternuxx-wakelock-manager", "status":"lease-owner-checked", "evidence":"wakelock.status"}, "state":{"current":"not-queried", "desired":"owner-configured", "readiness":"query-required", "source_operation":"wakelock.status"}, "configuration":{"schema_id":"wakelock-owner-state.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["wakelock.status","wakelock.acquire","wakelock.release","wakelock.ssh-policy.status","wakelock.ssh-policy.preview","wakelock.ssh-policy.apply"], "planned_operations":[], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"owner-leased"}, "boot":{"configurable":False,"status":"native.sshd user policy applies on next service start"}, "logs":{"status":"available", "path":"$TERNUXX_STATE_DIR/wakelock"}, "diagnostics":["wakelock.status"], "recovery":[], "identity":{"source":"lease record and caller PID", "installed":"source-backed-cli", "version":"unknown"}, "security":{"read_only":False,"disruptive_operations":[],"secret_values_returned":False}},
    {"id":"software.native-packages", "category_id":"software", "name":"Native Termux packages", "description":"Package inventory and supported native install preview/apply flow.", "status":"partial", "availability":"available", "provider":"native-termux", "environment":"termux-bionic", "ownership":{"authority":"pkg-and-apt-package-managers", "status":"package-manager-owned", "evidence":"tx install"}, "state":{"current":"not-queried", "desired":"owner-configured", "readiness":"query-required", "source_operation":"doctor.report"}, "configuration":{"schema_id":"install-package-preview.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["doctor.report"], "planned_operations":["software.inventory","software.install.preview","software.install.apply","software.remove.preview","software.update.preview"], "dependencies":[], "dependants":[], "background":{"supported":False,"status":"package-manager-operation"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"package-manager-owned", "path":""}, "diagnostics":["doctor.report"], "recovery":[], "identity":{"source":"Termux package database", "installed":"not-queried", "version":"package-specific"}, "security":{"read_only":False,"disruptive_operations":["software.install.apply"],"secret_values_returned":False}},
    {"id":"software.curated-apps", "category_id":"software", "name":"Curated Native Termux apps", "description":"Manage three reviewed htop, tmux, and tree app IDs from official Termux repositories. Install/update/remove use exact saved plans; directory-tree also accepts bounded, read-only paths inside Native HOME.", "status":"implemented", "availability":"fresh-official-index-required", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"Termux APT/dpkg", "status":"package-manager-owned", "evidence":"software.apps.list"}, "state":{"current":"not-queried", "desired":"curated-app-ids-only", "readiness":"fresh-official-index-required", "source_operation":"software.apps.list"}, "configuration":{"schema_id":"optional-software-catalog.schema.json", "defaults":{}, "contains_secrets":False}, "supported_operations":["software.apps.list","software.app.preview","software.app.apply","software.app.run"], "planned_operations":[], "dependencies":["official termux-main package indexes"], "dependants":[], "background":{"supported":False,"status":"foreground-preview-first-package-operation"}, "boot":{"configurable":False,"status":"not-applicable"}, "logs":{"status":"package-manager-result-recorded", "path":"private Ternuxx state"}, "diagnostics":["software.apps.list"], "recovery":["stale-or-failed-plan-requires-a-new-preview"], "identity":{"source":"configured signed Termux APT indexes", "installed":"queried-through-dpkg", "version":"candidate-rechecked-at-preview"}, "security":{"read_only":False,"disruptive_operations":["software.app.apply"],"secret_values_returned":False}},
    {"id":"server.generic-deployment", "category_id":"deployments", "name":"Managed server deployments", "description":"General server templates and deployment lifecycle are not implemented.", "status":"planned", "availability":"not-implemented", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"not-implemented", "status":"not-managed", "evidence":"management.catalog"}, "state":{"current":"unavailable", "desired":"owner-configured", "readiness":"not-implemented", "source_operation":"management.catalog"}, "configuration":{"schema_id":"none", "defaults":{}, "contains_secrets":False}, "supported_operations":[], "planned_operations":["server.template.list","server.deploy.preview","server.deploy.apply","server.status","server.logs","server.remove.preview"], "dependencies":[], "dependants":[], "background":{"supported":False,"status":"not-implemented"}, "boot":{"configurable":False,"status":"not-implemented"}, "logs":{"status":"not-available", "path":""}, "diagnostics":[], "recovery":[], "identity":{"source":"not-implemented", "installed":"not-implemented", "version":"unknown"}, "security":{"read_only":True,"disruptive_operations":[],"secret_values_returned":False}},
    {"id":"automation.cron-registry", "category_id":"boot-automation", "name":"Ternuxx Cron Job Registry", "description":"Persistent schedules, atomic claims, a lease-guarded Termux scheduler runtime and a bounded typed-action executor; device boot delivery is not installed.", "status":"partial", "availability":"registry-ledger-runtime-available-not-started", "provider":"native-termux", "environment":"native-termux", "ownership":{"authority":"ternuxx-cron-registry-and-ledger", "status":"private-atomic-schema-v1", "evidence":"cron.status"}, "state":{"current":"scheduler-runtime-available", "desired":"owner-configured", "readiness":"runtime-start-required", "source_operation":"cron.status"}, "configuration":{"schema_id":"cron-job-v1", "defaults":{"enabled":False,"run_after_device_boot":False,"run_after_scheduler_recovery":False}, "contains_secrets":False}, "supported_operations":["cron.status","cron.scheduler.start","cron.scheduler.stop","cron.executor.self_test","cron.jobs.list","cron.jobs.show","cron.jobs.validate","cron.jobs.next_runs","cron.jobs.mutation.preview","cron.jobs.mutation.apply","cron.executions.list","cron.executions.show"], "planned_operations":["cron.scheduler.start","cron.device-boot.deliver","cron.scheduler-recovery.deliver","cron.execution.cancel","cron.retry","cron.queue-one","cron.watchdog"], "dependencies":[], "dependants":[], "background":{"supported":True,"status":"explicit-user-start-no-boot-integration"}, "boot":{"configurable":True,"status":"trigger-fields-persisted-delivery-unqualified"}, "logs":{"status":"bounded-execution-summaries-only", "path":"$TERNUXX_STATE_DIR/cron/executions.json"}, "diagnostics":["cron.status","cron.executions.list"], "recovery":[], "identity":{"source":"private atomic versioned JSON registry and execution ledger", "installed":"native-state", "version":"1"}, "security":{"read_only":False,"disruptive_operations":["cron.scheduler.start","cron.scheduler.stop","cron.jobs.mutation.preview","cron.jobs.mutation.apply"],"secret_values_returned":False}},
    {"id":"agent.hermes", "category_id":"ai-providers", "name":"Hermes Agent scheduler", "description":"Optional native Hermes provider; this integration currently inspects scheduler status only and does not read task contents or manage schedules.", "status":"partial", "availability":"optional-provider-runtime-detected", "provider":"hermes-agent", "environment":"native-termux", "ownership":{"authority":"hermes-agent", "status":"externally-managed-independent-scheduler", "evidence":"agent.hermes.status"}, "state":{"current":"not-queried", "desired":"hermes-owned", "readiness":"query-required", "source_operation":"agent.hermes.status"}, "configuration":{"schema_id":"none", "defaults":{}, "contains_secrets":False}, "supported_operations":["agent.hermes.status"], "planned_operations":["agent.hermes.tasks.list","agent.hermes.task.validate","agent.hermes.execution.preview","agent.hermes.execution.run","agent.hermes.execution.cancel","agent.hermes.scheduler.bridge"], "dependencies":[], "dependants":[], "background":{"supported":"external", "status":"Hermes-owned-scheduler"}, "boot":{"configurable":False, "status":"independent-unverified"}, "logs":{"status":"not-read-by-adapter", "path":""}, "diagnostics":["agent.hermes.status"], "recovery":[], "identity":{"source":"verified local Hermes CLI read-only status", "installed":"runtime-detected", "version":"queried-at-status"}, "security":{"read_only":True, "disruptive_operations":[], "secret_values_returned":False}},
    {"id":"ai.runtime-providers", "category_id":"ai-providers", "name":"Remote AI providers", "description":"Cloud endpoints and selectable API providers are not implemented; local llama.cpp CPU, Vulkan, and HTP inference are listed separately.", "status":"planned", "availability":"not-implemented", "provider":"cloud-api", "environment":"not-configured", "ownership":{"authority":"not-implemented", "status":"not-managed", "evidence":"management.catalog"}, "state":{"current":"unavailable", "desired":"owner-configured", "readiness":"not-implemented", "source_operation":"management.catalog"}, "configuration":{"schema_id":"none", "defaults":{}, "contains_secrets":False}, "supported_operations":[], "planned_operations":["ai.runtime.list","ai.model.inventory","ai.model.load","ai.provider.health","ai.endpoint.configure"], "dependencies":[], "dependants":[], "background":{"supported":False,"status":"not-implemented"}, "boot":{"configurable":False,"status":"not-implemented"}, "logs":{"status":"not-available", "path":""}, "diagnostics":[], "recovery":[], "identity":{"source":"not-implemented", "installed":"not-implemented", "version":"unknown"}, "security":{"read_only":True,"disruptive_operations":[],"secret_values_returned":False}},
]

_VALID_STATUS = {"implemented", "partial", "external", "unverified", "unavailable", "planned"}


def _matches(resource: Resource, query: str) -> bool:
    haystack = " ".join((resource["id"], resource["name"], resource["description"], resource["category_id"], resource["provider"], *resource["supported_operations"], *resource["planned_operations"]))
    return query.casefold() in haystack.casefold()


def build_catalog(implemented_operations: set[str], *, category: str | None = None,
                  query: str | None = None, status: str | None = None) -> dict[str, object]:
    """Return discovery metadata; never probes or mutates live resources."""
    category_ids = {item["id"] for item in CATEGORIES}
    if category is not None and not isinstance(category, str):
        raise ValueError("resource category must be a string")
    if category is not None and category not in category_ids:
        raise ValueError("unknown resource category")
    if query is not None and (not isinstance(query, str) or len(query) > 120):
        raise ValueError("resource query must be a string up to 120 characters")
    if status is not None and not isinstance(status, str):
        raise ValueError("resource status must be a string")
    if status is not None and status not in _VALID_STATUS:
        raise ValueError("unknown resource status")

    categories = [dict(item) for item in CATEGORIES]
    resources = []
    for source in RESOURCES:
        if category is not None and source["category_id"] != category:
            continue
        if status is not None and source["status"] != status:
            continue
        if query and not _matches(source, query):
            continue
        resource = dict(source)
        resource["supported_operations"] = [op for op in source["supported_operations"] if op in implemented_operations]
        resource["operation_capabilities"] = {
            op: management_authorization.required_capability(op)
            for op in resource["supported_operations"]
        }
        resource["unavailable_operations"] = [op for op in source["supported_operations"] if op not in implemented_operations]
        resources.append(resource)

    if category is not None:
        categories = [item for item in categories if item["id"] == category]
    if query:
        matched_category_ids = {item["category_id"] for item in resources}
        categories = [item for item in categories if item["id"] in matched_category_ids]
    return {
        "schema_version": 2,
        "read_only": True,
        "providers": PROVIDERS,
        "domains": [
            {**domain,
             "available_operations": [op for op in domain.get("operations", []) if op in implemented_operations],
             "unavailable_operations": [op for op in domain.get("operations", []) if op not in implemented_operations]}
            for domain in DOMAINS
        ],
        "categories": categories,
        "resources": resources,
        "filters": {"category": category, "query": query, "status": status},
        "policy": {"mutations_require_preview_and_explicit_confirmation": True,
                   "external_cloud_calls_enabled": False, "credentials_in_catalog": False},
    }
