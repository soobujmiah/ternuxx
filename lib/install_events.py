"""Live categorized APT events and a private redacted failure log."""
from __future__ import annotations
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time


def clean(line):
    line=re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|.)','',line)
    line=''.join(c for c in line if ord(c)>=32 or c=='\t')
    line=re.sub(r'(https?://)[^/\s@]+@',r'\1<redacted>@',line)
    return re.sub(r'([?&](?:token|key|password|secret)=)[^\s&]+',r'\1<redacted>',line,flags=re.I)


def event(line,log_path=None):
    line=clean(line)
    if not line:return
    category=('ERROR' if line.startswith(('E:','Err:','dpkg: error')) else
              'WARNING' if line.startswith(('W:','WARNING:','Warning:')) else
              'DOWNLOAD' if line.startswith(('Get:','Fetched ','Need to get ','Ign:')) else
              'UNPACK' if line.startswith(('Unpacking ','Preparing to unpack','Selecting previously')) else
              'CONFIGURE' if line.startswith(('Setting up ','Processing triggers')) else 'INFO')
    rendered=f'[{category}] {line}'
    print(rendered,file=sys.stderr,flush=True)
    if log_path is not None:
        fd=os.open(log_path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:raise ValueError('unsafe private event log')
            if info.st_size<16*1024*1024:os.write(fd,(rendered+'\n').encode())
        finally:os.close(fd)


class InstallTimeout(subprocess.TimeoutExpired):
    def __init__(self,argv,timeout,kind,captured):
        super().__init__(argv,timeout)
        self.timeout_kind=kind
        self.last_output=clean(captured[-4096:].decode(errors='replace'))


def run(argv,*,timeout,env,idle_timeout=180,log_path=None):
    started=time.monotonic();last_output=started
    proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    captured=bytearray();pending=bytearray();completed=False
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        while selector.get_map():
            now=time.monotonic()
            if now-started>timeout:raise InstallTimeout(argv,timeout,'overall',captured)
            if now-last_output>idle_timeout:raise InstallTimeout(argv,idle_timeout,'no-output',captured)
            for key,_ in selector.select(.1):
                block=os.read(key.fileobj.fileno(),65536)
                if not block:selector.unregister(key.fileobj);continue
                last_output=time.monotonic();captured.extend(block)
                if len(captured)>16*1024*1024:raise ValueError('APT output exceeded bounded capture limit')
                pending.extend(block)
                while b'\n' in pending or b'\r' in pending:
                    end=min(v for v in (pending.find(b'\n'),pending.find(b'\r')) if v>=0)
                    event(pending[:end].decode(errors='replace'),log_path);del pending[:end+1]
                if len(pending)>8192:event(pending.decode(errors='replace'),log_path);pending.clear()
        if pending:event(pending.decode(errors='replace'),log_path)
        code=proc.wait(timeout=max(.01,timeout-(time.monotonic()-started)));completed=True
        return subprocess.CompletedProcess(argv,code,captured.decode(errors='replace'),'')
    except InstallTimeout as exc:
        event(f'E: APT {exc.timeout_kind} timeout after {exc.timeout}s; verified caches retained; review a new exact plan before retry.',log_path)
        raise
    finally:
        selector.close();proc.stdout.close()
        if not completed:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
