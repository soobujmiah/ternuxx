#!/usr/bin/env python3
"""Safety checks for recovery of a positively stale Termux:X11 :0 endpoint."""
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.x11_display import prepare, recover


class DisplayZeroRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ternuxx-x0-")
        self.root = Path(self.temp.name)
        (self.root / ".X11-unix").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_display_zero_is_available(self):
        self.assertEqual(prepare(str(self.root), "0"), "available")

    def test_dead_lock_is_reported_without_mutation(self):
        lock = self.root / ".X0-lock"
        lock.write_text("999999999\n", encoding="ascii")
        self.assertEqual(prepare(str(self.root), "0"), "stale")
        self.assertTrue((self.root / ".X0-lock").exists())

    def test_dead_lock_and_refused_socket_are_reported_without_mutation(self):
        lock = self.root / ".X0-lock"
        sock = self.root / ".X11-unix" / "X0"
        lock.write_text("999999999\n", encoding="ascii")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()
        self.assertEqual(prepare(str(self.root), "0"), "stale")
        self.assertTrue((self.root / ".X0-lock").exists())
        self.assertTrue((self.root / ".X11-unix/X0").exists())

    def test_live_pid_is_never_reclaimed(self):
        lock = self.root / ".X0-lock"
        lock.write_text(f"{os.getpid()}\n", encoding="ascii")
        self.assertEqual(prepare(str(self.root), "0"), "busy")
        self.assertTrue(lock.exists())

    def test_socket_without_lock_is_never_reclaimed(self):
        sock = self.root / ".X11-unix" / "X0"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()
        self.assertEqual(prepare(str(self.root), "0"), "busy")
        self.assertTrue(sock.exists())

    def test_nested_display_socket_without_lock_is_busy(self):
        sock = self.root / ".X11-unix" / "X2"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()
        self.assertEqual(prepare(str(self.root), "2"), "busy")
        self.assertTrue(sock.exists())

    def test_other_display_range_is_preserved(self):
        self.assertEqual(prepare(str(self.root), "1"), "available")
        self.assertEqual(prepare(str(self.root), "11"), "busy")

    def test_recorded_dead_pid_recovers_only_its_refused_socket_pair(self):
        lock = self.root / ".X1-lock"
        sock = self.root / ".X11-unix" / "X1"
        lock.write_text("999999999\n", encoding="ascii")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()

        self.assertEqual(recover(str(self.root), "1", "999999999"), "recovered")
        self.assertFalse(lock.exists())
        self.assertFalse(sock.exists())
        self.assertEqual(prepare(str(self.root), "1"), "available")

    def test_wrong_recorded_pid_does_not_remove_stale_artifacts(self):
        lock = self.root / ".X1-lock"
        sock = self.root / ".X11-unix" / "X1"
        lock.write_text("999999999\n", encoding="ascii")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()

        self.assertEqual(recover(str(self.root), "1", "999999998"), "busy")
        self.assertTrue(lock.exists())
        self.assertTrue(sock.exists())

    def test_missing_socket_can_recover_only_matching_dead_lock(self):
        lock = self.root / ".X1-lock"
        lock.write_text("999999999\n", encoding="ascii")
        self.assertEqual(recover(str(self.root), "1", "999999999"), "recovered")
        self.assertFalse(lock.exists())

    def test_live_socket_or_pid_is_never_recovered(self):
        lock = self.root / ".X1-lock"
        sock = self.root / ".X11-unix" / "X1"
        lock.write_text(f"{os.getpid()}\n", encoding="ascii")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.listen(1)
        try:
            self.assertEqual(recover(str(self.root), "1", str(os.getpid())), "busy")
        finally:
            server.close()
        self.assertTrue(lock.exists())
        self.assertTrue(sock.exists())

    def test_socket_without_matching_lock_is_never_recovered(self):
        sock = self.root / ".X11-unix" / "X1"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock))
        server.close()
        self.assertEqual(recover(str(self.root), "1", "999999999"), "busy")
        self.assertTrue(sock.exists())


if __name__ == "__main__":
    unittest.main()
