#!/usr/bin/env python3
"""Inspect displays and reclaim only artifacts tied to an exact stale session."""
import errno
import os
import re
import socket
import stat
import struct
import sys


def snapshot(path, expected):
    try:
        item = os.lstat(path)
    except FileNotFoundError:
        return None
    if item.st_uid != os.getuid() or stat.S_ISLNK(item.st_mode):
        raise RuntimeError("foreign artifact")
    if expected == "socket" and not stat.S_ISSOCK(item.st_mode):
        raise RuntimeError("not a socket")
    if expected == "lock" and not stat.S_ISREG(item.st_mode):
        raise RuntimeError("not a lock file")
    return item.st_dev, item.st_ino


def ensure_socket_directory(root):
    """Create the Native X11 socket directory only under a real owned temp root."""
    root = os.path.abspath(root)
    try:
        root_stat = os.lstat(root)
    except OSError:
        return "unsafe"
    if (stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.getuid() or os.path.realpath(root) != root):
        return "unsafe"

    socket_dir = os.path.join(root, ".X11-unix")
    try:
        os.mkdir(socket_dir, 0o700)
        created = True
    except FileExistsError:
        created = False
    except OSError:
        return "unsafe"
    try:
        directory_stat = os.lstat(socket_dir)
    except OSError:
        return "unsafe"
    if (stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.getuid()):
        return "unsafe"
    return "created" if created else "existing"


def attachable(proc_root, tmp_root, number):
    """Return identity for one exact, responsive native Termux:X11 process."""
    if not number.isdigit() or not 0 <= int(number) <= 10:
        return None
    sock = os.path.join(tmp_root, ".X11-unix", "X" + number)
    try:
        meta = os.lstat(sock)
        if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != os.getuid():
            return None
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.6)
            probe.connect(sock)
            probe.sendall(struct.pack("<BBHHHHH", ord("l"), 0, 11, 0, 0, 0, 0))
            reply = bytearray()
            while len(reply) < 8:
                chunk = probe.recv(8 - len(reply))
                if not chunk:
                    return None
                reply.extend(chunk)
            if reply[0] != 1 or struct.unpack("<H", reply[2:4])[0] != 11:
                return None
    except OSError:
        return None
    matches = []
    try:
        with os.scandir(proc_root) as entries:
            for entry in entries:
                if not entry.name.isdecimal():
                    continue
                base = os.path.join(proc_root, entry.name)
                try:
                    with open(os.path.join(base, "cmdline"), "rb") as stream:
                        args = stream.read().split(b"\0")
                    with open(os.path.join(base, "status"), encoding="ascii") as stream:
                        status = stream.read()
                    with open(os.path.join(base, "stat"), encoding="ascii") as stream:
                        stat_line = stream.read()
                except OSError:
                    continue
                uid = re.search(r"^Uid:\s+(\d+)", status, re.M)
                if not uid or int(uid.group(1)) != os.getuid():
                    continue
                native_argv = args == [b"termux-x11", b"com.termux.x11", (b":" + number.encode()), b""]
                if not native_argv:
                    try:
                        with open(os.path.join(base, "environ"), "rb") as stream:
                            env = stream.read().split(b"\0")
                    except OSError:
                        continue
                    has_x11_loader = any(item.startswith(b"CLASSPATH=") and item.endswith(b"termux-x11/loader.apk") for item in env)
                    if not has_x11_loader:
                        continue
                    try:
                        with open(os.path.join(base, "maps"), encoding="utf-8", errors="replace") as stream:
                            maps = stream.read()
                    except OSError:
                        continue
                    native_app_process = (
                        any("/com.termux.x11-" in line and line.rstrip().endswith("/base.apk")
                            for line in maps.splitlines())
                    )
                    if not native_app_process:
                        continue
                _comm, sep, tail = stat_line.rpartition(")")
                fields = tail.strip().split() if sep else []
                if len(fields) >= 20:
                    matches.append((int(entry.name), fields[19]))
    except OSError:
        return None
    if len(matches) != 1:
        return None
    pid, ticks = matches[0]
    lock = os.path.join(tmp_root, ".X" + number + "-lock")
    try:
        lock_meta = os.lstat(lock)
    except FileNotFoundError:
        return pid, ticks
    except OSError:
        return None
    if (stat.S_ISLNK(lock_meta.st_mode) or not stat.S_ISREG(lock_meta.st_mode)
            or lock_meta.st_uid != os.getuid()):
        return None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(lock, flags)
        try:
            current = os.fstat(fd)
            if (not stat.S_ISREG(current.st_mode) or current.st_uid != os.getuid()
                    or (current.st_dev, current.st_ino) != (lock_meta.st_dev, lock_meta.st_ino)):
                return None
            with os.fdopen(fd, "r", encoding="ascii", closefd=False) as stream:
                lock_pid = stream.read(64).strip()
        finally:
            os.close(fd)
    except OSError:
        return None
    return (pid, ticks) if lock_pid == str(pid) else None


def prepare(root, number):
    if not number.isdigit() or not 0 <= int(number) <= 10:
        return "busy"
    root = os.path.abspath(root)
    try:
        rstat = os.lstat(root)
        sockdir = os.path.join(root, ".X11-unix")
        dstat = os.lstat(sockdir)
        if (stat.S_ISLNK(rstat.st_mode) or not stat.S_ISDIR(rstat.st_mode)
                or rstat.st_uid != os.getuid()):
            return "busy"
        if (stat.S_ISLNK(dstat.st_mode) or not stat.S_ISDIR(dstat.st_mode)
                or dstat.st_uid != os.getuid()):
            return "busy"
    except OSError:
        return "busy"

    lock = os.path.join(root, ".X{}-lock".format(number))
    sockpath = os.path.join(sockdir, "X{}".format(number))
    try:
        lock_id = snapshot(lock, "lock")
        socket_id = snapshot(sockpath, "socket")
    except (OSError, RuntimeError):
        return "busy"
    if lock_id is None and socket_id is None:
        return "available"
    if lock_id is None:
        return "busy"

    try:
        with open(lock, "r", encoding="ascii") as stream:
            raw_pid = stream.read(64).strip()
        if not raw_pid.isdigit():
            return "busy"
        pid = int(raw_pid)
    except OSError:
        return "busy"
    if os.path.exists("/proc/{}".format(pid)):
        return "busy"

    if socket_id is not None:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(sockpath)
            return "busy"
        except OSError as error:
            if error.errno != errno.ECONNREFUSED:
                return "busy"
        finally:
            probe.close()

    # This is inspection only. Cleanup requires a separately authorized
    # lifecycle operation tied to a verified Ternuxx session identity.
    return "stale"


def recover(root, number, expected_pid):
    """Remove an unresponsive socket/lock pair only for its recorded dead PID."""
    if not number.isdigit() or not 0 <= int(number) <= 10 or not expected_pid.isdigit():
        return "busy"
    root = os.path.abspath(root)
    try:
        rstat = os.lstat(root)
        sockdir = os.path.join(root, ".X11-unix")
        dstat = os.lstat(sockdir)
        if (stat.S_ISLNK(rstat.st_mode) or not stat.S_ISDIR(rstat.st_mode)
                or rstat.st_uid != os.getuid()):
            return "busy"
        if (stat.S_ISLNK(dstat.st_mode) or not stat.S_ISDIR(dstat.st_mode)
                or dstat.st_uid != os.getuid()):
            return "busy"
    except OSError:
        return "busy"

    lock = os.path.join(root, ".X{}-lock".format(number))
    sockpath = os.path.join(sockdir, "X{}".format(number))
    try:
        lock_id = snapshot(lock, "lock")
        socket_id = snapshot(sockpath, "socket")
    except (OSError, RuntimeError):
        return "busy"
    if lock_id is None and socket_id is None:
        return "available"
    if lock_id is None:
        # External Termux:X11 may leave a lockless socket. Reclaim only when
        # the exact PID in the stale Ternuxx record is absent and the same
        # private socket refuses connections throughout the guarded check.
        if socket_id is None or int(expected_pid) <= 1:
            return "busy"
        try:
            os.stat("/proc/{}".format(expected_pid))
            return "busy"
        except FileNotFoundError:
            pass
        except OSError:
            return "busy"
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(sockpath)
            return "busy"
        except OSError as error:
            if error.errno != errno.ECONNREFUSED:
                return "busy"
        finally:
            probe.close()
        try:
            if snapshot(lock, "lock") is not None or snapshot(sockpath, "socket") != socket_id:
                return "busy"
            os.stat("/proc/{}".format(expected_pid))
            return "busy"
        except FileNotFoundError:
            pass
        except (OSError, RuntimeError):
            return "busy"
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(sockpath)
            return "busy"
        except OSError as error:
            if error.errno != errno.ECONNREFUSED:
                return "busy"
        finally:
            probe.close()
        try:
            if snapshot(lock, "lock") is not None or snapshot(sockpath, "socket") != socket_id:
                return "busy"
            os.unlink(sockpath)
        except (OSError, RuntimeError):
            return "busy"
        return "recovered"
    if int(expected_pid) <= 1 or os.path.exists("/proc/{}".format(expected_pid)):
        return "busy"
    try:
        with open(lock, "r", encoding="ascii") as stream:
            if stream.read(64).strip() != expected_pid:
                return "busy"
    except OSError:
        return "busy"
    if socket_id is not None:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(sockpath)
            return "busy"
        except OSError as error:
            if error.errno != errno.ECONNREFUSED:
                return "busy"
        finally:
            probe.close()

    try:
        if snapshot(lock, "lock") != lock_id or snapshot(sockpath, "socket") != socket_id:
            return "busy"
        with open(lock, "r", encoding="ascii") as stream:
            if stream.read(64).strip() != expected_pid:
                return "busy"
        if socket_id is not None:
            os.unlink(sockpath)
        if snapshot(lock, "lock") != lock_id:
            return "busy"
        os.unlink(lock)
    except OSError:
        return "busy"
    return "recovered"


def recover_proot_link2symlink(root, number, guest_rootfs, proc_root="/proc"):
    """Reclaim a dead Xephyr lock only through PRoot's exact Debian l2s chain."""
    if not number.isdigit() or not 0 <= int(number) <= 10:
        return "busy"
    root = os.path.abspath(root)
    rootfs = os.path.abspath(guest_rootfs)
    try:
        root_stat = os.lstat(root)
        sockdir = os.path.join(root, ".X11-unix")
        dir_stat = os.lstat(sockdir)
        rootfs_stat = os.lstat(rootfs)
        l2s = os.path.join(rootfs, ".l2s")
        l2s_stat = os.lstat(l2s)
        if (stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode)
                or root_stat.st_uid != os.getuid() or os.path.realpath(root) != root
                or stat.S_ISLNK(dir_stat.st_mode) or not stat.S_ISDIR(dir_stat.st_mode)
                or dir_stat.st_uid != os.getuid()
                or stat.S_ISLNK(rootfs_stat.st_mode) or not stat.S_ISDIR(rootfs_stat.st_mode)
                or rootfs_stat.st_uid != os.getuid() or os.path.realpath(rootfs) != rootfs
                or stat.S_ISLNK(l2s_stat.st_mode) or not stat.S_ISDIR(l2s_stat.st_mode)
                or l2s_stat.st_uid != os.getuid()):
            return "busy"
    except OSError:
        return "busy"

    sockpath = os.path.join(sockdir, "X" + number)
    lock = os.path.join(root, ".X" + number + "-lock")
    alias = backing = None
    try:
        lock_meta = os.lstat(lock)
        if not stat.S_ISLNK(lock_meta.st_mode) or lock_meta.st_uid != os.getuid():
            return "busy"
        link_target = os.readlink(lock)
        if (not os.path.isabs(link_target)
                or os.path.normpath(link_target) != os.path.join(l2s, os.path.basename(link_target))):
            return "busy"
        alias = os.path.normpath(link_target)
        if not re.fullmatch(r"\.l2s\.\.tX" + re.escape(number) + r"-lock[0-9]{4}", os.path.basename(alias)):
            return "busy"
        alias_meta = os.lstat(alias)
        if not stat.S_ISLNK(alias_meta.st_mode) or alias_meta.st_uid != os.getuid():
            return "busy"
        alias_target = os.readlink(alias)
        backing = (os.path.normpath(alias_target) if os.path.isabs(alias_target)
                   else os.path.normpath(os.path.join(l2s, alias_target)))
        if (os.path.dirname(backing) != l2s or not re.fullmatch(
                re.escape(os.path.basename(alias)) + r"\.[0-9]{4}", os.path.basename(backing))):
            return "busy"
        backing_meta = os.lstat(backing)
        if (stat.S_ISLNK(backing_meta.st_mode) or not stat.S_ISREG(backing_meta.st_mode)
                or backing_meta.st_uid != os.getuid() or backing_meta.st_size > 64):
            return "busy"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(backing, flags)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (backing_meta.st_dev, backing_meta.st_ino):
                return "busy"
            raw_pid = os.read(fd, 64).decode("ascii").strip()
        finally:
            os.close(fd)
        if not raw_pid.isdigit() or int(raw_pid) <= 1:
            return "busy"
        try:
            os.stat(os.path.join(proc_root, raw_pid))
            return "busy"
        except FileNotFoundError:
            pass
        except OSError:
            return "busy"

        sock_meta = snapshot(sockpath, "socket")
        if sock_meta is not None:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            probe.settimeout(0.5)
            try:
                probe.connect(sockpath)
                return "busy"
            except ConnectionRefusedError:
                pass
            except OSError:
                return "busy"
            finally:
                probe.close()

        # Recheck identities and the dead PID immediately before unlinking.
        current_lock = os.lstat(lock)
        current_alias = os.lstat(alias)
        if (not stat.S_ISLNK(current_lock.st_mode) or current_lock.st_uid != os.getuid()
                or (current_lock.st_dev, current_lock.st_ino) != (lock_meta.st_dev, lock_meta.st_ino)):
            return "busy"
        if (not stat.S_ISLNK(current_alias.st_mode) or current_alias.st_uid != os.getuid()
                or (current_alias.st_dev, current_alias.st_ino) != (alias_meta.st_dev, alias_meta.st_ino)):
            return "busy"
        if snapshot(backing, "file") != (backing_meta.st_dev, backing_meta.st_ino):
            return "busy"
        if snapshot(sockpath, "socket") != sock_meta:
            return "busy"
        resolved_alias = os.path.normpath(os.readlink(lock))
        target = os.readlink(alias)
        resolved_backing = os.path.realpath(target if os.path.isabs(target) else os.path.join(l2s, target))
        if resolved_alias != alias or resolved_backing != backing:
            return "busy"
        try:
            os.stat(os.path.join(proc_root, raw_pid))
            return "busy"
        except FileNotFoundError:
            pass
        except OSError:
            return "busy"

        # Keep the socket path in place while removing the stale lock chain;
        # it prevents another X server from binding :N during recovery.
        os.unlink(lock)
        os.unlink(alias)
        os.unlink(backing)
        if sock_meta is not None:
            if snapshot(sockpath, "socket") != sock_meta:
                return "busy"
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            probe.settimeout(0.5)
            try:
                probe.connect(sockpath)
                return "busy"
            except ConnectionRefusedError:
                pass
            except OSError:
                return "busy"
            finally:
                probe.close()
            os.unlink(sockpath)
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return "busy"
    return "recovered"


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "attachable":
        identity = attachable(sys.argv[2], sys.argv[3], sys.argv[4])
        if identity is None:
            raise SystemExit(1)
        print(*identity)
        raise SystemExit(0)
    elif len(sys.argv) == 3 and sys.argv[1] == "ensure-directory":
        result = ensure_socket_directory(sys.argv[2])
    elif len(sys.argv) == 3:
        result = prepare(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == "recover":
        result = recover(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 5 and sys.argv[1] == "recover-proot":
        result = recover_proot_link2symlink(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(2)
    print(result)
    raise SystemExit(0 if result in ("available", "recovered", "created", "existing") else 1)
