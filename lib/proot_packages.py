"""Package database readers shared by managed PRoot profile adapters."""
from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
from pathlib import Path


class PackageInventoryError(ValueError):
    pass


# Paths are allowlisted so a profile cannot redirect inventory reads outside
# the guest rootfs. RPM databases need a runtime query adapter and are not yet
# declared here.
DATABASE_PATHS = {
    "dpkg-status": Path("var/lib/dpkg/status"),
    "apk-installed": Path("lib/apk/db/installed"),
}


def _read_database(rootfs: str | Path, database: str) -> bytes:
    relative = DATABASE_PATHS.get(database)
    if relative is None:
        raise PackageInventoryError("guest package database adapter is unsupported")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise PackageInventoryError("safe guest package database reads are unavailable")
    try:
        root = Path(rootfs).resolve(strict=True)
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise PackageInventoryError("guest package root is unavailable or unsafe") from exc
    fd = -1
    try:
        for component in relative.parts[:-1]:
            component_stat = os.stat(component, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(component_stat.st_mode):
                label = "dpkg status database" if database == "dpkg-status" else "guest package database"
                raise PackageInventoryError(label + " is unsafe: symbolic link in database path")
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                              dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(relative.parts[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                     dir_fd=directory_fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 64 * 1024 * 1024:
            raise PackageInventoryError("guest package database is not a bounded regular file")
        chunks = []
        remaining = 64 * 1024 * 1024 + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        raw = b"".join(chunks)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity_before != identity_after or len(raw) > 64 * 1024 * 1024:
            raise PackageInventoryError("guest package database changed while being read")
        try:
            raw.decode("utf-8", "strict")
        except UnicodeError as exc:
            raise PackageInventoryError("guest package database is not UTF-8") from exc
        return raw
    except PackageInventoryError:
        raise
    except OSError as exc:
        label = "dpkg status database" if database == "dpkg-status" else "guest package database"
        if exc.errno == errno.ELOOP:
            raise PackageInventoryError(label + " is unsafe: symbolic link in database path") from exc
        raise PackageInventoryError(label + " is unavailable or unsafe") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(directory_fd)


def parse_dpkg_status(raw: bytes) -> dict[str, list[dict[str, str]]]:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise PackageInventoryError("dpkg status database is not UTF-8") from exc
    installed: dict[str, list[dict[str, str]]] = {}
    for paragraph in text.split("\n\n"):
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        state = fields.get("Status", "").split()
        package = fields.get("Package", "")
        architecture = fields.get("Architecture", "")
        name = package.split(":", 1)[0]
        if (len(state) != 3 or state[1:] != ["ok", "installed"]
                or state[0] not in {"install", "hold"}
                or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]{0,127}", name)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", architecture)):
            continue
        installed.setdefault(name, []).append({
            "architecture": architecture,
            "version": fields.get("Version", "unknown"),
            "held": "true" if state[0] == "hold" else "false",
        })
    return installed


def parse_apk_installed(raw: bytes) -> dict[str, list[dict[str, str]]]:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise PackageInventoryError("APK installed database is not UTF-8") from exc
    installed: dict[str, list[dict[str, str]]] = {}
    for paragraph in text.split("\n\n"):
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if len(line) > 2 and line[1] == ":":
                fields[line[0]] = line[2:]
        name, version, architecture = fields.get("P", ""), fields.get("V", ""), fields.get("A", "")
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}", name)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:~-]{0,127}", version)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", architecture)):
            continue
        installed.setdefault(name, []).append({
            "architecture": architecture, "version": version, "held": "false",
        })
    return installed


def installed_packages(rootfs: str | Path, database: str = "dpkg-status") -> tuple[dict[str, list[dict[str, str]]], str]:
    raw = _read_database(rootfs, database)
    parser = {"dpkg-status": parse_dpkg_status, "apk-installed": parse_apk_installed}.get(database)
    if parser is None:
        raise PackageInventoryError("guest package database adapter is unsupported")
    return parser(raw), hashlib.sha256(raw).hexdigest()


def grouped_inventory(rootfs: str | Path, manifest: dict[str, object]) -> dict[str, object]:
    database = manifest.get("package_database", "dpkg-status")
    installed, digest = installed_packages(rootfs, str(database))
    architecture = manifest.get("architecture")
    if database == "dpkg-status":
        expected_arch = {"aarch64": "arm64", "x86_64": "amd64"}.get(architecture, architecture)
    else:
        expected_arch = {"arm64": "aarch64", "amd64": "x86_64"}.get(architecture, architecture)
    groups = manifest.get("packages")
    if not isinstance(groups, dict) or not isinstance(expected_arch, str):
        raise PackageInventoryError("guest package profile is invalid")
    inventory: dict[str, object] = {}
    for group, requested in groups.items():
        if (not isinstance(group, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", group)
                or not isinstance(requested, list) or len(requested) > 512):
            raise PackageInventoryError("guest package groups are malformed")
        present: dict[str, dict[str, str]] = {}
        missing: list[str] = []
        held: list[str] = []
        for package in requested:
            if not isinstance(package, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}", package):
                raise PackageInventoryError("guest package name is invalid")
            candidates = [item for item in installed.get(package, [])
                          if item["architecture"] in {expected_arch, "all", "noarch"}]
            if not candidates:
                missing.append(package)
                continue
            selected = next((item for item in candidates if item["architecture"] == expected_arch), candidates[0])
            present[package] = {"version": selected["version"], "architecture": selected["architecture"]}
            if selected["held"] == "true":
                held.append(package)
        inventory[group] = {"requested": len(requested), "installed": len(present),
                            "missing": missing, "held": held, "versions": present}
    return {"groups": inventory, "package_database": str(database),
            "package_database_sha256": digest,
            **({"dpkg_status_sha256": digest} if database == "dpkg-status" else {})}


def installed_names(rootfs: str | Path, database: str = "dpkg-status") -> set[str]:
    installed, _ = installed_packages(rootfs, database)
    return set(installed)
