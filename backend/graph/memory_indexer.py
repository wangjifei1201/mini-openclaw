"""
结构化记忆向量索引器 - 为 memory/memories.jsonl 构建 RAG 检索
"""
import traceback
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import settings
from .memory_store import MemoryStore


class MemoryIndexer:
    """
    结构化记忆向量索引器

    专门为 memory/memories.jsonl 中的 active 记忆构建 LlamaIndex 向量索引。
    """

    STRUCTURED_INDEX_MARKER = "structured_memory_index.marker"
    STRUCTURED_INDEX_VERSION = "structured-memory-v1"

    def __init__(
        self,
        base_dir: Path,
        memory_store: Optional[MemoryStore] = None,
        store: Optional[MemoryStore] = None,
    ):
        self.base_dir = base_dir
        self.memory_store = memory_store or store or MemoryStore(base_dir)
        self.memory_file = base_dir / "memory" / "memories.jsonl"
        self.storage_dir = base_dir / "storage" / "memory_index"
        self.marker_file = self.storage_dir / self.STRUCTURED_INDEX_MARKER
        self._index = None
        self._file_hash: Optional[str] = None

    def _get_file_hash(self) -> Optional[str]:
        """获取结构化记忆文件的 MD5 哈希。"""
        if not self.memory_file.exists():
            return None
        try:
            content = self.memory_file.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return None

    def _maybe_rebuild(self) -> bool:
        """
        检查文件是否变更，变更则自动重建索引。

        Returns:
            是否需要重建
        """
        current_hash = self._get_file_hash()
        if current_hash is None:
            return False

        if self._file_hash != current_hash:
            self._file_hash = current_hash
            return True

        return False

    def _build_memory_documents(self):
        """将 active 结构化记忆转换为 LlamaIndex Document。"""
        try:
            from llama_index.core import Document
        except ImportError:
            class Document:
                def __init__(self, text: str, metadata: Dict[str, Any]):
                    self.text = text
                    self.metadata = metadata

        documents = []
        for record in self.memory_store.list_active():
            text = f"[type: {record['type']}]\n{record['content']}"
            documents.append(
                Document(
                    text=text,
                    metadata={
                        "id": record["id"],
                        "type": record["type"],
                        "source": record["source"],
                    },
                )
            )
        return documents

    def rebuild_index(self) -> bool:
        """
        重建结构化记忆向量索引。

        Returns:
            是否成功
        """
        try:
            documents = self._build_memory_documents()
            if not documents:
                self._index = None
                self._file_hash = self._get_file_hash()
                self.marker_file.unlink(missing_ok=True)
                return False

            from llama_index.core import VectorStoreIndex, Settings as LlamaSettings
            from llama_index.core.node_parser import SentenceSplitter
            from llama_index.embeddings.openai import OpenAIEmbedding

            # 配置 Embedding（使用 model_name 绕过 OpenAI 模型枚举校验，兼容第三方 Embedding 模型）
            embed_model = OpenAIEmbedding(
                model_name=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
                api_base=settings.OPENAI_BASE_URL,
            )
            LlamaSettings.embed_model = embed_model

            splitter = SentenceSplitter(
                chunk_size=256,
                chunk_overlap=32,
            )
            nodes = splitter.get_nodes_from_documents(documents)
            if not nodes:
                self._index = None
                self._file_hash = self._get_file_hash()
                self.marker_file.unlink(missing_ok=True)
                return False

            self._index = VectorStoreIndex(nodes)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._index.storage_context.persist(persist_dir=str(self.storage_dir))
            self.marker_file.write_text(self.STRUCTURED_INDEX_VERSION, encoding="utf-8")
            self._file_hash = self._get_file_hash()
            return True

        except Exception as e:
            print(traceback.format_exc())
            print(f"结构化记忆索引构建失败: {e}")
            return False

    def _has_compatible_persisted_index(self) -> bool:
        """检查持久化索引是否是当前结构化记忆索引格式。"""
        if not self.memory_file.exists():
            return False
        if not self.marker_file.exists():
            return False
        try:
            return self.marker_file.read_text(encoding="utf-8").strip() == self.STRUCTURED_INDEX_VERSION
        except Exception:
            return False

    def _load_index(self) -> bool:
        """加载已有索引。"""
        if self._index is not None:
            return True

        if not self.storage_dir.exists():
            return False

        if not self._has_compatible_persisted_index():
            return False

        try:
            from llama_index.core import (
                StorageContext,
                load_index_from_storage,
                Settings as LlamaSettings,
            )
            from llama_index.embeddings.openai import OpenAIEmbedding

            # 配置 Embedding（使用 model_name 绕过 OpenAI 模型枚举校验，兼容第三方 Embedding 模型）
            embed_model = OpenAIEmbedding(
                model_name=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
                api_base=settings.OPENAI_BASE_URL,
            )
            LlamaSettings.embed_model = embed_model

            storage_context = StorageContext.from_defaults(
                persist_dir=str(self.storage_dir)
            )
            self._index = load_index_from_storage(storage_context)
            self._file_hash = self._get_file_hash()
            return True

        except Exception:
            return False

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        语义检索结构化记忆。

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表 [{"id": ..., "type": ..., "text": ..., "score": ..., "source": ...}, ...]
        """
        # 缺失结构化记忆文件等同于空记忆列表，不加载旧的持久化索引。
        if not self.memory_file.exists():
            self._index = None
            self._file_hash = None
            return []

        # 检查文件变更
        if self._maybe_rebuild():
            self.rebuild_index()

        # 尝试加载索引
        if self._index is None:
            if not self._load_index():
                # 索引不存在，尝试构建
                if not self.rebuild_index():
                    return []

        try:
            retriever = self._index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)

            results = []
            for node in nodes:
                metadata = getattr(node, "metadata", {}) or {}
                results.append({
                    "id": metadata.get("id", ""),
                    "type": metadata.get("type", ""),
                    "text": node.get_content(),
                    "score": getattr(node, "score", 0),
                    "source": metadata.get("source", "auto"),
                })

            return results

        except Exception as e:
            print(f"结构化记忆检索失败: {e}")
            return []

    def format_active_memory_context(self, limit: int = 20) -> str:
        """格式化 active 结构化记忆为对话上下文。"""
        records = sorted(
            self.memory_store.list_active(),
            key=lambda record: 0 if record["type"] == "preference" else 1,
        )[:limit]
        if not records:
            return ""

        lines = [
            "[长期结构化记忆]",
            "以下是用户长期偏好和项目上下文。preference 类型记忆代表用户最新偏好，优先级高于静态用户画像。除非用户本轮明确提出相反要求，否则必须遵循这些记忆；用户仅使用某种语言提问不代表要求使用该语言回答。",
        ]
        for i, record in enumerate(records, 1):
            lines.append(f"\n【记忆 {i}】(类型: {record['type']}, id: {record['id']})")
            lines.append(record["content"])

        return "\n".join(lines)

    def format_retrieval_context(self, results: List[Dict[str, Any]]) -> str:
        """格式化结构化记忆检索结果为上下文字符串。"""
        if not results:
            return ""

        lines = ["[结构化记忆检索结果]"]
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            memory_type = r.get("type", "unknown")
            memory_id = r.get("id", "")
            lines.append(f"\n【记忆 {i}】(类型: {memory_type}, 相关度: {score:.2f}, id: {memory_id})")
            lines.append(r.get("text", ""))

        return "\n".join(lines)
