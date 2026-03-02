"""
会话管理器 - JSON 文件持久化会话历史
"""
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import settings


# UUID v4 格式校验正则
_UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


class SessionManager:
    """
    会话持久化管理器
    
    以 JSON 文件管理每个会话的完整历史
    """
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        (self.sessions_dir / "archive").mkdir(exist_ok=True)
    
    def _validate_session_id(self, session_id: str) -> bool:
        """验证 session_id 是否为合法 UUID 格式"""
        if not session_id or not isinstance(session_id, str):
            return False
        return bool(_UUID_PATTERN.match(session_id))
    
    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        if not self._validate_session_id(session_id):
            raise ValueError(f"非法的会话ID格式: {session_id}")
        return self.sessions_dir / f"{session_id}.json"
    
    def _read_file(self, session_id: str) -> Dict[str, Any]:
        """读取会话文件"""
        path = self._get_session_path(session_id)
        if not path.exists():
            return self._create_empty_session(session_id)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # v1 兼容：如果是纯数组格式，迁移为 v2
            if isinstance(data, list):
                data = {
                    "title": "新对话",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "compressed_context": None,
                    "messages": data,
                }
                self._write_file(session_id, data)
            
            return data
        except Exception:
            return self._create_empty_session(session_id)
    
    def _write_file(self, session_id: str, data: Dict[str, Any]) -> None:
        """写入会话文件"""
        path = self._get_session_path(session_id)
        data["updated_at"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _create_empty_session(self, session_id: str) -> Dict[str, Any]:
        """创建空会话"""
        return {
            "title": "新对话",
            "created_at": time.time(),
            "updated_at": time.time(),
            "compressed_context": None,
            "messages": [],
        }
    
    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        加载会话消息（原始格式）
        
        Returns:
            消息数组
        """
        data = self._read_file(session_id)
        return data.get("messages", [])
    
    def load_session_for_agent(self, session_id: str) -> List[Dict[str, Any]]:
        """
        为 Agent 加载优化后的会话历史
        
        - 合并连续的 assistant 消息
        - 注入 compressed_context
        
        Returns:
            优化后的消息数组
        """
        data = self._read_file(session_id)
        messages = data.get("messages", [])
        compressed_context = data.get("compressed_context")
        
        # 合并连续的 assistant 消息
        merged = []
        for msg in messages:
            if merged and merged[-1]["role"] == "assistant" and msg["role"] == "assistant":
                # 合并内容
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(msg.copy())
        
        # 注入压缩上下文
        if compressed_context:
            context_msg = {
                "role": "assistant",
                "content": f"[以下是之前对话的摘要]\n{compressed_context}"
            }
            merged.insert(0, context_msg)
        
        return merged
    
    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        追加消息到会话
        
        Args:
            session_id: 会话ID
            role: 角色 (user/assistant)
            content: 消息内容
            tool_calls: 工具调用记录
        """
        data = self._read_file(session_id)
        
        message = {
            "role": role,
            "content": content,
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        data["messages"].append(message)
        self._write_file(session_id, data)
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """获取会话元信息"""
        data = self._read_file(session_id)
        return {
            "id": session_id,
            "title": data.get("title", "新对话"),
            "created_at": data.get("created_at", 0),
            "updated_at": data.get("updated_at", 0),
            "message_count": len(data.get("messages", [])),
        }
    
    def update_title(self, session_id: str, title: str) -> None:
        """更新会话标题"""
        data = self._read_file(session_id)
        data["title"] = title
        self._write_file(session_id, data)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            if path.name == "archive":
                continue
            session_id = path.stem
            info = self.get_session_info(session_id)
            sessions.append(info)
        
        # 按更新时间倒序
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions
    
    def compress_history(
        self,
        session_id: str,
        summary: str,
        n: int
    ) -> int:
        """
        压缩历史消息
        
        Args:
            session_id: 会话ID
            summary: 摘要内容
            n: 要归档的消息数量
            
        Returns:
            归档的消息数量
        """
        data = self._read_file(session_id)
        messages = data.get("messages", [])
        
        if len(messages) < n:
            n = len(messages)
        
        if n == 0:
            return 0
        
        # 归档消息
        archived_messages = messages[:n]
        remaining_messages = messages[n:]
        
        # 保存归档文件
        archive_path = self.sessions_dir / "archive" / f"{session_id}_{int(time.time())}.json"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archived_messages, f, indent=2, ensure_ascii=False)
        
        # 更新压缩上下文
        existing_context = data.get("compressed_context") or ""
        if existing_context:
            new_context = existing_context + "\n\n---\n\n" + summary
        else:
            new_context = summary
        
        data["messages"] = remaining_messages
        data["compressed_context"] = new_context
        self._write_file(session_id, data)
        
        return n
    
    def get_compressed_context(self, session_id: str) -> Optional[str]:
        """获取压缩上下文"""
        data = self._read_file(session_id)
        return data.get("compressed_context")
