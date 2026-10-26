"""Exact-plan ordinary account setup for an existing managed-profile rootfs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import proot_desktop_setup as desktop
import proot_fresh_setup as fresh
import proot_guest_retirement


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def plan(*, prefix, home, state_dir, alias, user, sudo_mode, allow_system_accounts=False):
    if not isinstance(user, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user) or user == 'root':
        raise ValueError('choose an ordinary guest username')
    if sudo_mode not in ('password', 'passwordless'):
        raise ValueError('choose password or passwordless sudo')
    root, identity = desktop._rootfs(prefix, alias)
    passwd = root / 'etc/passwd'
    digest = desktop._private_digest(passwd)
    entries = [line.split(':') for line in passwd.read_text().splitlines()]
    existing = [v for v in entries if len(v) == 7 and v[0] == user]
    if existing:
        if len(existing) != 1 or not existing[0][2].isdigit() or not 1000 <= int(existing[0][2]) < 60000 or existing[0][5] != '/home/' + user or existing[0][6].rsplit('/',1)[-1] in ('nologin','false'):
            raise ValueError('existing account is not an ordinary login account; preserved')
        action = 'select'
    else:
        action = 'create'
        policy = root / 'etc/sudoers.d' / ('ternuxx-guest-' + user)
        if policy.exists() or policy.is_symlink(): raise ValueError('existing sudo policy preserved')
        if (root/'home').is_symlink() or (root/'etc/sudoers.d').is_symlink(): raise ValueError('unsafe guest account directory')
        if (root / 'home' / user).exists() or (root / 'home' / user).is_symlink():
            raise ValueError('unowned existing home directory preserved')
    body = dict(schema_version=1, alias=alias, user=user, sudo_mode=sudo_mode,
                action=action, rootfs_identity=identity, passwd_sha256=digest)
    if allow_system_accounts:
        if any(len(v)!=7 for v in entries) or len({v[0] for v in entries})!=len(entries):
            raise ValueError('account database has malformed or duplicate records')
        body.update(schema_version=2, allow_added_system_accounts=True,
                    passwd_records={v[0]:hashlib.sha256(':'.join(v).encode()).hexdigest() for v in entries})
    return {**body, 'plan_id': _digest(body)}


def preview(**kwargs):
    value = plan(**kwargs)
    state = fresh._state_root(kwargs['home'], kwargs['state_dir'], create=True)
    proot_guest_retirement._assert_idle(state, desktop._rootfs(kwargs['prefix'], kwargs['alias'])[0])
    for path in state.glob('account-operation-*.json'):
        old=fresh._read_private(path)
        if old.get('alias')==kwargs['alias'] and old.get('state')=='applying': raise ValueError('unfinished account setup exists; inspect its retained journal before retry')
    fresh._private_write(state / 'previews' / ('account-' + value['plan_id'] + '.json'), value)
    return value


def apply(*, prefix, home, state_dir, plan_id, confirmed, password=None, runner=subprocess.run):
    if confirmed is not True or (not isinstance(plan_id,str) or not re.fullmatch(r'[a-f0-9]{64}', plan_id)):
        raise ValueError('account setup requires an exact confirmed preview')
    state = fresh._state_root(home, state_dir, create=False)
    fd = desktop._lock(state)
    try:
        saved = fresh._read_private(state / 'previews' / ('account-' + plan_id + '.json'))
        if saved.get('plan_id') != plan_id or _digest({k:v for k,v in saved.items() if k != 'plan_id'}) != plan_id:
            raise ValueError('account plan identity changed')
        current = plan(prefix=prefix, home=home, state_dir=state_dir, alias=saved['alias'], user=saved['user'], sudo_mode=saved['sudo_mode'],allow_system_accounts=saved.get('allow_added_system_accounts',False))
        if saved != current:
            permitted=False
            if saved.get('allow_added_system_accounts') is True:
                ignored={'plan_id','passwd_sha256','passwd_records'}
                same={k:v for k,v in saved.items() if k not in ignored}=={k:v for k,v in current.items() if k not in ignored}
                before=saved['passwd_records'];after=current['passwd_records']
                preserved=all(after.get(k)==v for k,v in before.items())
                root,_identity=desktop._rootfs(prefix,saved['alias'])
                additions=[v.split(':') for v in (root/'etc/passwd').read_text().splitlines() if v.split(':')[0] not in before]
                safe=all(len(v)==7 and v[2].isdigit() and 1<=int(v[2])<1000 and not v[5].startswith('/home/') and v[6].rsplit('/',1)[-1] in ('nologin','false') for v in additions)
                permitted=same and preserved and safe
            if not permitted:raise ValueError('guest account/rootfs changed; preview again')
        root, identity = desktop._rootfs(prefix, saved['alias'])
        proot_guest_retirement._assert_idle(state, root)
        user = saved['user']
        journal = state / ('account-operation-' + plan_id + '.json')
        fresh._private_write(journal, {'state':'applying','plan_id':plan_id,'alias':saved['alias'],'user':user})
        if saved['action'] == 'create':
            if saved['sudo_mode'] == 'password':
                if not isinstance(password,str): raise ValueError('new account password is required through a private descriptor')
                fresh._validate_guest_password(password)
            # Only a new account is configured. Existing accounts/passwords are never rewritten.
            script = '\n'.join(['set -eu', 'command -v useradd >/dev/null; command -v visudo >/dev/null',
                f'! getent passwd {user} >/dev/null', f'useradd --create-home --shell /bin/bash {user}',
                f'usermod -aG sudo {user}',
                f"printf '%s\\n' '{user} ALL=(ALL:ALL) " + ('NOPASSWD: ALL' if saved['sudo_mode']=='passwordless' else 'ALL') + "' > /etc/sudoers.d/ternuxx-guest-" + user,
                f'chmod 0440 /etc/sudoers.d/ternuxx-guest-{user}', f'visudo -cf /etc/sudoers.d/ternuxx-guest-{user}'])
            argv=[str(Path(prefix)/'bin/proot-distro'),'login','--isolated','--user','root',saved['alias'],'--']
            result=runner([*argv,'/bin/bash','-lc',script],check=False,timeout=120)
            if result.returncode: raise ValueError('account creation failed; inspect retained account journal before retry')
            if saved['sudo_mode']=='password':
                result=runner([*argv,'/usr/sbin/chpasswd'],input=user+':'+password+'\n',text=True,capture_output=True,check=False,timeout=120)
                if result.returncode: raise ValueError('new guest password setup failed; inspect account journal')
        if desktop._rootfs(prefix,saved['alias'])[1] != identity:
            raise ValueError('guest rootfs changed during account setup')
        checked=plan(prefix=prefix,home=home,state_dir=state_dir,alias=saved['alias'],user=user,sudo_mode=saved['sudo_mode'])
        if checked['action'] != 'select': raise ValueError('new account could not be verified')
        fresh._private_write(state / ('account-provider-'+saved['alias']+'.json'),
                            dict(schema_version=1,alias=saved['alias'],guest_user=user,rootfs_identity=identity,plan_id=plan_id))
        fresh._private_write(journal,{'state':'complete','plan_id':plan_id})
        return {'status':'account_ready','user':user,'alias':saved['alias']}
    finally:
        os.close(fd)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['preview','apply','users','resolve'])
    p.add_argument('--alias',default='debian');p.add_argument('--user');p.add_argument('--sudo-mode',default='password')
    p.add_argument('--allow-system-accounts',action='store_true',help='Preview permits only newly added non-login UID 1-999 package accounts; preserves all existing records')
    p.add_argument('--plan-id');p.add_argument('--yes',action='store_true');p.add_argument('--password-fd',type=int)
    a=p.parse_args(); kw=dict(prefix=os.environ['PREFIX'],home=os.environ['HOME'],state_dir=os.environ.get('TERNUXX_STATE_DIR',str(Path.home()/'.local/share/ternuxx')))
    try:
        if a.action=='resolve':
            import proot_diagnostics
            print(proot_diagnostics.resolve_proot_guest_user(distro=a.alias,prefix=kw['prefix']));return 0
        if a.action=='users':
            import proot_diagnostics
            result=proot_diagnostics.ordinary_guest_users(distro=a.alias,prefix=kw['prefix'])
        elif a.action=='preview': result=preview(**kw,alias=a.alias,user=a.user,sudo_mode=a.sudo_mode,allow_system_accounts=a.allow_system_accounts)
        else:
            password=None
            if a.password_fd is not None:
                if a.password_fd<3: raise ValueError('private credential descriptor required')
                with os.fdopen(os.dup(a.password_fd)) as stream:password=stream.read(1026).removesuffix('\n')
            result=apply(**kw,plan_id=a.plan_id,confirmed=a.yes,password=password)
        print(json.dumps(result));return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('Guest account setup: '+str(exc),file=__import__('sys').stderr);return 1

if __name__=='__main__':raise SystemExit(main())
