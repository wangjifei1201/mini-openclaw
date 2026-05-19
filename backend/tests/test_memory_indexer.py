import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_rebuild_index_without_active_documents_clears_index_and_updates_hash(self):
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

            rebuilt = indexer.rebuild_index()

            self.assertFalse(rebuilt)
            self.assertIsNone(indexer._index)
            self.assertEqual(indexer._file_hash, indexer._get_file_hash())

    def test_retrieve_returns_structured_records_from_node_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MemoryIndexer(Path(tmpdir), memory_store=MemoryStore(Path(tmpdir)))
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

    def test_init_accepts_task3_store_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            indexer = MemoryIndexer(Path(tmpdir), store=store)

            self.assertIs(indexer.memory_store, store)


if __name__ == "__main__":
    unittest.main()
