"""Optional offline contract check against the actual installed routing source.

Set DLOG_TEST_ROUTE to its path. urllib is mocked; no platform calls are made.
The source is loaded from verified bytes; nothing is written to its repository.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

from dispatch_log.record import Recorder
from dispatch_log.route import TRUSTED_SHA256, execute, load_module
from dispatch_log.store import Store


@unittest.skipUnless(os.environ.get("DLOG_TEST_ROUTE"), "set DLOG_TEST_ROUTE for installed-source offline check")
class PinnedRouteTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(os.environ["DLOG_TEST_ROUTE"])
        source = self.path.read_bytes()
        self.assertIn(hashlib.sha256(source).hexdigest(), TRUSTED_SHA256)
        self.module = load_module(self.path, source)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name) / "records")
        self.dispatch = self.store.create(self.temporary.name, "T1")["dispatch_id"]
        environment = mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "offline-key"})
        environment.start()
        self.addCleanup(environment.stop)

    def response(self):
        answers = {"tier": {"probabilities": {"0": 0.100001, "1": 0.899998, "2": 0.000001},
                            "confidence": 0.923456, "score": 1.1},
                   "visible": {"noul": 0.1234567}, "doc_only": {"noul": 0.2345678}}
        answers.update({"cross_" + k: {"noul": 0.1} for k in self.module.CROSS_REVIEW})
        return {"model": "synthetic-model", "answers": answers, "usage": {"tokens": 12},
                "additional": {"preserve": True}}

    def execute_with(self, **urlopen_options):
        output = io.StringIO()
        with mock.patch("urllib.request.urlopen", **urlopen_options) as calls:
            with mock.patch("dispatch_log.route.load_module", return_value=self.module):
                with contextlib.redirect_stdout(output):
                    code = execute(self.path, " task \n", Recorder(self.store, self.dispatch))
        return code, output.getvalue(), calls.call_count

    def test_success_exact_output_and_full_response(self):
        payload = json.dumps(self.response()).encode()
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(payload)) as direct:
            expected = self.module.route("task")
        code, output, count = self.execute_with(return_value=io.BytesIO(payload))
        self.assertEqual(code, 0)
        self.assertEqual(output, json.dumps(expected, ensure_ascii=False) + "\n")
        self.assertEqual((direct.call_count, count), (1, 1))
        event = self.store.events(self.dispatch)[-1]
        parsed = json.loads(self.store.read_blob(event["data"]["parsed_response"]["sha256"]))
        self.assertEqual(parsed, self.response())

    def test_original_retry_policy_preserved_without_extra_adapter_retry(self):
        failure = urllib.error.URLError("offline synthetic")
        with mock.patch("urllib.request.urlopen", side_effect=failure) as direct:
            expected = self.module.route("task")
        code, output, count = self.execute_with(side_effect=failure)
        self.assertEqual(code, 1)
        self.assertEqual(output, json.dumps(expected, ensure_ascii=False) + "\n")
        self.assertEqual((direct.call_count, count), (2, 2))

    def test_shape_failure_still_preserves_response_and_never_replays(self):
        code, output, count = self.execute_with(return_value=io.BytesIO(b'{"unexpected":true}'))
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output)["ok"])
        self.assertEqual(count, 1)
        event = self.store.events(self.dispatch)[-1]
        self.assertEqual(json.loads(self.store.read_blob(event["data"]["parsed_response"]["sha256"])),
                         {"unexpected": True})
