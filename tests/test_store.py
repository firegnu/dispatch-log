from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from dispatch_log.store import Store


class StoreTests(unittest.TestCase):
    def test_concurrent_events_do_not_overwrite_and_blobs_remain_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(Path(temporary) / "records")
            context = store.create(temporary, "T1")

            def write(index):
                return store.event(context["dispatch_id"], context, "test", {
                    "index": index, "content": store.blob("same raw text")})

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(write, range(32)))
            events = store.events(context["dispatch_id"])
            self.assertEqual({e["data"]["index"] for e in events}, set(range(32)))
            for event in events:
                self.assertEqual(store.read_blob(event["data"]["content"]["sha256"]), b"same raw text")
            self.assertEqual(list(store.root.rglob(".tmp-*")), [])

    def test_invalid_context_fails_explicitly_without_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(temporary)
            with self.assertRaises(ValueError):
                store.get("../outside")
            context = store.create(temporary, "T1")
            path = store.root / "dispatches" / (context["dispatch_id"] + ".json")
            path.write_text(json.dumps([]))
            with self.assertRaises(ValueError):
                store.get(context["dispatch_id"])
