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


def install_catalog(repo_root: str | Path) -> dict[str, object]:
    """Return the distro and desktop choices backed by complete Ternuxx profiles."""
    import proot_desktops

    profiles = []
    for alias, profile_id in PROFILE_ALIASES.items():
        manifest, digest, _raw = load(repo_root, profile_id)
        desktop_ids = proot_desktops.catalog(profile_id)
        desktops = [{
            "id": desktop_id,
            "name": proot_desktops.PROVIDERS[profile_id][desktop_id]["name"],
            "routes": sorted(proot_desktops.DESKTOP_ROUTES.get(
                desktop_id, frozenset({"standalone", "nested"}))),
        } for desktop_id in desktop_ids]
        database = manifest.get("package_database", proot_desktops.PACKAGE_DATABASES.get(profile_id))
        package_manager = manifest.get("package_manager") or {"dpkg-status": "apt"}.get(database, "unsupported")
        if package_manager != "apt" or not isinstance(manifest.get("fresh_install"), dict):
            continue
        profiles.append({
            "distro": alias,
            "profile_id": profile_id,
            "label": manifest.get("release_name") or f"{manifest['distro']} {manifest['release']}",
            "release": manifest["release"],
            "manifest_sha256": digest,
            "package_manager": package_manager,
            "package_database": database,
            "default_desktops": list(proot_desktops.DEFAULT_DESKTOPS),
            "desktops": desktops,
        })
    return {"profiles": profiles}


def installable_aliases(repo_root: str | Path) -> tuple[str, ...]:
    return tuple(item["distro"] for item in install_catalog(repo_root)["profiles"])


def install_profile(repo_root: str | Path, alias: str) -> dict[str, object]:
    for profile in install_catalog(repo_root)["profiles"]:
        if profile["distro"] == alias:
            return profile
    raise ProfileError("no complete managed install profile is available for this distro")


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
