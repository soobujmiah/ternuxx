"""Account and pinned GPU installer fixtures; never enter an actual guest/display."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import proot_account_setup as accounts
import proot_diagnostics as guests
import proot_fresh_setup as private
import native_gpu_setup as gpu
import graphics_manager
import management_service
import proot_sessions


class RepairsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.prefix=self.home/'prefix';self.state=self.home/'state'
        self.root=self.prefix/'var/lib/proot-distro/containers/debian/rootfs'
        (self.root/'etc').mkdir(parents=True)
        (self.root/'etc/os-release').write_text('ID=debian\nVERSION_CODENAME=trixie\n')
        self.passwd=self.root/'etc/passwd';self.passwd.write_text('root:x:0:0:root:/root:/bin/bash\naid_u0:x:10490:10490::/:/sbin/nologin\n')
        self.kw=dict(prefix=str(self.prefix),home=str(self.home),state_dir=str(self.state))

    def test_real_gpu_manifest_contract_includes_pinned_release_and_original_artifact(self):
        profile,digest=gpu._profile(str(ROOT))
        self.assertEqual(profile['input_snapshot']['workflow_artifact_sha256'],gpu.SHA256)
        self.assertTrue(profile['distribution']['url'].startswith('https://github.com/soobujmiah/ternuxx/releases/download/'))
        self.assertEqual(len(digest),64)

    def test_missing_account_is_distinguished_from_ambiguity_without_root_fallback(self):
        with mock.patch.dict(os.environ,{'HOME':str(self.home),'TERNUXX_STATE_DIR':str(self.state)}),mock.patch.object(Path,'home',return_value=self.home):
            with self.assertRaisesRegex(guests.GuestProfileError,'no ordinary guest account'):
                guests.resolve_proot_guest_user(distro='debian',prefix=str(self.prefix))

    def test_create_account_uses_exact_plan_private_password_and_bound_default_receipt(self):
        with mock.patch.object(accounts.proot_guest_retirement,'_assert_idle'):
            plan=accounts.preview(**self.kw,alias='debian',user='sbj',sudo_mode='password')
            calls=[]
            def run(argv,**kw):
                calls.append((argv,kw))
                if argv[-2:][0]=='-lc':
                    with self.passwd.open('a') as f:f.write('sbj:x:1000:1000:Owner:/home/sbj:/bin/bash\n')
                return subprocess.CompletedProcess(argv,0)
            result=accounts.apply(**self.kw,plan_id=plan['plan_id'],confirmed=True,password='fixture-secret',runner=run)
            self.assertEqual(result['status'],'account_ready')
            self.assertTrue(all('fixture-secret' not in str(argv) for argv,kw in calls))
            self.assertEqual(calls[-1][1]['input'],'sbj:fixture-secret\n')
            for path in self.state.rglob('*.json'): self.assertNotIn('fixture-secret',path.read_text())
            # An additional ordinary account must not change the receipted default.
            with self.passwd.open('a') as f:f.write('other:x:1001:1001::/home/other:/bin/bash\n')
            with mock.patch.dict(os.environ,{'TERNUXX_STATE_DIR':str(self.state)}),mock.patch.object(Path,'home',return_value=self.home):
                self.assertEqual(guests.resolve_proot_guest_user(distro='debian',prefix=str(self.prefix)),'sbj')

    def test_account_plan_drift_and_existing_credentials_are_preserved(self):
        with self.passwd.open('a') as f:f.write('sbj:x:1000:1000::/home/sbj:/bin/bash\n')
        with mock.patch.object(accounts.proot_guest_retirement,'_assert_idle'):
            plan=accounts.preview(**self.kw,alias='debian',user='sbj',sudo_mode='password')
            with mock.patch.object(accounts.subprocess,'run') as run:
                result=accounts.apply(**self.kw,plan_id=plan['plan_id'],confirmed=True,runner=run)
                run.assert_not_called();self.assertEqual(result['user'],'sbj')
            plan=accounts.preview(**self.kw,alias='debian',user='new',sudo_mode='passwordless')
            self.passwd.write_text(self.passwd.read_text()+'# drift\n')
            with mock.patch.object(accounts.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'changed'):
                    accounts.apply(**self.kw,plan_id=plan['plan_id'],confirmed=True,runner=run)
                run.assert_not_called()

    def gpu_fixture(self):
        self.repo=self.home/'repo';(self.repo/'config/graphics').mkdir(parents=True)
        files={'lib/dri/libdril_dri.so':b'dri','lib/libgallium-26.3.0-devel.so':b'gallium','lib/libvulkan_freedreno.so':b'turnip','share/glvnd/egl_vendor.d/50_mesa.json':b'{}'}
        package_blobs={'mesa':b'mesa-fixture','mesa-vulkan-icd-freedreno':b'icd-fixture'}
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as z:
            for name,value in package_blobs.items():z.writestr(name+'.deb',value)
        blob=blob.getvalue()
        profile={'provider':'native-termux-bionic','schema_version':1,'distribution':{'url':'https://github.com/soobujmiah/ternuxx/releases/download/native-mesa-adreno825-fixture/mesa.zip','sha256':hashlib.sha256(blob).hexdigest()},'input_snapshot':{'workflow_artifact_sha256':gpu.SHA256,'packages':[{'name':name,'sha256':hashlib.sha256(value).hexdigest()} for name,value in package_blobs.items()]},'verified_files':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()}}
        (self.repo/'config/graphics/native-kgsl.json').write_text(json.dumps(profile))
        def extract(argv,**kwargs):
            self.assertEqual(argv[1],'--extract')
            root=Path(argv[-1])/'data/data/com.termux/files/usr'
            for name,value in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
            return subprocess.CompletedProcess(argv,0)
        return dict(**self.kw,repo_root=str(self.repo)),blob,extract

    def test_release_download_hashes_files_probe_and_verified_cache_reuse(self):
        kw,blob,extract=self.gpu_fixture()
        plan=gpu.preview(**kw)
        with mock.patch.object(private,'_download_archive',return_value=blob) as download,mock.patch.object(graphics_manager,'_run',return_value=(0,'deviceName = Adreno 825')):
            result=gpu.apply(**kw,plan_id=plan['plan_id'],confirmed=True,runner=extract)
            self.assertEqual(result['backend'],'kgsl-freedreno');download.assert_called_once()
        self.assertFalse((self.prefix/'lib').exists())  # no system library replacement
        plan=gpu.preview(**kw)
        with mock.patch.object(private,'_download_archive',side_effect=AssertionError('cache should not download')),mock.patch.object(graphics_manager,'_run',return_value=(0,'deviceName = Adreno 825')):
            self.assertFalse(gpu.apply(**kw,plan_id=plan['plan_id'],confirmed=True,runner=extract)['changed'])
        saved=(self.state/'native-graphics-prefix').read_bytes()
        with mock.patch.object(graphics_manager,'_run',return_value=(1,'CANNOT LINK EXECUTABLE')):
            with self.assertRaisesRegex(ValueError,'ABI'):gpu.apply(**kw,plan_id=plan['plan_id'],confirmed=True,runner=extract)
        self.assertEqual((self.state/'native-graphics-prefix').read_bytes(),saved)

    def test_corrupt_release_never_extracts_or_selects(self):
        kw,blob,extract=self.gpu_fixture();plan=gpu.preview(**kw)
        unused=mock.Mock()
        with mock.patch.object(private,'_download_archive',return_value=b'corrupt'):
            with self.assertRaisesRegex(ValueError,'checksum'):gpu.apply(**kw,plan_id=plan['plan_id'],confirmed=True,runner=unused)
            unused.assert_not_called()
        self.assertFalse((self.state/'native-graphics-prefix').exists())

    def test_confirmed_ubuntu_start_passes_alias_through_session_layers(self):
        with mock.patch.object(proot_sessions,'preview_start',return_value={'plan_id':'exact'}) as preview, mock.patch.object(proot_sessions,'login_interactive',return_value={'state':'stopped'}) as login:
            result=proot_sessions.start_profile(self.state,prefix=str(self.prefix),profile='debian-interactive',confirmed=True,plan_id='exact',alias='ubuntu')
            self.assertEqual(result['state'],'stopped')
            self.assertEqual(preview.call_args.kwargs['alias'],'ubuntu')
            self.assertEqual(login.call_args.kwargs['alias'],'ubuntu')
        for command in ('db','debian','ub','ubuntu'):
            output=subprocess.run(['bash',str(ROOT/'tx'),command,'--help'],capture_output=True,text=True,check=True).stdout
            self.assertIn('Login aliases:',output)
        unsupported=subprocess.run(['bash',str(ROOT/'tx'),'kali'],capture_output=True,text=True)
        self.assertEqual(unsupported.returncode,2)
        self.assertIn('no qualified Ternuxx provider',unsupported.stderr)

    def test_shared_ubuntu_preview_receives_its_alias_and_rejects_unknown_distro(self):
        request={'api_version':1,'request_id':'alias-preview','operation':'proot.start.preview','args':{'profile':'debian-interactive','alias':'ubuntu'}}
        with mock.patch.object(proot_sessions,'preview_start',return_value={'plan_id':'fixture'}) as preview:
            result=management_service.dispatch(request)
            self.assertTrue(result['ok'],result);self.assertEqual(preview.call_args.kwargs['alias'],'ubuntu')
        request['args']['alias']='kali'
        self.assertFalse(management_service.dispatch(request)['ok'])
