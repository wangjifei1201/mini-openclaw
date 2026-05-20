"""
System Prompt 组装器 - 动态拼接 6 个 Markdown 文件
"""
from pathlib import Path
from typing import Optional
from config import settings, get_rag_mode


class PromptBuilder:
    """
    System Prompt 组装器
    
    按固定顺序拼接 6 个 Markdown 文件为完整的 System Prompt
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.workspace_dir = base_dir / "workspace"
        self.memory_dir = base_dir / "memory"
        self.max_length = settings.MAX_CONTENT_LENGTH
    
    def _read_file(self, path: Path, label: str) -> str:
        """
        读取文件内容并添加标签
        
        Args:
            path: 文件路径
            label: 标签名称
            
        Returns:
            带标签的文件内容
        """
        if not path.exists():
            return ""
        
        try:
            content = path.read_text(encoding="utf-8")
            
            # 截断过长内容
            if len(content) > self.max_length:
                content = content[:self.max_length] + "\n...[truncated]"
            
            return f"<!-- {label} -->\n{content}"
        except Exception:
            return ""
    
    def build_system_prompt(self, rag_mode: Optional[bool] = None) -> str:
        """
        构建完整的 System Prompt
        
        Args:
            rag_mode: RAG 模式开关（None 表示使用配置）
            
        Returns:
            完整的 System Prompt
        """
        if rag_mode is None:
            rag_mode = get_rag_mode()
        
        parts = []
        
        # 1. SKILLS_SNAPSHOT.md (能力列表)
        skills_snapshot = self._read_file(
            self.base_dir / "SKILLS_SNAPSHOT.md",
            "Skills Snapshot"
        )
        if skills_snapshot:
            parts.append(skills_snapshot)
        
        # 2. SOUL.md (核心设定)
        soul = self._read_file(
            self.workspace_dir / "SOUL.md",
            "Soul"
        )
        if soul:
            parts.append(soul)
        
        # 3. IDENTITY.md (自我认知)
        identity = self._read_file(
            self.workspace_dir / "IDENTITY.md",
            "Identity"
        )
        if identity:
            parts.append(identity)
        
        # 4. USER.md (用户画像)
        user = self._read_file(
            self.workspace_dir / "USER.md",
            "User Profile"
        )
        if user:
            parts.append(user)
        
        # 5. AGENTS.md (行为准则 & 记忆操作指南)
        agents = self._read_file(
            self.workspace_dir / "AGENTS.md",
            "Agents Guide"
        )
        if agents:
            parts.append(agents)
        
        # 6. MEMORY.md (长期记忆) 或 RAG 引导语
        if rag_mode:
            # RAG 模式下跳过 MEMORY.md，添加引导语
            rag_guide = """<!-- Long-term Memory (RAG Mode) -->
## 记忆检索模式

当前已启用 RAG 记忆检索模式。你的长期记忆将通过语义检索动态注入到对话中。
当你需要回忆过去的信息时，相关的记忆片段会自动出现在对话历史中。
"""
            parts.append(rag_guide)
        else:
            memory = self._read_file(
                self.memory_dir / "MEMORY.md",
                "Long-term Memory"
            )
            if memory:
                parts.append(memory)
        
        interaction_guide = """<!-- Interactive Chat Cards -->
## 交互卡片友好输出

当回答适合用户继续选择下一步时，请在正文末尾用自然语言列出 2-3 个明确的下一步选项。
如果回答中存在多个可选方案，请用清晰的编号或小标题描述每个方案。
不要输出 JSON、HTML、按钮代码或任何前端协议字段。
交互卡片由系统根据你的自然语言回答自动生成。
"""
        parts.append(interaction_guide)

        return "\n\n".join(parts)
    
    def get_system_prompt_tokens(self) -> int:
        """
        获取 System Prompt 的 Token 数量
        
        Returns:
            Token 数量
        """
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            prompt = self.build_system_prompt()
            return len(encoding.encode(prompt))
        except Exception:
            return 0
