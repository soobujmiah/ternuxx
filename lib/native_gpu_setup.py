"""Pinned experimental Native Mesa acquisition; never installs system packages."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
import urllib.request

import graphics_manager
import proot_fresh_setup as private

SHA256='8493482210f9cc625f4fadb95e53cb417650c31f6e2b5a0d8725a2ef3c82ff5e'


def _profile(repo_root):
    p=Path(repo_root)/'config/graphics/native-kgsl.json'
    raw=p.read_bytes(); data=json.loads(raw)
    if data.get('provider')!='native-termux-bionic' or data.get('input_snapshot',{}).get('workflow_artifact_sha256')!=SHA256:
        raise ValueError('pinned Native GPU profile changed')
    distribution=data.get('distribution', {})
    if not distribution.get('url','').startswith('https://github.com/soobujmiah/ternuxx/releases/download/native-mesa-adreno825-') or not re.fullmatch(r'[a-f0-9]{64}',distribution.get('sha256','')): raise ValueError('pinned release source is unavailable')
    return data,hashlib.sha256(raw).hexdigest()


def _verify(target, profile):
    root=target/'extracted/data/data/com.termux/files/usr'
    if target.is_symlink() or root.is_symlink(): raise ValueError('GPU provider path is symlinked')
    for name,digest in profile['verified_files'].items():
        p=root/name
        current=p
        while current!=target:
            if current.is_symlink(): raise ValueError('GPU payload contains a symlink in a verified path')
            current=current.parent
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            raise ValueError('GPU payload checksum verification failed')
    return root


def _selection(state_dir):
    result={}
    for name in ('native-graphics-prefix','native-graphics-backend'):
        path=Path(state_dir)/name
        if not path.exists() and not path.is_symlink():result[name]=None;continue
        if path.is_symlink() or not path.is_file() or path.stat().st_uid!=os.getuid() or path.stat().st_size>4096:raise ValueError('saved GPU selection is unsafe')
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def preview(*, repo_root, home, state_dir, prefix):
    profile,digest=_profile(repo_root)
    # Derive provider root explicitly; the extraction prefix is nested below it.
    target=Path(state_dir)/'graphics/providers/native-mesa-0219ff84'
    private._state_root(home,state_dir,create=True)
    for parent in (Path(state_dir)/'graphics',Path(state_dir)/'graphics/providers'):
        if parent.is_symlink(): raise ValueError('GPU provider ancestor is symlinked')
    exists=target.exists() or target.is_symlink()
    if exists: _verify(target,profile)
    body=dict(schema_version=1,home=home,state_dir=state_dir,prefix=prefix,manifest_sha256=digest,
              archive_url=profile['distribution']['url'],archive_sha256=profile['distribution']['sha256'],cached=exists,selection=_selection(state_dir))
    plan_id=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    private._state_root(home,state_dir,create=True)
    return {**body,'plan_id':plan_id}


def apply(*, repo_root, home, state_dir, prefix, plan_id, confirmed, runner=subprocess.run):
    if confirmed is not True: raise ValueError('Native GPU setup needs explicit confirmation')
    plan=preview(repo_root=repo_root,home=home,state_dir=state_dir,prefix=prefix)
    if plan_id!=plan['plan_id']: raise ValueError('GPU preview changed; review again')
    profile,_digest=_profile(repo_root)
    parent=Path(state_dir)/'graphics/providers'
    for directory in (parent.parent,parent):
        if directory.is_symlink(): raise ValueError('GPU provider directory is unsafe')
        directory.mkdir(mode=0o700,exist_ok=True)
        info=directory.stat()
        if info.st_uid!=os.getuid() or info.st_mode&0o022: raise ValueError('unsafe GPU provider owner/mode')
    lock=os.open(parent/'.install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        target=parent/'native-mesa-0219ff84'
        if not plan['cached']:
            request=urllib.request.Request(plan['archive_url'], headers={'User-Agent':'Ternuxx-pinned-gpu/1'})
            blob=private._download_archive(request)
            if not isinstance(blob,bytes) or len(blob)>64*1024*1024 or hashlib.sha256(blob).hexdigest()!=plan['archive_sha256']:
                raise ValueError('release checksum mismatch; no alternative source was used')
            packages={p['sha256']:p['name'] for p in profile['input_snapshot']['packages']}
            with tempfile.TemporaryDirectory(prefix='.mesa-stage-',dir=parent) as temporary:
                stage=Path(temporary)/'provider'; stage.mkdir(mode=0o700)
                extracted=stage/'extracted'; extracted.mkdir()
                found=set()
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    for member in archive.infolist():
                        if not member.filename.endswith('.deb'): continue
                        if member.file_size>64*1024*1024: raise ValueError('oversized GPU package')
                        payload=archive.read(member)
                        digest=hashlib.sha256(payload).hexdigest()
                        if digest not in packages: raise ValueError('unrecognized package in pinned artifact')
                        name=packages[digest]
                        if name not in ('mesa','mesa-vulkan-icd-freedreno'): continue
                        if name in found: raise ValueError('duplicate GPU package')
                        found.add(name); package=Path(temporary)/(name+'.deb');package.write_bytes(payload)
                        code=runner([str(Path(prefix)/'bin/dpkg-deb'),'--extract',str(package),str(extracted)],capture_output=True,check=False,timeout=60)
                        if code.returncode: raise ValueError('GPU package private extraction failed')
                if found!={'mesa','mesa-vulkan-icd-freedreno'}: raise ValueError('pinned GPU artifact is incomplete')
                root=_verify(stage,profile)
                probe_icd=stage/'probe.json';probe_icd.write_text(json.dumps({'file_format_version':'1.0.0','ICD':{'library_path':str(root/'lib/libvulkan_freedreno.so'),'api_version':'1.3.0'}}))
                env=dict(os.environ, PREFIX=prefix,LD_LIBRARY_PATH=str(root/'lib')+':'+prefix+'/lib',VK_ICD_FILENAMES=str(probe_icd))
                for key in ('VK_DRIVER_FILES','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE'):env.pop(key,None)
                code,output=graphics_manager._run([str(Path(prefix)/'bin/vulkaninfo'),'--summary'],env,20)
                if code or not re.search(r'deviceName\s*=.*(?:Adreno|FD6830)',output,re.I):
                    raise ValueError('pinned Mesa did not enumerate a supported GPU; no backend was selected')
                probe_icd.unlink()
                final_root=target/'extracted/data/data/com.termux/files/usr'
                (stage/'freedreno-isolated.json').write_text(json.dumps({'file_format_version':'1.0.0','ICD':{'library_path':str(final_root/'lib/libvulkan_freedreno.so'),'api_version':'1.3.0'}}))
                os.chmod(stage/'freedreno-isolated.json',0o600)
                private._private_write(stage/'acquisition.json',plan)
                if target.exists() or target.is_symlink(): raise ValueError('GPU provider appeared during staging; preserved')
                os.rename(stage,target)
        root=_verify(target,profile)
        if plan['cached']:
            icd=target/'freedreno-isolated.json'
            if icd.is_symlink() or not icd.is_file() or json.loads(icd.read_text()).get('ICD',{}).get('library_path')!=str(root/'lib/libvulkan_freedreno.so'): raise ValueError('cached ICD identity changed')
            env=dict(os.environ,PREFIX=prefix,LD_LIBRARY_PATH=str(root/'lib')+':'+prefix+'/lib',VK_ICD_FILENAMES=str(icd))
            for key in ('VK_DRIVER_FILES','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE'):env.pop(key,None)
            code,output=graphics_manager._run([str(Path(prefix)/'bin/vulkaninfo'),'--summary'],env,20)
            if code or not re.search(r'deviceName\s*=.*(?:Adreno|FD6830)',output,re.I):raise ValueError('cached Mesa runtime is incompatible with this device/library ABI; backend preserved')
        if _selection(state_dir)!=plan['selection']:raise ValueError('GPU selection changed during setup; review a new plan')
        return graphics_manager.configure_native('kgsl-freedreno',home=home,state_dir=state_dir,repo_root=repo_root,prefix=prefix)
    finally:
        os.close(lock)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['preview','apply']);p.add_argument('--plan-id');p.add_argument('--yes',action='store_true');a=p.parse_args()
    kw=dict(repo_root=str(Path(__file__).resolve().parents[1]),home=os.environ['HOME'],state_dir=os.environ.get('TERNUXX_STATE_DIR',str(Path.home()/'.local/share/ternuxx')),prefix=os.environ['PREFIX'])
    try:
        value=preview(**kw) if a.action=='preview' else apply(**kw,plan_id=a.plan_id,confirmed=a.yes)
        print(json.dumps(value));return 0
    except (ValueError,OSError,subprocess.SubprocessError,zipfile.BadZipFile) as exc:
        print('Native GPU setup: '+str(exc),file=__import__('sys').stderr);return 1

if __name__=='__main__':raise SystemExit(main())
