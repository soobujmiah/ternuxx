"""Interactive CLI client for the shared local terminal broker."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import select
import shutil
import signal
import sys
import termios
import time
import tty

import terminal_broker
import fixed_service_deployment as terminal_service_deployment


def _client() -> terminal_broker.UnixBrokerClient:
    state = os.environ.get("TERNUXX_STATE_DIR") or str(Path.home()/".local/share/ternuxx")
    return terminal_broker.UnixBrokerClient(state)


def _ok(response: dict[str, object]) -> dict[str, object]:
    if response.get("ok") is not True:
        error=response.get("error")
        code=error.get("code") if isinstance(error,dict) else "operation_failed"
        raise terminal_broker.BrokerError("terminal broker operation failed: "+str(code))
    return response


def _dimensions() -> tuple[int,int]:
    size=shutil.get_terminal_size((80,24))
    return max(1,min(size.columns,500)),max(1,min(size.lines,300))


def attach(session_id: str, *, client: terminal_broker.UnixBrokerClient | None = None,
           principal: str = "native-termux", lease: dict[str,object] | None = None) -> int:
    client = client or _client()
    try:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise terminal_broker.BrokerError("interactive attach requires a local terminal")
        if lease is None:
            lease = _ok(client.request("terminal.attach", session_id=session_id))
        return _relay_attachment(client, lease)
    finally:
        # A start response may already hold the writer before the local TTY
        # disappears. Release every acquired lease, including explicit detach
        # and setup failures, without closing the guest session.
        if lease is not None:
            try:
                client.request("terminal.detach", session_id=lease["session_id"],
                               generation=lease["generation"],
                               attachment_id=lease["attachment_id"])
            except (OSError, terminal_broker.BrokerError):
                pass


def _relay_attachment(client, lease) -> int:
    session_id = lease["session_id"]
    generation = lease["generation"]
    attachment_id = lease["attachment_id"]
    columns,rows=_dimensions()
    _ok(client.request("terminal.resize",session_id=session_id,generation=generation,
                   attachment_id=attachment_id,args={"columns":columns,"rows":rows}))
    old=termios.tcgetattr(sys.stdin.fileno())
    previous_handlers={}
    def interrupted(signum, _frame):
        raise InterruptedError(f"terminal client interrupted by signal {signum}")
    cursor=0
    last_size=(columns,rows)
    try:
        for sig in (signal.SIGHUP,signal.SIGTERM):
            previous_handlers[sig]=signal.signal(sig,interrupted)
        tty.setraw(sys.stdin.fileno())
        while True:
            readable,_,_=select.select([sys.stdin.fileno()],[],[],0.04)
            if readable:
                data=os.read(sys.stdin.fileno(),2048)
                if not data: break
                if b"\x1d" in data:
                    before,_,after=data.partition(b"\x1d")
                    if before:
                        client.request("terminal.input",session_id=session_id,generation=generation,
                            attachment_id=attachment_id,args={"data_base64":base64.b64encode(before).decode("ascii")})
                    break
                client.request("terminal.input",session_id=session_id,generation=generation,
                    attachment_id=attachment_id,args={"data_base64":base64.b64encode(data).decode("ascii")})
            size=_dimensions()
            if size!=last_size:
                columns,rows=size; last_size=size
                client.request("terminal.resize",session_id=session_id,generation=generation,
                    attachment_id=attachment_id,args={"columns":columns,"rows":rows})
            response=_ok(client.request("terminal.output",session_id=session_id,generation=generation,
                    attachment_id=attachment_id,args={"after_sequence":cursor}))
            if response.get("truncated"):
                sys.stdout.write("\r\n[terminal output skipped while disconnected]\r\n")
            chunks=response.get("chunks",[])
            if isinstance(chunks,list):
                for chunk in chunks:
                    if isinstance(chunk,dict) and isinstance(chunk.get("data_base64"),str):
                        payload=base64.b64decode(chunk["data_base64"],validate=True)
                        sys.stdout.buffer.write(payload); sys.stdout.buffer.flush()
                        cursor=int(chunk["sequence"])
            if response.get("next_sequence",cursor)>cursor and not chunks:
                cursor=int(response["next_sequence"])
            if response.get("session_closed") is True and cursor >= int(response.get("next_sequence", cursor)):
                sys.stdout.write("\r\n[Debian session ended]\r\n")
                sys.stdout.flush()
                return 0
        return 0
    finally:
        try:
            termios.tcsetattr(sys.stdin.fileno(),termios.TCSADRAIN,old)
        finally:
            for sig,handler in previous_handlers.items():
                signal.signal(sig,handler)


def run(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(prog="tx terminal",description="Attach to the fixed Debian interactive terminal")
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("status",help="show the optional broker state")
    sub.add_parser("serve",help="run the Native Termux broker in the foreground")
    sub.add_parser("start",help="preview and start a fixed Debian interactive login")
    attach_parser=sub.add_parser("attach",help="attach to one verified Ternuxx session")
    attach_parser.add_argument("session_id")
    close_parser=sub.add_parser("close",help="preview and stop one verified Ternuxx session")
    close_parser.add_argument("session_id")
    service_parser=sub.add_parser("service",help="preview or install the persistent Runit broker service")
    service_sub=service_parser.add_subparsers(dest="service_action",required=True)
    service_sub.add_parser("status",help="show the installed broker service state")
    service_sub.add_parser("preview-install",help="preview the exact fixed Runit service registration")
    install_parser=service_sub.add_parser("install",help="apply a fresh service registration preview")
    install_parser.add_argument("--yes",action="store_true")
    install_parser.add_argument("--plan-id")
    socket_parser=service_sub.add_parser("socket",help="inspect or recover one stale broker socket")
    socket_sub=socket_parser.add_subparsers(dest="socket_action",required=True)
    socket_sub.add_parser("preview",help="inspect the exact socket and preview stale-socket recovery")
    recover_parser=socket_sub.add_parser("recover",help="remove one unchanged stale socket after explicit review")
    recover_parser.add_argument("--yes",action="store_true")
    recover_parser.add_argument("--plan-id")
    args=parser.parse_args(argv)
    try:
        if args.action=="serve":
            import terminal_broker_service
            return terminal_broker_service.serve()
        if args.action=="service":
            prefix=os.environ.get("PREFIX","/data/data/com.termux/files/usr")
            if args.service_action=="status":
                print(json.dumps(terminal_service_deployment.status(prefix=prefix, service_id=terminal_service_deployment.TERMINAL_BROKER_SERVICE_ID),indent=2));return 0
            if args.service_action=="preview-install":
                print(json.dumps(terminal_service_deployment.preview_install(prefix=prefix, service_id=terminal_service_deployment.TERMINAL_BROKER_SERVICE_ID),indent=2));return 0
            if args.service_action=="install":
                if not args.yes or not args.plan_id:
                    print("Preview first, then apply with --yes --plan-id PLAN_ID.",file=sys.stderr);return 1
                result=terminal_service_deployment.install(prefix=prefix,service_id=terminal_service_deployment.TERMINAL_BROKER_SERVICE_ID,confirmed=True,plan_id=args.plan_id)
                print(json.dumps(result,indent=2));return 0
            if args.service_action=="socket":
                state=os.environ.get("TERNUXX_STATE_DIR") or str(Path.home()/".local/share/ternuxx")
                if args.socket_action=="preview":
                    print(json.dumps(terminal_broker.preview_stale_socket_recovery(state),indent=2));return 0
                if not args.yes or not args.plan_id:
                    print("Preview first, then apply with --yes --plan-id PLAN_ID.",file=sys.stderr);return 1
                result=terminal_broker.recover_stale_socket(
                    state,confirmed=True,plan_id=args.plan_id)
                print(json.dumps(result,indent=2));return 0
        client=_client()
        if args.action=="status":
            print(json.dumps(_ok(client.request("broker.status")),indent=2)); return 0
        if args.action=="start":
            if not sys.stdin.isatty(): raise terminal_broker.BrokerError("starting an interactive guest requires a local terminal")
            preview=_ok(client.request("terminal.start.preview"))["plan"]
            print(json.dumps(preview,indent=2))
            if input("Start this fixed Debian login? [y/N] ").strip().lower()!="y": return 1
            result=_ok(client.request("terminal.start",args={"confirmed":True,"plan_id":preview["plan_id"]}))
            return attach(result["result"]["session_id"],client=client,lease=result["result"])
        if args.action=="attach":
            return attach(args.session_id,client=client)
        if args.action=="close":
            lease=_ok(client.request("terminal.attach",session_id=args.session_id))
            generation=lease["generation"]; attachment=lease["attachment_id"]
            try:
                preview=_ok(client.request("terminal.close.preview",session_id=args.session_id,
                    generation=generation,attachment_id=attachment))["plan"]
                print(json.dumps(preview,indent=2))
                if input("Stop this exact verified session? [y/N] ").strip().lower()!="y": return 1
                _ok(client.request("terminal.close",session_id=args.session_id,generation=generation,
                    attachment_id=attachment,args={"confirmed":True,"plan_id":preview["plan_id"]}))
                return 0
            finally:
                try: client.request("terminal.detach",session_id=args.session_id,generation=generation,attachment_id=attachment)
                except terminal_broker.BrokerError: pass
        return 2
    except (OSError,ValueError,InterruptedError,terminal_broker.BrokerError,
            terminal_service_deployment.ServiceInstallError) as exc:
        print(f"tx terminal: {exc}",file=sys.stderr); return 1


if __name__=="__main__":
    raise SystemExit(run())
