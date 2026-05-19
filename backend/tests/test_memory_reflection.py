import tempfile
import unittest
from pathlib import Path

from graph.memory_reflection import MemoryReflectionService, parse_reflection_operations
from graph.memory_store import MemoryStore


class MemoryReflectionTests(unittest.TestCase):
    def test_parse_operations_accepts_valid_json_object(self):
        payload = '''
        {
          "operations": [
            {
              "action": "ADD",
              "type": "preference",
              "content": "用户希望回答简洁直接。",
              "confidence": 0.86
            }
          ]
        }
        '''

        operations = parse_reflection_operations(payload)

        self.assertEqual(
            operations,
            [
                {
                    "action": "ADD",
                    "type": "preference",
                    "content": "用户希望回答简洁直接。",
                    "confidence": 0.86,
                }
            ],
        )

    def test_parse_operations_extracts_json_from_markdown_fence(self):
        payload = '''```json
        {"operations":[{"action":"NONE"}]}
        ```'''

        operations = parse_reflection_operations(payload)

        self.assertEqual(operations, [{"action": "NONE"}])

    def test_parse_operations_drops_invalid_actions_and_low_confidence(self):
        payload = '''
        {
          "operations": [
            {"action": "ADD", "type": "preference", "content": "低置信度", "confidence": 0.3},
            {"action": "UPSERT", "type": "preference", "content": "错误动作", "confidence": 0.9},
            {"action": "ADD", "type": "unknown", "content": "错误类型", "confidence": 0.9}
          ]
        }
        '''

        operations = parse_reflection_operations(payload)

        self.assertEqual(operations, [])

    def test_apply_add_update_delete_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            existing = store.add_memory(
                memory_type="preference",
                content="旧偏好。",
                source="manual",
                confidence=0.9,
            )
            service = MemoryReflectionService(store=store, llm=None)

            changed = service.apply_operations(
                [
                    {
                        "action": "ADD",
                        "type": "project",
                        "content": "项目使用结构化记忆。",
                        "confidence": 0.88,
                    },
                    {
                        "action": "UPDATE",
                        "id": existing["id"],
                        "type": "preference",
                        "content": "新偏好。",
                        "confidence": 0.91,
                    },
                    {
                        "action": "DELETE",
                        "id": existing["id"],
                        "confidence": 0.95,
                    },
                ]
            )

            records = store.list_all()
            self.assertTrue(changed)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["content"], "新偏好。")
            self.assertEqual(records[0]["status"], "deleted")
            self.assertEqual(records[1]["content"], "项目使用结构化记忆。")
            self.assertEqual(records[1]["status"], "active")

    def test_apply_none_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = MemoryReflectionService(store=MemoryStore(Path(tmpdir)), llm=None)

            changed = service.apply_operations([{"action": "NONE"}])

            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
