"""Private combined workstation plan and resource report; no package mutation."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys
import textwrap


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load_parts(root):
    result={}
    for path in sorted(root.glob('*.part.json')):
        st=path.lstat()
        if path.is_symlink() or st.st_uid!=os.getuid() or st.st_mode & 0o077 or st.st_size>16*1024*1024:
            raise ValueError('unsafe master-plan component')
        data=json.loads(path.read_text())
        if not isinstance(data,dict):raise ValueError('plan component is not an object')
        if path.name=='entrypoint.part.json':
            details=data.get('data',{})
            if data.get('ok') is not True or type(details.get('changed')) is not bool:
                raise ValueError('CLI entrypoint preview is incomplete')
            plan_id=details.get('plan_id')
        else:plan_id=data.get('plan_id')
        if path.name!='choices.part.json' and not (path.name=='native.part.json' and data.get('install')=='already_installed'):
            if not isinstance(plan_id,str) or not re.fullmatch(r'[a-f0-9]{64}',plan_id):raise ValueError('exact component plan ID is missing')
        result[path.name]=data
    if 'native.part.json' not in result: raise ValueError('Native plan is missing')
    return result


def build(root):
    parts=load_parts(root);lines=['Combined workstation plan','No workstation packages/guests have been applied by this planning phase.']
    download=0;disk=0;unknown=[]
    for name,data in parts.items():
        lines.append('')
        lines.append(name.removesuffix('.part.json'))
        lines.append('Exact subplan: '+str(data.get('plan_id',data.get('data',{}).get('plan_id','selection/no-op'))))
        if name=='native.part.json':
            sizes=data.get('resource_estimates',{})
            if data.get('install')=='already_installed': sizes={'complete':True,'download_bytes':0,'installed_kib':0}
            if sizes.get('complete'):
                d=sizes.get('download_bytes',0);s=sizes.get('installed_kib',0)*1024
                download+=d;disk+=s
                lines.append(f'Native download: {d/1048576:.1f} MiB; installed payload: {s/1048576:.1f} MiB (conservative, includes upgraded payload).')
            else: unknown.append('Native package size metadata')
            lines.append('Native requested packages: '+', '.join(data.get('packages',[])))
            lines.append('Native exact transaction: '+', '.join(data.get('transaction',[])))
        elif name.startswith('guest-'):
            op=data.get('operation',{});tx=data.get('transaction',{})
            lines.append('Desktops: '+', '.join(op.get('desktop_environments',[])))
            lines.append('Apps: '+', '.join(op.get('apps',op.get('package_groups',[]))))
            lines.append('Account: '+str(op.get('guest_user','existing account plan listed separately')))
            if 'transaction_summary' in op:
                for key,label in (('download','download'),('disk','additional disk')):
                    v=tx.get(key)
                    if v is None:
                        # No-op transactions require no package payload.
                        if not op.get('transaction_packages'): amount=0
                        else: unknown.append(name+': '+label);continue
                    else: amount=v['value']*{'kB':1000,'MB':1000000,'GB':1000000000}[v['unit']]
                    if key=='download':download+=amount
                    else:disk+=amount
                    lines.append(f'Guest {label}: {amount/1048576:.1f} MiB')
                lines.append('Guest package changes: '+str(len(op.get('transaction_packages',[]))))
                if op.get('download_transport'):
                    lines.append('Download transport: '+op['download_transport'])
                    staging=sum(v['size'] for v in op.get('native_fetch',{}).get('archives',[]))
                    disk+=staging
                    lines.append(f'Additional verified-cache staging reserve: {staging/1048576:.1f} MiB (Native cache plus guest cache at peak).')
                lines.append('Guest exact transaction: '+', '.join(p+'='+v for p,v in op.get('transaction_packages',[])))
                if op.get('graphics_runtime'):unknown.append(name+': optional graphics archive/unpacked size')
            else:
                unknown.append(name+': fresh rootfs unpacked size and guest APT dependency sizes (not resolved until rootfs exists)')
                archive=op.get('rootfs_archive_bytes')
                if isinstance(archive,int):
                    download+=archive;lines.append(f'Pinned compressed rootfs layer: {archive/1048576:.1f} MiB (guest APT additional)')
                lines.append('Pinned rootfs image: '+str(op.get('image','unknown')))
                lines.append('Guest requested packages: '+', '.join(op.get('packages',[])))
        elif name=='choices.part.json':
            lines.extend(f'{k}: {v}' for k,v in data.items())
        elif name.startswith('account-'):
            lines.append('Account: '+data['user']+'; action: '+data['action']+'; sudo: '+data['sudo_mode'])
            if data.get('allow_added_system_accounts'):lines.append('Package-added non-login UID 1-999 accounts permitted before this step; existing account records and selected account identity must be unchanged.')
        elif name=='gpu.part.json':
            unknown.append('Native GPU download/unpacked size; pinned archive hashes are verified at apply')
    unknown.append('GTK compilation temporary space and optional guest graphics payloads')
    free=shutil.disk_usage(os.environ['PREFIX']).free
    peak=download+disk
    lines.extend(['',f'Known download subtotal: {download/1048576:.1f} MiB',f'Known additional storage subtotal (payload + extra verified cache): {disk/1048576:.1f} MiB',f'Known download + installed peak estimate: {peak/1048576:.1f} MiB',f'Free space: {free/1073741824:.2f} GiB','Estimates are metadata-based; caches, filesystem allocation and build scratch can vary.'])
    if peak>free:raise ValueError('Known required space exceeds available storage; no apply is permitted')
    lines.append('Unresolved sizes: '+'; '.join(unknown))
    lines.append('Unresolved sizes are included in the final installation approval.')
    report='\n'.join(piece for line in lines for piece in (textwrap.wrap(line,70) or ['']))
    body={'report_sha256':hashlib.sha256(report.encode()).hexdigest(),'schema_version':1,'parts':parts,'download_bytes_known':download,'disk_bytes_known':disk,'unknown_estimates':unknown}
    record={**body,'plan_id':digest(body)}
    (root/'master.json').write_text(json.dumps(record,sort_keys=True));os.chmod(root/'master.json',0o600)
    (root/'report.txt').write_text(report);os.chmod(root/'report.txt',0o600)
    return record['plan_id']


def summary(root, plan_id):
    verify(root, plan_id)
    record=json.loads((root/'master.json').read_text())
    parts=record['parts']; choices=parts.get('choices.part.json',{})
    components=list(dict.fromkeys(choices.get('components','').split(',')))
    print('Native: '+', '.join(filter(None,components)))
    print('Graphics: CPU fallback + supported GPU; Native '+choices.get('native_backend','system'))
    for name,data in parts.items():
        if not name.startswith('guest-'):continue
        distro=name.removeprefix('guest-').removesuffix('.part.json');op=data.get('operation',{})
        account=parts.get('account-'+distro+'.part.json',{}).get('user',op.get('guest_user','existing user'))
        print(distro+': '+account+' | '+', '.join(op.get('desktop_environments',[]))+' | '+', '.join(op.get('apps',op.get('package_groups',[]))))
    print(f"Download >= {record['download_bytes_known']/1048576:.1f} MiB | extra disk >= {record['disk_bytes_known']/1048576:.1f} MiB")
    print(f"Known peak >= {(record['download_bytes_known']+record['disk_bytes_known'])/1048576:.1f} MiB | free {shutil.disk_usage(os.environ['PREFIX']).free/1073741824:.1f} GiB")
    if record['unknown_estimates']:
        print('Unresolved size estimates (reasons below):')
        for item in record['unknown_estimates']:
            print('  - '+item)
    print('One approval starts all steps; no further questions. Technical details saved privately.')


def verify(root,plan_id):
    record=json.loads((root/'master.json').read_text());body={k:v for k,v in record.items() if k!='plan_id'}
    if digest(body)!=plan_id or record.get('plan_id')!=plan_id or load_parts(root)!=record['parts'] or hashlib.sha256((root/'report.txt').read_bytes()).hexdigest()!=record['report_sha256']:
        raise ValueError('Combined plan changed; rebuild and review before any further action')


if __name__=='__main__':
    try:
        action,folder,*args=sys.argv[1:];root=Path(folder)
        if action=='build':print(build(root))
        elif action=='summary':summary(root,args[0])
        elif action in ('verify','capacity'):
            verify(root,args[0])
            if action=='capacity':
                record=json.loads((root/'master.json').read_text())
                if shutil.disk_usage(os.environ['PREFIX']).free < record['download_bytes_known']+record['disk_bytes_known']:
                    raise ValueError('Free storage fell below the reviewed known peak; replan')
        else:raise ValueError('unsupported action')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('Combined plan: '+str(exc),file=sys.stderr);sys.exit(2)
