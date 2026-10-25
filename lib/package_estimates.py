#!/usr/bin/env python3
"""Best-effort resource estimates for an exact APT transaction closure."""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

PACKAGE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
VERSION = re.compile(r"^[A-Za-z0-9.+:~_-]+$")


def _records(payload: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for paragraph in re.split(r"\n\s*\n", payload.strip()):
        fields: dict[str, str] = {}
        for line in paragraph.splitlines():
            if line[:1].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields:
            result.append(fields)
    return result


def _metadata(package: str, version: str, architecture: str) -> dict[str, Any]:
    if not PACKAGE.fullmatch(package) or not VERSION.fullmatch(version):
        return {"package": package, "version": version, "download_bytes": None,
                "installed_kib": None, "status": "invalid-apt-record"}
    try:
        result = subprocess.run(
            ["apt-cache", "show", f"{package}={version}"],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    matches = []
    if result is not None and result.returncode == 0:
        for record in _records(result.stdout):
            if (record.get("Package") != package or record.get("Version") != version
                    or record.get("Architecture") not in {architecture, "all"}):
                continue
            size = record.get("Size", "")
            installed = record.get("Installed-Size", "")
            if size.isdecimal() and installed.isdecimal():
                matches.append((int(size), int(installed)))
    # Conflicting or incomplete metadata must not become a confident aggregate.
    if not matches or len(set(matches)) != 1:
        return {"package": package, "version": version, "download_bytes": None,
                "installed_kib": None, "status": "metadata-unavailable"}
    size, installed = matches[0]
    return {"package": package, "version": version, "download_bytes": size,
            "installed_kib": installed, "status": "estimated"}


def _memory() -> dict[str, int | None]:
    values: dict[str, int | None] = {"total_bytes": None, "available_bytes": None}
    try:
        for line in pathlib.Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, _, raw = line.partition(":")
            if key not in {"MemTotal", "MemAvailable"}:
                continue
            match = re.fullmatch(r"\s*(\d+)\s+kB\s*", raw)
            if match:
                target = "total_bytes" if key == "MemTotal" else "available_bytes"
                values[target] = int(match.group(1)) * 1024
    except OSError:
        pass
    return values


def estimate(prefix: str, transactions: list[str]) -> dict[str, Any]:
    try:
        architecture = subprocess.run(
            ["dpkg", "--print-architecture"], check=True, capture_output=True,
            text=True, timeout=10,
        ).stdout.strip()
        if not architecture:
            raise ValueError("empty architecture")
    except (OSError, subprocess.SubprocessError, ValueError):
        architecture = "unknown"

    packages = []
    for entry in transactions:
        package, separator, version = entry.partition("=")
        if not separator:
            packages.append({"package": entry, "version": None, "download_bytes": None,
                             "installed_kib": None, "status": "invalid-apt-record"})
        else:
            packages.append(_metadata(package, version, architecture))

    complete = bool(packages) and all(item["status"] == "estimated" for item in packages)
    download = sum(item["download_bytes"] or 0 for item in packages) if complete else None
    installed = sum(item["installed_kib"] or 0 for item in packages) if complete else None
    try:
        filesystem_free = shutil.disk_usage(prefix).free
    except OSError:
        filesystem_free = None
    return {
        "schema_version": 1,
        "source": "apt-cache exact package/version metadata",
        "architecture": architecture,
        "complete": complete,
        "download_bytes": download,
        "installed_kib": installed,
        "filesystem_free_bytes": filesystem_free,
        "memory": _memory(),
        "packages": packages,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "--":
        print("usage: package_estimates.py -- package=version ...", file=sys.stderr)
        return 2
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    print(json.dumps(estimate(prefix, argv[1:]), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
