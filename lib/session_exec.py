#!/usr/bin/env python3
"""Exec one command inside a fresh session/process group."""
from __future__ import annotations
import os
import sys

if len(sys.argv) < 2:
    raise SystemExit("usage: session_exec.py COMMAND [ARG ...]")
os.setsid()
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
