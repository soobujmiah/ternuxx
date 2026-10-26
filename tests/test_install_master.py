"""Combined approval barrier and streaming fixtures; no actual package manager runs."""
import contextlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import install_master_plan as plans
import install_events


class MasterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.prefix=self.home/'prefix';self.prefix.mkdir()
        self.env={**os.environ,'HOME':str(self.home),'PREFIX':str(self.prefix),'TERNUXX_STATE_DIR':str(self.home/'state'),'TERNUXX_JSON':'0','TERNUXX_QUIET':'0'}

    def part(self,name,value):
        p=self.home/name;p.write_text(json.dumps(value));p.chmod(0o600)

    def test_aggregate_sizes_private_records_and_tamper_rejection(self):
        self.part('native.part.json',dict(plan_id='a'*64,resource_estimates=dict(complete=True,download_bytes=100,installed_kib=2),packages=['python=1'],transaction=['python=1']))
        self.part('guest-debian.part.json',dict(plan_id='b'*64,operation=dict(transaction_summary={},desktop_environments=['plasma'],transaction_packages=[['kde','1']]),transaction=dict(download=dict(value=3,unit='MB'),disk=dict(value=4,unit='MB'))))
        with mock.patch.dict(os.environ,self.env):
            plan=plans.build(self.home);plans.verify(self.home,plan)
            d=json.loads((self.home/'master.json').read_text())
            self.assertEqual(d['download_bytes_known'],3000100)
            self.assertEqual(d['disk_bytes_known'],4002048)
            self.assertTrue(d['unknown_estimates'])
            self.assertIn('Guest package changes: 1',(self.home/'report.txt').read_text())
            self.part('guest-debian.part.json',{'plan_id':'c'*64})
            with self.assertRaisesRegex(ValueError,'changed'):plans.verify(self.home,plan)

    def coordinator(self,approve,tamper=False):
        log=self.home/'trace'
        script=f'''set -u
source "{ROOT}/lib/phases.sh"
source "{ROOT}/lib/install_wizard.sh"
_nt_window_stage() {{ echo "STAGE:$1" >>'{log}'; }}
_nt_window_run() {{ "$@"; }}
_nt_master_prepare() {{ echo METADATA_ONLY >>'{log}'; }}
_nt_collect_guest() {{ echo COLLECT_$1 >>'{log}'; }}
_nt_master_gpu_choices() {{ _NT_MASTER_BACKEND=keep; echo GPU_CHOICES >>'{log}'; }}
nt_cmd_install() {{
 echo NATIVE_$1 >>'{log}'
 if [ "$1" = preview ]; then echo '{{"plan_id":"{'a'*64}","resource_estimates":{{"complete":true,"download_bytes":0,"installed_kib":0}},"transaction":[]}}'; fi
}}
_nt_master_guest_preview() {{
 echo GUEST_PREVIEW_$1 >>'{log}'
 printf '%s' '{{"plan_id":"{'b'*64}","operation":{{"operation":"debian-desktop-install","transaction_summary":{{}},"transaction_packages":[]}},"transaction":{{}}}}' >"$3/guest-$1.part.json"
}}
_nt_master_review() {{ echo REVIEW_AND_{'APPROVE' if approve else 'REJECT'} >>'{log}'; {'echo changed >"$1/report.txt";' if tamper else ''} return {0 if approve else 130}; }}
_nt_master_apply_guest() {{ echo GUEST_APPLY_$3 >>'{log}'; }}
python3() {{
 if [[ "$1" = */scripts/cli_entrypoint.py ]]; then
   echo ENTRY_$2 >>'{log}'
   echo '{{"ok":true,"data":{{"changed":true,"plan_id":"{'c'*64}"}}}}'
 else command python3 "$@"; fi
}}
bash() {{ echo MANAGEMENT_APPLY >>'{log}'; }}
_nt_master_workstation '{ROOT}' terminal debian,ubuntu
'''
        result=subprocess.run(['bash','-c',script],env=self.env,capture_output=True,text=True,timeout=15)
        return result,log.read_text()

    def test_rejecting_full_plan_never_calls_any_apply(self):
        result,trace=self.coordinator(False)
        self.assertEqual(result.returncode,130,result.stderr)
        self.assertIn('GUEST_PREVIEW_debian',trace)
        self.assertIn('GUEST_PREVIEW_ubuntu',trace)
        self.assertNotIn('NATIVE_apply',trace)
        self.assertNotIn('GUEST_APPLY',trace)
        self.assertNotIn('MANAGEMENT_APPLY',trace)
        self.assertNotIn('ENTRY_apply',trace)

    def test_every_preview_and_choice_precedes_approval_and_apply(self):
        result,trace=self.coordinator(True)
        self.assertEqual(result.returncode,0,result.stderr)
        approval=trace.index('REVIEW_AND_APPROVE')
        for marker in ('COLLECT_debian','COLLECT_ubuntu','GPU_CHOICES','NATIVE_preview','GUEST_PREVIEW_debian','GUEST_PREVIEW_ubuntu','ENTRY_preview'):
            self.assertLess(trace.index(marker),approval)
        for marker in ('NATIVE_apply','ENTRY_apply','MANAGEMENT_APPLY','GUEST_APPLY_debian','GUEST_APPLY_ubuntu'):
            self.assertGreater(trace.index(marker),approval)

    def test_changed_review_report_blocks_all_apply(self):
        result,trace=self.coordinator(True,tamper=True)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('NATIVE_apply',trace)
        self.assertNotIn('GUEST_APPLY',trace)

    def test_combined_native_upgrade_is_one_exact_transaction(self):
        script=f'''source '{ROOT}/lib/phases.sh'
_NT_BASE_PACKAGES=(new-tool); _NT_ACTIVE_COMPONENTS=terminal,system-upgrade
_nt_package_installed() {{ [ "$1" = old-tool ]; }}
_nt_package_candidate_from_official_repo() {{ echo 2; }}
_nt_capture_install_resource_estimates() {{ :; }}
apt-get() {{
 if [[ " $* " = *' upgrade '* ]]; then
  printf 'Inst old-tool [1] (2 termux-main [aarch64])\\n'
 else
  printf '%s\\n' "$*" >&2
  printf 'Inst old-tool [1] (2 termux-main [aarch64])\\nInst new-tool (2 termux-main [aarch64])\\n'
 fi
}}
_nt_make_install_plan || exit $?
printf 'MODE=%s ROOTS=%s TRANSACTION=%s\\n' "$_NT_PLAN_MODE" "${{_NT_PLAN_VERSIONS[*]}}" "${{_NT_PLAN_TRANSACTION[*]}}"
'''
        result=subprocess.run(['bash','-c',script],capture_output=True,text=True,env=self.env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('MODE=update',result.stdout)
        self.assertIn('old-tool=2',result.stdout)
        self.assertIn('new-tool=2',result.stdout)
        self.assertNotIn('--no-upgrade',result.stderr)

    def test_stream_emits_before_child_completion_and_keeps_machine_stdout_clean(self):
        script=f'''import sys;sys.path.insert(0,{str(ROOT/'lib')!r});import install_events
install_events.run([sys.executable,'-u','-c',"import time;print('Get:1 fixture',flush=True);time.sleep(1);print('Setting up fixture',flush=True)"],timeout=5,env=None)
print('{{"ok":true}}')'''
        proc=subprocess.Popen([sys.executable,'-u','-c',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda:proc.kill() if proc.poll() is None else None)
        self.assertTrue(select.select([proc.stderr],[],[],2)[0])
        first=proc.stderr.readline()
        self.assertIn('[DOWNLOAD]',first)
        self.assertIsNone(proc.poll())
        stdout,stderr=proc.communicate(timeout=5)
        self.assertEqual(json.loads(stdout),{'ok':True})
        self.assertIn('[CONFIGURE]',stderr)
        self.assertEqual(proc.returncode,0)

    def test_stream_timeout_terminates_only_owned_fixture(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(subprocess.TimeoutExpired):
                install_events.run([sys.executable,'-c','import time;time.sleep(10)'],timeout=.1,env=None)
