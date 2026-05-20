import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from graph.memory_store import MemoryStore


class MemoriesApiTests(unittest.TestCase):
    def test_list_memories_returns_stable_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )

            with patch("api.memories.agent_manager") as mock_agent_manager:
                mock_agent_manager.memory_store = store
                from api.memories import list_memories

                result = asyncio.run(list_memories())

            self.assertEqual(len(result["memories"]), 1)
            memory = result["memories"][0]
            self.assertEqual(memory["type"], "preference")
            self.assertEqual(memory["content"], "用户希望回答简洁直接。")
            self.assertEqual(memory["status"], "active")
            self.assertEqual(memory["source"], "auto")
            self.assertEqual(memory["confidence"], 0.86)
            self.assertIn("id", memory)
            self.assertIn("created_at", memory)
            self.assertIn("updated_at", memory)

    def test_list_memories_returns_empty_when_memory_store_missing(self):
        with patch("api.memories.agent_manager") as mock_agent_manager:
            mock_agent_manager.memory_store = None
            from api.memories import list_memories

            result = asyncio.run(list_memories())

        self.assertEqual(result, {"memories": []})

    def test_memories_router_is_exported(self):
        from api import memories_router

        self.assertIsNotNone(memories_router)

    def test_app_registers_memories_route(self):
        import app

        routes = [getattr(route, "path", "") for route in app.app.routes]

        self.assertIn("/api/memories", routes)

    def test_http_get_memories_returns_store_records(self):
        import app

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            store.add_memory(
                memory_type="project",
                content="用户正在维护结构化记忆接口。",
                source="manual",
                confidence=0.91,
            )

            with patch("api.memories.agent_manager") as mock_agent_manager:
                mock_agent_manager.memory_store = store
                response = TestClient(app.app).get("/api/memories")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["memories"]), 1)
        memory = payload["memories"][0]
        self.assertEqual(memory["type"], "project")
        self.assertEqual(memory["content"], "用户正在维护结构化记忆接口。")
        self.assertEqual(memory["status"], "active")
        self.assertEqual(memory["source"], "manual")
        self.assertEqual(memory["confidence"], 0.91)

    def test_saving_memories_jsonl_rebuilds_memory_index(self):
        from api.files import SaveFileRequest, save_file

        for path in ("memory/memories.jsonl", "./memory/memories.jsonl"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmpdir:
                with patch("api.files.BASE_DIR", Path(tmpdir)), patch("api.files.agent_manager") as mock_agent_manager:
                    mock_indexer = MagicMock()
                    mock_agent_manager.memory_indexer = mock_indexer

                    result = asyncio.run(
                        save_file(SaveFileRequest(path=path, content=""))
                    )

                self.assertEqual(result, {"success": True, "path": path})
                mock_indexer.rebuild_index.assert_called_once_with()

    def test_rebuild_trigger_normalizes_slash_prefixed_memory_path(self):
        from api.files import _memory_rebuild_trigger_path

        self.assertEqual(_memory_rebuild_trigger_path("/memory/memories.jsonl"), "memory/memories.jsonl")


if __name__ == "__main__":
    unittest.main()
