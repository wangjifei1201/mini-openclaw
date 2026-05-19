"""
半自动记忆反思 - 从对话中提取结构化记忆操作
"""
import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .memory_store import ALLOWED_MEMORY_TYPES, MemoryStore

ALLOWED_ACTIONS = {"ADD", "UPDATE", "DELETE", "NONE"}
MIN_CONFIDENCE = 0.75


REFLECTION_SYSTEM_PROMPT = """你是 BaseClaw 的记忆反思器。你的任务是从本轮用户消息和助手回复中提取长期有用的记忆操作。

只保存以下信息：
- durable user preferences about assistant behavior or workflow
- durable project facts, constraints, or product decisions
- explicit feedback/corrections/confirmations about assistant behavior
- stable external references

不要保存：
- 一次性任务进度
- 命令输出、错误堆栈、临时调试信息
- 可以从代码或 git 历史读取到的事实
- 低置信度猜测

如果新记忆与已有记忆冲突或重复，优先 UPDATE 已有记忆，不要 ADD 重复项。
只输出 JSON，不要输出 Markdown 或解释。

JSON 格式：
{
  "operations": [
    {
      "action": "ADD",
      "type": "preference|project|feedback|reference",
      "content": "记忆内容",
      "confidence": 0.85
    },
    {
      "action": "UPDATE",
      "id": "mem_...",
      "type": "preference|project|feedback|reference",
      "content": "更新后的记忆内容",
      "confidence": 0.85
    },
    {
      "action": "DELETE",
      "id": "mem_...",
      "confidence": 0.85
    },
    {"action": "NONE"}
  ]
}
"""


def parse_reflection_operations(text: str) -> List[Dict[str, Any]]:
    """解析并保守过滤反思 JSON 输出。"""
    payload = _extract_json_object(text)
    if not payload:
        return []

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []

    operations = parsed.get("operations", [])
    if not isinstance(operations, list):
        return []

    valid_operations = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        action = operation.get("action")
        if action not in ALLOWED_ACTIONS:
            continue
        if action == "NONE":
            valid_operations.append({"action": "NONE"})
            continue

        confidence = operation.get("confidence", 0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            continue
        if confidence < MIN_CONFIDENCE or confidence > 1:
            continue

        if action == "ADD":
            memory_type = operation.get("type")
            content = operation.get("content")
            if memory_type not in ALLOWED_MEMORY_TYPES:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            valid_operations.append(
                {
                    "action": "ADD",
                    "type": memory_type,
                    "content": content.strip(),
                    "confidence": confidence,
                }
            )
            continue

        if action == "UPDATE":
            memory_id = operation.get("id")
            memory_type = operation.get("type")
            content = operation.get("content")
            if not isinstance(memory_id, str) or not memory_id:
                continue
            if memory_type not in ALLOWED_MEMORY_TYPES:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            valid_operations.append(
                {
                    "action": "UPDATE",
                    "id": memory_id,
                    "type": memory_type,
                    "content": content.strip(),
                    "confidence": confidence,
                }
            )
            continue

        if action == "DELETE":
            memory_id = operation.get("id")
            if not isinstance(memory_id, str) or not memory_id:
                continue
            valid_operations.append(
                {
                    "action": "DELETE",
                    "id": memory_id,
                    "confidence": confidence,
                }
            )

    return valid_operations


def _extract_json_object(text: str) -> Optional[str]:
    if not text:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


class MemoryReflectionService:
    """运行半自动记忆反思并应用记忆操作。"""

    def __init__(self, store: MemoryStore, llm: Any):
        self.store = store
        self.llm = llm

    async def reflect(self, user_message: str, assistant_response: str) -> bool:
        """运行反思；发生任何错误都返回 False。"""
        if self.llm is None:
            return False
        try:
            existing_memories = self.store.list_active()
            prompt = self._build_user_prompt(user_message, assistant_response, existing_memories)
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=REFLECTION_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            content = getattr(response, "content", "")
            operations = parse_reflection_operations(content)
            return self.apply_operations(operations)
        except Exception as exc:
            print(f"记忆反思失败: {exc}")
            return False

    def apply_operations(self, operations: List[Dict[str, Any]]) -> bool:
        changed = False
        for operation in operations:
            action = operation.get("action")
            if action == "ADD":
                self.store.add_memory(
                    memory_type=operation["type"],
                    content=operation["content"],
                    source="auto",
                    confidence=operation["confidence"],
                )
                changed = True
            elif action == "UPDATE":
                updated = self.store.update_memory(
                    operation["id"],
                    memory_type=operation["type"],
                    content=operation["content"],
                    confidence=operation["confidence"],
                )
                changed = changed or updated is not None
            elif action == "DELETE":
                deleted = self.store.delete_memory(operation["id"])
                changed = changed or deleted is not None
        return changed

    def _build_user_prompt(
        self,
        user_message: str,
        assistant_response: str,
        existing_memories: List[Dict[str, Any]],
    ) -> str:
        existing = json.dumps(existing_memories[:50], ensure_ascii=False, indent=2)
        return f"""现有 active 记忆：
{existing}

当前用户消息：
{user_message}

最终助手回复：
{assistant_response}

请根据规则输出记忆操作 JSON。"""
