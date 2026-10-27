"""Fetch the exact guest APT plan through Native TLS, with SHA-256 verification.
No repository substitution, guest package execution, or unsigned metadata resolver.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import ssl
import stat
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

import install_events


def _sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):digest.update(block)
    return digest.hexdigest()


def _safe_file(path, limit):
    info=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>limit:
        raise ValueError('unsafe APT index/cache file')
    return info


def metadata(root, prefix, packages):
    """Read already acquired guest APT indexes using the trusted Native decoder."""
    wanted=dict(packages);found={};indexes={}
    directory=root
    for part in ('var','lib','apt','lists'):
        directory=directory/part
        if directory.is_symlink() or not directory.is_dir():raise ValueError('guest APT index ancestor is unsafe')
    helper=Path(prefix)/'lib/apt/apt-helper'
    for path in sorted(directory.glob('*Packages*')):
        if path.suffix not in ('.lz4','.gz','.xz') and not path.name.endswith('_Packages'):continue
        _safe_file(path,64*1024*1024)
        before=_sha256(path);indexes[path.name]=before
        proc=subprocess.Popen([str(helper),'cat-file',str(path)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        fields={};deadline=time.monotonic()+30;seen=0
        try:
            for line in proc.stdout:
                seen+=len(line)
                if seen>512*1024*1024 or time.monotonic()>deadline:raise ValueError('APT index decoding exceeded its bound')
                if line.strip():
                    if ': ' in line and not line[0].isspace():
                        key,value=line.rstrip().split(': ',1)
                        if key in ('Package','Version','Architecture','Filename','SHA256','Size'):fields[key]=value
                else:
                    name=fields.get('Package');version=fields.get('Version')
                    key=name if name in wanted else name+':'+fields.get('Architecture','') if name else None
                    if key in wanted and version==wanted[key]:
                        if not re.fullmatch(r'[a-f0-9]{64}',fields.get('SHA256','')) or not fields.get('Size','').isdigit():
                            raise ValueError('guest APT metadata lacks SHA-256 or size')
                        record={k:fields[k] for k in ('Package','Version','Architecture','Filename','SHA256','Size')}
                        if key in found and found[key]!=record:raise ValueError('ambiguous guest APT archive metadata')
                        found[key]=record
                    fields={}
            if proc.wait(timeout=5):raise ValueError('Native APT index decoder failed')
        finally:
            proc.stdout.close()
            if proc.poll() is None:proc.kill();proc.wait()
        if _sha256(path)!=before:raise ValueError('guest APT index changed during preview')
    if set(found)!=set(wanted):raise ValueError('exact guest package archive metadata is incomplete')
    return found,indexes


def bind_uris(output, records):
    """APT provides authoritative cache filenames/URIs; indexes provide SHA-256."""
    by_file={}
    for name,record in records.items():
        key=(Path(record['Filename']).name,int(record['Size']))
        if key in by_file:raise ValueError('ambiguous guest archive filename')
        by_file[key]=(name,record)
    result=[];used=set()
    for line in output.splitlines():
        if not line.startswith("'"):continue
        values=shlex.split(line)
        if len(values)<3 or not values[2].isdigit() or not 0<int(values[2])<=512*1024*1024:raise ValueError('invalid or oversized APT archive URI record')
        url,filename,size=values[:3];parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('guest archive URI must be credential-free HTTPS')
        if not re.fullmatch(r'[A-Za-z0-9_+.%~:-]+\.deb',filename) or '/' in filename:
            raise ValueError('unsafe APT cache filename')
        key=(Path(urllib.parse.unquote(parsed.path)).name,int(size))
        if key not in by_file:raise ValueError('APT URI differs from reviewed index metadata')
        name,record=by_file[key]
        if name in used:raise ValueError('duplicate APT archive URI')
        if not urllib.parse.unquote(parsed.path).endswith('/'+record['Filename']):raise ValueError('APT archive path differs from its index')
        used.add(name)
        result.append(dict(package=name,version=record['Version'],url=url,filename=filename,size=int(size),sha256=record['SHA256']))
    # APT can omit archives already in the guest cache. Resolve those separately
    # only when the caller can prove their exact cache bytes (otherwise replan).
    if used!=set(records):raise ValueError('APT omitted package URIs; clear/review the selected guest cache explicitly before this transport plan')
    return sorted(result,key=lambda r:r['package'])


def _valid(path,record):
    _safe_file(path,512*1024*1024)
    return path.stat().st_size==record['size'] and _sha256(path)==record['sha256']


def fetch(root, state, archives, *, ca_file, log_path=None, opener=urllib.request.urlopen):
    """Stage all verified archives before guest dpkg is allowed to run."""
    cache=state/'artifacts'/'packages'
    for directory in (state/'artifacts',cache):
        if directory.is_symlink():raise ValueError('Native package cache directory is symlinked')
        directory.mkdir(mode=0o700,exist_ok=True)
    context=ssl.create_default_context(cafile=str(ca_file))
    for number,record in enumerate(archives,1):
        target=cache/(record['sha256']+'.deb')
        install_events.event(f'Get: {number}/{len(archives)} {record["package"]} {record["size"]} bytes',log_path)
        if target.exists() or target.is_symlink():
            if not _valid(target,record):raise ValueError('Native cached guest package hash failed; file preserved')
            install_events.event('Verified cached package: '+record['package'],log_path);continue
        last_error=None
        for attempt in range(1,4):
            fd,tmp=tempfile.mkstemp(prefix='.download-',dir=cache);tmp=Path(tmp)
            try:
                digest=hashlib.sha256();received=0;started=time.monotonic();tick=started
                request=urllib.request.Request(record['url'],headers={'User-Agent':'curl/8','Accept':'*/*'})
                with os.fdopen(fd,'wb') as stream,opener(request,context=context,timeout=20) as response:
                    while True:
                        if time.monotonic()-started>300:raise TimeoutError('package transfer exceeded 300 seconds')
                        block=response.read(128*1024)
                        if not block:break
                        received+=len(block)
                        if received>record['size']:raise ValueError('guest package exceeded its reviewed size')
                        digest.update(block);stream.write(block)
                        if time.monotonic()-tick>=1:
                            install_events.event(f'Get: {number}/{len(archives)} {record["package"]} {received}/{record["size"]} bytes',log_path);tick=time.monotonic()
                    stream.flush();os.fsync(stream.fileno())
                if received!=record['size'] or digest.hexdigest()!=record['sha256']:raise ValueError('guest archive SHA-256/size verification failed')
                os.replace(tmp,target);last_error=None;break
            except ValueError:raise # integrity failures never retry an alternative payload/source
            except (OSError,TimeoutError) as exc:
                last_error=exc;install_events.event(f'Warning: exact package download attempt {attempt}/3 failed ({type(exc).__name__}): {install_events.clean(str(exc))[:300]}',log_path)
            finally:
                if tmp.exists():tmp.unlink()
        if last_error:raise ValueError('Exact Native HTTPS download failed after 3 attempts: '+record['package']+'; '+install_events.clean(str(last_error))[:300]) from last_error
    destination=root/'var/cache/apt/archives'
    current=root
    for part in ('var','cache','apt','archives'):
        current=current/part
        if current.is_symlink():raise ValueError('guest APT cache ancestor is symlinked')
        current.mkdir(exist_ok=True)
    for record in archives:
        source=cache/(record['sha256']+'.deb');target=destination/record['filename']
        if not _valid(source,record):raise ValueError('Native cached package changed before staging')
        if target.exists() or target.is_symlink():
            if not _valid(target,record):raise ValueError('unverified existing guest cache archive preserved')
            continue
        fd,tmp=tempfile.mkstemp(prefix='.ternuxx-',dir=destination);os.close(fd);tmp=Path(tmp)
        try:
            shutil.copyfile(source,tmp)
            if not _valid(tmp,record):raise ValueError('staged guest package hash failed')
            os.replace(tmp,target)
        finally:
            if tmp.exists():tmp.unlink()
    install_events.event('All exact guest archives verified; guest installation will use --no-download.',log_path)
