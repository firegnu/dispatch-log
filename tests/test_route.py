import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dispatch_log.record import Recorder
from dispatch_log.route import execute
from dispatch_log.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "route.py"


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.store = Store(self.base / "records")
        self.dispatch = self.store.create(self.base / "project", "T1")["dispatch_id"]
        self.calls = self.base / "calls"
        self.environment = mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "synthetic-secret-never-save",
                                                       "DLOG_TEST_CALLS": str(self.calls)}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_adapter(self, trusted=True, store=None):
        stdout_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8")
        stderr = io.StringIO()
        digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        with mock.patch("dispatch_log.route.TRUSTED_SHA256", {digest} if trusted else set()):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = execute(FIXTURE, "  中文摘要\n", Recorder(store or self.store, self.dispatch))
        stdout.flush()
        text = stdout_bytes.getvalue().decode()
        stdout.detach()
        return code, text, stderr.getvalue()

    def last_route(self):
        return next(e for e in reversed(self.store.events(self.dispatch)) if e["kind"] == "jev.route")

    def test_B_preserves_parsed_response_before_shape_and_only_one_call(self):
        code, output, _ = self.run_adapter()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {"ok": True, "score": 0.123})
        self.assertEqual(self.calls.read_text(), "call\n")
        event = self.last_route()
        self.assertEqual(event["data"]["mode"], "B")
        response = json.loads(self.store.read_blob(event["data"]["parsed_response"]["sha256"]))
        self.assertEqual(response["score"], 0.123456789)
        self.assertEqual(response["extra"], "kept before shape")
        request = json.loads(self.store.read_blob(event["data"]["request"]["sha256"]))
        self.assertEqual(request["state"]["task_summary"], "中文摘要")
        raw = b"".join(p.read_bytes() for p in self.store.root.rglob("*") if p.is_file())
        self.assertNotIn(b"synthetic-secret-never-save", raw)

    def test_version_mismatch_falls_back_before_request_once(self):
        code, output, stderr = self.run_adapter(trusted=False)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["ok"])
        self.assertEqual(self.calls.read_text(), "call\n")
        self.assertIn("降级", stderr)
        event = self.last_route()
        self.assertEqual(event["data"]["mode"], "A")
        self.assertIsNone(event["data"]["parsed_response"])

    def test_upstream_failure_does_not_trigger_fallback_or_second_request(self):
        os.environ["DLOG_TEST_FAIL"] = "1"
        code, output, _ = self.run_adapter()
        self.assertEqual(code, 1)
        self.assertIn("synthetic failure", json.loads(output)["error"])
        self.assertTrue(self.calls.exists(), "the one underlying call must actually run")
        self.assertEqual(self.calls.read_text(), "call\n")
        self.assertEqual(self.last_route()["data"]["mode"], "B")

    def test_record_failure_does_not_become_JEV_failure(self):
        broken = self.base / "not_directory"
        broken.write_text("file")
        code, output, stderr = self.run_adapter(store=Store(broken))
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["ok"])
        self.assertEqual(self.calls.read_text(), "call\n")
        self.assertIn("记录失败", stderr)

    def test_missing_key_does_not_call_upstream(self):
        del os.environ["TYPESAFE_API_KEY"]
        code, output, _ = self.run_adapter()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["error"], "TYPESAFE_API_KEY is not set")
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
