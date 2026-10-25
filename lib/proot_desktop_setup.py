"""Preview-bound additional Debian desktop package transactions."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

import proot_desktops
import proot_fresh_setup
import proot_guest_retirement


class DesktopSetupError(ValueError):
    pass


def _rootfs(prefix: str) -> tuple[Path, dict[str, int]]:
    container, root = proot_fresh_setup._target_paths(prefix, "debian")
    try:
        ident = proot_fresh_setup._root_identity(container, root)
        release_path = root / "etc/os-release"
        resolved_release = release_path.resolve(strict=True)
        if root.resolve(strict=True) not in resolved_release.parents:
            raise DesktopSetupError("Debian release identity resolves outside the managed rootfs")
        release_info = resolved_release.stat()
        if not stat.S_ISREG(release_info.st_mode) or release_info.st_size > 64 * 1024:
            raise DesktopSetupError("Debian release identity is unsafe")
        release = resolved_release.read_text(encoding="utf-8")
    except (OSError, proot_fresh_setup.FreshSetupError) as exc:
        raise DesktopSetupError("the managed Debian rootfs is unavailable or unsafe") from exc
    values = {}
    for line in release.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key] = value.strip().strip('"')
    if values.get("ID") != "debian" or values.get("VERSION_CODENAME") != "trixie":
        raise DesktopSetupError("additional desktop installation currently requires managed Debian Trixie")
    return root, ident


def _private_digest(path: Path) -> str:
    if path.is_symlink():
        raise DesktopSetupError("guest package state contains a symbolic link")
    try:
        info = path.stat()
        if not path.is_file() or info.st_size > 128 * 1024 * 1024:
            raise DesktopSetupError("guest package state is not a bounded regular file")
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise DesktopSetupError("guest package state cannot be read") from exc


def _package_inventory(root: Path) -> dict[str, str]:
    status = root / "var/lib/dpkg/status"
    if status.is_symlink():
        raise DesktopSetupError("guest dpkg status is unsafe")
    try:
        raw = status.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DesktopSetupError("guest dpkg status is unavailable") from exc
    result: dict[str, str] = {}
    for paragraph in raw.split("\n\n"):
        fields = {}
        for line in paragraph.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if fields.get("Status") == "install ok installed":
            name, version = fields.get("Package", ""), fields.get("Version", "")
            if re.fullmatch(r"[a-z0-9][a-z0-9+.-]{0,127}(?::[a-z0-9-]+)?", name) and version:
                result[name] = version
    return result


def _source_digest(root: Path) -> str:
    base = root / "etc/apt"
    records = []
    for path in (base / "sources.list", *(base / "sources.list.d").glob("*")):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not path.is_file() or path.is_symlink() or info.st_size > 1024 * 1024:
            raise DesktopSetupError("guest APT source identity is unsafe")
        records.append((str(path.relative_to(base)), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(sorted(records), separators=(",", ":")).encode()).hexdigest()


def _run_guest(prefix: str, packages: list[str], *, apply: bool,
               runner=subprocess.run) -> dict[str, object]:
    manager = str(Path(prefix) / "bin/proot-distro")
    apt = ["/usr/bin/apt-get", "--no-install-recommends", "--no-upgrade", "--no-remove",
           "-o", "Acquire::https::User-Agent=curl/8",
           "-o", "Acquire::https::Pipeline-Depth=0",
           "-o", "Acquire::https::Timeout=60",
           "-o", "Acquire::https::Retries=2"]
    if apply:
        apt += ["-y", "install", *packages]
    else:
        apt += ["--simulate", "--yes", "install", *packages]
    env = {key: value for key, value in os.environ.items()
           if key not in {"DBUS_SESSION_BUS_ADDRESS", "DBUS_SESSION_BUS_PID", "DBUS_STARTER_ADDRESS",
                          "DBUS_STARTER_BUS_TYPE", "LD_LIBRARY_PATH", "LD_PRELOAD", "DISPLAY"}
           and not key.startswith("ANDROID_")}
    command = [manager, "run", "debian", "--isolated", "--env",
               "DEBIAN_FRONTEND=noninteractive", "--"]
    result = runner([*command, *apt], capture_output=True, text=True, check=False, timeout=7200 if apply else 1800, env=env)
    output = (getattr(result, "stdout", "") or "") + "\n" + (getattr(result, "stderr", "") or "")
    estimate_output = output
    if not isinstance(output, str) or len(output) > 16 * 1024 * 1024:
        raise DesktopSetupError("guest APT output is invalid or too large")
    summary = re.search(r"^(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded\.", output, re.MULTILINE)
    if summary is None:
        raise DesktopSetupError("guest APT did not provide a complete transaction summary")
    upgraded, new_count, removed, not_upgraded = map(int, summary.groups())
    if upgraded or removed:
        raise DesktopSetupError("desktop transaction would upgrade or remove existing packages")
    if not apply and getattr(result, "returncode", 1) != 0:
        raise DesktopSetupError("guest APT simulation failed: " + output[-1200:].strip())
    estimate_result = result
    if not apply:
        estimate_result = runner([*command, *apt[:apt.index("--simulate")], "--assume-no",
                                  "install", *packages], capture_output=True, text=True,
                                 check=False, timeout=1800, env=env)
        estimate_output = ((getattr(estimate_result, "stdout", "") or "") + "\n"
                           + (getattr(estimate_result, "stderr", "") or ""))
        if (not isinstance(estimate_output, str) or len(estimate_output) > 16 * 1024 * 1024
                or getattr(estimate_result, "returncode", 1) not in {0, 1}):
            raise DesktopSetupError("guest APT size estimate failed")
        estimate_summary = re.search(r"^(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded\.", estimate_output, re.MULTILINE)
        if estimate_summary is None or tuple(map(int, estimate_summary.groups())) != (upgraded, new_count, removed, not_upgraded):
            raise DesktopSetupError("APT size estimate differs from the exact simulated package transaction")
    if apply and getattr(result, "returncode", 1) != 0:
        raise DesktopSetupError("guest desktop package transaction failed: " + output[-1200:].strip())
    if apply:
        installs = []
    else:
        installs = []
        for line in output.splitlines():
            match = re.match(r"^Inst (\S+) \((\S+)", line)
            if match:
                installs.append([match.group(1), match.group(2)])
        if len(installs) != new_count or new_count <= 0:
            raise DesktopSetupError("APT simulation package list does not match its transaction summary")
    download = re.search(r"Need to get ([0-9]+(?:\.[0-9]+)?) (kB|MB|GB)(?:/[0-9]+(?:\.[0-9]+)? (?:kB|MB|GB))? of archives\.", estimate_output)
    disk = re.search(r"After this operation, ([0-9]+(?:\.[0-9]+)?) (kB|MB|GB) of additional disk space will be used\.", estimate_output)
    return {"returncode": int(getattr(result, "returncode", 0)), "output": output,
            "new_packages": installs, "new_package_count": new_count,
            "upgraded": upgraded, "removed": removed, "not_upgraded": not_upgraded,
            "download": None if download is None else {"value": float(download.group(1)), "unit": download.group(2)},
            "disk": None if disk is None else {"value": float(disk.group(1)), "unit": disk.group(2)}}


def _plan(root: Path, identity: dict[str, int], *, selected: list[str],
          prefix: str, runner=subprocess.run) -> dict[str, object]:
    try:
        desktops = proot_desktops.validate_selection("debian-trixie", selected)
        installed = set(proot_desktops.installed_desktops(root))
    except proot_desktops.DesktopError as exc:
        raise DesktopSetupError(str(exc)) from exc
    already = sorted(set(desktops) & installed)
    if already:
        raise DesktopSetupError("requested Debian desktop is already installed: " + ", ".join(already))
    packages = proot_desktops.packages_for("debian-trixie", desktops)
    before = _package_inventory(root)
    status_path = root / "var/lib/dpkg/status"
    status_hash = _private_digest(status_path)
    source_hash = _source_digest(root)
    transaction = _run_guest(prefix, packages, apply=False, runner=runner)
    after_hash = _private_digest(status_path)
    if status_hash != after_hash:
        raise DesktopSetupError("guest dpkg status changed during the read-only preview")
    transaction_packages = transaction["new_packages"]
    transaction_versions = {name: version for name, version in transaction_packages}
    versions = {package: transaction_versions.get(package, before.get(package))
                for package in packages}
    missing = sorted(package for package, version in versions.items() if version is None)
    if missing:
        raise DesktopSetupError("APT did not include selected desktop packages: " + ", ".join(missing))
    body: dict[str, object] = {
        "schema_version": 1, "operation": "debian-desktop-install",
        "alias": "debian", "rootfs_identity": identity,
        "desktop_environments": list(desktops), "requested_packages": packages,
        "requested_versions": [[package, versions[package]] for package in packages],
        "transaction_packages": transaction_packages,
        "transaction_summary": {key: transaction[key] for key in
                                 ("new_package_count", "upgraded", "removed", "not_upgraded", "download", "disk")},
        "dpkg_status_sha256": status_hash, "apt_sources_sha256": source_hash,
        "installed_package_count": len(before), "guest_packages_changed": False,
    }
    plan_id = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**body, "plan_id": plan_id}


def _dpkg_records(root: Path) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    def ingest(raw: str) -> None:
        for paragraph in raw.split("\n\n"):
            fields = {}
            for line in paragraph.splitlines():
                if line and not line[0].isspace() and ":" in line:
                    key, value = line.split(":", 1)
                    fields[key] = value.strip()
            package = fields.get("Package")
            if package:
                records[package] = fields
    ingest((root / "var/lib/dpkg/status").read_text(encoding="utf-8"))
    updates = root / "var/lib/dpkg/updates"
    if updates.exists():
        for path in sorted(updates.iterdir()):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                raise DesktopSetupError("interrupted dpkg update record is unsafe")
            ingest(path.read_text(encoding="utf-8"))
    return records


def _resume_plan(root: Path, identity: dict[str, int], state: Path, failed_plan_id: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{64}", failed_plan_id):
        raise DesktopSetupError("failed desktop plan ID is invalid")
    saved = proot_fresh_setup._read_private(state / "previews" / f"desktop-{failed_plan_id}.json")
    if saved.get("plan_id") != failed_plan_id or saved.get("rootfs_identity") != identity:
        raise DesktopSetupError("failed desktop preview does not match this managed Debian rootfs")
    journal = proot_fresh_setup._read_private(state / f"desktop-{failed_plan_id}.journal.json")
    if journal.get("plan_id") != failed_plan_id or journal.get("state") != "failed":
        raise DesktopSetupError("desktop resume requires a failed prior installation journal")
    if _source_digest(root) != saved.get("apt_sources_sha256"):
        raise DesktopSetupError("Debian APT sources changed since the failed desktop transaction")
    expected = {name.split(":", 1)[0]: version for name, version in saved.get("transaction_packages", [])}
    records = _dpkg_records(root)
    pending = []
    repair_archives = []
    for package, record in records.items():
        status = record.get("Status", "")
        if status == "install ok installed":
            continue
        if not status.startswith("install "):
            continue
        planned = package in expected and record.get("Version") == expected.get(package)
        trigger_only = status == "install ok triggers-pending"
        if not planned and not trigger_only:
            raise DesktopSetupError(f"interrupted dpkg state includes an unexpected package: {package}")
        pending.append([package, record.get("Version", ""), status])
        if "reinstreq" in status or "half-installed" in status:
            architecture = record.get("Architecture", "")
            cache = root / "var/cache/apt/archives"
            candidates = list(cache.glob(f"{package}_{record.get('Version','')}_{architecture}.deb"))
            if len(candidates) != 1:
                raise DesktopSetupError(f"verified cached archive is unavailable for interrupted package: {package}")
            archive = candidates[0]
            if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 512 * 1024 * 1024:
                raise DesktopSetupError(f"cached archive is unsafe for interrupted package: {package}")
            repair_archives.append([package, str(archive.relative_to(root)),
                                    hashlib.sha256(archive.read_bytes()).hexdigest()])
    updates = root / "var/lib/dpkg/updates"
    update_names = [list(item) for item in sorted((path.name, hashlib.sha256(path.read_bytes()).hexdigest())
                                                  for path in updates.iterdir())] if updates.exists() else []
    status_hash = _private_digest(root / "var/lib/dpkg/status")
    body = {"schema_version": 1, "operation": "debian-desktop-resume-configure",
            "failed_plan_id": failed_plan_id, "rootfs_identity": identity,
            "dpkg_status_sha256": status_hash, "pending_packages": sorted(pending),
            "repair_archives": sorted(repair_archives), "dpkg_update_files": update_names,
            "desktop_environments": saved["desktop_environments"]}
    plan_id = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**body, "plan_id": plan_id}


def resume_preview(*, prefix: str, home: str, state_dir: str, failed_plan_id: str) -> dict[str, object]:
    root, identity = _rootfs(prefix)
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    proot_guest_retirement._assert_idle(state, root)
    plan = _resume_plan(root, identity, state, failed_plan_id)
    proot_fresh_setup._private_write(state / "previews" / f"desktop-resume-{plan['plan_id']}.json", plan)
    return {"status": "preview", "plan_id": plan["plan_id"], "operation": plan,
            "pending_package_count": len(plan["pending_packages"]),
            "repair_archive_count": len(plan["repair_archives"]),
            "guest_packages_changed": False}


def resume_apply(*, prefix: str, home: str, state_dir: str, plan_id: str,
                 confirmed: bool) -> dict[str, object]:
    if confirmed is not True or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise DesktopSetupError("dpkg recovery requires --yes and the exact recovery preview plan ID")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    fd = _lock(state)
    try:
        saved = proot_fresh_setup._read_private(state / "previews" / f"desktop-resume-{plan_id}.json")
        if saved.get("plan_id") != plan_id:
            raise DesktopSetupError("dpkg recovery preview identity is invalid")
        root, identity = _rootfs(prefix)
        current = _resume_plan(root, identity, state, saved["failed_plan_id"])
        if current != saved:
            raise DesktopSetupError("dpkg recovery state changed; create a fresh preview")
        manager = str(Path(prefix) / "bin/proot-distro")
        env = {key: value for key, value in os.environ.items()
               if key not in {"DBUS_SESSION_BUS_ADDRESS", "DBUS_SESSION_BUS_PID", "DBUS_STARTER_ADDRESS",
                              "DBUS_STARTER_BUS_TYPE", "LD_LIBRARY_PATH", "LD_PRELOAD", "DISPLAY"}
               and not key.startswith("ANDROID_")}
        command = [manager, "run", "debian", "--isolated", "--env", "DEBIAN_FRONTEND=noninteractive", "--"]
        journal = state / f"desktop-{saved['failed_plan_id']}.journal.json"
        proot_fresh_setup._private_write(journal, {"plan_id": saved["failed_plan_id"], "state": "resuming-dpkg",
                                                   "resume_plan_id": plan_id})
        for _package, relative, _digest in saved["repair_archives"]:
            result = subprocess.run([*command, "/usr/bin/dpkg", "--unpack", "/" + relative],
                                    capture_output=True, text=True, check=False, timeout=600, env=env)
            if result.returncode != 0:
                proot_fresh_setup._private_write(journal, {"plan_id": saved["failed_plan_id"], "state": "failed",
                                                           "resume_plan_id": plan_id})
                raise DesktopSetupError("cached package repair failed: " + (result.stderr or result.stdout)[-1000:])
        result = subprocess.run([*command, "/usr/bin/dpkg", "--configure", "-a"],
                                capture_output=True, text=True, check=False, timeout=7200, env=env)
        audit = subprocess.run([*command, "/usr/bin/dpkg", "--audit"],
                               capture_output=True, text=True, check=False, timeout=600, env=env)
        if result.returncode != 0 or audit.returncode != 0 or (audit.stdout or "").strip():
            proot_fresh_setup._private_write(journal, {"plan_id": saved["failed_plan_id"], "state": "failed",
                                                       "resume_plan_id": plan_id})
            raise DesktopSetupError("dpkg recovery remains incomplete; audit output retained: " +
                                    ((audit.stdout or "") + (audit.stderr or ""))[-1000:])
        proot_fresh_setup._private_write(journal, {"plan_id": saved["failed_plan_id"],
                                                   "state": "dpkg-recovered", "resume_plan_id": plan_id})
        return {"status": "dpkg-recovered", "plan_id": plan_id,
                "failed_plan_id": saved["failed_plan_id"],
                "configured_pending_packages": len(saved["pending_packages"]),
                "repaired_packages": len(saved["repair_archives"]), "dpkg_audit": "clean"}
    finally:
        os.close(fd)


def preview(*, prefix: str, home: str, state_dir: str, selected: list[str], runner=subprocess.run) -> dict[str, object]:
    root, identity = _rootfs(prefix)
    state = proot_fresh_setup._state_root(home, state_dir, create=True)
    proot_guest_retirement._assert_idle(state, root)
    plan = _plan(root, identity, selected=selected, prefix=prefix, runner=runner)
    proot_fresh_setup._private_write(state / "previews" / f"desktop-{plan['plan_id']}.json", plan)
    transaction = dict(plan["transaction_summary"])
    return {"status": "preview", "plan_id": plan["plan_id"], "operation": plan,
            "transaction": transaction}


def _lock(state: Path):
    path = state / "desktop-install.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        os.close(fd)
        raise DesktopSetupError("desktop install operation lock is unsafe")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def apply(*, prefix: str, home: str, state_dir: str, plan_id: str,
          confirmed: bool, runner=subprocess.run) -> dict[str, object]:
    if confirmed is not True or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise DesktopSetupError("desktop installation requires --yes and an exact preview plan ID")
    state = proot_fresh_setup._state_root(home, state_dir, create=False)
    fd = _lock(state)
    try:
        saved = proot_fresh_setup._read_private(state / "previews" / f"desktop-{plan_id}.json")
        if saved.get("plan_id") != plan_id:
            raise DesktopSetupError("desktop preview identity is invalid")
        body = {key: value for key, value in saved.items() if key != "plan_id"}
        if hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != plan_id:
            raise DesktopSetupError("desktop preview plan was changed")
        root, identity = _rootfs(prefix)
        if identity != saved.get("rootfs_identity"):
            raise DesktopSetupError("managed Debian rootfs identity changed after preview")
        proot_guest_retirement._assert_idle(state, root)
        current = _plan(root, identity, selected=saved["desktop_environments"], prefix=prefix, runner=runner)
        if current != saved:
            raise DesktopSetupError("Debian packages or APT transaction changed after preview; review a fresh plan")
        journal = state / f"desktop-{plan_id}.journal.json"
        proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "applying",
                                                   "desktop_environments": saved["desktop_environments"]})
        before = _package_inventory(root)
        exact_requests = [f"{package}={version}" for package, version in saved["requested_versions"]]
        try:
            result = _run_guest(prefix, exact_requests, apply=True, runner=runner)
        except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "failed",
                                                       "failure_type": type(exc).__name__})
            raise
        after = _package_inventory(root)
        expected_new = {name.split(":", 1)[0] for name, _version in saved["transaction_packages"]}
        actual_new = set(after) - set(before)
        changed_existing = {name for name in set(before) & set(after) if before[name] != after[name]}
        removed_existing = set(before) - set(after)
        if result["returncode"] != 0:
            proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "failed"})
            raise DesktopSetupError("guest desktop package transaction failed")
        if actual_new != expected_new or changed_existing or removed_existing:
            proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "failed",
                                                       "unexpected_new": sorted(actual_new - expected_new),
                                                       "changed_existing": sorted(changed_existing),
                                                       "removed_existing": sorted(removed_existing)})
            raise DesktopSetupError("guest package changes differ from the exact preview; inspect the retained journal")
        if not set(saved["desktop_environments"]).issubset(proot_desktops.installed_desktops(root)):
            proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "failed"})
            raise DesktopSetupError("APT completed but requested desktops are not fully installed")
        receipt = {"schema_version": 1, "plan_id": plan_id, "alias": "debian",
                   "rootfs_identity": identity, "desktop_environments": saved["desktop_environments"],
                   "requested_packages": saved["requested_packages"],
                   "transaction_packages": saved["transaction_packages"],
                   "installed_package_count": len(after), "status": "complete",
                   "created_at_unix": int(time.time())}
        proot_fresh_setup._private_write(state / f"desktop-{plan_id}.receipt.json", receipt)
        proot_fresh_setup._private_write(journal, {"plan_id": plan_id, "state": "complete"})
        return {"status": "complete", "plan_id": plan_id,
                "desktop_environments": saved["desktop_environments"],
                "installed_package_count": len(after),
                "transaction_package_count": len(saved["transaction_packages"])}
    finally:
        os.close(fd)
