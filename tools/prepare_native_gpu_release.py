#!/usr/bin/env python3
"""Prepare a deterministic, reviewable two-package Mesa mirror with source/notices."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import zipfile
import argparse

ROOT=Path(__file__).resolve().parents[1]
SOURCE_COMMIT='98f3d6229d61452cef80f8563af7c56ae599dc14'
SOURCE_SHA='5211bd235658a0585740fb2dfbe64e7e8ca3085ad8e423fc333b4d5e0de6fd93'
UPSTREAM_SHA='8493482210f9cc625f4fadb95e53cb417650c31f6e2b5a0d8725a2ef3c82ff5e'
TAG='native-mesa-adreno825-2026.10.27'
NAME='native-mesa-0219ff84-aarch64.zip'


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'config/graphics/native-kgsl.json').read_text())
    artifact=subprocess.run(['gh','api','repos/lfdevs/termux-packages/actions/artifacts/10951543592/zip'],capture_output=True,check=True,timeout=240).stdout
    if hashlib.sha256(artifact).hexdigest()!=UPSTREAM_SHA:raise ValueError('upstream artifact changed')
    selected={}; expected={v['sha256']:v['name'] for v in profile['input_snapshot']['packages']}
    with zipfile.ZipFile(io.BytesIO(artifact)) as z:
        values=[z.read(v) for v in z.infolist() if v.filename.endswith('.tar')]
    if len(values)!=1 or hashlib.sha256(values[0]).hexdigest()!=profile['input_snapshot']['bundle_sha256']:raise ValueError('upstream tar identity changed')
    with tarfile.open(fileobj=io.BytesIO(values[0])) as archive:
        for item in archive:
            if not item.isfile() or not item.name.endswith('.deb'):continue
            blob=archive.extractfile(item).read(); package=expected.get(hashlib.sha256(blob).hexdigest())
            if package is None:raise ValueError('unrecognized upstream package')
            if package in {'mesa','mesa-vulkan-icd-freedreno'}:selected[Path(item.name).name]=blob
    if len(selected)!=2:raise ValueError('missing exact GPU packages')
    source=output/'mesa-source-98f3d6229d.tar.gz'
    if not source.exists():
        with urllib.request.urlopen('https://codeload.github.com/lfdevs/mesa-for-android-container/tar.gz/'+SOURCE_COMMIT,timeout=180) as response:
            source.write_bytes(response.read(128*1024*1024))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('corresponding source archive changed')
    notices={}
    with tarfile.open(source) as archive:
        for item in archive:
            name='/'.join(item.name.split('/')[1:])
            if item.isfile() and (name.startswith('licenses/') or name=='docs/license.rst'):
                if item.size>1024*1024:raise ValueError('oversized license notice')
                notices['source-notices/'+name]=archive.extractfile(item).read()
    if not notices:raise ValueError('source notices absent')
    recipe=subprocess.run(['gh','api','repos/lfdevs/termux-packages/git/trees/0219ff84b372c9d38aad4e40f448c20ec3d1588e?recursive=1'],capture_output=True,check=True,text=True,timeout=120)
    tree=json.loads(recipe.stdout)
    if tree.get('truncated'):raise ValueError('recipe tree is truncated')
    recipe_files={}
    for entry in tree['tree']:
        if entry['type']=='blob' and entry['path'].startswith('packages/mesa/'):
            data=subprocess.run(['gh','api','-H','Accept: application/vnd.github.raw+json','repos/lfdevs/termux-packages/contents/'+entry['path']+'?ref=0219ff84b372c9d38aad4e40f448c20ec3d1588e'],capture_output=True,check=True,timeout=60).stdout
            recipe_files['recipe/'+entry['path']]=data
    metadata={'schema_version':1,'upstream_repository':'lfdevs/termux-packages','upstream_commit':'0219ff84b372c9d38aad4e40f448c20ec3d1588e','workflow_run_id':36377469447,'artifact_id':10951543592,'upstream_zip_sha256':UPSTREAM_SHA,'source_repository':'lfdevs/mesa-for-android-container','source_commit':SOURCE_COMMIT,'source_archive_sha256':SOURCE_SHA,'status':'experimental driver; permanent versioned acquisition','system_package_installation':False,'license_summary':'Mesa has component-specific licenses; all matching source license notices and full source are included. This is not an MIT-only assertion.','licenseConcluded':'NOASSERTION','source_build_attribution_gate':'P12 transitive build-input attribution remains open; not declared closed by this mirror','packages':{k:hashlib.sha256(v).hexdigest() for k,v in selected.items()}}
    (output/'PROVENANCE.json').write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n')
    notice=('Third-party experimental Mesa distribution.\nThe core is predominantly MIT; per-component licenses also apply.\nSee source-notices/, the full matching source archive and pinned build recipe.\nNo conformance, every-workload support or byte-reproducible rebuild is claimed.\nOriginal package bytes are unchanged; system dpkg packages are not replaced.\n')
    entries={**selected,**notices,**recipe_files,'PROVENANCE.json':(output/'PROVENANCE.json').read_bytes(),'NOTICE.txt':notice.encode()}
    with zipfile.ZipFile(output/NAME,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    (output/'NOTICE.txt').write_text(notice)
    assets=[NAME,source.name,'PROVENANCE.json','NOTICE.txt']
    sums={name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in assets}
    (output/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(sums.items())))
    print(json.dumps({'tag':TAG,'url':'https://github.com/soobujmiah/ternuxx/releases/download/'+TAG+'/'+NAME,'sha256':sums[NAME],'assets':assets+['SHA256SUMS'],'output':str(output)},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);prepare(p.parse_args().output)
