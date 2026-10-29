"""Deterministic Native inference backend priority selection."""
from __future__ import annotations

from typing import Any


def select_backend(npu_status: dict[str, Any], gpu_status: dict[str, Any]) -> dict[str, Any]:
    """Choose the highest-priority backend with a usable hardware probe.

    Selection happens once before inference. A failed inference is never silently
    retried on another backend, preventing duplicate work and hidden offload loss.
    """
    if npu_status.get("available") is True and npu_status.get("device") == "HTP0":
        return {"backend": "npu", "device_id": "HTP0",
                "reason": "HTP0 runtime and device probe passed"}
    devices = gpu_status.get("devices")
    if gpu_status.get("available") is True and isinstance(devices, list):
        for device in devices:
            if (isinstance(device, dict) and isinstance(device.get("id"), str)
                    and device["id"] and isinstance(device.get("name"), str)):
                return {"backend": "vulkan", "device_id": device["id"],
                        "reason": "no usable HTP0; Vulkan inference device probe passed"}
    return {"backend": "cpu", "device_id": None,
            "reason": "no usable HTP0 or Vulkan inference device; select CPU fallback"}
