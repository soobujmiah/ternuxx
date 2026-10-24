#!/usr/bin/env python3
"""Prepare a truthful PRoot /proc/cpuinfo view with model names from lscpu."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


def render(cpuinfo: str, lscpu_csv: str) -> str:
    models: dict[int, str] = {}
    for row in csv.reader(line for line in lscpu_csv.splitlines() if line and not line.startswith("#")):
        if len(row) < 2 or not row[0].strip().isdigit():
            continue
        model = row[1].strip()
        if model and not re.search(r"[\x00-\x1f\x7f]", model):
            models[int(row[0])] = model
    if not models:
        raise ValueError("lscpu did not report CPU model names")

    rendered: list[str] = []
    blocks = re.split(r"(\n\s*\n)", cpuinfo)
    for block in blocks:
        if not block or block.isspace():
            rendered.append(block)
            continue
        processor = re.search(r"(?m)^processor\s*:\s*(\d+)\s*$", block)
        if processor and not re.search(r"(?m)^(?:model name|cpu|Processor)\s*:", block):
            cpu_id = int(processor.group(1))
            model = models.get(cpu_id)
            if model:
                end = processor.end()
                block = block[:end] + f"\nmodel name\t: {model}" + block[end:]
        rendered.append(block)
    result = "".join(rendered)
    found = {int(x) for x in re.findall(r"(?m)^processor\s*:\s*(\d+)\s*$", result)}
    if not found.intersection(models):
        raise ValueError("CPU model names could not be matched to /proc/cpuinfo processors")
    return result


def prepare(destination: Path) -> None:
    parent = destination.parent
    metadata = parent.lstat()
    if (not parent.is_dir() or parent.is_symlink() or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700):
        raise ValueError("CPU info state directory must be a private, owned directory")
    if destination.is_symlink():
        raise ValueError("CPU info output must not be a symlink")
    cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
    result = subprocess.run(["lscpu", "-p=CPU,MODELNAME"], check=True,
                            capture_output=True, text=True, timeout=10)
    content = render(cpuinfo, result.stdout)
    fd, temporary = tempfile.mkstemp(prefix=".cpuinfo.", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: proot_cpuinfo.py OUTPUT_PATH")
    try:
        prepare(Path(sys.argv[1]))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"proot_cpuinfo: {exc}", file=sys.stderr)
        raise SystemExit(1)
