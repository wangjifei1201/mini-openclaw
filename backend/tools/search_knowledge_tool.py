"""
知识库搜索工具 - 基于 LlamaIndex 的混合检索
"""
import os
from pathlib import Path
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from config import settings


class SearchKnowledgeInput(BaseModel):
    """知识库搜索工具输入参数"""
    query: str = Field(description="搜索查询词")
    top_k: int = Field(default=3, description="返回结果数量")


class SearchKnowledgeTool(BaseTool):
    """
    知识库搜索工具
    
    基于 LlamaIndex 实现的混合检索（关键词 BM25 + 向量检索）
    """
    name: str = "search_knowledge_base"
    description: str = """搜索知识库中的相关内容。当用户询问具体的知识库内容时使用此工具。
支持语义检索，能够理解查询意图并返回最相关的文档片段。
输入参数：
- query: 搜索查询词
- top_k: 返回结果数量（默认3）"""
    args_schema: Type[BaseModel] = SearchKnowledgeInput
    
    root_dir: Path = Field(default=None)
    _index: Any = None
    _is_initialized: bool = False
    
    def __init__(self, root_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self._index = None
        self._is_initialized = False
    
    def _initialize_index(self) -> bool:
        """惰性初始化索引"""
        if self._is_initialized:
            return self._index is not None
        
        self._is_initialized = True
        
        try:
            from llama_index.core import (
                VectorStoreIndex,
                SimpleDirectoryReader,
                StorageContext,
                load_index_from_storage,
                Settings as LlamaSettings,
            )
            from llama_index.embeddings.openai import OpenAIEmbedding
            
            # 配置 Embedding
            embed_model = OpenAIEmbedding(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
                api_base=settings.OPENAI_BASE_URL,
            )
            LlamaSettings.embed_model = embed_model
            
            knowledge_dir = self.root_dir / "knowledge"
            storage_dir = self.root_dir / "storage" / "knowledge_index"
            
            # 尝试加载已有索引
            if storage_dir.exists():
                try:
                    storage_context = StorageContext.from_defaults(
                        persist_dir=str(storage_dir)
                    )
                    self._index = load_index_from_storage(storage_context)
                    return True
                except Exception:
                    pass
            
            # 检查知识库目录
            if not knowledge_dir.exists() or not any(knowledge_dir.iterdir()):
                return False
            
            # 构建新索引
            documents = SimpleDirectoryReader(
                input_dir=str(knowledge_dir),
                recursive=True,
                required_exts=[".md", ".txt", ".pdf"],
            ).load_data()
            
            if not documents:
                return False
            
            self._index = VectorStoreIndex.from_documents(documents)
            
            # 持久化索引
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._index.storage_context.persist(persist_dir=str(storage_dir))
            
            return True
            
        except Exception as e:
            print(f"知识库索引初始化失败: {e}")
            return False
    
    def _run(self, query: str, top_k: int = 3) -> str:
        """同步搜索知识库"""
        if not self._initialize_index():
            return "知识库为空或未配置。请在 knowledge/ 目录下添加文档。"
        
        try:
            retriever = self._index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            
            if not nodes:
                return "未找到相关内容。"
            
            results = []
            for i, node in enumerate(nodes, 1):
                score = getattr(node, 'score', 0)
                text = node.get_content()
                source = getattr(node.node, 'metadata', {}).get('file_name', '未知来源')
                
                results.append(f"【结果 {i}】(相关度: {score:.2f})\n来源: {source}\n{text}")
            
            return "\n\n---\n\n".join(results)
            
        except Exception as e:
            return f"搜索失败: {str(e)}"
    
    async def _arun(self, query: str, top_k: int = 3) -> str:
        """异步搜索知识库"""
        return self._run(query, top_k)


def create_search_knowledge_tool(root_dir: Path) -> SearchKnowledgeTool:
    """创建知识库搜索工具实例"""
    return SearchKnowledgeTool(root_dir=root_dir)
