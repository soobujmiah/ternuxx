"""Reviewed package-manager rules for the pinned PRoot distribution profiles."""
from __future__ import annotations

import re


# Noble's Firefox transition package invokes Snap, which is not a supported
# workload inside PRoot. The software catalog uses Epiphany and the guest keeps
# snapd on hold so later package transactions cannot install it as a dependency.
PROFILE_POLICIES: dict[str, dict[str, tuple[str, ...]]] = {
    "debian-trixie": {"always_hold": (), "forbidden_packages": ()},
    "ubuntu-noble": {"always_hold": ("snapd",), "forbidden_packages": ("snapd",)},
}
PROFILE_ID_ALIASES = {
    "ternuxx-debian-trixie-workstation": "debian-trixie",
    "ternuxx-ubuntu-noble-workstation": "ubuntu-noble",
}


def policy_for(profile_id: str) -> dict[str, list[str]]:
    profile_id = PROFILE_ID_ALIASES.get(profile_id, profile_id)
    try:
        policy = PROFILE_POLICIES[profile_id]
    except KeyError as exc:
        raise ValueError("no reviewed package-manager policy exists for this PRoot profile") from exc
    return {key: list(values) for key, values in policy.items()}


def hold_command(packages: list[str] | tuple[str, ...]) -> str | None:
    if (not isinstance(packages, (list, tuple))
            or any(not isinstance(item, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", item)
                   for item in packages)):
        raise ValueError("package hold policy is invalid")
    unique = list(dict.fromkeys(packages))
    if not unique:
        return None
    command = "apt-mark hold " + " ".join(unique)
    for package in unique:
        command += " && apt-mark showhold | grep -Fqx -- " + package
    return command


def reject_forbidden(packages: list[tuple[str, str]] | tuple[tuple[str, str], ...],
                     policy: dict[str, list[str]]) -> None:
    forbidden = set(policy.get("forbidden_packages", []))
    found = sorted({name.split(":", 1)[0] for name, _version in packages} & forbidden)
    if found:
        raise ValueError("PRoot transaction includes unsupported distro packages: " + ", ".join(found))
