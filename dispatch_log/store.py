"""Local immutable events and content snapshots; no service or global state."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, content):
    # mkdir(parents=True) uses default modes for intermediate directories.
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def create(self, project, task, kind="initial", parent=None):
        project = str(Path(project).expanduser().resolve())
        if parent:
            record = self.get(parent)
            if (record["project"], record["task"]) != (project, task):
                raise ValueError("parent 必须属于同一项目和任务")
        record = {"schema_version": 1, "dispatch_id": uuid.uuid4().hex,
                  "project": project, "task": task, "kind": kind,
                  "parent": parent, "created_at": now(), "source": "controller_declared"}
        atomic_write(self.root / "dispatches" / (record["dispatch_id"] + ".json"), encoded(record))
        return record

    def get(self, dispatch):
        if not re.fullmatch(r"[a-f0-9]{32}", dispatch):
            raise ValueError("无效 dispatch_id")
        record = json.loads((self.root / "dispatches" / (dispatch + ".json")).read_bytes())
        if (not isinstance(record, dict) or record.get("schema_version") != 1
                or record.get("dispatch_id") != dispatch
                or not isinstance(record.get("project"), str) or not isinstance(record.get("task"), str)):
            raise ValueError("无效派发记录")
        return record

    def list(self, project=None, task=None):
        project = str(Path(project).expanduser().resolve()) if project else None
        rows = [self.get(p.stem) for p in (self.root / "dispatches").glob("*.json")]
        return sorted((r for r in rows if (not project or r["project"] == project)
                       and (not task or r["task"] == task)), key=lambda r: r["created_at"])

    def events(self, dispatch):
        rows = [json.loads(p.read_bytes()) for p in (self.root / "events").glob("*.json")]
        for row in rows:
            if (not isinstance(row, dict) or row.get("schema_version") != 1
                    or not isinstance(row.get("data"), dict)
                    or not all(key in row for key in ("dispatch_id", "kind", "observed_at", "event_id"))):
                raise ValueError("无效事件记录")
        return sorted((r for r in rows if r["dispatch_id"] == dispatch),
                      key=lambda r: (r["observed_at"], r["event_id"]))

    def blob(self, content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        atomic_write(self.root / "blobs" / "sha256" / digest[:2] / digest, content)
        return {"sha256": digest, "bytes": len(content)}

    def read_blob(self, digest):
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("无效 sha256")
        content = (self.root / "blobs" / "sha256" / digest[:2] / digest).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("内容哈希不匹配")
        return content

    def event(self, dispatch, context, kind, data, source="recorder_observation"):
        event = {"schema_version": 1, "event_id": uuid.uuid4().hex, "observed_at": now(),
                 "dispatch_id": dispatch, "project": context.get("project"),
                 "task": context.get("task"), "kind": kind, "source": source,
                 "association": {"source": "controller_declared" if dispatch else "unassociated",
                                 "context_found": bool(context)}, "data": data}
        atomic_write(self.root / "events" / (event["event_id"] + ".json"), encoded(event))
        return event
