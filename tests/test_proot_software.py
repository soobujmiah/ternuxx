"""Optional guest software is curated and bound to the default base profile."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import proot_software
import proot_fresh_setup


class GuestSoftwareTests(unittest.TestCase):
    def test_expanded_catalog_binds_graphics_tools_and_ai_prerequisites(self):
        for distro in ('debian', 'ubuntu'):
            selected = ['blender', 'gimp', 'inkscape', 'krita', 'ncdu', 'ai-codex', 'ai-hermes', 'ai-claude']
            packages = proot_software.packages(distro, selected + ['graphics-runtime'])
            for package in ('blender', 'gimp', 'inkscape', 'krita', 'ncdu', 'nodejs', 'npm', 'libatomic1'):
                self.assertIn(package, packages)
            self.assertNotIn('claude-code', packages)
            self.assertIn('x11-utils', packages)
            self.assertEqual(len(packages), len(set(packages)))
            # Agent choices declare prerequisites and recipes, not a hidden curl installer.
            self.assertIn('recipe', proot_software.catalog(distro)['ai-codex'][0])

    def test_writer_is_selected_without_calc_or_impress(self):
        for distro in ('debian', 'ubuntu'):
            manifest = json.loads((ROOT / 'config/proot' / {'debian': 'debian-trixie.json', 'ubuntu': 'ubuntu-noble.json'}[distro]).read_text())
            result = proot_fresh_setup._packages(manifest, ['base', 'app-writer', 'app-music'])
            self.assertIn('libreoffice-writer', result)
            self.assertIn('audacious', result)
            self.assertNotIn('libreoffice-calc', result)
            self.assertNotIn('libreoffice-impress', result)
            # Base is mandatory and retains CPU Mesa, Vulkan and PulseAudio clients.
            for package in ('libgl1-mesa-dri', 'vulkan-tools', 'pulseaudio-utils'):
                self.assertIn(package, result)

    def test_clean_default_has_no_optional_apps(self):
        manifest = json.loads((ROOT / 'config/proot/debian-trixie.json').read_text())
        result = proot_fresh_setup._packages(manifest)
        self.assertNotIn('libreoffice-writer', result)
        self.assertNotIn('audacious', result)
        self.assertEqual(proot_fresh_setup._selected_groups(None), ['base'])

    def test_headless_cpu_runtime_keeps_sound_without_desktops_or_duplicate_packages(self):
        manifest = json.loads((ROOT / 'config/proot/debian-trixie.json').read_text())
        result = proot_fresh_setup._workstation_packages(manifest, ['base', 'app-cpu-runtime'], ())
        self.assertNotIn('xfce4', result)
        self.assertNotIn('xfce4-terminal', result)
        self.assertIn('mesa-vulkan-drivers', result)
        self.assertIn('pulseaudio-utils', result)
        self.assertEqual(len(result), len(set(result)))

    def test_ubuntu_browser_avoids_snap_and_unknown_apps_fail(self):
        self.assertEqual(proot_software.packages('ubuntu', ['browser']), ['epiphany-browser'])
        self.assertEqual(proot_software.packages('debian', ['browser']), ['firefox-esr'])
        with self.assertRaises(ValueError):
            proot_software.packages('ubuntu', ['shell;bad'])
        with self.assertRaises(ValueError):
            proot_software.packages('debian', ['writer', 'writer'])


if __name__ == '__main__':
    unittest.main()
