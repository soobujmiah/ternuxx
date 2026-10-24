"""Native production assembly for the optional interactive PRoot broker."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
import threading

import proot_sessions
import terminal_broker


def build_service(*, prefix: str | None = None, home: str | None = None,
                  guest_alias: str = "debian"):
    """Build the fixed-profile runtime and private local socket server."""
    prefix = prefix or os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    home = home or str(Path.home())
    if not os.environ.get("TERMUX_VERSION") or prefix != "/data/data/com.termux/files/usr":
        raise terminal_broker.BrokerError("terminal broker requires Native Termux")
    state_dir = Path(os.environ.get("TERNUXX_STATE_DIR") or
                     (Path(home) / ".local/share/ternuxx")).absolute()
    guest_alias = proot_sessions._guest_alias(guest_alias)
    registry = terminal_broker.TerminalAttachmentRegistry()
    runtime: terminal_broker.TerminalPTYRuntime

    def record_exit(record: dict[str, object], state: str, code: int | None) -> None:
        session_id = record.get("session_id")
        if not isinstance(session_id, str):
            return
        def update(saved: dict[str, object]) -> None:
            proot_sessions._append_transition(saved, state, "terminal-broker-exit")
            saved["last_verified_at"] = proot_sessions._timestamp()
            if code is not None:
                saved["last_exit_code"] = code
        proot_sessions._update_session(state_dir, session_id, update)

    runtime = terminal_broker.TerminalPTYRuntime(
        registry,
        preview_start=lambda: proot_sessions.preview_start(
            "debian-interactive", prefix=prefix, alias=guest_alias),
        spawn_login=lambda plan_id: proot_sessions.spawn_login_interactive(
            state_dir, prefix=prefix, confirmed=True, plan_id=plan_id, alias=guest_alias),
        verify_record=lambda record: proot_sessions._verified(record),
        session_members=proot_sessions._members,
        record_exit=record_exit,
    )

    def authorize(_request: dict[str, object], peer_uid: int) -> str | None:
        # The Unix endpoint is restricted to the owning Android application UID.
        # Web session scope and CSRF are checked by the HTTP adapter before it
        # delegates a typed operation; browser code never opens this socket.
        return "native-termux" if peer_uid == os.getuid() else None

    def close_apply(session_id: str, plan_id: str) -> dict[str, object]:
        result = proot_sessions.stop_session(
            state_dir, session_id, confirmed=True, plan_id=plan_id)
        if result.get("state") == "stopped":
            try:
                runtime.release_after_stop(session_id)
            except terminal_broker.BrokerError:
                if runtime.status() != "not_connected":
                    raise
        return result

    dispatcher = terminal_broker.TerminalBrokerDispatcher(
        registry,
        authorize=authorize,
        verify_session=runtime.is_verified,
        write_input=runtime.write_input,
        resize_pty=runtime.resize,
        close_preview=lambda session_id: proot_sessions.preview_stop(state_dir, session_id),
        close_apply=close_apply,
        start_preview=lambda: proot_sessions.preview_start(
            "debian-interactive", prefix=prefix, alias=guest_alias),
        start_apply=lambda plan_id, principal: runtime.start(
            plan_id, principal, confirmed=True),
        pty_relay_status=runtime.status,
    )
    server = terminal_broker.UnixBrokerServer(state_dir, dispatcher)
    return server, runtime


def serve(*, guest_alias: str = "debian") -> int:
    server, runtime = build_service(guest_alias=guest_alias)
    stopping = threading.Event()
    def request_stop(_signum, _frame):
        stopping.set()
    previous = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, request_stop)
    try:
        server.open()
        while not stopping.is_set():
            try:
                server.serve_one()
            except (OSError, terminal_broker.BrokerError):
                if stopping.is_set():
                    break
        return 0
    finally:
        server.close()
        runtime.close()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the optional Ternuxx interactive terminal broker")
    parser.add_argument("action", choices=("serve",))
    parser.add_argument("--guest-alias", default="debian",
                        help="Exact guest: debian (default) or ternuxx-replay-NAME; use a separate private state directory for qualification")
    args = parser.parse_args(argv)
    try:
        return serve(guest_alias=args.guest_alias)
    except (OSError, proot_sessions.SessionError, terminal_broker.BrokerError) as exc:
        print(f"Ternuxx terminal broker: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
