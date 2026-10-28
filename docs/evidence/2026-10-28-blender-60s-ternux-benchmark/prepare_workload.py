#!/usr/bin/env python3
"""Prepare a Native-Blender-compatible copy of Ternux's 60s procedural film."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: prepare_workload.py TERNux_CLONE_DIR WORK_ROOT")
clone = Path(sys.argv[1]).resolve()
work_root = Path(sys.argv[2]).resolve()
source = clone / "experiments/bengali-short-film"
work_project = work_root / "experiments/bengali-short-film"
if not source.is_dir():
    raise SystemExit(f"upstream film source missing: {source}")

source_commit = subprocess.check_output(
    ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
).strip()
tracked = [
    "README.md", "project_config.json", "film.py", "environment.py", "humans.py",
    "head.py", "render_film.py", "assets/lines.json", "assets/cues.json",
]

def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

source_hashes = {name: sha(source / name) for name in tracked}
if work_root.exists():
    shutil.rmtree(work_root)
work_project.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, work_project, ignore=shutil.ignore_patterns("__pycache__"))

film_path = work_project / "film.py"
film_text = film_path.read_text(encoding="utf-8")
old_engine = 's.render.engine = "BLENDER_EEVEE_NEXT"'
new_engine = 's.render.engine = "BLENDER_EEVEE"'
if old_engine not in film_text:
    raise SystemExit("expected upstream EEVEE Next engine declaration not found")
film_path.write_text(film_text.replace(old_engine, new_engine, 1), encoding="utf-8")

lines = json.loads((work_project / "assets/lines.json").read_text(encoding="utf-8"))
lipsync = {}
for line in lines:
    text = line["text"]
    frames = max(48, min(192, round(len(text) * 2.5 * 24 / 10)))
    openness = []
    phase = (line["scene"] * 7 + len(text)) % 13
    for frame in range(frames):
        gate = (frame + phase) % 15
        value = 0.0 if gate in (0, 1, 2, 3) else (0.55 + 0.45 * math.sin(frame * 0.47 + phase))
        openness.append(round(max(0.0, min(1.0, value)), 4))
    lipsync[line["id"]] = {
        "speaker": line["speaker"], "scene": line["scene"],
        "frames": frames, "seconds": round(frames / 24, 3),
        "openness": openness,
    }
expected = work_root / "experiments/assets/lipsync.json"
expected.parent.mkdir(parents=True, exist_ok=True)
expected.write_text(json.dumps(lipsync, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

manifest = {
    "upstream_repository": "https://github.com/soobujmiah/ternux.git",
    "upstream_branch": "main",
    "upstream_commit": source_commit,
    "upstream_project": "experiments/bengali-short-film",
    "upstream_license": "Apache-2.0 (repository LICENSE)",
    "source_sha256": source_hashes,
    "native_adaptation": {
        "only_engine_change": "BLENDER_EEVEE_NEXT -> BLENDER_EEVEE (Native Blender 5.2.2 exposes only BLENDER_EEVEE)",
        "lip_sync": "deterministic synthetic mouth envelope; original generated TTS/lipsync assets are absent from Git",
        "audio_and_captions": "omitted; this test measures Blender scene rendering only",
        "output_settings": {"fps": 24, "frames": 1440, "resolution": [1280, 720], "eevee_samples": 16},
        "render_processes": "one Blender process per scene, five scenes, matching the reported Ternux pipeline",
    },
    "synthetic_lipsync_sha256": sha(expected),
    "work_root": str(work_root),
}
manifest_path = Path(__file__).with_name("workload-manifest.json")
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"prepared": str(work_project), "manifest": str(manifest_path), **manifest}, ensure_ascii=False, indent=2))
