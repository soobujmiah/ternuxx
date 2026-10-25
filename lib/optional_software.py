"""Preview-first lifecycle for a small, official Native Termux app catalog."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import re
import shlex
import subprocess
from typing import Callable
from contextlib import contextmanager
from urllib.parse import urlparse


class SoftwareError(ValueError):
    """A curated app operation cannot be safely planned or applied."""


APPS: tuple[dict[str, str], ...] = (
    {"id": "process-monitor", "name": "Process monitor", "package": "htop",
     "description": "Interactive view of processes and resource use.", "repo": "termux-main"},
    {"id": "terminal-multiplexer", "name": "Terminal multiplexer", "package": "tmux",
     "description": "Keep terminal sessions available across disconnects.", "repo": "termux-main"},
    {"id": "directory-tree", "name": "Directory tree", "package": "tree",
     "description": "Print directory contents as a readable tree.", "repo": "termux-main"},
)
APP_BY_ID = {item["id"]: item for item in APPS}
OFFICIAL_REPOSITORIES = ("termux-main", "termux-x11")
_VERSION = re.compile(r"^[A-Za-z0-9.+:~_-]{1,128}$")
_APP_ID = re.compile(r"^[a-z][a-z0-9-]{1,47}$")
PLAN_TTL_SECONDS = 15 * 60


def _env(env: dict[str, str] | None = None, prefix: str | None = None) -> dict[str, str]:
    value = dict(os.environ if env is None else env)
    value["PREFIX"] = prefix or value.get("PREFIX", "/data/data/com.termux/files/usr")
    value["LC_ALL"] = "C"
    return value


def _run(argv: list[str], *, env: dict[str, str], runner: Callable = subprocess.run,
         timeout: int = 30) -> subprocess.CompletedProcess:
    process_env = dict(env)
    if Path(argv[0]).name in {"apt-get", "apt-cache", "dpkg", "dpkg-query"}:
        # Codex can inject its own library directory. Native Termux package
        # tools and their maintainer scripts must resolve Termux libraries.
        process_env.pop("LD_LIBRARY_PATH", None)
    try:
        return runner(argv, capture_output=True, text=True, timeout=timeout, check=False, env=process_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SoftwareError(f"package operation could not run {Path(argv[0]).name}") from exc


def _index_status(prefix: str, *, now: datetime | None = None) -> tuple[bool, str]:
    root = Path(prefix) / "var/lib/apt/lists"
    now = now or datetime.now(timezone.utc)
    for repo in OFFICIAL_REPOSITORIES:
        files = list(root.glob(f"*{repo}*_InRelease")) if root.is_dir() else []
        if not files:
            return False, f"missing signed index: {repo}"
        dates: list[datetime] = []
        for path in files:
            try:
                info = path.lstat()
                if not path.is_file() or path.is_symlink() or info.st_size > 4 * 1024 * 1024:
                    continue
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("Date: "):
                        parsed = parsedate_to_datetime(line[6:])
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        dates.append(parsed.astimezone(timezone.utc))
                        break
            except (OSError, ValueError, TypeError, OverflowError):
                continue
        if not dates:
            return False, f"unreadable signed index date: {repo}"
        stamp = max(dates)
        age = (now - stamp).total_seconds()
        if age < -900 or age > 14 * 24 * 60 * 60:
            return False, f"signed index is future-dated or older than 14 days: {repo}"
    return True, "fresh"


def _app(app_id: object) -> dict[str, str]:
    if not isinstance(app_id, str) or not _APP_ID.fullmatch(app_id) or app_id not in APP_BY_ID:
        raise SoftwareError("app ID is not in the curated Native catalog")
    return APP_BY_ID[app_id]


def _installed(package: str, *, env: dict[str, str], runner: Callable) -> tuple[bool, str | None]:
    result = _run(["dpkg-query", "-W", "-f=${Status}\t${Version}\n", package], env=env, runner=runner)
    if result.returncode != 0:
        return False, None
    parts = result.stdout.strip().split("\t", 1)
    if len(parts) != 2 or parts[0] != "install ok installed" or not _VERSION.fullmatch(parts[1]):
        return False, None
    return True, parts[1]


def _configured_repo_origins(prefix: str, expected_repo: str) -> set[str]:
    """Return exact active APT URIs whose path names the expected Termux repo."""
    root = Path(prefix) / "etc/apt"
    files = [root / "sources.list"]
    sources_dir = root / "sources.list.d"
    if sources_dir.is_dir():
        files.extend(sorted(sources_dir.glob("*.list")))
    found: set[str] = set()
    for path in files:
        try:
            metadata = path.lstat()
            if path.is_symlink() or not path.is_file() or metadata.st_size > 256 * 1024:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                parts = shlex.split(line, comments=True)
            except ValueError:
                continue
            if not parts or parts[0] != "deb":
                continue
            uri = next((part for part in parts[1:] if part.startswith(("https://", "http://"))), None)
            if not uri:
                continue
            parsed = urlparse(uri)
            if (parsed.scheme in {"https", "http"} and parsed.hostname
                    and expected_repo in parsed.path.strip("/").split("/")):
                found.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}")
    return found


def _candidate(package: str, expected_repo: str, *, env: dict[str, str], runner: Callable) -> str:
    result = _run(["apt-cache", "policy", package], env=env, runner=runner)
    if result.returncode != 0:
        raise SoftwareError(f"could not inspect the official candidate for {package}")
    lines = result.stdout.splitlines()
    candidate = next((line.split(":", 1)[1].strip() for line in lines
                      if line.strip().startswith("Candidate:")), None)
    if not candidate or candidate == "(none)" or not _VERSION.fullmatch(candidate):
        raise SoftwareError(f"no package candidate is available for {package}")
    found = False
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(?:\*\*\*\s+)?([^\s]+)\s+\d+\s*$", line)
        if not match or match.group(1) != candidate:
            continue
        for following in lines[index + 1:index + 5]:
            if re.match(r"^\s*\S+\s+\d+\s*$", following):
                break
            origin = re.match(r"^\s*\d+\s+(https?://\S+)", following)
            if origin:
                uri = urlparse(origin.group(1))
                configured = _configured_repo_origins(env["PREFIX"], expected_repo)
                normalized = f"{uri.scheme}://{uri.netloc}{uri.path.rstrip('/')}"
                if expected_repo in uri.path.strip("/").split("/") and normalized in configured:
                    found = True
                break
        if found:
            break
    if not found:
        raise SoftwareError(f"{package} candidate is not from official {expected_repo}")
    return candidate


def _version_greater(left: str, right: str, *, env: dict[str, str], runner: Callable) -> bool:
    result = _run(["dpkg", "--compare-versions", left, "gt", right], env=env, runner=runner)
    if result.returncode not in (0, 1):
        raise SoftwareError("could not compare installed and candidate versions")
    return result.returncode == 0


def _parse_changes(simulation: str, *, action: str, target_package: str) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for line in simulation.splitlines():
        if line.startswith("Remv "):
            fields = line.split()
            if len(fields) < 2:
                raise SoftwareError("APT returned an invalid removal row")
            changes.append({"action": "remove", "package": fields[1]})
        elif line.startswith("Inst "):
            match = re.match(r"^Inst\s+(\S+)\s+(?:\[[^]]+\]\s+)?\(([^\s)]+)\s+(\S+)", line)
            if not match or not _VERSION.fullmatch(match.group(2)):
                raise SoftwareError("APT returned an invalid install row")
            package, version, source = match.groups()
            if not any(repo in source for repo in OFFICIAL_REPOSITORIES):
                raise SoftwareError("the dependency transaction includes a non-official package source")
            old = re.match(r"^Inst\s+\S+\s+\[([^]]+)\]", line)
            changes.append({"action": "install", "package": package, "version": version,
                            "repository": source, "installed_version": old.group(1) if old else None})
    if action in {"install", "update"}:
        if any(item["action"] == "remove" for item in changes):
            raise SoftwareError("the package transaction would remove software")
        if not any(item["package"] == target_package and item["action"] == "install" for item in changes):
            raise SoftwareError("APT did not include the exact curated app in the transaction")
    else:
        removed = [item["package"] for item in changes if item["action"] == "remove"]
        if removed != [target_package] or any(item["action"] == "install" for item in changes):
            raise SoftwareError("removal would change packages outside the selected app")
    if not changes:
        raise SoftwareError("APT returned no verifiable package changes")
    return changes


def _plan(app_id: str, action: str, *, env: dict[str, str], runner: Callable,
          now: datetime | None = None) -> dict[str, object]:
    app = _app(app_id)
    if action not in {"install", "update", "remove"}:
        raise SoftwareError("action must be install, update, or remove")
    prefix = env["PREFIX"]
    if action != "remove":
        fresh, index_message = _index_status(prefix, now=now)
        if not fresh:
            raise SoftwareError(f"Termux package indexes are not usable: {index_message}; refresh them through your normal Termux workflow and preview again")
    installed, installed_version = _installed(app["package"], env=env, runner=runner)
    if action == "install" and installed:
        raise SoftwareError("app is already installed; choose update or remove")
    if action in {"update", "remove"} and not installed:
        raise SoftwareError("app is not installed")
    candidate = installed_version if action == "remove" else _candidate(app["package"], app["repo"], env=env, runner=runner)
    if action == "update":
        if installed_version == candidate or not _version_greater(candidate, installed_version or "", env=env, runner=runner):
            raise SoftwareError("no newer official app candidate is available")
    if action == "remove":
        command = ["apt-get", "-s", "--no-install-recommends", "--no-auto-remove", "remove", app["package"]]
    else:
        command = ["apt-get", "-s", "--no-install-recommends", "--no-remove"]
        if action == "install":
            command.append("--no-upgrade")
        command.extend(["install", f"{app['package']}={candidate}"])
    result = _run(command, env=env, runner=runner, timeout=90)
    simulation = result.stdout + result.stderr
    if result.returncode != 0:
        raise SoftwareError("APT simulation failed; no package state was changed")
    changes = _parse_changes(simulation, action=action, target_package=app["package"])
    if action in {"install", "update"}:
        direct = next((item for item in changes if item["package"] == app["package"]), None)
        if direct is None or direct["version"] != candidate:
            raise SoftwareError("APT did not resolve the exact reviewed app candidate")
        for item in changes:
            old = item.get("installed_version")
            if old and _version_greater(old, item["version"], env=env, runner=runner):
                raise SoftwareError(f"the dependency transaction would downgrade {item['package']}")
            package_candidate = _candidate(item["package"], item["repository"], env=env, runner=runner)
            if package_candidate != item["version"]:
                raise SoftwareError(f"APT transaction version for {item['package']} differs from its official candidate")
    payload: dict[str, object] = {
        "action": action, "app_id": app_id, "package": app["package"],
        "installed_version": installed_version, "candidate_version": candidate,
        "repository": app["repo"], "simulation": simulation[-12000:],
        "changes": changes,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {**payload, "plan_id": hashlib.sha256(canonical).hexdigest(),
            "read_only": True, "requires_confirmation": True,
            "confirmation": action.upper(), "index_status": "fresh"}


def list_apps(*, env: dict[str, str] | None = None, prefix: str | None = None,
              runner: Callable = subprocess.run, now: datetime | None = None) -> dict[str, object]:
    process_env = _env(env, prefix)
    fresh, reason = _index_status(process_env["PREFIX"], now=now)
    items: list[dict[str, object]] = []
    for app in APPS:
        installed, version = _installed(app["package"], env=process_env, runner=runner)
        item: dict[str, object] = {**app, "installed": installed, "installed_version": version,
                                   "candidate_version": None, "status": "installed" if installed else "unknown"}
        if fresh:
            try:
                candidate = _candidate(app["package"], app["repo"], env=process_env, runner=runner)
                item["candidate_version"] = candidate
                newer = (installed and version != candidate
                         and _version_greater(candidate, version or "", env=process_env, runner=runner))
                item["status"] = "update_available" if newer else "installed" if installed else "available"
            except SoftwareError:
                item["status"] = "unavailable"
        else:
            item["status"] = "unknown"
        items.append(item)
    return {"apps": items, "index_status": "fresh" if fresh else "unusable",
            "index_message": reason, "read_only": True}



def inspect_directory_tree(path_value: object, *, home: str | Path,
                           env: dict[str, str] | None = None, prefix: str | None = None,
                           runner: Callable = subprocess.run) -> dict[str, object]:
    """Pass one explicitly selected HOME path to the fixed, read-only tree app."""
    app = _app("directory-tree")
    if not isinstance(path_value, str) or not path_value or any(ch in path_value for ch in ("\x00", "\n", "\r")):
        raise SoftwareError("select a non-empty Native HOME path")
    try:
        if len(path_value.encode("utf-8", "strict")) > 4096:
            raise SoftwareError("selected path exceeds 4096 UTF-8 bytes")
    except UnicodeError as exc:
        raise SoftwareError("selected path is not valid UTF-8") from exc
    base = Path(home).expanduser()
    try:
        base_info = base.lstat()
        if stat.S_ISLNK(base_info.st_mode) or not stat.S_ISDIR(base_info.st_mode):
            raise SoftwareError("Native HOME is not a safe directory")
        base = base.resolve(strict=True)
    except OSError as exc:
        raise SoftwareError("Native HOME is unavailable") from exc
    raw = Path(path_value).expanduser()
    candidate = raw if raw.is_absolute() else base / raw
    if any(part == ".." for part in candidate.parts):
        raise SoftwareError("parent-directory traversal is not allowed")
    try:
        relative = candidate.relative_to(base)
    except ValueError as exc:
        raise SoftwareError("file handoff is limited to paths under Native HOME") from exc
    target = base
    try:
        for part in relative.parts:
            if part in {"", "."}:
                continue
            target = target / part
            info = target.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise SoftwareError("symbolic-link paths are not allowed")
        info = target.stat(follow_symlinks=False)
    except FileNotFoundError as exc:
        raise SoftwareError("selected HOME path does not exist") from exc
    except OSError as exc:
        raise SoftwareError("selected HOME path cannot be inspected safely") from exc
    is_directory = stat.S_ISDIR(info.st_mode)
    if not is_directory and not stat.S_ISREG(info.st_mode):
        raise SoftwareError("only regular files and directories can be handed to tree")
    process_env = _env(env, prefix)
    executable = Path(process_env["PREFIX"]) / "bin" / app["package"]
    try:
        executable_info = executable.lstat()
    except OSError as exc:
        raise SoftwareError("the curated directory-tree app is unavailable") from exc
    if (stat.S_ISLNK(executable_info.st_mode) or not stat.S_ISREG(executable_info.st_mode)
            or not os.access(executable, os.X_OK)):
        raise SoftwareError("the curated directory-tree executable is unsafe or unavailable")
    if is_directory:
        cwd = target
        argv = [str(executable), "-L", "2", "--filelimit", "32", "-n", "-q",
                "--noreport", "--", "."]
        input_text = None
    else:
        cwd = target.parent
        argv = [str(executable), "--fromfile", "-n", "-q", "--noreport"]
        input_text = target.name + "\n"
    try:
        result = runner(argv, capture_output=True, text=True, timeout=8, check=False,
                        env=process_env, cwd=str(cwd), input=input_text)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SoftwareError("the selected HOME path could not be handed to tree") from exc
    if result.returncode != 0:
        raise SoftwareError("tree could not inspect the selected HOME path")
    output = result.stdout if isinstance(result.stdout, str) else ""
    encoded = output.encode("utf-8", "replace")
    truncated = len(encoded) > 32768
    if truncated:
        output = encoded[:32768].decode("utf-8", "ignore") + "\n… output truncated at 32 KiB"
    label = "~/" + relative.as_posix() if relative.parts else "~/"
    return {"app_id": app["id"], "path": label, "kind": "directory" if is_directory else "file",
            "output": output, "truncated": truncated, "read_only": True,
            "contents_read": False, "handoff": "native-home-only"}

def _state_paths(*, home: str | Path | None, state_dir: str | Path | None,
                 create: bool) -> tuple[Path, Path]:
    home_path = Path(home or Path.home()).expanduser().resolve(strict=True)
    state_input = Path(state_dir or (home_path / ".local/share/ternuxx")).expanduser()
    state_path = Path(os.path.abspath(state_input))
    try:
        relative = state_path.relative_to(home_path)
    except ValueError as exc:
        raise SoftwareError("software operation state must stay inside HOME") from exc
    current = home_path
    for part in relative.parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise SoftwareError("software operation state contains a symbolic link")
        except FileNotFoundError:
            if create:
                current.mkdir(mode=0o700)
        except OSError as exc:
            raise SoftwareError("software operation state is unsafe") from exc
    try:
        info = state_path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise SoftwareError("software operation state directory is not privately owned")
        os.chmod(state_path, 0o700)
    except OSError as exc:
        raise SoftwareError("software operation state directory is unavailable") from exc
    plans = state_path / "software-plans"
    try:
        if create:
            plans.mkdir(mode=0o700, exist_ok=True)
        info = plans.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise SoftwareError("software preview directory is unsafe")
        os.chmod(plans, 0o700)
    except OSError as exc:
        raise SoftwareError("software preview directory is unavailable") from exc
    return plans, plans / ".package-operations.lock"


@contextmanager
def _operation_lock(lock_path: Path):
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError as exc:
        raise SoftwareError("cannot open the private package-operation lock") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise SoftwareError("package-operation lock is unsafe")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SoftwareError("another curated package operation is active") from exc
        yield
    finally:
        os.close(fd)


def _write_record(path: Path, record: dict[str, object], *, allow_applying: bool = False) -> None:
    try:
        existing = path.lstat()
        if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid():
            raise SoftwareError("saved package plan is unsafe")
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("status") == "applying" and not allow_applying:
            raise SoftwareError("an earlier package operation has an unresolved result")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, SoftwareError):
            raise
        raise SoftwareError("saved package plan cannot be verified") from exc
    fd, temporary = tempfile.mkstemp(prefix=".software-plan-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _read_record(path: Path) -> dict[str, object]:
    try:
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 256 * 1024):
            raise SoftwareError("saved package plan is unsafe")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, SoftwareError):
            raise
        raise SoftwareError("saved package plan is unavailable") from exc
    if not isinstance(value, dict):
        raise SoftwareError("saved package plan is malformed")
    return value


def preview(app_id: str, action: str, *, env: dict[str, str] | None = None,
            prefix: str | None = None, home: str | Path | None = None,
            state_dir: str | Path | None = None, runner: Callable = subprocess.run,
            now: datetime | None = None) -> dict[str, object]:
    process_env = _env(env, prefix)
    plan = _plan(app_id, action, env=process_env, runner=runner, now=now)
    plans, lock_path = _state_paths(home=home, state_dir=state_dir, create=True)
    created_at = (now or datetime.now(timezone.utc)).timestamp()
    record = {"schema_version": 1, "plan_id": plan["plan_id"], "app_id": app_id,
              "action": action, "created_at": created_at, "status": "preview"}
    with _operation_lock(lock_path):
        _write_record(plans / f"{plan['plan_id']}.json", record)
    return {**plan, "created_at": created_at}


def apply(app_id: str, action: str, plan_id: str, confirmed: object, *,
          env: dict[str, str] | None = None, prefix: str | None = None,
          home: str | Path | None = None, state_dir: str | Path | None = None,
          runner: Callable = subprocess.run, now: datetime | None = None) -> dict[str, object]:
    if confirmed is not True or action not in {"install", "update", "remove"}:
        raise SoftwareError("explicit confirmation and a supported app action are required")
    if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise SoftwareError("a current 64-character preview ID is required")
    process_env = _env(env, prefix)
    plans, lock_path = _state_paths(home=home, state_dir=state_dir, create=False)
    with _operation_lock(lock_path):
        record_path = plans / f"{plan_id}.json"
        record = _read_record(record_path)
        if (record.get("schema_version") != 1 or record.get("plan_id") != plan_id
                or record.get("app_id") != app_id or record.get("action") != action
                or record.get("status") != "preview"):
            raise SoftwareError("saved preview does not match this app action or is no longer available")
        current_time = (now or datetime.now(timezone.utc)).timestamp()
        created = record.get("created_at")
        if type(created) not in {int, float} or current_time - created < 0 or current_time - created > PLAN_TTL_SECONDS:
            raise SoftwareError("saved preview expired; create and review a new preview")
        current = _plan(app_id, action, env=process_env, runner=runner, now=now)
        if current["plan_id"] != plan_id:
            raise SoftwareError("the package state or simulation changed; create and review a new preview")
        _write_record(record_path, {**record, "status": "applying"})
        changes = current["changes"]
        if action == "remove":
            command = ["apt-get", "--assume-yes", "--no-install-recommends", "--no-auto-remove", "remove", current["package"]]
        else:
            command = ["apt-get", "--assume-yes", "--no-install-recommends", "--no-remove"]
            if action == "install":
                command.append("--no-upgrade")
            command.append("install")
            command.extend(f"{item['package']}={item['version']}" for item in changes)
        try:
            result = _run(command, env=process_env, runner=runner, timeout=900)
            output = (result.stdout + result.stderr)[-12000:]
        except SoftwareError as exc:
            result = subprocess.CompletedProcess(command, 1, "", str(exc))
            output = str(exc)
        result_payload = {"app_id": app_id, "package": current["package"], "action": action,
                          "plan_id": plan_id, "returncode": result.returncode,
                          "complete": result.returncode == 0, "changes": changes,
                          "output": output}
        _write_record(record_path, {**record, "status": "complete" if result.returncode == 0 else "failed",
                                    "result": result_payload}, allow_applying=True)
        return result_payload
