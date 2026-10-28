#!/usr/bin/env python3
"""Call the local Native Blender MCP adapter over newline-delimited JSON-RPC."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
ADAPTER = HOME / "skb/integrations/codex/restore/native_blender_gpu_mcp.py"


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: mcp_call.py TOOL_NAME ARGUMENTS_JSON_OR_SCRIPT_PATH")
    tool = sys.argv[1]
    if tool == "gui_submit_script":
        arguments = {"source": Path(sys.argv[2]).read_text(encoding="utf-8")}
    else:
        arguments = json.loads(sys.argv[2])
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)
    proc = subprocess.Popen(
        [sys.executable, str(ADAPTER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ternuxx-benchmark-runner", "version": "1"},
        },
    }) + "\n")
    proc.stdin.flush()
    init = proc.stdout.readline()
    if not init:
        raise RuntimeError("MCP adapter closed before initialize response")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }) + "\n")
    proc.stdin.flush()
    response = proc.stdout.readline()
    proc.stdin.close()
    exit_code = proc.wait(timeout=1900)
    stderr = proc.stderr.read() if proc.stderr else ""
    result = {
        "initialize": json.loads(init),
        "call": json.loads(response) if response else None,
        "adapter_exit_code": exit_code,
        "adapter_stderr": stderr,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if exit_code == 0 and result["call"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
