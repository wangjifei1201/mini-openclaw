import json
import tempfile
import unittest
from pathlib import Path

from graph.memory_store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_missing_file_loads_empty_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            self.assertEqual(store.list_all(), [])
            self.assertEqual(store.list_active(), [])

    def test_add_memory_writes_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            record = store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )

            self.assertTrue(record["id"].startswith("mem_"))
            self.assertEqual(record["type"], "preference")
            self.assertEqual(record["content"], "用户希望回答简洁直接。")
            self.assertEqual(record["status"], "active")
            self.assertEqual(record["source"], "auto")
            self.assertEqual(record["confidence"], 0.86)
            self.assertIn("created_at", record)
            self.assertIn("updated_at", record)

            persisted = (Path(tmpdir) / "memory" / "memories.jsonl").read_text(encoding="utf-8")
            persisted_record = json.loads(persisted.strip())
            self.assertEqual(persisted_record["id"], record["id"])

    def test_update_memory_changes_content_and_updated_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            record = store.add_memory(
                memory_type="project",
                content="旧项目约束。",
                source="manual",
                confidence=0.9,
            )

            updated = store.update_memory(
                record["id"],
                memory_type="project",
                content="新项目约束。",
                confidence=0.95,
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated["content"], "新项目约束。")
            self.assertEqual(updated["confidence"], 0.95)
            self.assertGreaterEqual(updated["updated_at"], record["updated_at"])
            self.assertEqual(store.list_all()[0]["content"], "新项目约束。")

    def test_delete_memory_marks_deleted_and_excludes_from_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            record = store.add_memory(
                memory_type="reference",
                content="Grafana 看板用于请求延迟排查。",
                source="manual",
                confidence=1.0,
            )

            deleted = store.delete_memory(record["id"])

            self.assertIsNotNone(deleted)
            self.assertEqual(deleted["status"], "deleted")
            self.assertEqual(len(store.list_all()), 1)
            self.assertEqual(store.list_active(), [])

    def test_invalid_jsonl_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            memory_dir.mkdir(parents=True)
            memory_file = memory_dir / "memories.jsonl"
            memory_file.write_text(
                "not-json\n"
                + json.dumps(
                    {
                        "id": "mem_valid",
                        "type": "feedback",
                        "content": "用户确认这个流程正确。",
                        "status": "active",
                        "source": "manual",
                        "confidence": 0.8,
                        "created_at": "2026-05-19T12:00:00",
                        "updated_at": "2026-05-19T12:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            store = MemoryStore(Path(tmpdir))

            self.assertEqual(len(store.list_all()), 1)
            self.assertEqual(store.list_all()[0]["id"], "mem_valid")

    def test_invalid_records_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            memory_dir.mkdir(parents=True)
            memory_file = memory_dir / "memories.jsonl"
            memory_file.write_text(
                json.dumps(
                    {
                        "id": "mem_bad",
                        "type": "unknown",
                        "content": "bad",
                        "status": "active",
                        "source": "manual",
                        "confidence": 0.8,
                        "created_at": "2026-05-19T12:00:00",
                        "updated_at": "2026-05-19T12:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            store = MemoryStore(Path(tmpdir))

            self.assertEqual(store.list_all(), [])


if __name__ == "__main__":
    unittest.main()
