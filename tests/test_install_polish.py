"""Installer regressions using isolated HOME/prefix fixtures; no host changes."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import proot_fresh_setup
import installer_launch
import proot_setup
import management_service
import management_authorization
import management_sessions


class PolishTests(unittest.TestCase):
    def shell(self, script, home):
        return subprocess.run(['bash', '-c', f'source "{ROOT}/lib/phases.sh"\nsource "{ROOT}/lib/install_wizard.sh"\n' + script],
            env={**os.environ, 'HOME': str(home), 'TERNUXX_STATE_DIR': str(home / 'state'),
                 'TERNUXX_JSON': '0', 'TERNUXX_QUIET': '0'}, capture_output=True, text=True, timeout=12)

    def test_native_catalog_resolves_new_apps_and_correct_official_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.shell('''_nt_select_install_profile custom gimp,krita,inkscape,ncdu,ai-codex,ai-hermes,nodejs,music || exit $?
printf 'PACKAGES=%s\\n' "${_NT_BASE_PACKAGES[*]}"
for package in mpv gnuplot octave nodejs-lts gimp krita audacious audacious-plugins; do
 printf '%s=%s\\n' "$package" "$(_nt_native_app_repository "$package")"
done
_nt_native_app_lookup 'not-an-app; touch unsafe' && exit 90
exit 0
''', Path(tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            packages = result.stdout.splitlines()[0].split('=', 1)[1].split()
            for package in ('gimp', 'krita', 'inkscape', 'ncdu', 'nodejs-lts', 'gnupg', 'audacious', 'audacious-plugins'):
                self.assertIn(package, packages)
            self.assertEqual(len(packages), len(set(packages)))
            for package in ('mpv', 'gnuplot', 'octave', 'nodejs-lts'):
                self.assertIn(package + '=termux-main', result.stdout)
            self.assertIn('gimp=termux-x11', result.stdout)

    def test_transport_retries_are_bounded_and_signature_failures_never_retry(self):
        for output, expected in [('Could not resolve mirror', 3), ('Hash Sum mismatch', 1)]:
            with self.subTest(output=output), tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp)
                result=self.shell(f'''sleep() {{ :; }}
transport() {{ echo call >> "$HOME/calls"; echo '{output}'; return 7; }}
_nt_network_retry fixture transport
''', home)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(len((home/'calls').read_text().splitlines()), expected)

    def test_package_mutation_reuses_downloaded_exact_versions_and_does_not_retry_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            result=self.shell('''env() { printf '%s\\n' "$*" >> "$HOME/calls"; }
_NT_PLAN_TRANSACTION=(python=3.14.8)
TERNUXX_WIZARD_ACTIVE=1 _nt_apply_install_transaction
''', home)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls=(home/'calls').read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn('--download-only', calls[0])
            self.assertIn('--no-download', calls[1])
            self.assertTrue(all('python=3.14.8' in call for call in calls))

    def test_session_lock_rejects_competitor_without_stopping_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            env={**os.environ,'HOME':str(home),'TERNUXX_STATE_DIR':str(home/'state'),'TERNUXX_QUIET':'0'}
            script=f'source "{ROOT}/lib/phases.sh"; source "{ROOT}/lib/install_preflight.sh"; _nt_install_lock || exit $?; echo HELD; read -r reply'
            holder=subprocess.Popen(['bash','-c',script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            try:
                self.assertEqual(holder.stdout.readline().strip(),'HELD')
                contender=self.shell('_nt_install_lock',home)
                self.assertEqual(contender.returncode,75,contender.stderr)
                self.assertIsNone(holder.poll())
            finally:
                holder.communicate('done\n',timeout=3)
            self.assertEqual(self.shell('_nt_install_lock',home).returncode,0)

    def test_preflight_refuses_low_storage_or_incomplete_package_state(self):
        for storage, audit in [(1024, ''), (1048576, 'package needs configuration')]:
            with self.subTest(storage=storage), tempfile.TemporaryDirectory() as tmp:
                home=Path(tmp)
                result=self.shell(f'''df() {{ printf 'Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 2000000 1 {storage} 1%% /\\n'; }}
env() {{ printf '%s' '{audit}'; }}
_nt_install_preflight || exit $?
echo MUTATION
''',home)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('MUTATION',result.stdout)

    def test_diagnostic_excludes_environment_and_passwords(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); (home/'state').mkdir()
            result=self.shell('''PASSWORD=not-for-report
_NT_WINDOW_STARTED=$SECONDS
_NT_WINDOW_STAGE='Native package phase'
_nt_install_diagnostic 1
''',home)
            self.assertEqual(result.returncode,0,result.stderr)
            summary=(home/'state/install-last-result.txt').read_text()
            self.assertIn('exit_code=1',summary)
            self.assertNotIn('not-for-report',summary)
            self.assertEqual((home/'state/install-last-result.txt').stat().st_mode & 0o777,0o600)

    def test_graphics_download_retries_same_request_but_not_certificate_failures(self):
        request=object()
        response=io.BytesIO(b'pinned bytes')
        with mock.patch.object(proot_fresh_setup.urllib.request,'urlopen',side_effect=[urllib.error.URLError('temporary'),response]) as open_url, mock.patch.object(proot_fresh_setup.time,'sleep'):
            self.assertEqual(proot_fresh_setup._download_archive(request),b'pinned bytes')
            self.assertEqual(open_url.call_count,2)
            self.assertTrue(all(call.args[0] is request for call in open_url.call_args_list))
        import ssl
        with mock.patch.object(proot_fresh_setup.urllib.request,'urlopen',side_effect=urllib.error.URLError(ssl.SSLCertVerificationError('certificate'))) as open_url:
            with self.assertRaises(urllib.error.URLError): proot_fresh_setup._download_archive(request)
            self.assertEqual(open_url.call_count,1)

    def test_precollected_guest_password_uses_private_fd_without_prompt_or_output(self):
        import contextlib
        read_fd, write_fd = os.pipe()
        os.write(write_fd,b'fixture-password\n'); os.close(write_fd)
        output=io.StringIO()
        args=['proot_setup.py','fresh-install','--repo-root',str(ROOT),'--prefix','/fixture/prefix',
              '--home','/fixture/home','--state-dir','/fixture/home/state','--alias','debian',
              '--plan-id','a'*64,'--yes','--password-fd',str(read_fd),'--json']
        try:
            with mock.patch.object(sys,'argv',args), mock.patch.object(proot_setup.getpass,'getpass',side_effect=AssertionError('unexpected prompt')), \
                 mock.patch.object(proot_setup.proot_fresh_setup,'apply',return_value={'status':'complete'}) as apply, contextlib.redirect_stdout(output):
                self.assertEqual(proot_setup.main(),0)
            self.assertEqual(apply.call_args.kwargs['password'],'fixture-password')
            self.assertNotIn('fixture-password',output.getvalue())
            self.assertNotIn('fixture-password',' '.join(args))
        finally:
            os.close(read_fd)

    def test_installer_handoff_is_allowlisted_and_authorized_as_mutating_software(self):
        self.assertEqual(management_authorization.OPERATION_CAPABILITIES['installer.open'],'software.manage')
        self.assertIn('installer.open',management_sessions.MUTATING_OPERATIONS)
        with self.assertRaises(ValueError): installer_launch.command('arbitrary-shell',prefix='/tmp')
        request={'api_version':1,'request_id':'fixture-request','operation':'installer.open','args':{'target':'sh -c evil'}}
        result=management_service.dispatch(request)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'],'invalid_arguments')

    def test_missing_external_apps_optin_does_not_change_android_configuration(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(installer_launch,'command',return_value=['/fixed/tx','install']), mock.patch.object(installer_launch.subprocess,'run') as run:
            result=installer_launch.open_terminal('workstation',home=tmp,prefix='/data/data/com.termux/files/usr')
            self.assertEqual(result['status'],'manual_action_required')
            run.assert_not_called()
            self.assertFalse((Path(tmp)/'.termux/termux.properties').exists())

if __name__=='__main__': unittest.main()
