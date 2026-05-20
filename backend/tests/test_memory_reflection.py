import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import HumanMessage, SystemMessage

from graph.memory_reflection import MemoryReflectionService, parse_reflection_operations
from graph.memory_store import MemoryStore


class MemoryReflectionTests(unittest.IsolatedAsyncioTestCase):
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

    def test_parse_operations_drops_missing_required_fields(self):
        payload = '''
        {
          "operations": [
            {"action": "ADD", "type": "preference", "confidence": 0.9},
            {"action": "UPDATE", "type": "project", "content": "缺少 ID", "confidence": 0.9},
            {"action": "DELETE", "confidence": 0.9}
          ]
        }
        '''

        operations = parse_reflection_operations(payload)

        self.assertEqual(operations, [])

    def test_parse_operations_drops_non_numeric_and_nan_confidence(self):
        payload = '''
        {
          "operations": [
            {"action": "ADD", "type": "preference", "content": "非数字", "confidence": "high"},
            {"action": "ADD", "type": "preference", "content": "NaN", "confidence": NaN}
          ]
        }
        '''

        operations = parse_reflection_operations(payload)

        self.assertEqual(operations, [])

    def test_parse_operations_keeps_valid_none_in_mixed_payload(self):
        payload = '''
        {
          "operations": [
            {"action": "ADD", "type": "preference", "confidence": 0.9},
            {"action": "NONE"}
          ]
        }
        '''

        operations = parse_reflection_operations(payload)

        self.assertEqual(operations, [{"action": "NONE"}])

    async def test_reflect_invokes_llm_with_context_applies_operation_and_returns_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            existing = store.add_memory(
                memory_type="preference",
                content="用户偏好简洁回答。",
                source="manual",
                confidence=0.9,
            )
            llm = SimpleNamespace(
                ainvoke=AsyncMock(
                    return_value=SimpleNamespace(
                        content='''{"operations":[{"action":"ADD","type":"feedback","content":"用户确认方案可行。","confidence":0.88}]}'''
                    )
                )
            )
            service = MemoryReflectionService(store=store, llm=llm)

            changed = await service.reflect("请保持简洁", "已按简洁风格回复。")

            self.assertTrue(changed)
            llm.ainvoke.assert_awaited_once()
            messages = llm.ainvoke.await_args.args[0]
            self.assertEqual(len(messages), 2)
            self.assertIsInstance(messages[0], SystemMessage)
            self.assertIsInstance(messages[1], HumanMessage)
            human_prompt = messages[1].content
            self.assertIn(existing["content"], human_prompt)
            self.assertIn("请保持简洁", human_prompt)
            self.assertIn("已按简洁风格回复。", human_prompt)
            records = store.list_active()
            self.assertEqual(len(records), 2)
            self.assertEqual(records[1]["type"], "feedback")
            self.assertEqual(records[1]["content"], "用户确认方案可行。")

    async def test_reflect_returns_false_when_llm_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError("LLM unavailable")))
            service = MemoryReflectionService(store=MemoryStore(Path(tmpdir)), llm=llm)

            changed = await service.reflect("用户消息", "助手回复")

            self.assertFalse(changed)
            llm.ainvoke.assert_awaited_once()

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
