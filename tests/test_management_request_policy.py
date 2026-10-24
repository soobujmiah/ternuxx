"""Contract tests for the pre-dispatch local HTTP request guard."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import management_request_policy  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 10.0

    def __call__(self) -> float:
        return self.now


class ManagementRequestPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = management_request_policy.LoopbackRequestPolicy(
            "http://127.0.0.1:8765", burst=30)

    def check(self, **overrides):
        values = {
            "host": "127.0.0.1:8765", "method": "GET", "origin": None,
            "content_type": None, "content_length": 0,
        }
        values.update(overrides)
        return self.policy.check(**values)

    def test_accepts_exact_loopback_host_and_same_origin_json_post(self) -> None:
        self.assertEqual(self.check().reason, "accepted")
        post = self.check(method="POST", origin="http://127.0.0.1:8765",
                          content_type="application/json; charset=utf-8", content_length=10)
        self.assertTrue(post.allowed)

    def test_rejects_host_origin_method_and_content_type_confusion(self) -> None:
        cases = [
            ({"host": "0.0.0.0:8765"}, "host_rejected"),
            ({"host": "127.0.0.1"}, "host_rejected"),
            ({"origin": "http://evil.example"}, "origin_rejected"),
            ({"method": "POST", "origin": None, "content_type": "application/json"}, "origin_required"),
            ({"method": "POST", "origin": "http://127.0.0.1:8765", "content_type": "text/plain"}, "content_type_rejected"),
            ({"method": "PUT"}, "method_rejected"),
        ]
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(self.check(**overrides).reason, expected)

    def test_rejects_missing_negative_oversized_and_noninteger_lengths(self) -> None:
        for length in (-1, 65537, True, "12", None):
            with self.subTest(length=length):
                self.assertEqual(self.check(content_length=length).reason,
                                 "body_size_rejected")

    def test_rate_limiter_bounds_burst_and_refills_monotonically(self) -> None:
        clock = FakeClock()
        policy = management_request_policy.LoopbackRequestPolicy(
            "http://127.0.0.1:8765", burst=2, rate_per_second=1, clock=clock)
        self.assertTrue(policy.check(host="127.0.0.1:8765", method="GET").allowed)
        self.assertTrue(policy.check(host="127.0.0.1:8765", method="GET").allowed)
        self.assertEqual(policy.check(host="127.0.0.1:8765", method="GET").reason,
                         "rate_limited")
        clock.now += 1
        self.assertTrue(policy.check(host="127.0.0.1:8765", method="GET").allowed)

    def test_rate_limiter_is_thread_safe(self) -> None:
        policy = management_request_policy.LoopbackRequestPolicy(
            "http://127.0.0.1:8765", burst=3, rate_per_second=1,
            clock=FakeClock())
        def request(_index):
            return policy.check(host="127.0.0.1:8765", method="GET").allowed
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(request, range(32)))
        self.assertEqual(sum(results), 3)

    def test_expected_origin_is_explicit_loopback_http_with_port(self) -> None:
        for origin in (
            "http://0.0.0.0:8765", "https://127.0.0.1:8765",
            "http://localhost:8765", "http://127.0.0.1", "http://user@127.0.0.1:8765",
            "http://127.0.0.1:8765/path",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                management_request_policy.LoopbackRequestPolicy(origin)


if __name__ == "__main__":
    unittest.main()
