"""Fresh, isolated Debian Trixie provisioning for Ternuxx."""
from __future__ import annotations

import hashlib
import fcntl
import json
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import tarfile
import urllib.request


ALIAS = "debian"


class FreshSetupError(ValueError):
    pass



def _alias(value: str) -> str:
    if value != ALIAS and not re.fullmatch(r"ternuxx-replay-[a-z0-9][a-z0-9-]{0,31}", value):
        raise FreshSetupError("fresh alias must be debian or an explicit ternuxx-replay-NAME")
    return value


def _directory(path: Path, *, private: bool = False) -> os.stat_result:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & (0o077 if private else 0o022)):
        raise FreshSetupError("fresh setup directory identity is unsafe")
    return info


def _target_paths(prefix: str, alias: str) -> tuple[Path, Path]:
    """Return the manager-owned destination while tolerating an uninitialized store.

    A freshly installed proot-distro package creates its runtime data tree on the
    first guest install, not when the package is unpacked. Preview must therefore
    handle absent parents without creating host state, while rejecting symlinks
    or unsafe ownership anywhere in an existing path prefix.
    """
    prefix_path = Path(prefix).absolute()
    try:
        _directory(prefix_path)
    except OSError as exc:
        raise FreshSetupError("Native Termux prefix is unavailable") from exc
    runtime = prefix_path / "var/lib/proot-distro"
    containers = runtime / "containers"
    for directory in (prefix_path / "var", prefix_path / "var/lib", runtime, containers):
        try:
            directory.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise FreshSetupError("PRoot storage path cannot be inspected") from exc
        try:
            _directory(directory)
        except (OSError, FreshSetupError) as exc:
            raise FreshSetupError("PRoot storage path is not a safe owned directory") from exc
        if directory.resolve() != directory.absolute():
            raise FreshSetupError("PRoot storage path contains a symbolic link")
    container = containers / _alias(alias)
    if container.is_symlink():
        raise FreshSetupError("fresh container destination is a symbolic link")
    if container.exists():
        _directory(container)
    rootfs = container / "rootfs"
    if rootfs.is_symlink():
        raise FreshSetupError("fresh rootfs destination is a symbolic link")
    return container, rootfs


def _storage_anchor(prefix: str, container: Path) -> Path:
    """Find the nearest existing verified ancestor for a read-only disk check."""
    current = container
    prefix_path = Path(prefix).absolute()
    while True:
        try:
            _directory(current)
            return current
        except FileNotFoundError:
            if current == prefix_path:
                raise FreshSetupError("Native Termux prefix is unavailable")
            current = current.parent
        except OSError as exc:
            raise FreshSetupError("PRoot storage path cannot be inspected") from exc


def _state_root(home: str, state_dir: str, *, create: bool) -> Path:
    base = Path(os.path.abspath(state_dir))
    owner_home = Path(home).resolve()
    try:
        relative = base.relative_to(owner_home)
    except ValueError as exc:
        raise FreshSetupError("fresh setup state must be inside HOME") from exc
    if not relative.parts:
        raise FreshSetupError("fresh setup state cannot be HOME")
    cursor = owner_home
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise FreshSetupError("fresh setup state path contains a symbolic link")
        if cursor.exists():
            _directory(cursor)
    if create:
        base.mkdir(parents=True, mode=0o700, exist_ok=True)
    _directory(base, private=True)
    state = base / "proot-setup"
    for directory in (state, state / "previews"):
        if create:
            directory.mkdir(mode=0o700, exist_ok=True)
        _directory(directory, private=True)
    return state


def _read_private(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 1024*1024):
            raise FreshSetupError("fresh setup record identity is unsafe")
        data = json.load(stream)
    if not isinstance(data, dict):
        raise FreshSetupError("fresh setup record is invalid")
    return data


def _native_ca_bundle(prefix: str) -> tuple[Path, str]:
    path = Path(prefix) / "etc/tls/cert.pem"
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or path.resolve(strict=True) != path.absolute()
                or info.st_uid != os.getuid() or info.st_size < 1024 or info.st_size > 16 * 1024 * 1024):
            raise FreshSetupError("Native Termux CA bundle identity is unsafe")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise FreshSetupError("Native Termux CA bundle is unavailable for verified HTTPS bootstrap") from exc
    return path, digest


def _root_identity(container: Path, rootfs: Path) -> dict:
    parent = _directory(container)
    child = _directory(rootfs)
    return {"container_device": parent.st_dev, "container_inode": parent.st_ino,
            "rootfs_device": child.st_dev, "rootfs_inode": child.st_ino}


def _verify_owned_target(prefix: str, alias: str, identity: dict | None) -> Path:
    container, rootfs = _target_paths(prefix, alias)
    if identity is None or _root_identity(container, rootfs) != identity:
        raise FreshSetupError("fresh destination identity differs from the verified owned install")
    return rootfs


def _version_inventory(output: str, packages: list[str]) -> None:
    installed = set()
    for line in output.splitlines():
        status, tab, entry = line.partition("\t")
        if not tab or len(status) != 3:
            raise FreshSetupError("installed package-version inventory lacks dpkg status")
        if status[1:] != "i ":
            continue
        name, separator, version = entry.partition("=")
        if (not separator or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?", name)
                or not re.fullmatch(r"[0-9][0-9A-Za-z.+:~_-]*", version)):
            raise FreshSetupError("installed package-version inventory is malformed")
        installed.add(name.split(":", 1)[0])
    missing = sorted(set(packages) - installed)
    if missing:
        raise FreshSetupError("requested packages missing from installed inventory: " + ", ".join(missing))


def _private_write(path: Path, data: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fresh-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


_PACKAGE_GROUPS = ("base", "desktop-compat", "development", "desktop-apps", "fonts")


def _selected_groups(groups: list[str] | None) -> list[str]:
    if groups is None:
        return ["base"]
    if not isinstance(groups, list) or not groups:
        raise FreshSetupError("select base and only known, non-duplicate Debian package groups")
    if any(not isinstance(group, str) or group not in _PACKAGE_GROUPS for group in groups):
        raise FreshSetupError("select base and only known, non-duplicate Debian package groups")
    if "base" not in groups or len(set(groups)) != len(groups):
        raise FreshSetupError("select base and only known, non-duplicate Debian package groups")
    return [group for group in _PACKAGE_GROUPS if group in groups]


def _packages(manifest: dict, selected: list[str] | None = None) -> list[str]:
    groups = manifest.get("packages")
    if not isinstance(groups, dict):
        raise FreshSetupError("Debian package groups are invalid")
    chosen = _selected_groups(selected)
    result = []
    for group in chosen:
        values = groups.get(group)
        if not isinstance(values, list) or not values:
            raise FreshSetupError(f"Debian package group is missing: {group}")
        for package in values:
            if not isinstance(package, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]{0,100}", package):
                raise FreshSetupError("invalid package name in the Debian manifest")
            result.append(package)
    if len(set(result)) != len(result):
        raise FreshSetupError("duplicate package in Debian package groups")
    return result


def _assert_resume_compatible(previous: dict, current: dict) -> None:
    keys = ("schema_version", "alias", "guest_user", "image", "image_pin",
            "arch_manifest_digest", "config_digest", "layer_digest", "rootfs_target",
            "package_groups", "packages",
            "existing_debian_rootfs_changed")
    if previous.get("schema_version") != 2 or previous.get("operation") not in {
            "fresh-debian-trixie", "resume-fresh-debian-trixie"}:
        raise FreshSetupError("previous setup plan is not a Ternuxx fresh-install plan")
    if any(previous.get(key) != current.get(key) for key in keys):
        raise FreshSetupError("current setup profile changes packages or pinned image; failed install cannot resume")
    old_snapshot, new_snapshot = previous.get("apt_snapshot"), current.get("apt_snapshot")
    snapshot_keys = ("snapshot_id", "suites", "components", "valid_until")
    if (not isinstance(old_snapshot, dict) or not isinstance(new_snapshot, dict)
            or any(old_snapshot.get(key) != new_snapshot.get(key) for key in snapshot_keys)):
        raise FreshSetupError("failed install uses a different Debian snapshot; refusing resume")
    old_graphics, new_graphics = previous.get("graphics"), current.get("graphics")
    graphics_keys = ("kgsl_accessible_at_preview", "turnip_archive_sha256",
                     "turnip_install_planned", "rendering_verified")
    if (not isinstance(old_graphics, dict) or not isinstance(new_graphics, dict)
            or any(old_graphics.get(key) != new_graphics.get(key) for key in graphics_keys)):
        raise FreshSetupError("graphics capability or pinned driver changed; failed install cannot resume")


def _assert_rootfs_idle_for_resume(state: Path, rootfs: Path) -> None:
    try:
        import proot_guest_retirement
        proot_guest_retirement._assert_idle(state, rootfs)
    except (OSError, ValueError) as exc:
        raise FreshSetupError("failed replay guest is active or its process ownership cannot be verified") from exc


def preview(*, repo_root: str, prefix: str, home: str, state_dir: str, user: str,
            alias: str = ALIAS, resume_plan_id: str | None = None,
            groups: list[str] | None = None) -> dict:
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user == "root":
        raise FreshSetupError("provide an ordinary Debian guest username")
    repo = Path(repo_root)
    manifest_path = repo / "config/proot/debian-trixie.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or manifest.get("provider") != "proot-distro":
        raise FreshSetupError("Debian setup profile schema is unsupported")
    alias = _alias(alias)
    container, rootfs = _target_paths(prefix, alias)
    containers = container.parent
    state = _state_root(home, state_dir, create=True)
    previews = state / "previews"
    if groups is None and container.exists() and resume_plan_id is not None:
        inherited = _read_private(previews / f"fresh-{resume_plan_id}.json")
        groups = inherited.get("package_groups")
    chosen_groups = _selected_groups(groups)
    packages = _packages(manifest, chosen_groups)
    ca_path, ca_sha256 = _native_ca_bundle(prefix)
    guest_ca_path = "/tmp/ternuxx-native-ca.pem"
    kgsl = _kgsl_accessible()
    if kgsl:
        for name in manifest.get("graphics", {}).get("hold_packages", []):
            if name not in packages:
                packages.append(name)
    plan = {
        "schema_version": 2, "operation": "fresh-debian-trixie", "alias": alias,
        "image": _pinned_image_reference(manifest["fresh_install"]), "image_pin": manifest["fresh_install"]["image_index_digest"],
        "arch_manifest_digest": manifest["fresh_install"]["arch_manifest_digest"],
        "config_digest": manifest["fresh_install"]["config_digest"],
        "layer_digest": manifest["fresh_install"]["layer_digest"],
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "rootfs_target": str(rootfs), "guest_user": user,
        "package_groups": chosen_groups,
        "packages": packages,
        "apt_snapshot": manifest["fresh_install"]["apt_snapshot"],
        "https_bootstrap": {"source": str(ca_path), "sha256": ca_sha256,
                            "guest_temporary_path": guest_ca_path,
                            "release_signature_required": True},
        "package_versions": "pinned by the dated Debian snapshot archive",
        "existing_debian_rootfs_changed": False,
        "graphics": {
            "kgsl_accessible_at_preview": kgsl,
            "turnip_archive_sha256": manifest["graphics"]["turnip_archive"]["sha256"],
            "turnip_install_planned": kgsl,
            "rendering_verified": False,
        },
        "free_bytes_at_preview": shutil.disk_usage(_storage_anchor(prefix, containers)).free,
    }
    if container.exists():
        if resume_plan_id is None or not re.fullmatch(r"[0-9a-f]{64}", resume_plan_id):
            raise FreshSetupError("Ternuxx fresh container already exists; only an exact failed-plan resume is allowed")
        previous = _read_private(previews / f"fresh-{resume_plan_id}.json")
        journal_record = _read_private(state / f"fresh-{resume_plan_id}.journal.json")
        previous_identity = {key: value for key, value in previous.items() if key != "plan_id"}
        if (previous.get("plan_id") != resume_plan_id
                or hashlib.sha256(json.dumps(previous_identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != resume_plan_id
                or journal_record.get("plan_id") != resume_plan_id or journal_record.get("alias") != alias
                or journal_record.get("state") != "failed" or not isinstance(journal_record.get("rootfs_identity"), dict)):
            raise FreshSetupError("resume requires a matching failed Ternuxx setup journal")
        rootfs_identity = journal_record["rootfs_identity"]
        if _root_identity(container, rootfs) != rootfs_identity:
            raise FreshSetupError("failed replay rootfs identity changed; refusing resume")
        if previous.get("guest_user") != user or previous.get("alias") != alias:
            raise FreshSetupError("resume target or guest account differs from the failed setup")
        _assert_resume_compatible(previous, plan)
        _assert_rootfs_idle_for_resume(state, rootfs)
        plan["operation"] = "resume-fresh-debian-trixie"
        plan["resume_from_plan_id"] = resume_plan_id
        plan["rootfs_identity"] = rootfs_identity
    elif resume_plan_id is not None:
        raise FreshSetupError("failed replay target is missing; refusing resume")
    plan_id = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    plan["plan_id"] = plan_id
    _private_write(previews / f"fresh-{plan_id}.json", plan)
    return {"status": "preview", "plan_id": plan_id, "operation": plan}


def _artifact_bytes(path: Path) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_size > 256*1024*1024):
                raise FreshSetupError("cached graphics artifact identity is unsafe")
            content = stream.read(256*1024*1024 + 1)
            if len(content) > 256*1024*1024:
                raise FreshSetupError("graphics artifact exceeds the size limit")
            return content
    except OSError as exc:
        raise FreshSetupError("cached graphics artifact is unavailable or unsafe") from exc


def _store_artifact(path: Path, content: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if _artifact_bytes(path) != content:
            raise FreshSetupError("existing graphics artifact differs; refusing overwrite")
        return
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            info = path.lstat()
            if (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                path.unlink()
        except OSError:
            pass
        raise


def _stage_turnip(manifest: dict, artifact_dir: Path) -> tuple[Path, Path]:
    spec = manifest["graphics"]["turnip_archive"]
    artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _directory(artifact_dir, private=True)
    lock_fd = os.open(artifact_dir / ".stage.lock",
                     os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise FreshSetupError("graphics artifact lock is unsafe")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FreshSetupError("another graphics artifact staging operation is active") from exc
        archive_path = artifact_dir / (spec["sha256"] + ".tar.gz")
        if archive_path.exists() or archive_path.is_symlink():
            archive_bytes = _artifact_bytes(archive_path)
        else:
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "Ternuxx/1"})
            chunks = []
            total = 0
            with urllib.request.urlopen(request, timeout=90) as response:
                while chunk := response.read(1024*1024):
                    total += len(chunk)
                    if total > 256*1024*1024:
                        raise FreshSetupError("graphics archive exceeds the size limit")
                    chunks.append(chunk)
            archive_bytes = b"".join(chunks)
            if hashlib.sha256(archive_bytes).hexdigest() != spec["sha256"]:
                raise FreshSetupError("Turnip archive hash does not match the profile")
            _store_artifact(archive_path, archive_bytes)
        if hashlib.sha256(archive_bytes).hexdigest() != spec["sha256"]:
            raise FreshSetupError("cached Turnip archive hash does not match the profile")
        outputs = []
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            for name, expected in ((spec["driver_member"], spec["driver_sha256"]),
                                   (spec["icd_member"], spec["icd_sha256"])):
                found = [member for member in archive.getmembers() if member.name.removeprefix("./") == name]
                if len(found) != 1 or not found[0].isreg() or found[0].size > 256*1024*1024:
                    raise FreshSetupError("Turnip archive member is missing or unsafe")
                stream = archive.extractfile(found[0])
                if stream is None:
                    raise FreshSetupError("Turnip archive member could not be read")
                content = stream.read()
                if hashlib.sha256(content).hexdigest() != expected:
                    raise FreshSetupError("Turnip archive member hash does not match the profile")
                output = artifact_dir / (expected + ".member")
                _store_artifact(output, content)
                outputs.append(output)
        return outputs[0], outputs[1]
    finally:
        os.close(lock_fd)


def _managed_turnip_paths(manifest: dict) -> tuple[str, str]:
    try:
        paths = manifest["graphics"]["managed_install_paths"]
        driver = paths["driver"]
        icd = paths["icd"]
    except (KeyError, TypeError) as exc:
        raise FreshSetupError("manifest managed Turnip paths are unavailable") from exc
    for value, prefix in ((driver, "/usr/local/lib/"), (icd, "/usr/local/share/vulkan/icd.d/")):
        if (not isinstance(value, str) or not value.startswith(prefix)
                or "\x00" in value or any(part in {".", ".."} for part in Path(value).parts)
                or str(Path(value)) != value or len(value) > 256):
            raise FreshSetupError("manifest managed Turnip path is invalid")
    if driver == icd or Path(driver).name in {"", ".", ".."} or Path(icd).name in {"", ".", ".."}:
        raise FreshSetupError("manifest managed Turnip paths collide")
    return driver, icd


def _guest_turnip_install(packages: list[str], driver: Path, icd: Path,
                          manager: str, alias: str, runner, manifest: dict) -> None:
    driver_path, icd_path = _managed_turnip_paths(manifest)
    for source, name in ((driver, "ternuxx-turnip-driver.so"), (icd, "ternuxx-turnip-icd.json")):
        result = runner([manager, "copy", str(source), f"{alias}:/tmp/{name}"],
                        check=False, timeout=180)
        if result.returncode:
            raise FreshSetupError("verified Turnip artifact could not be copied to the new guest")
    icd_config = json.loads(icd.read_text(encoding="utf-8"))
    if not isinstance(icd_config, dict) or not isinstance(icd_config.get("ICD"), dict):
        raise FreshSetupError("Turnip ICD metadata is invalid")
    icd_config["ICD"]["library_path"] = driver_path
    icd_text = json.dumps(icd_config, sort_keys=True, separators=(",", ":"))
    driver_parent = shlex.quote(str(Path(driver_path).parent))
    icd_parent = shlex.quote(str(Path(icd_path).parent))
    quoted_driver = shlex.quote(driver_path)
    quoted_icd = shlex.quote(icd_path)
    driver_hash = shlex.quote(hashlib.sha256(driver.read_bytes()).hexdigest())
    icd_hash = shlex.quote(hashlib.sha256(icd_text.encode()).hexdigest())
    script = "\n".join([
        "set -eu",
        f"install -d -m 0755 {driver_parent} {icd_parent}",
        f"if [ -L {quoted_driver} ] || [ -L {quoted_icd} ]; then exit 1; fi",
        'if [ -e ' + quoted_driver + ' ]; then set -- $(sha256sum < ' + quoted_driver
        + '); [ "$1" = ' + driver_hash + ' ] || exit 1; fi',
        'if [ -e ' + quoted_icd + ' ]; then set -- $(sha256sum < ' + quoted_icd
        + '); [ "$1" = ' + icd_hash + ' ] || exit 1; fi',
        f"install -m 0644 /tmp/ternuxx-turnip-driver.so {quoted_driver}",
        f"printf %s {shlex.quote(icd_text)} > {quoted_icd}",
        "rm -f /tmp/ternuxx-turnip-driver.so /tmp/ternuxx-turnip-icd.json",
        "apt-mark hold " + " ".join(shlex.quote(p) for p in manifest_holds(packages)),
    ])
    result = runner([manager, "login", "--isolated", "--user", "root", alias,
                     "--", "/bin/bash", "-lc", script], check=False, timeout=300)
    if result.returncode:
        raise FreshSetupError("Turnip files or Mesa package holds could not be installed")


def manifest_holds(packages: list[str]) -> list[str]:
    holds = ["libegl-mesa0", "libgbm1", "libgl1-mesa-dri", "libglx-mesa0", "mesa-vulkan-drivers"]
    return [item for item in holds if item in packages]


def _pinned_image_reference(spec: dict) -> str:
    image = spec.get("base_image")
    digest = spec.get("image_index_digest")
    if (not isinstance(image, str) or not re.fullmatch(r"[a-z0-9][a-z0-9./:_-]{0,255}", image)
            or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
        raise FreshSetupError("Debian image reference or index digest is invalid")
    return f"{image}@{digest}"


def _verify_base_image(prefix: str, manifest: dict, alias: str = ALIAS) -> None:
    spec = manifest["fresh_install"]
    pinned_image = _pinned_image_reference(spec)
    container, _rootfs = _target_paths(prefix, alias)
    path = container / "manifest.json"
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 1024 * 1024:
        raise FreshSetupError("installed base image manifest is unsafe")
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        image_manifest = saved["manifest"]
        image_config = saved["image_config"]
        config = image_manifest["config"]
        layers = image_manifest["layers"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise FreshSetupError("installed OCI image metadata is incomplete") from exc
    if (saved.get("image_ref") != pinned_image or saved.get("arch") != "aarch64"
            or image_config.get("architecture") != "arm64"
            or image_config.get("created") != spec["image_created"]
            or config.get("digest") != spec["config_digest"]
            or config.get("size") != spec["config_size"]
            or not isinstance(layers, list) or len(layers) != 1
            or layers[0].get("digest") != spec["layer_digest"]
            or layers[0].get("size") != spec["layer_size"]):
        raise FreshSetupError("installed Debian base image does not match the pinned arm64 image content")


def _kgsl_accessible() -> bool:
    path = Path("/dev/kgsl-3d0")
    return path.is_char_device() and os.access(path, os.R_OK | os.W_OK)


def _validate_guest_password(password: str) -> None:
    # Debian's local sudo credential is user-selected; allow short credentials
    # while still rejecting empty, oversized, and command-breaking values.
    if len(password) < 4 or len(password) > 1024 or any(ch in password for ch in "\x00\r\n"):
        raise FreshSetupError("guest password must be 4-1024 characters without line breaks")


def apply(*, repo_root: str, prefix: str, home: str, state_dir: str, user: str | None = None,
          plan_id: str, confirmed: bool, runner=subprocess.run, alias: str | None = None,
          password: str | None = None) -> dict:
    if confirmed is not True:
        raise FreshSetupError("fresh Debian install requires explicit confirmation")
    if password is None:
        raise FreshSetupError("fresh Debian setup requires a sudo password for the selected guest user")
    _validate_guest_password(password)
    if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise FreshSetupError("valid fresh setup preview ID required")
    manifest_path = Path(repo_root) / "config/proot/debian-trixie.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    state = _state_root(home, state_dir, create=False)
    previews = state / "previews"
    plan_path = previews / f"fresh-{plan_id}.json"
    plan = _read_private(plan_path)
    planned_user = plan.get("guest_user")
    planned_alias = plan.get("alias")
    user = planned_user if user is None else user
    alias = planned_alias if alias is None else alias
    if not isinstance(user, str) or not isinstance(alias, str):
        raise FreshSetupError("fresh setup preview lacks its selected guest account or target")
    alias = _alias(alias)
    identity = {key: value for key, value in plan.items() if key != "plan_id"}
    recalculated = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (plan.get("schema_version") != 2 or plan.get("operation") not in {
                "fresh-debian-trixie", "resume-fresh-debian-trixie"}
            or plan.get("plan_id") != plan_id or recalculated != plan_id
            or plan.get("guest_user") != user or plan.get("alias") != alias
            or plan.get("manifest_sha256") != hashlib.sha256(raw).hexdigest()
            or plan.get("rootfs_target") != str(Path(prefix) / "var/lib/proot-distro/containers" / alias / "rootfs")):
        raise FreshSetupError("fresh setup preview differs from the reviewed plan or current profile")
    ca_path, ca_sha256 = _native_ca_bundle(prefix)
    guest_ca_path = "/tmp/ternuxx-native-ca.pem"
    if plan.get("https_bootstrap") != {"source": str(ca_path), "sha256": ca_sha256,
                                        "guest_temporary_path": guest_ca_path,
                                        "release_signature_required": True}:
        raise FreshSetupError("Native Termux CA bundle or HTTPS trust policy changed since setup preview")
    if plan.get("operation") == "resume-fresh-debian-trixie":
        previous_id = plan.get("resume_from_plan_id")
        if not isinstance(previous_id, str) or not re.fullmatch(r"[0-9a-f]{64}", previous_id):
            raise FreshSetupError("resume preview lacks its previous failed plan identity")
    manager = shutil.which("proot-distro")
    if not manager:
        raise FreshSetupError("proot-distro is unavailable")
    container, rootfs = _target_paths(prefix, alias)
    if bool(plan["graphics"]["kgsl_accessible_at_preview"]) != _kgsl_accessible():
        raise FreshSetupError("KGSL capability changed since the fresh setup preview; create a new preview")
    journal = state / f"fresh-{plan_id}.journal.json"
    lock_path = state / f"fresh-alias-{alias}.lock"
    if journal.is_symlink() or lock_path.is_symlink():
        raise FreshSetupError("fresh setup journal or lock is a symbolic link")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    meta = os.fstat(lock_fd)
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid()
            or stat.S_IMODE(meta.st_mode) != 0o600):
        os.close(lock_fd)
        raise FreshSetupError("fresh setup lock identity is unsafe")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise FreshSetupError("another fresh Debian setup operation is active") from exc
    owned = None
    attempted = False
    try:
        container, rootfs = _target_paths(prefix, alias)
        if container.exists():
            if plan.get("operation") == "resume-fresh-debian-trixie":
                previous_id = plan["resume_from_plan_id"]
                previous_journal = _read_private(state / f"fresh-{previous_id}.journal.json")
                previous_plan = _read_private(previews / f"fresh-{previous_id}.json")
                if (previous_journal.get("plan_id") != previous_id
                        or previous_journal.get("alias") != alias
                        or previous_journal.get("state") != "failed"
                        or previous_journal.get("rootfs_identity") != plan.get("rootfs_identity")
                        or previous_plan.get("plan_id") != previous_id):
                    raise FreshSetupError("resume source is no longer a matching failed setup")
                _assert_resume_compatible(previous_plan, plan)
                owned = plan["rootfs_identity"]
                if _root_identity(container, rootfs) != owned:
                    raise FreshSetupError("failed replay rootfs identity changed after resume preview")
                _assert_rootfs_idle_for_resume(state, rootfs)
            else:
                try:
                    prior = _read_private(journal)
                except (OSError, ValueError) as exc:
                    raise FreshSetupError("fresh destination exists without a verified owned install journal") from exc
                if (prior.get("plan_id") != plan_id or prior.get("alias") != alias
                        or prior.get("state") != "failed" or not isinstance(prior.get("rootfs_identity"), dict)):
                    raise FreshSetupError("fresh destination is not a failed verified install from this exact preview")
                owned = prior["rootfs_identity"]
                _verify_owned_target(prefix, alias, owned)
        elif plan.get("operation") == "resume-fresh-debian-trixie":
            raise FreshSetupError("failed replay target disappeared after resume preview")
        turnip_files = None
        if plan["graphics"]["turnip_install_planned"]:
            turnip_files = _stage_turnip(manifest, state / "artifacts")
        attempted = True
        _private_write(journal, {"plan_id": plan_id, "alias": alias, "state": "installing",
                                 "rootfs_identity": owned})
        if owned is None:
            result = runner([manager, "install", "--name", alias, "--architecture", manifest["fresh_install"]["architecture"], _pinned_image_reference(manifest["fresh_install"])],
                            check=False, timeout=1800)
            if result.returncode:
                raise FreshSetupError("proot-distro failed to create the new Debian alias")
        # Validate the exact OCI content that proot-distro installed before
        # changing APT sources, installing packages, or creating guest users.
        _verify_base_image(prefix, manifest, alias)
        if owned is None:
            owned = _root_identity(container, rootfs)
        _verify_owned_target(prefix, alias, owned)
        _private_write(journal, {"plan_id": plan_id, "alias": alias, "state": "configuring",
                                 "rootfs_identity": owned})
        package_set = list(plan["packages"])
        if bool(turnip_files) != bool(plan["graphics"]["turnip_install_planned"]):
            raise FreshSetupError("Turnip plan and verified artifact selection do not match")
        package_args = " ".join(shlex.quote(item) for item in package_set)
        guest_user = shlex.quote(user)
        _verify_owned_target(prefix, alias, owned)
        guest_ca_quoted = shlex.quote(guest_ca_path)
        copied_ca = runner([manager, "copy", str(ca_path), f"{alias}:{guest_ca_path}"],
                           check=False, timeout=180)
        if copied_ca.returncode:
            raise FreshSetupError("verified Native Termux CA bundle could not be staged in the new guest")
        snapshot = manifest["fresh_install"]["apt_snapshot"]
        sources = (
            "Types: deb\nURIs: " + snapshot["main_archive"] + "\nSuites: trixie trixie-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\nCheck-Valid-Until: no\n\n"
            "Types: deb\nURIs: " + snapshot["security_archive"] + "\nSuites: trixie-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\nCheck-Valid-Until: no\n"
        )
        configure_sources = "rm -f /etc/apt/sources.list && find /etc/apt/sources.list.d -maxdepth 1 -type f \\( -name '*.sources' -o -name '*.list' \\) -delete && printf %s " + shlex.quote(sources) + " > /etc/apt/sources.list.d/ternuxx-snapshot.sources"
        script = "\n".join([
            "set -eu", f"trap 'rm -f {guest_ca_quoted}' EXIT", "export DEBIAN_FRONTEND=noninteractive", configure_sources,
            f"apt-get -o Acquire::https::CaInfo={guest_ca_quoted} -o Acquire::Check-Valid-Until=false update",
            f"apt-get -o Acquire::https::CaInfo={guest_ca_quoted} install -y --no-install-recommends {package_args}",
            f"rm -f {guest_ca_quoted}",
            "printf '%s\\n' 'en_US.UTF-8 UTF-8' > /etc/locale.gen", "locale-gen",
            "if ! getent passwd " + guest_user + " >/dev/null; then useradd --create-home --shell /bin/bash " + guest_user + "; fi",
            f"usermod -aG sudo {guest_user}", "update-locale LANG=en_US.UTF-8",
            # PRoot's login helper does not reliably populate Debian supplementary
            # groups, so grant sudo to this validated account explicitly.
            "printf '%s\\n' " + shlex.quote(user + " ALL=(ALL:ALL) ALL") + " > /etc/sudoers.d/ternuxx-guest-user",
            "chmod 0440 /etc/sudoers.d/ternuxx-guest-user",
            "visudo -cf /etc/sudoers.d/ternuxx-guest-user",
        ])
        _verify_owned_target(prefix, alias, owned)
        result = runner([manager, "login", "--isolated", "--user", "root", alias,
                         "--", "/bin/bash", "-lc", script], check=False, timeout=3600)
        if result.returncode:
            raise FreshSetupError("Debian package setup failed; new alias retained for inspection")
        # Secret is sent only over stdin; never place it in argv, script, logs, plans, or receipts.
        result = runner([manager, "login", "--isolated", "--user", "root", alias,
                         "--", "/usr/sbin/chpasswd"], input=f"{user}:{password}\n",
                        text=True, capture_output=True, check=False, timeout=120)
        if result.returncode:
            raise FreshSetupError("Debian guest password could not be configured")
        release = (rootfs / "etc/os-release").read_text(encoding="utf-8")
        release_values = dict(line.split("=", 1) for line in release.splitlines() if "=" in line)
        if (release_values.get("ID", "").strip('"') != "debian"
                or release_values.get("VERSION_CODENAME", "").strip('"') != "trixie"):
            raise FreshSetupError("new guest release did not match Debian Trixie")
        if turnip_files:
            _verify_owned_target(prefix, alias, owned)
            _guest_turnip_install(package_set, turnip_files[0], turnip_files[1], manager, alias, runner, manifest)
            expected_driver = manifest["graphics"]["turnip_archive"]["driver_sha256"]
            actual_driver = hashlib.sha256((rootfs / manifest["graphics"]["managed_install_paths"]["driver"].lstrip("/")).read_bytes()).hexdigest()
            if actual_driver != expected_driver:
                raise FreshSetupError("installed Turnip driver does not match the pinned artifact")
        _verify_owned_target(prefix, alias, owned)
        versions = runner([manager, "login", "--isolated", "--user", "root", alias,
                           "--", "/usr/bin/dpkg-query", "-W", "-f", "$"+"{db:Status-Abbrev}\\t$"+"{binary:Package}=$"+"{Version}\\n"],
                          capture_output=True, text=True, check=False, timeout=120)
        out = getattr(versions, "stdout", "")
        if versions.returncode != 0 or not isinstance(out, str) or not out.strip():
            raise FreshSetupError("installed package-version inventory could not be recorded")
        _verify_owned_target(prefix, alias, owned)
        _version_inventory(out, package_set)
        version_path = state / f"{alias}-package-versions.txt"
        fd, version_tmp = tempfile.mkstemp(prefix=".versions-", dir=state)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(out)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(version_tmp, version_path)
        finally:
            try:
                os.unlink(version_tmp)
            except FileNotFoundError:
                pass
        record = {
            "schema_version": 1, "plan_id": plan_id, "alias": alias, "guest_user": user,
            "manifest_sha256": plan["manifest_sha256"], "release": "Debian Trixie",
            "package_versions_sha256": hashlib.sha256(out.encode() if isinstance(out, str) else b"").hexdigest(),
            "package_versions_recorded": True, "requested_packages_verified_installed": True,
            "package_versions_file": str(version_path),
            "existing_debian_rootfs_changed": False,
            "turnip_installed": bool(turnip_files), "turnip_runtime_verified": False,
            "origin": "fresh-preview-confirmed-install",
        }
        record["rootfs_identity"] = owned
        _private_write(state / ("fresh-provider.json" if alias == ALIAS else f"fresh-provider-{alias}.json"), record)
        _private_write(journal, {"plan_id": plan_id, "alias": alias, "state": "complete", "rootfs_identity": owned})
        return {"status": "installed", "record": record}
    except (OSError, subprocess.TimeoutExpired, FreshSetupError) as exc:
        if attempted:
            _private_write(journal, {"plan_id": plan_id, "alias": alias, "state": "failed",
                                     "rootfs_identity": owned, "detail": str(exc)[:240]})
        raise
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
