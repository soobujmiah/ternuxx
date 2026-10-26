"""Live APT events on stderr; machine-readable results remain on stdout."""
from __future__ import annotations
import os
import re
import selectors
import signal
import subprocess
import sys
import time


def event(line):
    line = re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|.)', '', line)
    line = ''.join(c for c in line if ord(c) >= 32 or c == '\t')
    if not line: return
    category = ('ERROR' if line.startswith(('E:', 'Err:', 'dpkg: error')) else
                'WARNING' if line.startswith(('W:', 'WARNING:', 'Warning:')) else
                'DOWNLOAD' if line.startswith(('Get:', 'Fetched ', 'Need to get ', 'Ign:')) else
                'UNPACK' if line.startswith(('Unpacking ', 'Preparing to unpack', 'Selecting previously')) else
                'CONFIGURE' if line.startswith(('Setting up ', 'Processing triggers')) else 'INFO')
    print(f'[{category}] {line}', file=sys.stderr, flush=True)


def run(argv, *, timeout, env):
    started = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, start_new_session=True)
    captured = bytearray(); pending = bytearray()
    selector = selectors.DefaultSelector(); selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout:
                raise subprocess.TimeoutExpired(argv, timeout)
            for key, _ in selector.select(.25):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj); continue
                captured.extend(block)
                if len(captured) > 16 * 1024 * 1024:
                    raise ValueError('APT output exceeded the bounded capture limit')
                pending.extend(block)
                while b'\n' in pending or b'\r' in pending:
                    positions = [v for v in (pending.find(b'\n'), pending.find(b'\r')) if v >= 0]
                    end = min(positions); event(pending[:end].decode(errors='replace')); del pending[:end + 1]
                if len(pending) > 8192:
                    event(pending.decode(errors='replace')); pending.clear()
        if pending: event(pending.decode(errors='replace'))
        return subprocess.CompletedProcess(argv, proc.wait(timeout=max(.01, timeout-(time.monotonic()-started))), captured.decode(errors='replace'), '')
    finally:
        selector.close(); proc.stdout.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait()
