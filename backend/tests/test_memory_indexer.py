import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.agent import AgentManager
from graph.memory_indexer import MemoryIndexer
from graph.memory_store import MemoryStore


class MemoryIndexerTests(unittest.TestCase):
    def test_build_memory_documents_uses_only_active_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            active = store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )
            deleted = store.add_memory(
                memory_type="project",
                content="已删除项目记忆。",
                source="manual",
                confidence=0.9,
            )
            store.delete_memory(deleted["id"])
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)

            docs = indexer._build_memory_documents()

            self.assertEqual(len(docs), 1)
            self.assertIn("[type: preference]", docs[0].text)
            self.assertIn("用户希望回答简洁直接。", docs[0].text)
            self.assertEqual(docs[0].metadata["id"], active["id"])
            self.assertEqual(docs[0].metadata["type"], "preference")
            self.assertEqual(docs[0].metadata["source"], "auto")

    def test_hash_changes_when_structured_memory_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)

            before = indexer._get_file_hash()
            store.add_memory(
                memory_type="feedback",
                content="用户确认这个流程正确。",
                source="manual",
                confidence=0.9,
            )
            after = indexer._get_file_hash()

            self.assertIsNone(before)
            self.assertIsNotNone(after)

    def test_rebuild_index_without_active_documents_clears_index_hash_and_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            record = store.add_memory(
                memory_type="project",
                content="已删除项目记忆。",
                source="manual",
                confidence=0.9,
            )
            store.delete_memory(record["id"])
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)
            indexer._index = object()
            indexer.storage_dir.mkdir(parents=True, exist_ok=True)
            indexer.marker_file.write_text(indexer.STRUCTURED_INDEX_VERSION, encoding="utf-8")

            rebuilt = indexer.rebuild_index()

            self.assertFalse(rebuilt)
            self.assertIsNone(indexer._index)
            self.assertEqual(indexer._file_hash, indexer._get_file_hash())
            self.assertFalse(indexer.marker_file.exists())

    def test_retrieve_returns_structured_records_from_node_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))
            indexer.memory_file.parent.mkdir(parents=True, exist_ok=True)
            indexer.memory_file.write_text("", encoding="utf-8")
            indexer._file_hash = indexer._get_file_hash()
            node = MagicMock()
            node.metadata = {"id": "mem_1", "type": "preference", "source": "auto"}
            node.score = 0.82
            node.get_content.return_value = "[type: preference]\n用户希望回答简洁直接。"
            retriever = MagicMock()
            retriever.retrieve.return_value = [node]
            indexer._index = MagicMock()
            indexer._index.as_retriever.return_value = retriever

            results = indexer.retrieve("偏好", top_k=1)

            self.assertEqual(
                results,
                [
                    {
                        "id": "mem_1",
                        "type": "preference",
                        "text": "[type: preference]\n用户希望回答简洁直接。",
                        "score": 0.82,
                        "source": "auto",
                    }
                ],
            )
            indexer._index.as_retriever.assert_called_once_with(similarity_top_k=1)

    def test_retrieve_returns_empty_when_index_build_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))
            indexer._load_index = MagicMock(return_value=False)
            indexer.rebuild_index = MagicMock(return_value=False)

            results = indexer.retrieve("偏好")

            self.assertEqual(results, [])

    def test_retrieve_missing_memory_file_returns_empty_without_loading_stale_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))
            indexer.storage_dir.mkdir(parents=True, exist_ok=True)
            indexer.marker_file.write_text(indexer.STRUCTURED_INDEX_VERSION, encoding="utf-8")
            indexer._load_index = MagicMock(return_value=True)
            indexer.rebuild_index = MagicMock(return_value=True)

            results = indexer.retrieve("偏好")

            self.assertEqual(results, [])
            self.assertIsNone(indexer._index)
            self.assertIsNone(indexer._file_hash)
            indexer._load_index.assert_not_called()
            indexer.rebuild_index.assert_not_called()

    def test_load_index_rejects_missing_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)
            indexer.storage_dir.mkdir(parents=True, exist_ok=True)

            with patch("graph.memory_indexer.settings"):
                loaded = indexer._load_index()

            self.assertFalse(loaded)
            self.assertIsNone(indexer._index)

    def test_load_index_rejects_wrong_marker_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)
            indexer.storage_dir.mkdir(parents=True, exist_ok=True)
            indexer.marker_file.write_text("legacy-memory-index", encoding="utf-8")

            loaded = indexer._load_index()

            self.assertFalse(loaded)
            self.assertIsNone(indexer._index)

    def test_load_index_rejects_valid_marker_when_memory_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))
            indexer.storage_dir.mkdir(parents=True, exist_ok=True)
            indexer.marker_file.write_text(indexer.STRUCTURED_INDEX_VERSION, encoding="utf-8")

            loaded = indexer._load_index()

            self.assertFalse(loaded)
            self.assertIsNone(indexer._index)

    def test_format_retrieval_context_uses_memory_record_labels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))

            context = indexer.format_retrieval_context(
                [
                    {
                        "id": "mem_1",
                        "type": "preference",
                        "text": "用户希望回答简洁直接。",
                        "score": 0.82,
                        "source": "auto",
                    }
                ]
            )

            self.assertIn("[结构化记忆检索结果]", context)
            self.assertIn("【记忆 1】", context)
            self.assertIn("类型: preference", context)
            self.assertIn("相关度: 0.82", context)
            self.assertIn("id: mem_1", context)
            self.assertIn("用户希望回答简洁直接。", context)

    def test_format_active_memory_context_uses_active_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            active = store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )
            deleted = store.add_memory(
                memory_type="project",
                content="已删除项目记忆。",
                source="manual",
                confidence=0.9,
            )
            store.delete_memory(deleted["id"])
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)

            context = indexer.format_active_memory_context()

            self.assertIn("[长期结构化记忆]", context)
            self.assertIn(active["id"], context)
            self.assertIn("类型: preference", context)
            self.assertIn("用户希望回答简洁直接。", context)
            self.assertNotIn("已删除项目记忆。", context)

    def test_format_active_memory_context_prioritizes_preference_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            project = store.add_memory(
                memory_type="project",
                content="当前项目需要生成招标文件分析。",
                source="auto",
                confidence=0.8,
            )
            preference = store.add_memory(
                memory_type="preference",
                content="用户偏好后续交流统一使用英文回答，不论其输入语言。",
                source="auto",
                confidence=0.99,
            )
            indexer = MemoryIndexer(Path(tmpdir), memory_store=store)

            context = indexer.format_active_memory_context()

            self.assertIn("preference 类型记忆代表用户最新偏好，优先级高于静态用户画像", context)
            self.assertLess(context.index(preference["content"]), context.index(project["content"]))

    def test_agent_build_messages_preserves_system_memory_context(self):
        manager = AgentManager()

        messages = manager._build_messages([
            {
                "role": "system",
                "content": "[长期结构化记忆]\n用户希望回答简洁直接。",
            }
        ])

        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIn("用户希望回答简洁直接。", messages[0].content)

    def test_init_accepts_task3_store_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            indexer = MemoryIndexer(Path(tmpdir), store=store)

            self.assertIs(indexer.memory_store, store)

    def test_format_session_output_context_includes_session_scoped_paths(self):
        manager = AgentManager()
        session_id = "123e4567-e89b-12d3-a456-426614174000"

        context = manager._format_session_output_context(session_id)

        self.assertIn(f"当前会话 ID: {session_id}", context)
        self.assertIn(f"outputs/{session_id}/", context)
        self.assertIn(f"/outputs/{session_id}/<filename>", context)
        self.assertIn("不要写入 outputs/ 根目录", context)

    def test_build_messages_injects_session_output_context_before_user_message(self):
        manager = AgentManager()
        session_id = "123e4567-e89b-12d3-a456-426614174000"

        messages = manager._build_messages(
            [
                {"role": "user", "content": "生成 PDF"},
            ],
            session_id=session_id,
        )

        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIn(f"outputs/{session_id}/", messages[0].content)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(messages[1].content, "生成 PDF")

    def test_build_messages_preserves_order_with_session_context_and_existing_history(self):
        manager = AgentManager()
        session_id = "session-ordering"

        messages = manager._build_messages(
            [
                {"role": "system", "content": "existing system instruction"},
                {"role": "user", "content": "previous user message"},
                {"role": "assistant", "content": "previous assistant response"},
            ],
            session_id=session_id,
        )

        self.assertEqual(len(messages), 4)
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIn(f"outputs/{session_id}/", messages[0].content)
        self.assertIsInstance(messages[1], SystemMessage)
        self.assertEqual(messages[1].content, "existing system instruction")
        self.assertIsInstance(messages[2], HumanMessage)
        self.assertEqual(messages[2].content, "previous user message")
        self.assertIsInstance(messages[3], AIMessage)
        self.assertEqual(messages[3].content, "previous assistant response")

    def test_build_messages_with_session_context_does_not_mutate_history(self):
        manager = AgentManager()
        history = [
            {"role": "system", "content": "existing system instruction"},
            {"role": "user", "content": "生成 PDF"},
        ]
        original_history = [dict(item) for item in history]

        manager._build_messages(history, session_id="session-no-mutation")

        self.assertEqual(history, original_history)

    def test_astream_passes_session_id_to_build_messages_and_input_state_has_session_context(self):
        class FakeAgent:
            def __init__(self):
                self.input_state = None

            async def astream_events(self, input_state, config=None, version=None):
                self.input_state = input_state
                return
                yield

        manager = AgentManager()
        fake_agent = FakeAgent()
        session_id = "session-astream"
        history = [{"role": "user", "content": "previous request"}]
        manager.memory_indexer = MagicMock()
        manager.memory_indexer.format_active_memory_context.return_value = ""
        manager._build_agent = MagicMock(return_value=fake_agent)
        original_build_messages = manager._build_messages
        manager._build_messages = MagicMock(wraps=original_build_messages)

        events = asyncio.run(_collect_async(manager.astream("生成 PDF", session_id=session_id, history=history)))

        manager._build_messages.assert_called_once_with(history, session_id=session_id)
        self.assertEqual(events[-1]["type"], "done")
        messages = fake_agent.input_state["messages"]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIn(f"outputs/{session_id}/", messages[0].content)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(messages[1].content, "previous request")
        self.assertIsInstance(messages[2], HumanMessage)
        self.assertEqual(messages[2].content, "生成 PDF")


async def _collect_async(async_iterable):
    return [item async for item in async_iterable]


if __name__ == "__main__":
    unittest.main()
