from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import proot_distro_removal


class ProotDistroRemovalTests(unittest.TestCase):
    def test_exact_preview_and_confirmation_remove_only_named_guest(self):
        with tempfile.TemporaryDirectory(prefix="ternuxx-remove-proot-") as temp:
            base = Path(temp)
            prefix = base / "prefix"
            target = prefix / "var/lib/proot-distro/containers/alpine"
            (target / "rootfs/etc").mkdir(parents=True)
            (target / "rootfs/etc/os-release").write_text("ID=alpine\n")
            home = base / "home"
            home.mkdir()
            state_dir = home / ".local/share/ternuxx"
            bin_dir = base / "bin"
            bin_dir.mkdir()
            manager = bin_dir / "proot-distro"
            manager.write_text("#!/bin/sh\nif [ \"$1\" = list ]; then printf 'alpine\\n'; exit 0; fi\nif [ \"$1\" = remove ] && [ \"$2\" = alpine ]; then rm -rf " + str(target.parent / "alpine") + "; exit 0; fi\nexit 2\n")
            manager.chmod(0o700)
            with patch.object(proot_distro_removal.shutil, "which", return_value=str(manager)):
                preview = proot_distro_removal.preview(prefix=str(prefix), home=str(home),
                    state_dir=str(state_dir), alias="alpine")
                with self.assertRaises(proot_distro_removal.RemovalError):
                    proot_distro_removal.apply(prefix=str(prefix), home=str(home), state_dir=str(state_dir),
                        alias="alpine", plan_id=preview["plan_id"], typed_alias="debian", confirmed=True)
                result = proot_distro_removal.apply(prefix=str(prefix), home=str(home), state_dir=str(state_dir),
                    alias="alpine", plan_id=preview["plan_id"], typed_alias="alpine", confirmed=True)
            self.assertEqual(result["status"], "removed")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
