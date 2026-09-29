import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "records"
        self.project = self.base / "project"
        self.project.mkdir()
        self.counter = self.base / "calls"
        self.fake = self.base / "corral"
        self.fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ["FAKE_CALLS"], "a") as f:
    f.write(sys.argv[1] + "\\n")
snapshot = os.environ.get("CHECK_SNAPSHOT")
if snapshot:
    assert (Path(os.environ["RECORD_ROOT"]) / "blobs" / "sha256" / snapshot[:2] / snapshot).exists()
if os.environ.get("CHANGE_TASK"):
    Path(os.environ["CHANGE_TASK"]).write_text("changed after invocation")
print(os.environ.get("FAKE_OUTPUT", '{"ok":true,"name":"dev-2","instance":"abc123","secret_extra":"do-not-store"}'))
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
''')
        self.fake.chmod(0o700)
        self.env = dict(os.environ, FAKE_CALLS=str(self.counter), RECORD_ROOT=str(self.root))

    def run_cli(self, *args, input=None, env=None):
        return subprocess.run(
            [sys.executable, "-m", "dispatch_log", "--data-dir", str(self.root), *args],
            cwd=REPO, env=env or self.env, input=input, text=True, capture_output=True,
        )

    def new(self):
        result = self.run_cli("new", "--project", str(self.project), "--task", "T41")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "new must return a persisted dispatch ID")
        return result.stdout.strip()

    def events(self):
        return [json.loads(p.read_text()) for p in sorted((self.root / "events").glob("*.json"))]

    def blob(self, ref):
        digest = ref["sha256"]
        return (self.root / "blobs" / "sha256" / digest[:2] / digest).read_bytes()

    def test_new_persists_context_and_reloads_without_writes(self):
        dispatch = self.new()
        result = self.run_cli("show", dispatch)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["dispatch"]["project"], str(self.project.resolve()))
        self.assertEqual(record["dispatch"]["task"], "T41")
        self.assertEqual(record["dispatch"]["dispatch_id"], dispatch)
        listed = self.run_cli("ls", "--project", str(self.project), "--task", "T41")
        self.assertEqual(json.loads(listed.stdout)[0]["dispatch_id"], dispatch)

    def test_start_records_snapshot_before_command_and_only_allowed_fields(self):
        dispatch = self.new()
        worktree = self.base / "worktree"
        worktree.mkdir()
        task = worktree / "task.md"
        content = "任务书 initial\n".encode()
        task.write_bytes(content)
        env = dict(self.env, CHECK_SNAPSHOT=hashlib.sha256(content).hexdigest(), CHANGE_TASK=str(task))
        result = self.run_cli("start", "--dispatch", dispatch, "--task-file", "task.md", "--",
                              str(self.fake), "start", "dev", "--cwd", str(worktree),
                              "--prompt", "read task.md", "--env", "SECRET=do-not-store",
                              "--label", "model=label-model", "--", "claude", "--model", "opus",
                              "--effort", "high", "--unrelated", "do-not-store", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.counter.read_text(), "start\n")
        event = next(e for e in self.events() if e["kind"] == "corral.start")
        self.assertEqual(event["project"], str(self.project.resolve()))
        self.assertEqual(event["data"]["cwd"], str(worktree.resolve()))
        self.assertEqual(self.blob(event["data"]["task_file"]["content"]), content)
        self.assertEqual(event["data"]["agent_parameters"]["model"], "opus")
        self.assertEqual(event["data"]["labels"]["model"], "label-model")
        self.assertIn('"secret_extra"', result.stdout)
        all_bytes = b"".join(p.read_bytes() for p in self.root.rglob("*") if p.is_file())
        self.assertNotIn(b"do-not-store", all_bytes)

    def test_send_and_reply_keep_observation_separate_from_attribution(self):
        dispatch = self.new()
        send = {"ok": True, "name": "dev", "instance": "old", "confirmed": True, "merged_with_draft": True}
        result = self.run_cli("send", "--dispatch", dispatch, "--kind", "rework", "--",
                              str(self.fake), "send", "dev", "fix it", env=dict(self.env, FAKE_OUTPUT=json.dumps(send)))
        self.assertEqual(result.returncode, 0, result.stderr)
        reply = {"ok": True, "name": "dev", "instance": "new", "text": "DONE 中文", "at": 123.5}
        result = self.run_cli("reply", "--dispatch", dispatch, "--", str(self.fake), "reply", "dev",
                              env=dict(self.env, FAKE_OUTPUT=json.dumps(reply)))
        self.assertEqual(result.returncode, 0, result.stderr)
        event = next(e for e in self.events() if e["kind"] == "corral.reply")
        self.assertEqual(event["association"]["source"], "controller_declared")
        self.assertEqual(event["data"]["instance_check"], "mismatch")
        self.assertEqual(self.blob(event["data"]["reply"]), "DONE 中文".encode())
        self.assertEqual(self.counter.read_text(), "send\nreply\n")
        event = next(e for e in self.events() if e["kind"] == "corral.send")
        self.assertFalse(event["data"]["complete_input_known"])

    def test_pending_is_not_delivery_and_failure_is_not_retried(self):
        dispatch = self.new()
        output = '{"ok":true,"instance":"x","pending":true,"after_instance":"y"}\n'
        result = self.run_cli("send", "--dispatch", dispatch, "--", str(self.fake), "send", "dev", "hello",
                              "--after", "other", "--timeout", "60", env=dict(self.env, FAKE_OUTPUT=output.strip()))
        self.assertEqual(result.stdout, output)
        event = next(e for e in self.events() if e["kind"] == "corral.send")
        self.assertEqual(event["data"]["delivery"], "queued")
        result = self.run_cli("reply", "--dispatch", dispatch, "--", str(self.fake), "reply", "dev",
                              env=dict(self.env, FAKE_EXIT="3", FAKE_OUTPUT='{"ok":false,"error":"no_reply"}', FAKE_STDERR="private-stderr"))
        self.assertEqual(result.returncode, 3)
        self.assertIn("private-stderr", result.stderr)
        self.assertEqual(self.counter.read_text(), "send\nreply\n")

    def test_unwritable_store_does_not_repeat_or_hide_command_result(self):
        self.root.write_text("not a directory")
        result = self.run_cli("reply", "--", str(self.fake), "reply", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("记录失败", result.stderr)
        self.assertIn("不要因记录失败重发", result.stderr)
        self.assertEqual(self.counter.read_text(), "reply\n")
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_explicit_review_and_decision_are_controller_statements(self):
        dispatch = self.new()
        result = self.run_cli("decide", "--dispatch", dispatch, "--model", "opus", "--effort", "high",
                              "--budget", "targeted tests", "--reason", "ordinary change")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_cli("note", "--dispatch", dispatch, "--kind", "review", input="review raw\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        event = next(e for e in self.events() if e["kind"] == "controller.note")
        self.assertEqual(event["source"], "controller_statement")
        self.assertEqual(self.blob(event["data"]["content"]), b"review raw\n")

    def test_different_task_parent_rejected_and_no_upstream_called(self):
        dispatch = self.new()
        result = self.run_cli("new", "--project", str(self.project), "--task", "T42", "--parent", dispatch)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.counter.exists())

    def test_records_private_permissions(self):
        dispatch = self.new()
        self.run_cli("note", "--dispatch", dispatch, "--kind", "review", input="private material")
        for p in self.root.rglob("*"):
            self.assertEqual(p.stat().st_mode & 0o077, 0, str(p))

    def test_unassociated_reply_does_not_infer_from_other_unassociated_sends(self):
        self.run_cli("send", "--", str(self.fake), "send", "dev", "hello")
        self.run_cli("reply", "--", str(self.fake), "reply", "dev")
        event = next(e for e in self.events() if e["kind"] == "corral.reply")
        self.assertEqual(event["association"]["source"], "unassociated")
        self.assertEqual(event["data"]["instance_check"], "unknown")

    def test_rework_snapshots_updated_task_before_send(self):
        dispatch = self.new()
        task = self.base / "revised.md"
        task.write_text("new brief")
        result = self.run_cli("send", "--dispatch", dispatch, "--kind", "rework",
                              "--task-file", str(task), "--", str(self.fake), "send", "dev", "read revision",
                              env=dict(self.env, CHANGE_TASK=str(task)))
        self.assertEqual(result.returncode, 0, result.stderr)
        event = next(e for e in self.events() if e["kind"] == "corral.send")
        self.assertEqual(self.blob(event["data"]["task_file"]["content"]), b"new brief")


if __name__ == "__main__":
    unittest.main()
