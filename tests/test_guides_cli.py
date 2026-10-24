from __future__ import annotations

import os
from pathlib import Path
import pty
import select
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TX = ROOT / "bin" / "tx"


class GuidesCliTests(unittest.TestCase):
    def test_non_tty_shows_safe_fallback_instead_of_hanging(self) -> None:
        result = subprocess.run(
            ["bash", str(TX), "guides"],
            input="",
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ternuxx Native Termux and Debian guide", result.stdout)
        self.assertIn("Interactive menu needs a terminal", result.stdout)
        self.assertIn("tx install preview", result.stdout)

    def test_interactive_menu_renders_choices_and_exits_cleanly(self) -> None:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            ["bash", str(TX), "guides"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            env=os.environ.copy(),
        )
        os.close(slave_fd)
        output = bytearray()
        deadline = time.monotonic() + 5
        sent_exit = False
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master_fd], [], [], 0.1)
                if readable:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        chunk = b""
                    output.extend(chunk)
                if not sent_exit and b"Choose an item:" in output:
                    os.write(master_fd, b"0\n")
                    sent_exit = True
                if proc.poll() is not None:
                    break
            self.assertTrue(sent_exit, output.decode(errors="replace"))
            self.assertIsNotNone(proc.poll(), "guide did not exit after choosing 0")
            self.assertEqual(proc.returncode, 0, output.decode(errors="replace"))
            rendered = output.decode(errors="replace")
            self.assertIn("1) Preview Native package setup", rendered)
            self.assertIn("8) Check CPU, GPU, and NPU inference status", rendered)
            self.assertIn("9) Inspect Debian or preview fresh guest setup", rendered)
            self.assertIn("12) Open GTK management center", rendered)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            os.close(master_fd)


if __name__ == "__main__":
    unittest.main()
