# Session-Scoped Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate backend-generated output files by chat session using `backend/outputs/<session_id>/` and `/outputs/<session_id>/<filename>` links.

**Architecture:** Reuse the existing UUID `session_id` as the output namespace. The chat API validates the session ID, creates the session output directory before agent execution, and the agent receives runtime-only system guidance telling it where to write files and what Markdown links to return. Static skill/workspace guidance is updated to use session-scoped paths while the frontend keeps resolving `/outputs/...` links via the existing backend URL helper.

**Tech Stack:** FastAPI, Python unittest, LangChain SystemMessage runtime context, Next.js 14, ReactMarkdown, TypeScript.

---

## File Structure

- Modify `backend/api/chat.py`
  - Validate `session_id` before using it as a filesystem directory name.
  - Ensure `backend/outputs/<session_id>/` exists for streaming and non-streaming chat requests.
- Modify `backend/graph/agent.py`
  - Inject a runtime-only output-directory system message into agent history using the current `session_id`.
- Modify `backend/workspace/AGENTS.md`
  - Replace global `./outputs/` and `{http://ip:port}` guidance with session-scoped output guidance.
- Modify `backend/skills/table-generator/SKILL.md`
  - Update examples and instructions to use `outputs/<session_id>/` and `/outputs/<session_id>/<filename>`.
- Modify `backend/tests/test_chat_interactive_cards.py`
  - Add backend tests for output directory creation and invalid session ID rejection in the chat API.
- Modify `backend/tests/test_memory_indexer.py`
  - Add agent-message test coverage for runtime session output context injection.
- Verify `frontend/src/lib/api.ts` and `frontend/src/components/chat/ChatMessage.tsx`
  - Existing `/outputs/...` link handling should continue to support `/outputs/<session_id>/<filename>` without extra changes.

---

### Task 1: Create Session Output Directory in Chat API

**Files:**
- Modify: `backend/api/chat.py:4-21`
- Modify: `backend/api/chat.py:152-210`
- Test: `backend/tests/test_chat_interactive_cards.py`

- [ ] **Step 1: Add failing tests for output directory creation and invalid session IDs**

Append these tests before the final `if __name__ == "__main__":` block in `backend/tests/test_chat_interactive_cards.py`:

```python
    async def test_streaming_chat_creates_session_output_directory(self):
        from api.chat import ChatRequest, chat

        session_id = "123e4567-e89b-12d3-a456-426614174000"

        manager = SimpleNamespace(
            session_manager=MagicMock(load_session=MagicMock(return_value=[])),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.chat.agent_manager", manager), patch("api.chat.BASE_DIR", Path(tmpdir)):
                response = await chat(ChatRequest(message="生成文件", session_id=session_id, stream=True))

            self.assertEqual(response.media_type, "text/event-stream")
            self.assertTrue((Path(tmpdir) / "outputs" / session_id).is_dir())

    async def test_non_streaming_chat_rejects_invalid_session_id_before_creating_output_directory(self):
        from fastapi import HTTPException
        from api.chat import ChatRequest, chat

        invalid_session_id = "../escape"
        manager = SimpleNamespace(
            session_manager=MagicMock(load_session=MagicMock(return_value=[])),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api.chat.agent_manager", manager), patch("api.chat.BASE_DIR", Path(tmpdir)):
                with self.assertRaises(HTTPException) as ctx:
                    await chat(ChatRequest(message="生成文件", session_id=invalid_session_id, stream=False))

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertFalse((Path(tmpdir) / "outputs" / invalid_session_id).exists())
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run from `backend/`:

```bash
python3 -m unittest tests/test_chat_interactive_cards.py -v
```

Expected: the two new tests fail because `api.chat.BASE_DIR` does not exist yet and the chat API does not create `outputs/<session_id>/` or reject invalid session IDs.

- [ ] **Step 3: Implement UUID validation and directory creation in `backend/api/chat.py`**

Update the import block near the top of `backend/api/chat.py` from:

```python
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph import agent_manager
```

to:

```python
import json
import asyncio
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import BASE_DIR
from graph import agent_manager
```

Then add these helpers after `ChatRequest`:

```python
def _validate_session_id(session_id: str) -> str:
    """Validate session_id before using it as an output directory name."""
    try:
        return str(uuid.UUID(session_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")


def _ensure_session_output_dir(session_id: str) -> Path:
    """Create and return backend/outputs/<session_id>."""
    safe_session_id = _validate_session_id(session_id)
    output_dir = BASE_DIR / "outputs" / safe_session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
```

Then update `chat()` so it validates and creates the output directory before loading history:

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    """
    聊天接口 - SSE 流式输出

    事件类型：
    - retrieval: RAG 检索结果
    - token: LLM 输出的 token
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - new_response: 新的响应段开始
    - done: 完成
    - title: 自动生成的标题（首条消息）
    - error: 错误
    """
    _ensure_session_output_dir(request.session_id)

    # 检查是否为首条消息
    history = agent_manager.session_manager.load_session(request.session_id)
    is_first_message = len(history) == 0
```

- [ ] **Step 4: Run the chat API tests and verify they pass**

Run from `backend/`:

```bash
python3 -m unittest tests/test_chat_interactive_cards.py -v
```

Expected: all tests in `test_chat_interactive_cards.py` pass.

---

### Task 2: Inject Runtime Session Output Context into Agent

**Files:**
- Modify: `backend/graph/agent.py:133-196`
- Test: `backend/tests/test_memory_indexer.py`

- [ ] **Step 1: Add failing tests for runtime output context**

Append these tests before the final `if __name__ == "__main__":` block in `backend/tests/test_memory_indexer.py`:

```python
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
```

Also update the import near the top of `backend/tests/test_memory_indexer.py` from:

```python
from langchain_core.messages import SystemMessage
```

to:

```python
from langchain_core.messages import HumanMessage, SystemMessage
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run from `backend/`:

```bash
python3 -m unittest tests/test_memory_indexer.py -v
```

Expected: fails because `_format_session_output_context` does not exist and `_build_messages` does not accept `session_id`.

- [ ] **Step 3: Implement output context formatting and injection in `backend/graph/agent.py`**

Add this method above `_build_messages` in `AgentManager`:

```python
    def _format_session_output_context(self, session_id: str) -> str:
        """Format runtime-only instructions for session-scoped output files."""
        return (
            f"当前会话 ID: {session_id}\n"
            f"生成文件必须保存到 outputs/{session_id}/ 目录。\n"
            f"回复用户时必须使用 Markdown 链接，并使用 /outputs/{session_id}/<filename> 形式。\n"
            "不要写入 outputs/ 根目录，不要返回 localhost、IP 地址、前端地址或本地绝对路径。"
        )
```

Change `_build_messages` signature from:

```python
    def _build_messages(self, history: List[Dict[str, Any]]) -> List:
```

to:

```python
    def _build_messages(self, history: List[Dict[str, Any]], session_id: Optional[str] = None) -> List:
```

Then initialize `messages` with runtime output context when `session_id` is present:

```python
        messages = []
        if session_id:
            messages.append(SystemMessage(content=self._format_session_output_context(session_id)))
```

Update the call site in `astream()` from:

```python
            chat_history = self._build_messages(history)
```

to:

```python
            chat_history = self._build_messages(history, session_id=session_id)
```

- [ ] **Step 4: Run memory indexer tests and verify they pass**

Run from `backend/`:

```bash
python3 -m unittest tests/test_memory_indexer.py -v
```

Expected: all tests pass.

---

### Task 3: Update Static Output Guidance

**Files:**
- Modify: `backend/workspace/AGENTS.md:46-48`
- Modify: `backend/skills/table-generator/SKILL.md:18`
- Modify: `backend/skills/table-generator/SKILL.md:40-42`
- Modify: `backend/skills/table-generator/SKILL.md:64-70`

- [ ] **Step 1: Update `backend/workspace/AGENTS.md` output guidance**

Replace this section in `backend/workspace/AGENTS.md`:

```markdown
### 根据任务需要生成文件

如果当用户任务完成时，有生成结果文件的需要时，必须将结果保存在 `./outputs/` 文件夹下。并给出生成文件的跳转链接，链接参考：<a href="{http://ip:port}/outputs/{file_name}">生成的文件名称</a>
```

with:

```markdown
### 根据任务需要生成文件

如果任务需要生成结果文件，必须保存到当前会话专属输出目录 `outputs/<session_id>/` 下；当前 `session_id` 会在运行时上下文中给出。
回复用户时必须使用 Markdown 链接，并使用 `/outputs/<session_id>/<filename>` 形式，例如：`[查看 PDF](/outputs/<session_id>/report.pdf)`。
不要写入 `outputs/` 根目录，不要返回 `localhost`、IP 地址、前端地址或本地绝对路径。
```

- [ ] **Step 2: Update `backend/skills/table-generator/SKILL.md` core flow and code example**

Change line 18 from:

```markdown
5. 将文件保存到 `outputs/` 目录，并返回可下载路径。
```

to:

```markdown
5. 将文件保存到运行时上下文指定的 `outputs/<session_id>/` 目录，并返回 Markdown 下载链接。
```

Change the Python example from:

```python
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "table.xlsx"
```

to:

```python
session_id = "从运行时上下文读取当前 session_id"
output_dir = Path("outputs") / session_id
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "table.xlsx"
```

- [ ] **Step 3: Update `backend/skills/table-generator/SKILL.md` output path section**

Replace the current output path section:

```markdown
## 输出路径

- 文件应保存到后端 `outputs/` 目录。
- 回复用户时必须使用 Markdown 链接，并使用 `/outputs/<filename>` 形式的相对输出路径。
- 不要返回 `localhost`、IP 地址、前端地址或本地绝对路径。
- Excel 示例：`已生成文件：[下载 Excel](/outputs/table-20260521.xlsx)`。
- PDF 示例：`已生成文件：[查看 PDF](/outputs/report-20260521.pdf)`。
```

with:

```markdown
## 输出路径

- 文件应保存到运行时上下文指定的后端 `outputs/<session_id>/` 目录。
- 回复用户时必须使用 Markdown 链接，并使用 `/outputs/<session_id>/<filename>` 形式的相对输出路径。
- 不要写入 `outputs/` 根目录。
- 不要返回 `localhost`、IP 地址、前端地址或本地绝对路径。
- Excel 示例：`已生成文件：[下载 Excel](/outputs/<session_id>/table-20260522.xlsx)`。
- PDF 示例：`已生成文件：[查看 PDF](/outputs/<session_id>/report-20260522.pdf)`。
```

- [ ] **Step 4: Validate the table-generator skill**

Run from `backend/`:

```bash
python3 skills/skill-creator/scripts/quick_validate.py skills/table-generator
```

Expected:

```text
Skill is valid!
```

---

### Task 4: Final Verification

**Files:**
- Verify: `backend/api/chat.py`
- Verify: `backend/graph/agent.py`
- Verify: `backend/workspace/AGENTS.md`
- Verify: `backend/skills/table-generator/SKILL.md`
- Verify: `frontend/src/lib/api.ts`
- Verify: `frontend/src/components/chat/ChatMessage.tsx`

- [ ] **Step 1: Run backend unit tests**

Run from `backend/`:

```bash
python3 -m unittest tests/test_chat_interactive_cards.py tests/test_memory_indexer.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Validate table-generator skill**

Run from `backend/`:

```bash
python3 skills/skill-creator/scripts/quick_validate.py skills/table-generator
```

Expected:

```text
Skill is valid!
```

- [ ] **Step 3: Run frontend build**

Run from `backend/`:

```bash
npm run build --prefix ../frontend
```

Expected: Next.js build completes successfully.

- [ ] **Step 4: Inspect final diff**

Run from `backend/`:

```bash
git diff -- api/chat.py graph/agent.py workspace/AGENTS.md skills/table-generator/SKILL.md tests/test_chat_interactive_cards.py tests/test_memory_indexer.py ../frontend/src/components/chat/ChatMessage.tsx ../frontend/src/lib/api.ts ../docs/superpowers/specs/2026-05-22-session-scoped-outputs-design.md
```

Expected:

- `api/chat.py` validates `session_id` and creates `outputs/<session_id>/` before agent execution.
- `agent.py` injects runtime session output instructions.
- `AGENTS.md` and `table-generator` instruct session-scoped output paths.
- Frontend output link behavior remains compatible with `/outputs/<session_id>/<filename>`.
- The design spec exists and matches the implementation.

- [ ] **Step 5: Commit implementation**

Only stage files for this feature and the already-needed link-rendering fix:

```bash
git add api/chat.py graph/agent.py workspace/AGENTS.md skills/table-generator/SKILL.md tests/test_chat_interactive_cards.py tests/test_memory_indexer.py ../frontend/src/components/chat/ChatMessage.tsx ../docs/superpowers/specs/2026-05-22-session-scoped-outputs-design.md
git commit -m "按会话隔离后端输出文件。"
```

Do not stage unrelated files such as `backend/memory/MEMORY.md`, `.vscode/`, or the older output-link plan unless explicitly requested.

---

## Self-Review

- Spec coverage: session ID reuse, session-scoped output directories, runtime agent context, static guidance updates, frontend compatibility, historical link compatibility, and validation/security are covered.
- Placeholder scan: checked for placeholder markers and none remain.
- Type consistency: `session_id`, `outputs/<session_id>/`, and `/outputs/<session_id>/<filename>` are used consistently across tests, backend code, prompt guidance, and skill guidance.
