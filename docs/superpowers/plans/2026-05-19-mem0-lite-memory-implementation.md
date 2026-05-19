# Mem0-lite Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Mem0-inspired structured memory layer that writes durable memories to `backend/memory/memories.jsonl`, retrieves active structured memories in RAG mode, and shows them in the frontend memory files panel.

**Architecture:** Add a focused `MemoryStore` for JSONL persistence, a `MemoryReflectionService` for conservative ADD/UPDATE/DELETE extraction, and update `MemoryIndexer` to index active structured records instead of raw `MEMORY.md`. Expose read-only memories through FastAPI and render `memory/memories.jsonl` with a structured read-only viewer in the inspector, while keeping raw JSONL fallback.

**Tech Stack:** Python 3, FastAPI, Pydantic-style response dictionaries, LangChain chat model wrapper, LlamaIndex vector retrieval, React, TypeScript, Next.js, Tailwind CSS.

---

## File Structure

### Backend files

- Create `backend/graph/memory_store.py`
  - Owns the structured JSONL record schema.
  - Loads all records from `backend/memory/memories.jsonl`.
  - Skips invalid JSONL lines with log output.
  - Adds records, updates records, marks records deleted, and rewrites the file through a temp file + replace.
  - Does not call LLMs, embeddings, or the indexer.

- Create `backend/graph/memory_reflection.py`
  - Owns reflection prompt construction, JSON parsing, operation validation, and applying accepted operations through `MemoryStore`.
  - Keeps reflection best-effort: catches/logs failures and never breaks chat completion.
  - Uses the existing `agent_manager.llm` object passed in from `AgentManager`.

- Modify `backend/graph/agent.py`
  - Instantiate `MemoryStore` and `MemoryReflectionService` during initialization.
  - After a normal assistant response completes, run reflection in best-effort mode.
  - Rebuild memory index after accepted memory writes.

- Modify `backend/graph/memory_indexer.py`
  - Use `MemoryStore` and `memory/memories.jsonl` as the structured retrieval source.
  - Index only `status == "active"` records.
  - Preserve metadata on each indexed document/node: `id`, `type`, `source`.
  - Return record-like retrieval results instead of raw markdown chunks.

- Create `backend/api/memories.py`
  - Add `GET /api/memories`.
  - Return `{ "memories": [...] }` with stable record fields.

- Modify `backend/api/__init__.py`
  - Export `memories_router`.

- Modify `backend/app.py`
  - Import and register the memory API router.
  - Update startup log wording from `MEMORY.md` index to structured memory index.

- Modify `backend/api/files.py`
  - Trigger index rebuild when saving `memory/memories.jsonl` as well as `memory/MEMORY.md`.

- Create `backend/tests/test_memory_store.py`
  - Unit-test JSONL store load/add/update/delete behavior and invalid-line skipping.

- Create `backend/tests/test_memory_reflection.py`
  - Unit-test operation parsing and validation without calling a real model.

- Create `backend/tests/test_memory_indexer.py`
  - Unit-test structured memory document preparation and deleted-memory exclusion without requiring embeddings.

- Create `backend/tests/test_memories_api.py`
  - Unit-test `GET /api/memories` with FastAPI `TestClient` or direct endpoint invocation.

### Frontend files

- Modify `frontend/src/lib/api.ts`
  - Add `MemoryRecord` type.
  - Add `getMemories()` API client.

- Modify `frontend/src/components/layout/Sidebar.tsx`
  - Add `结构化记忆` entry under `记忆文件` using path `memory/memories.jsonl`.

- Modify `frontend/src/components/editor/InspectorPanel.tsx`
  - Import `getMemories` and `MemoryRecord`.
  - Detect `currentFile === 'memory/memories.jsonl'`.
  - Render a structured read-only viewer with filters and raw JSONL fallback.
  - Preserve existing Monaco editor behavior for all other files and for raw JSONL mode.

---

## Task 1: Add MemoryStore JSONL persistence

**Files:**
- Create: `backend/graph/memory_store.py`
- Test: `backend/tests/test_memory_store.py`

- [ ] **Step 1: Write failing MemoryStore tests**

Create `backend/tests/test_memory_store.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from graph.memory_store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_missing_file_loads_empty_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            self.assertEqual(store.list_all(), [])
            self.assertEqual(store.list_active(), [])

    def test_add_memory_writes_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))

            record = store.add_memory(
                memory_type="preference",
                content="用户希望回答简洁直接。",
                source="auto",
                confidence=0.86,
            )

            self.assertTrue(record["id"].startswith("mem_"))
            self.assertEqual(record["type"], "preference")
            self.assertEqual(record["content"], "用户希望回答简洁直接。")
            self.assertEqual(record["status"], "active")
            self.assertEqual(record["source"], "auto")
            self.assertEqual(record["confidence"], 0.86)
            self.assertIn("created_at", record)
            self.assertIn("updated_at", record)

            persisted = (Path(tmpdir) / "memory" / "memories.jsonl").read_text(encoding="utf-8")
            persisted_record = json.loads(persisted.strip())
            self.assertEqual(persisted_record["id"], record["id"])

    def test_update_memory_changes_content_and_updated_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            record = store.add_memory(
                memory_type="project",
                content="旧项目约束。",
                source="manual",
                confidence=0.9,
            )

            updated = store.update_memory(
                record["id"],
                memory_type="project",
                content="新项目约束。",
                confidence=0.95,
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated["content"], "新项目约束。")
            self.assertEqual(updated["confidence"], 0.95)
            self.assertGreaterEqual(updated["updated_at"], record["updated_at"])
            self.assertEqual(store.list_all()[0]["content"], "新项目约束。")

    def test_delete_memory_marks_deleted_and_excludes_from_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir))
            record = store.add_memory(
                memory_type="reference",
                content="Grafana 看板用于请求延迟排查。",
                source="manual",
                confidence=1.0,
            )

            deleted = store.delete_memory(record["id"])

            self.assertIsNotNone(deleted)
            self.assertEqual(deleted["status"], "deleted")
            self.assertEqual(len(store.list_all()), 1)
            self.assertEqual(store.list_active(), [])

    def test_invalid_jsonl_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            memory_dir.mkdir(parents=True)
            memory_file = memory_dir / "memories.jsonl"
            memory_file.write_text(
                "not-json\n"
                + json.dumps(
                    {
                        "id": "mem_valid",
                        "type": "feedback",
                        "content": "用户确认这个流程正确。",
                        "status": "active",
                        "source": "manual",
                        "confidence": 0.8,
                        "created_at": "2026-05-19T12:00:00",
                        "updated_at": "2026-05-19T12:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            store = MemoryStore(Path(tmpdir))

            self.assertEqual(len(store.list_all()), 1)
            self.assertEqual(store.list_all()[0]["id"], "mem_valid")

    def test_invalid_records_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            memory_dir.mkdir(parents=True)
            memory_file = memory_dir / "memories.jsonl"
            memory_file.write_text(
                json.dumps(
                    {
                        "id": "mem_bad",
                        "type": "unknown",
                        "content": "bad",
                        "status": "active",
                        "source": "manual",
                        "confidence": 0.8,
                        "created_at": "2026-05-19T12:00:00",
                        "updated_at": "2026-05-19T12:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            store = MemoryStore(Path(tmpdir))

            self.assertEqual(store.list_all(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest backend/tests/test_memory_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph.memory_store'`.

- [ ] **Step 3: Implement MemoryStore**

Create `backend/graph/memory_store.py`:

```python
"""
结构化记忆存储 - JSONL 文件持久化
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_MEMORY_TYPES = {"preference", "project", "feedback", "reference"}
ALLOWED_MEMORY_STATUSES = {"active", "deleted"}
ALLOWED_MEMORY_SOURCES = {"auto", "manual"}


class MemoryStore:
    """管理 backend/memory/memories.jsonl 中的结构化记忆。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.memory_dir = base_dir / "memory"
        self.memory_file = self.memory_dir / "memories.jsonl"

    def list_all(self) -> List[Dict[str, Any]]:
        """返回所有有效记忆记录，包括 deleted。"""
        return self._load_records()

    def list_active(self) -> List[Dict[str, Any]]:
        """返回 active 记忆记录。"""
        return [record for record in self._load_records() if record["status"] == "active"]

    def add_memory(
        self,
        memory_type: str,
        content: str,
        source: str = "auto",
        confidence: float = 0.8,
    ) -> Dict[str, Any]:
        """新增一条 active 记忆。"""
        now = self._now()
        record = {
            "id": self._generate_id(),
            "type": memory_type,
            "content": content,
            "status": "active",
            "source": source,
            "confidence": float(confidence),
            "created_at": now,
            "updated_at": now,
        }
        self._validate_or_raise(record)
        records = self._load_records()
        records.append(record)
        self._write_records(records)
        return record

    def update_memory(
        self,
        memory_id: str,
        memory_type: Optional[str] = None,
        content: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新已有记忆，找不到则返回 None。"""
        records = self._load_records()
        for record in records:
            if record["id"] != memory_id:
                continue
            if memory_type is not None:
                record["type"] = memory_type
            if content is not None:
                record["content"] = content
            if confidence is not None:
                record["confidence"] = float(confidence)
            record["updated_at"] = self._now()
            self._validate_or_raise(record)
            self._write_records(records)
            return record
        return None

    def delete_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """将记忆标记为 deleted，找不到则返回 None。"""
        records = self._load_records()
        for record in records:
            if record["id"] != memory_id:
                continue
            record["status"] = "deleted"
            record["updated_at"] = self._now()
            self._write_records(records)
            return record
        return None

    def _load_records(self) -> List[Dict[str, Any]]:
        if not self.memory_file.exists():
            return []

        records = []
        try:
            with self.memory_file.open("r", encoding="utf-8") as f:
                for line_number, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        print(f"跳过无效记忆 JSONL 行 {line_number}: {exc}")
                        continue
                    if not self._is_valid_record(record):
                        print(f"跳过无效记忆记录 {line_number}: {record}")
                        continue
                    records.append(record)
        except Exception as exc:
            print(f"读取结构化记忆失败: {exc}")
            return []
        return records

    def _write_records(self, records: List[Dict[str, Any]]) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self.memory_file.with_suffix(".jsonl.tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                f.write("\n")
        os.replace(tmp_file, self.memory_file)

    def _is_valid_record(self, record: Any) -> bool:
        if not isinstance(record, dict):
            return False
        required = {
            "id",
            "type",
            "content",
            "status",
            "source",
            "confidence",
            "created_at",
            "updated_at",
        }
        if not required.issubset(record.keys()):
            return False
        if record["type"] not in ALLOWED_MEMORY_TYPES:
            return False
        if record["status"] not in ALLOWED_MEMORY_STATUSES:
            return False
        if record["source"] not in ALLOWED_MEMORY_SOURCES:
            return False
        if not isinstance(record["content"], str) or not record["content"].strip():
            return False
        try:
            confidence = float(record["confidence"])
        except (TypeError, ValueError):
            return False
        return 0 <= confidence <= 1

    def _validate_or_raise(self, record: Dict[str, Any]) -> None:
        if not self._is_valid_record(record):
            raise ValueError(f"Invalid memory record: {record}")

    def _generate_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d")
        suffix = uuid.uuid4().hex[:8]
        return f"mem_{timestamp}_{suffix}"

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
```

- [ ] **Step 4: Run MemoryStore tests**

Run:

```bash
python3 -m unittest backend/tests/test_memory_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/graph/memory_store.py backend/tests/test_memory_store.py
git commit -m "Add structured memory store"
```

---

## Task 2: Add memory reflection parsing and best-effort operation application

**Files:**
- Create: `backend/graph/memory_reflection.py`
- Test: `backend/tests/test_memory_reflection.py`

- [ ] **Step 1: Write failing reflection tests**

Create `backend/tests/test_memory_reflection.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest backend/tests/test_memory_reflection.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph.memory_reflection'`.

- [ ] **Step 3: Implement reflection parser and service**

Create `backend/graph/memory_reflection.py`:

```python
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
```

- [ ] **Step 4: Run reflection tests**

Run:

```bash
python3 -m unittest backend/tests/test_memory_reflection.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/graph/memory_reflection.py backend/tests/test_memory_reflection.py
git commit -m "Add memory reflection service"
```

---

## Task 3: Wire reflection into chat completion

**Files:**
- Modify: `backend/graph/agent.py:15-18`, `backend/graph/agent.py:59-98`, `backend/graph/agent.py:336-343`
- Modify: `backend/api/chat.py:80-104`, `backend/api/chat.py:150-172`

- [ ] **Step 1: Add AgentManager fields and initialization**

Modify imports in `backend/graph/agent.py`:

```python
from .memory_indexer import MemoryIndexer
from .memory_reflection import MemoryReflectionService
from .memory_store import MemoryStore
from .prompt_builder import PromptBuilder
```

Modify `AgentManager.__init__` fields:

```python
        self.memory_indexer: Optional[MemoryIndexer] = None
        self.memory_store: Optional[MemoryStore] = None
        self.memory_reflection: Optional[MemoryReflectionService] = None
        self._initialized = False
```

Modify `AgentManager.initialize` after prompt builder setup:

```python
        # 初始化结构化记忆存储
        self.memory_store = MemoryStore(base_dir)

        # 初始化记忆索引器
        self.memory_indexer = MemoryIndexer(base_dir, memory_store=self.memory_store)

        # 初始化半自动记忆反思服务
        self.memory_reflection = MemoryReflectionService(
            store=self.memory_store,
            llm=self.llm,
        )
```

This step will temporarily fail until Task 4 updates `MemoryIndexer.__init__` to accept `memory_store`.

- [ ] **Step 2: Add reflection helper to AgentManager**

Add this method to `AgentManager` before `generate_title`:

```python
    async def reflect_memory(self, user_message: str, assistant_response: str) -> bool:
        """在聊天完成后运行半自动记忆反思。"""
        if not self.memory_reflection:
            return False
        changed = await self.memory_reflection.reflect(user_message, assistant_response)
        if changed and self.memory_indexer:
            try:
                self.memory_indexer.rebuild_index()
            except Exception as exc:
                print(f"记忆索引重建失败: {exc}")
        return changed
```

- [ ] **Step 3: Call reflection after streaming response is saved**

In `backend/api/chat.py`, after saving assistant messages and before yielding the final `done` event, add:

```python
            assistant_text = "\n".join(seg["content"] for seg in segments if seg.get("content"))
            if assistant_text:
                await agent_manager.reflect_memory(message, assistant_text)
```

The final `done` block should keep yielding the same `done` event after reflection:

```python
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
```

- [ ] **Step 4: Call reflection for non-streaming responses**

In `backend/api/chat.py`, after saving the assistant message in the non-streaming branch, add:

```python
        if full_content:
            await agent_manager.reflect_memory(request.message, full_content)
```

- [ ] **Step 5: Run targeted import check**

Run:

```bash
python3 -m py_compile backend/graph/memory_store.py backend/graph/memory_reflection.py backend/graph/agent.py backend/api/chat.py
```

Expected: PASS after Task 4 has updated `MemoryIndexer.__init__`. If run before Task 4, expected failure is `TypeError` only at runtime, not py_compile.

- [ ] **Step 6: Commit**

```bash
git add backend/graph/agent.py backend/api/chat.py
git commit -m "Run memory reflection after chat responses"
```

---

## Task 4: Update MemoryIndexer for structured memories

**Files:**
- Modify: `backend/graph/memory_indexer.py`
- Test: `backend/tests/test_memory_indexer.py`

- [ ] **Step 1: Write failing MemoryIndexer tests**

Create `backend/tests/test_memory_indexer.py`:

```python
import tempfile
import unittest
from pathlib import Path

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

            self.assertIn("【记忆 1】", context)
            self.assertIn("类型: preference", context)
            self.assertIn("用户希望回答简洁直接。", context)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest backend/tests/test_memory_indexer.py -v
```

Expected: FAIL because `MemoryIndexer.__init__` does not accept `memory_store` and `_build_memory_documents` does not exist.

- [ ] **Step 3: Replace MemoryIndexer structured-memory source**

Modify `backend/graph/memory_indexer.py` so the top imports and initializer become:

```python
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

    def __init__(self, base_dir: Path, memory_store: Optional[MemoryStore] = None):
        self.base_dir = base_dir
        self.memory_store = memory_store or MemoryStore(base_dir)
        self.memory_file = base_dir / "memory" / "memories.jsonl"
        self.storage_dir = base_dir / "storage" / "memory_index"
        self._index = None
        self._file_hash: Optional[str] = None
```

Keep `_get_file_hash` but it should now read `memories.jsonl`; missing file returns `None`.

- [ ] **Step 4: Add document preparation helper**

Add this method inside `MemoryIndexer`:

```python
    def _build_memory_documents(self):
        """将 active 结构化记忆转换为 LlamaIndex Document。"""
        from llama_index.core import Document

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
```

- [ ] **Step 5: Update rebuild_index**

Replace the `rebuild_index` method body with structured memory indexing:

```python
    def rebuild_index(self) -> bool:
        """
        重建结构化记忆向量索引。

        Returns:
            是否成功
        """
        try:
            from llama_index.core import VectorStoreIndex, Settings as LlamaSettings
            from llama_index.core.node_parser import SentenceSplitter
            from llama_index.embeddings.openai import OpenAIEmbedding

            documents = self._build_memory_documents()
            if not documents:
                self._index = None
                self._file_hash = self._get_file_hash()
                return False

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
                return False

            self._index = VectorStoreIndex(nodes)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._index.storage_context.persist(persist_dir=str(self.storage_dir))
            self._file_hash = self._get_file_hash()
            return True

        except Exception as e:
            print(traceback.format_exc())
            print(f"结构化记忆索引构建失败: {e}")
            return False
```

- [ ] **Step 6: Update retrieval result shape**

In `retrieve`, update docstring and result append block:

```python
                metadata = getattr(node, "metadata", {}) or {}
                results.append({
                    "id": metadata.get("id", ""),
                    "type": metadata.get("type", ""),
                    "text": node.get_content(),
                    "score": getattr(node, "score", 0),
                    "source": metadata.get("source", "auto"),
                })
```

- [ ] **Step 7: Update retrieval context formatting**

Replace `format_retrieval_context` with:

```python
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
```

- [ ] **Step 8: Run MemoryIndexer tests**

Run:

```bash
python3 -m unittest backend/tests/test_memory_indexer.py -v
```

Expected: PASS.

- [ ] **Step 9: Run agent compile check**

Run:

```bash
python3 -m py_compile backend/graph/memory_store.py backend/graph/memory_reflection.py backend/graph/memory_indexer.py backend/graph/agent.py backend/api/chat.py
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/graph/memory_indexer.py backend/tests/test_memory_indexer.py
git commit -m "Index active structured memories"
```

---

## Task 5: Add read-only memories API

**Files:**
- Create: `backend/api/memories.py`
- Modify: `backend/api/__init__.py:4-20`
- Modify: `backend/app.py:21-29`, `backend/app.py:63-71`, `backend/app.py:100-107`
- Modify: `backend/api/files.py:129-154`
- Test: `backend/tests/test_memories_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_memories_api.py`:

```python
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest backend/tests/test_memories_api.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.memories'`.

- [ ] **Step 3: Implement memories API**

Create `backend/api/memories.py`:

```python
"""
结构化记忆 API - 只读查看 memories.jsonl
"""
from fastapi import APIRouter

from graph import agent_manager

router = APIRouter()


@router.get("/memories")
async def list_memories():
    """列出结构化记忆记录。"""
    if not agent_manager.memory_store:
        return {"memories": []}
    return {"memories": agent_manager.memory_store.list_all()}
```

- [ ] **Step 4: Export memories router**

Modify `backend/api/__init__.py`:

```python
from .memories import router as memories_router
```

Add to `__all__`:

```python
    "memories_router",
```

- [ ] **Step 5: Register memories router and update startup wording**

Modify `backend/app.py` API imports to include:

```python
    memories_router,
```

Modify router registration:

```python
app.include_router(memories_router, prefix="/api", tags=["Memories"])
```

Modify startup memory index messages:

```python
    3. memory_indexer.rebuild_index() → 构建结构化记忆向量索引
```

and:

```python
        if agent_manager.memory_indexer.rebuild_index():
            print("      结构化记忆索引已构建")
        else:
            print("      结构化记忆为空或不存在，跳过索引构建")
```

- [ ] **Step 6: Rebuild index when saving memories.jsonl**

In `backend/api/files.py`, update the comment and condition:

```python
    保存 memory/MEMORY.md 或 memory/memories.jsonl 时会自动触发索引重建
```

```python
        if request.path in {"memory/MEMORY.md", "memory/memories.jsonl"}:
            try:
                agent_manager.memory_indexer.rebuild_index()
            except Exception:
                pass
```

- [ ] **Step 7: Run API tests and compile checks**

Run:

```bash
python3 -m unittest backend/tests/test_memories_api.py -v
python3 -m py_compile backend/api/memories.py backend/api/__init__.py backend/app.py backend/api/files.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/api/memories.py backend/api/__init__.py backend/app.py backend/api/files.py backend/tests/test_memories_api.py
git commit -m "Expose structured memories API"
```

---

## Task 6: Add frontend memories API client and sidebar entry

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add MemoryRecord type and getMemories client**

In `frontend/src/lib/api.ts`, add near the other exported interfaces:

```ts
export interface MemoryRecord {
  id: string
  type: 'preference' | 'project' | 'feedback' | 'reference'
  content: string
  status: 'active' | 'deleted'
  source: 'auto' | 'manual'
  confidence: number
  created_at: string
  updated_at: string
}
```

Add near the file/config API functions:

```ts
export async function getMemories() {
  return request<{ memories: MemoryRecord[] }>('/api/memories')
}
```

- [ ] **Step 2: Add structured memory file entry**

In `frontend/src/components/layout/Sidebar.tsx`, update the memory files section:

```tsx
<div className="space-y-1">
  <FileItem path="memory/MEMORY.md" label="长期记忆" />
  <FileItem path="memory/memories.jsonl" label="结构化记忆" />
  <FileItem path="SKILLS_SNAPSHOT.md" label="技能快照" />
</div>
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/layout/Sidebar.tsx
git commit -m "Add structured memory frontend entry"
```

---

## Task 7: Add structured memory inspector viewer

**Files:**
- Modify: `frontend/src/components/editor/InspectorPanel.tsx`

- [ ] **Step 1: Update imports and state**

Modify imports in `frontend/src/components/editor/InspectorPanel.tsx`:

```tsx
import { readFile, saveFile, getFilesTokens, getMemories, MemoryRecord } from '@/lib/api'
```

Add after existing state declarations:

```tsx
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [memoryFilter, setMemoryFilter] = useState<'all' | MemoryRecord['status'] | MemoryRecord['type']>('all')
  const [showRawJsonl, setShowRawJsonl] = useState(false)
```

- [ ] **Step 2: Load memories when structured memory file is selected**

Add this effect after the file-loading effect:

```tsx
  useEffect(() => {
    if (currentFile !== 'memory/memories.jsonl') {
      setMemories([])
      setShowRawJsonl(false)
      return
    }

    getMemories()
      .then(data => setMemories(data.memories))
      .catch(err => {
        console.error('读取结构化记忆失败:', err)
        setMemories([])
      })
  }, [currentFile])
```

- [ ] **Step 3: Add filtered memory calculation**

Add before the `if (!currentFile)` block:

```tsx
  const isStructuredMemoryFile = currentFile === 'memory/memories.jsonl'
  const filteredMemories = memories.filter(memory => {
    if (memoryFilter === 'all') return true
    return memory.status === memoryFilter || memory.type === memoryFilter
  })
```

- [ ] **Step 4: Disable save for structured viewer unless raw mode is enabled**

Change the Save button `disabled` prop:

```tsx
            disabled={!hasChanges || isSaving || (isStructuredMemoryFile && !showRawJsonl)}
```

Keep the same button styling and label.

- [ ] **Step 5: Render structured memory viewer with raw fallback**

Replace the editor container block at lines 129-147 with:

```tsx
      {/* 编辑器 / 结构化记忆查看器 */}
      <div className="flex-1 min-h-0">
        {isStructuredMemoryFile && !showRawJsonl ? (
          <div className="h-full flex flex-col min-h-0">
            <div className="px-4 py-3 border-b border-apple-border flex flex-wrap items-center gap-2">
              {(['all', 'active', 'deleted', 'preference', 'project', 'feedback', 'reference'] as const).map(filter => (
                <button
                  key={filter}
                  onClick={() => setMemoryFilter(filter)}
                  className={`px-3 py-1 rounded-lg text-xs border ${
                    memoryFilter === filter
                      ? 'bg-klein-blue text-white border-klein-blue'
                      : 'bg-white text-gray-600 border-apple-border hover:bg-gray-50'
                  }`}
                >
                  {filter}
                </button>
              ))}
              <button
                onClick={() => setShowRawJsonl(true)}
                className="ml-auto px-3 py-1 rounded-lg text-xs border border-apple-border text-gray-600 hover:bg-gray-50"
              >
                查看原始 JSONL
              </button>
            </div>

            <div className="flex-1 min-h-0 overflow-auto p-4">
              {filteredMemories.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                  暂无结构化记忆
                </div>
              ) : (
                <div className="overflow-x-auto border border-apple-border rounded-xl">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 text-gray-500">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">类型</th>
                        <th className="px-3 py-2 text-left font-medium">内容</th>
                        <th className="px-3 py-2 text-left font-medium">来源</th>
                        <th className="px-3 py-2 text-left font-medium">置信度</th>
                        <th className="px-3 py-2 text-left font-medium">状态</th>
                        <th className="px-3 py-2 text-left font-medium">更新时间</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-apple-border">
                      {filteredMemories.map(memory => (
                        <tr key={memory.id} className="align-top">
                          <td className="px-3 py-2 text-gray-700 whitespace-nowrap">{memory.type}</td>
                          <td className="px-3 py-2 text-gray-800 min-w-[20rem] max-w-[36rem] whitespace-pre-wrap break-words">{memory.content}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{memory.source}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{Math.round(memory.confidence * 100)}%</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{memory.status}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{memory.updated_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : (
          <MonacoEditor
            height="100%"
            defaultLanguage="markdown"
            theme="vs"
            value={fileContent}
            onChange={(value) => setFileContent(value || '')}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: 'on',
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              padding: { top: 16 },
            }}
          />
        )}
      </div>
```

- [ ] **Step 6: Add raw mode footer label and return button**

Replace the footer block with:

```tsx
      {/* 底部状态栏 */}
      <div className="px-4 py-2 border-t border-apple-border flex items-center justify-between text-xs text-gray-400">
        <span>{isStructuredMemoryFile && !showRawJsonl ? 'Structured Memory' : 'Markdown'}</span>
        <div className="flex items-center gap-3">
          {isStructuredMemoryFile && showRawJsonl && (
            <button
              onClick={() => setShowRawJsonl(false)}
              className="text-klein-blue hover:underline"
            >
              返回结构化视图
            </button>
          )}
          <span>{tokenCount.toLocaleString()} tokens</span>
        </div>
      </div>
```

- [ ] **Step 7: Run frontend build**

Run:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/editor/InspectorPanel.tsx
git commit -m "Render structured memory viewer"
```

---

## Task 8: Full backend verification and behavior checks

**Files:**
- No new source files unless tests reveal a defect.

- [ ] **Step 1: Run backend memory test suite**

Run:

```bash
python3 -m unittest backend/tests/test_memory_store.py backend/tests/test_memory_reflection.py backend/tests/test_memory_indexer.py backend/tests/test_memories_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run existing backend tests touched by nearby behavior**

Run:

```bash
python3 -m unittest backend/tests/test_file_upload_validation.py backend/tests/test_terminal_tool.py -v
```

Expected: PASS.

- [ ] **Step 3: Run Python compile check for changed backend modules**

Run:

```bash
python3 -m py_compile backend/graph/memory_store.py backend/graph/memory_reflection.py backend/graph/memory_indexer.py backend/graph/agent.py backend/api/chat.py backend/api/memories.py backend/api/__init__.py backend/app.py backend/api/files.py
```

Expected: PASS.

- [ ] **Step 4: Verify missing memories.jsonl is safe**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from graph.memory_store import MemoryStore
store = MemoryStore(Path('backend'))
print(store.list_all())
print(store.list_active())
PY
```

Expected output includes two empty lists when `backend/memory/memories.jsonl` does not exist:

```text
[]
[]
```

- [ ] **Step 5: Commit fixes only if verification found defects**

If verification required fixes, commit them:

```bash
git add <fixed-files>
git commit -m "Fix structured memory verification issues"
```

If no fixes were needed, do not create a commit.

---

## Task 9: Full frontend verification

**Files:**
- No new source files unless build reveals a defect.

- [ ] **Step 1: Run frontend build**

Run:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 2: Manually verify memory viewer behavior in the app**

Run the app using the repository’s normal dev commands. Then verify:

1. Sidebar `记忆文件` contains `长期记忆`, `结构化记忆`, and `技能快照`.
2. Clicking `结构化记忆` opens a structured viewer, not Monaco by default.
3. Empty `memories.jsonl` or missing backend records shows `暂无结构化记忆`.
4. Filters `all`, `active`, `deleted`, `preference`, `project`, `feedback`, `reference` update the visible rows.
5. `查看原始 JSONL` switches to Monaco text viewing.
6. `返回结构化视图` returns to the table viewer.
7. Save button is disabled in structured table mode and works only in raw JSONL mode.

- [ ] **Step 3: Commit fixes only if verification found defects**

If frontend verification required fixes, commit them:

```bash
git add <fixed-files>
git commit -m "Fix structured memory viewer behavior"
```

If no fixes were needed, do not create a commit.

---

## Task 10: Final integration check

**Files:**
- No source edits expected.

- [ ] **Step 1: Check git status**

Run:

```bash
git status --short
```

Expected: no unintended generated files. If `__pycache__` appears, remove only generated cache files before final handoff.

- [ ] **Step 2: Run complete targeted verification**

Run:

```bash
python3 -m unittest backend/tests/test_memory_store.py backend/tests/test_memory_reflection.py backend/tests/test_memory_indexer.py backend/tests/test_memories_api.py backend/tests/test_file_upload_validation.py backend/tests/test_terminal_tool.py -v
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 3: Confirm acceptance criteria**

Check these outcomes explicitly:

- App still starts when only `backend/memory/MEMORY.md` exists.
- Missing `backend/memory/memories.jsonl` behaves as an empty memory list.
- Reflection creates only structured records in `backend/memory/memories.jsonl`.
- RAG mode retrieves active structured memory records.
- Deleted memories are excluded from retrieval.
- Frontend memory section includes `结构化记忆`.
- Clicking `结构化记忆` shows a readable table/list view.
- Viewer supports filters and raw JSONL fallback.
- No user/project isolation was introduced.

- [ ] **Step 4: Final commit only if needed**

If Task 10 required cleanup or fixes:

```bash
git add <fixed-files>
git commit -m "Complete Mem0-lite memory integration"
```

If the working tree is already clean, do not create a commit.

---

## Self-Review

### Spec coverage

- Structured storage in `backend/memory/memories.jsonl`: Task 1.
- Keep `MEMORY.md` compatibility: Tasks 4 and 5 do not remove normal `PromptBuilder` behavior; Task 5 keeps file save handling.
- ADD / UPDATE / DELETE lifecycle: Tasks 1 and 2.
- Semi-automatic memory extraction after assistant responses: Tasks 2 and 3.
- RAG indexes active structured memories: Task 4.
- `GET /api/memories`: Task 5.
- Frontend “结构化记忆” entry: Task 6.
- Structured Inspector viewer: Task 7.
- Filters and raw JSONL fallback: Task 7.
- Missing/invalid JSONL handling: Tasks 1 and 8.
- Deleted memories excluded from retrieval: Task 4.
- No user/project isolation: no task introduces user_id/project_id fields.

### Placeholder scan

No `TBD`, `TODO`, “similar to”, or unspecified implementation steps remain. Each code-writing step includes concrete file paths, concrete code, and exact verification commands.

### Type consistency

The backend schema uses `id`, `type`, `content`, `status`, `source`, `confidence`, `created_at`, and `updated_at` consistently across `MemoryStore`, API responses, index metadata, and frontend `MemoryRecord`. The allowed frontend unions match backend allowed values.
