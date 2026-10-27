"""Native fetch/integrity fixtures; no guest or package manager runs."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import proot_package_fetch as fetch
import install_events


class PackageFetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'root';self.root.mkdir();self.state=self.base/'state';self.state.mkdir()
        self.payload=b'verified fixture archive'
        self.record=dict(package='fixture',version='1:2',url='https://example.invalid/archive/pool/fixture_2_arm64.deb',filename='fixture_1%3a2_arm64.deb',size=len(self.payload),sha256=hashlib.sha256(self.payload).hexdigest())

    def test_native_sha_verified_cache_reuse_and_guest_cache_staging(self):
        opener=mock.Mock(side_effect=lambda *a,**k:io.BytesIO(self.payload))
        log=self.state/'events.log'
        with mock.patch.object(fetch.ssl,'create_default_context'),contextlib.redirect_stderr(io.StringIO()):
            fetch.fetch(self.root,self.state,[self.record],ca_file='fixture-ca',opener=opener,log_path=log)
            fetch.fetch(self.root,self.state,[self.record],ca_file='fixture-ca',opener=opener,log_path=log)
        self.assertEqual(opener.call_count,1)
        self.assertEqual(opener.call_args.args[0].get_header('User-agent'),'curl/8')
        self.assertEqual((self.root/'var/cache/apt/archives'/self.record['filename']).read_bytes(),self.payload)
        self.assertIn('All exact guest archives verified',log.read_text())
        self.assertEqual(log.stat().st_mode & 0o777,0o600)

    def test_hash_failure_never_stages_guest_files_or_switches_url(self):
        opener=mock.Mock(side_effect=lambda *a,**k:io.BytesIO(b'x'*len(self.payload)))
        with mock.patch.object(fetch.ssl,'create_default_context'),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                fetch.fetch(self.root,self.state,[self.record],ca_file='fixture-ca',opener=opener)
        self.assertEqual(opener.call_count,1)
        self.assertEqual(opener.call_args.args[0].full_url,self.record['url'])
        self.assertFalse((self.root/'var/cache/apt/archives').exists())

    def test_network_retry_is_limited_to_same_reviewed_url(self):
        opener=mock.Mock(side_effect=OSError('fixture network failure'))
        with mock.patch.object(fetch.ssl,'create_default_context'),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'3 attempts'):
                fetch.fetch(self.root,self.state,[self.record],ca_file='fixture-ca',opener=opener)
        self.assertEqual(opener.call_count,3)
        self.assertEqual({c.args[0].full_url for c in opener.call_args_list},{self.record['url']})
        self.assertFalse((self.root/'var/cache/apt/archives').exists())

    def test_uri_record_uses_apt_filename_and_index_sha256(self):
        metadata={'fixture':dict(Package='fixture',Version='1:2',Architecture='arm64',Filename='pool/fixture_2_arm64.deb',Size=str(len(self.payload)),SHA256=self.record['sha256'])}
        text=f"'{self.record['url']}' {self.record['filename']} {len(self.payload)} SHA512:ignored\n"
        self.assertEqual(fetch.bind_uris(text,metadata),[self.record])
        with self.assertRaises(ValueError):fetch.bind_uris(text.replace('https:','http:'),metadata)
        with self.assertRaises(ValueError):fetch.bind_uris(text.replace(self.record['filename'],'../bad.deb'),metadata)
        with self.assertRaises(ValueError):fetch.bind_uris(text.replace('pool/fixture','pool/other'),metadata)

    def test_native_index_decoder_binds_exact_versions_and_index_digest(self):
        prefix=self.base/'prefix';helper=prefix/'lib/apt/apt-helper';helper.parent.mkdir(parents=True)
        helper.write_text('#!/bin/sh\ncat "$2"\n');helper.chmod(0o700)
        lists=self.root/'var/lib/apt/lists';lists.mkdir(parents=True)
        index=lists/'fixture_Packages.lz4'
        index.write_text(f"Package: fixture\nVersion: 1:2\nArchitecture: arm64\nFilename: pool/fixture_2_arm64.deb\nSize: {len(self.payload)}\nSHA256: {self.record['sha256']}\n\n")
        records,indexes=fetch.metadata(self.root,str(prefix),[['fixture','1:2']])
        self.assertEqual(records['fixture']['SHA256'],self.record['sha256'])
        self.assertEqual(indexes[index.name],hashlib.sha256(index.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'incomplete'):fetch.metadata(self.root,str(prefix),[['fixture','missing']])

    def test_no_output_timeout_retains_redacted_tail_and_private_log(self):
        log=self.state/'events.log'
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(install_events.InstallTimeout) as raised:
                install_events.run([sys.executable,'-u','-c',"import time;print('https://user:secret@example.invalid/?token=hidden',flush=True);time.sleep(4)"],timeout=5,idle_timeout=.2,env=None,log_path=log)
        self.assertEqual(raised.exception.timeout_kind,'no-output')
        self.assertNotIn('secret',raised.exception.last_output)
        self.assertNotIn('hidden',log.read_text())
        self.assertIn('no-output timeout',log.read_text())
