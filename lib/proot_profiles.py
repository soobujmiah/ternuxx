"""Pinned Ternuxx PRoot distro profiles and safe manifest loading."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROFILE_FILES = {
    "debian-trixie": "debian-trixie.json",
    "ubuntu-noble": "ubuntu-noble.json",
}
PROFILE_IDS = {
    "debian-trixie": "ternuxx-debian-trixie-workstation",
    "ubuntu-noble": "ternuxx-ubuntu-noble-workstation",
}
PROFILE_ALIASES = {"debian": "debian-trixie", "ubuntu": "ubuntu-noble"}


class ProfileError(ValueError):
    pass


def profile_for_alias(alias: str) -> str:
    if alias in PROFILE_ALIASES:
        return PROFILE_ALIASES[alias]
    if alias.startswith("ternuxx-replay-ubuntu-noble-"):
        return "ubuntu-noble"
    if alias.startswith("ternuxx-replay-debian-trixie-"):
        return "debian-trixie"
    if alias.startswith("ternuxx-replay-"):
        return "debian-trixie"
    raise ProfileError("no Ternuxx profile is defined for this guest alias")


def load(repo_root: str | Path, profile_id: str) -> tuple[dict, str, str]:
    filename = PROFILE_FILES.get(profile_id)
    if filename is None:
        raise ProfileError("Ternuxx PRoot profile is unsupported")
    path = Path(repo_root) / "config/proot" / filename
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError("Ternuxx PRoot profile is unavailable or invalid") from exc
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("profile_id") != PROFILE_IDS.get(profile_id)):
        raise ProfileError("Ternuxx PRoot profile schema is unsupported")
    return manifest, hashlib.sha256(raw).hexdigest(), raw
