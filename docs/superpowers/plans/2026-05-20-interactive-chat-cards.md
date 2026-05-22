# Interactive Chat Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add protocol-level interactive chat cards so assistant messages can include clickable quick-reply and choice options that send follow-up prompts.

**Architecture:** Backend generates validated `interactive_cards` after the assistant response completes, emits them via a new SSE `interactive_card` event before `done`, and persists them with assistant messages. Frontend extends message/event types, attaches cards to streaming and historical assistant messages, and renders cards below assistant content with click-to-send behavior.

**Tech Stack:** FastAPI, Python `unittest`, LangChain chat model wrapper, React/Next.js 14, TypeScript, Tailwind CSS.

---

## File Structure

- Create `backend/graph/interactive_cards.py` — card schema validation, LLM parsing, and `InteractiveCardService`.
- Create `backend/tests/test_interactive_cards.py` — unit tests for card parsing, validation, service behavior, and prompt content.
- Modify `backend/graph/agent.py` — initialize `InteractiveCardService`, expose `generate_interactive_cards()`, and add card-friendly system prompt guidance.
- Modify `backend/api/chat.py` — emit `interactive_card` before `done`, include cards in non-streaming responses, and save cards in session history.
- Modify `backend/graph/session_manager.py` — persist optional `interactive_cards` on messages.
- Create `backend/tests/test_chat_interactive_cards.py` — API-level tests for SSE ordering and session persistence.
- Modify `frontend/src/lib/api.ts` — add `interactive_card` stream event type and card interfaces.
- Modify `frontend/src/lib/store.tsx` — add `interactive_cards` to `Message`, load history cards, handle stream card events.
- Create `frontend/src/components/chat/InteractiveCard.tsx` — render quick-reply and choice cards.
- Modify `frontend/src/components/chat/ChatMessage.tsx` — render assistant cards below message content.

---

### Task 1: Backend Interactive Card Service

**Files:**
- Create: `backend/graph/interactive_cards.py`
- Test: `backend/tests/test_interactive_cards.py`

- [ ] **Step 1: Write tests for card parsing and validation**

Create `backend/tests/test_interactive_cards.py` with:

```python
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langchain_core.messages import HumanMessage, SystemMessage

from graph.interactive_cards import (
    InteractiveCardService,
    parse_interactive_cards,
    validate_interactive_cards,
)


class InteractiveCardTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_cards_accepts_valid_payload(self):
        payload = '''
        {
          "cards": [
            {
              "type": "choice",
              "title": "请选择下一步",
              "description": "选择一个方向继续。",
              "options": [
                {"label": "生成计划", "prompt": "请生成实现计划。"},
                {"label": "开始开发", "prompt": "请开始开发。"}
              ]
            }
          ]
        }
        '''

        cards = parse_interactive_cards(payload)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["type"], "choice")
        self.assertEqual(cards[0]["title"], "请选择下一步")
        self.assertEqual(len(cards[0]["options"]), 2)
        self.assertTrue(cards[0]["id"].startswith("card_"))
        self.assertTrue(cards[0]["options"][0]["id"].startswith("opt_"))

    def test_parse_cards_extracts_json_from_markdown_fence(self):
        payload = '''```json
        {"cards":[{"type":"quick_replies","title":"继续操作","options":[{"label":"总结","prompt":"请总结上文。"}]}]}
        ```'''

        cards = parse_interactive_cards(payload)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["type"], "quick_replies")
        self.assertEqual(cards[0]["options"][0]["label"], "总结")

    def test_validate_cards_drops_invalid_cards_and_options(self):
        cards = validate_interactive_cards([
            {"type": "unknown", "title": "错误", "options": [{"label": "A", "prompt": "B"}]},
            {"type": "choice", "title": "", "options": [{"label": "A", "prompt": "B"}]},
            {
                "type": "choice",
                "title": "请选择",
                "options": [
                    {"label": "", "prompt": "空 label"},
                    {"label": "空 prompt", "prompt": ""},
                    {"label": "有效", "prompt": "请继续。"},
                ],
            },
        ])

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["title"], "请选择")
        self.assertEqual(len(cards[0]["options"]), 1)
        self.assertEqual(cards[0]["options"][0]["label"], "有效")

    def test_validate_cards_limits_to_one_card_three_options_and_truncates_text(self):
        long_label = "这是一段超过三十个字符的很长很长很长的标签"
        long_prompt = "继续" * 400
        cards = validate_interactive_cards([
            {
                "type": "quick_replies",
                "title": "第一张",
                "options": [
                    {"label": long_label, "prompt": long_prompt},
                    {"label": "第二", "prompt": "第二个 prompt"},
                    {"label": "第三", "prompt": "第三个 prompt"},
                    {"label": "第四", "prompt": "第四个 prompt"},
                ],
            },
            {
                "type": "choice",
                "title": "第二张",
                "options": [{"label": "不会保留", "prompt": "不会保留"}],
            },
        ])

        self.assertEqual(len(cards), 1)
        self.assertEqual(len(cards[0]["options"]), 3)
        self.assertLessEqual(len(cards[0]["options"][0]["label"]), 30)
        self.assertLessEqual(len(cards[0]["options"][0]["prompt"]), 500)

    async def test_service_invokes_llm_with_user_and_assistant_context(self):
        llm = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='''{"cards":[{"type":"quick_replies","title":"继续", "options":[{"label":"生成计划","prompt":"请生成计划。"}]}]}'''
                )
            )
        )
        service = InteractiveCardService(llm=llm)

        cards = await service.generate("用户想做卡片交互", "可以按协议级方案实现。")

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["type"], "quick_replies")
        llm.ainvoke.assert_awaited_once()
        messages = llm.ainvoke.await_args.args[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertIn("用户想做卡片交互", messages[1].content)
        self.assertIn("可以按协议级方案实现。", messages[1].content)

    async def test_service_returns_empty_when_llm_fails(self):
        llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError("unavailable")))
        service = InteractiveCardService(llm=llm)

        cards = await service.generate("用户消息", "助手回复")

        self.assertEqual(cards, [])

    async def test_service_skips_short_or_error_responses(self):
        llm = SimpleNamespace(ainvoke=AsyncMock())
        service = InteractiveCardService(llm=llm)

        self.assertEqual(await service.generate("hi", "好的"), [])
        self.assertEqual(await service.generate("运行", "错误: 工具失败"), [])
        llm.ainvoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend/`:

```bash
python3 -m unittest tests/test_interactive_cards.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph.interactive_cards'`.

- [ ] **Step 3: Implement card service**

Create `backend/graph/interactive_cards.py`:

```python
"""
Interactive chat card generation and validation.
"""
import json
import math
import re
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

ALLOWED_CARD_TYPES = {"quick_replies", "choice"}
MAX_CARDS = 1
MAX_OPTIONS = 3
MAX_LABEL_LENGTH = 30
MAX_PROMPT_LENGTH = 500
MIN_ASSISTANT_LENGTH = 40

INTERACTIVE_CARD_SYSTEM_PROMPT = """你是 DeepClaw 的交互卡片生成器。

根据用户消息和助手回复，判断是否需要生成一张交互卡片。
只输出 JSON，不要输出 Markdown、解释或额外文本。

输出格式：
{
  "cards": [
    {
      "type": "quick_replies" | "choice",
      "title": "卡片标题",
      "description": "可选描述",
      "options": [
        {"label": "按钮文案", "prompt": "点击后发送给助手的完整用户消息"}
      ]
    }
  ]
}

规则：
- 不适合生成卡片时返回 {"cards": []}。
- 如果助手回复包含多个明确方案，优先生成 type=choice。
- 如果助手回复适合继续追问，生成 type=quick_replies。
- 最多 1 张卡片，最多 3 个选项。
- label 使用简短中文，prompt 使用完整中文问题或指令。
- 不要生成空 title、空 label 或空 prompt。
"""


def _extract_json_payload(text: str) -> Optional[str]:
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def _clean_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _with_ids(card: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(card)
    normalized.setdefault("id", f"card_{uuid.uuid4().hex[:8]}")
    options = []
    for option in normalized.get("options", []):
        normalized_option = dict(option)
        normalized_option.setdefault("id", f"opt_{uuid.uuid4().hex[:8]}")
        options.append(normalized_option)
    normalized["options"] = options
    return normalized


def validate_interactive_cards(cards: Any) -> List[Dict[str, Any]]:
    if not isinstance(cards, list):
        return []

    valid_cards: List[Dict[str, Any]] = []
    for raw_card in cards:
        if len(valid_cards) >= MAX_CARDS:
            break
        if not isinstance(raw_card, dict):
            continue

        card_type = raw_card.get("type")
        title = _clean_text(raw_card.get("title"), 80)
        description = _clean_text(raw_card.get("description"), 160)
        if card_type not in ALLOWED_CARD_TYPES or not title:
            continue

        valid_options = []
        raw_options = raw_card.get("options", [])
        if not isinstance(raw_options, list):
            continue
        for raw_option in raw_options:
            if len(valid_options) >= MAX_OPTIONS:
                break
            if not isinstance(raw_option, dict):
                continue
            label = _clean_text(raw_option.get("label"), MAX_LABEL_LENGTH)
            prompt = _clean_text(raw_option.get("prompt"), MAX_PROMPT_LENGTH)
            if not label or not prompt:
                continue
            valid_options.append(
                {
                    "id": _clean_text(raw_option.get("id"), 64) or f"opt_{uuid.uuid4().hex[:8]}",
                    "label": label,
                    "prompt": prompt,
                }
            )

        if not valid_options:
            continue

        card = {
            "id": _clean_text(raw_card.get("id"), 64) or f"card_{uuid.uuid4().hex[:8]}",
            "type": card_type,
            "title": title,
            "options": valid_options,
        }
        if description:
            card["description"] = description
        valid_cards.append(card)

    return valid_cards


def parse_interactive_cards(text: str) -> List[Dict[str, Any]]:
    payload = _extract_json_payload(text)
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return validate_interactive_cards(data.get("cards", []))


class InteractiveCardService:
    def __init__(self, llm: Any):
        self.llm = llm

    def _should_generate(self, user_message: str, assistant_response: str) -> bool:
        if not self.llm:
            return False
        if len((assistant_response or "").strip()) < MIN_ASSISTANT_LENGTH:
            return False
        if assistant_response.lstrip().startswith("错误:"):
            return False
        return True

    async def generate(self, user_message: str, assistant_response: str) -> List[Dict[str, Any]]:
        if not self._should_generate(user_message, assistant_response):
            return []

        prompt = f"""用户消息：
{user_message}

助手回复：
{assistant_response}

请判断是否需要生成交互卡片，并严格按 JSON 格式返回。"""
        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=INTERACTIVE_CARD_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
            return parse_interactive_cards(getattr(response, "content", ""))
        except Exception:
            return []
```

- [ ] **Step 4: Run tests to verify service passes**

Run from `backend/`:

```bash
python3 -m unittest tests/test_interactive_cards.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/graph/interactive_cards.py backend/tests/test_interactive_cards.py
git commit -m "Add interactive chat card service"
```

---

### Task 2: Agent Integration and Prompt Guidance

**Files:**
- Modify: `backend/graph/agent.py`
- Modify: `backend/graph/prompt_builder.py`
- Test: `backend/tests/test_interactive_cards.py`

- [ ] **Step 1: Add tests for agent and prompt integration**

Append to `backend/tests/test_interactive_cards.py`:

```python
class InteractiveCardIntegrationTests(unittest.TestCase):
    def test_prompt_builder_includes_interactive_card_guidance(self):
        import tempfile
        from pathlib import Path

        from graph.prompt_builder import PromptBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            (base_dir / "workspace").mkdir()
            (base_dir / "memory").mkdir()
            prompt = PromptBuilder(base_dir).build_system_prompt(rag_mode=False)

        self.assertIn("交互卡片", prompt)
        self.assertIn("不要输出 JSON、HTML、按钮代码或任何前端协议字段", prompt)

    async def test_agent_generate_interactive_cards_delegates_to_service(self):
        from graph.agent import AgentManager

        manager = AgentManager()
        original_initialized = manager._initialized
        original_service = getattr(manager, "interactive_cards", None)
        try:
            manager.interactive_cards = SimpleNamespace(
                generate=AsyncMock(return_value=[{"id": "card_1", "type": "quick_replies", "title": "继续", "options": []}])
            )

            cards = await manager.generate_interactive_cards("用户", "助手回复内容足够长，可以继续生成卡片。")

            self.assertEqual(cards[0]["id"], "card_1")
            manager.interactive_cards.generate.assert_awaited_once_with("用户", "助手回复内容足够长，可以继续生成卡片。")
        finally:
            manager.interactive_cards = original_service
            manager._initialized = original_initialized
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend/`:

```bash
python3 -m unittest tests/test_interactive_cards.py -v
```

Expected: FAIL because prompt guidance and `generate_interactive_cards()` do not exist.

- [ ] **Step 3: Update prompt builder**

In `backend/graph/prompt_builder.py`, before `return "\n\n".join(parts)`, append:

```python
        interaction_guide = """<!-- Interactive Chat Cards -->
## 交互卡片友好输出

当回答适合用户继续选择下一步时，请在正文末尾用自然语言列出 2-3 个明确的下一步选项。
如果回答中存在多个可选方案，请用清晰的编号或小标题描述每个方案。
不要输出 JSON、HTML、按钮代码或任何前端协议字段。
交互卡片由系统根据你的自然语言回答自动生成。
"""
        parts.append(interaction_guide)
```

- [ ] **Step 4: Update agent manager**

In `backend/graph/agent.py`:

Add import:

```python
from .interactive_cards import InteractiveCardService
```

Add field in `__init__`:

```python
        self.interactive_cards: Optional[InteractiveCardService] = None
```

Initialize after memory reflection:

```python
        self.interactive_cards = InteractiveCardService(llm=self.llm)
```

Add method near `reflect_memory()` or before `astream()`:

```python
    async def generate_interactive_cards(self, user_message: str, assistant_response: str) -> List[Dict[str, Any]]:
        """Generate structured interactive cards for a completed assistant response."""
        if not self.interactive_cards:
            return []
        return await self.interactive_cards.generate(user_message, assistant_response)
```

- [ ] **Step 5: Run tests**

Run from `backend/`:

```bash
python3 -m unittest tests/test_interactive_cards.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/graph/agent.py backend/graph/prompt_builder.py backend/tests/test_interactive_cards.py
git commit -m "Wire interactive cards into agent prompts"
```

---

### Task 3: SSE Emission and Session Persistence

**Files:**
- Modify: `backend/api/chat.py`
- Modify: `backend/graph/session_manager.py`
- Create: `backend/tests/test_chat_interactive_cards.py`

- [ ] **Step 1: Write backend chat tests**

Create `backend/tests/test_chat_interactive_cards.py`:

```python
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from graph.session_manager import SessionManager


class ChatInteractiveCardsTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_generator_emits_interactive_card_before_done_and_saves_cards(self):
        from api.chat import event_generator

        session_id = "123e4567-e89b-12d3-a456-426614174000"
        cards = [
            {
                "id": "card_1",
                "type": "quick_replies",
                "title": "继续",
                "options": [{"id": "opt_1", "label": "生成计划", "prompt": "请生成计划。"}],
            }
        ]

        async def fake_astream(message, session):
            yield {"type": "token", "content": "这是一个足够长的助手回复，用于触发交互卡片。"}
            yield {"type": "done", "content": "这是一个足够长的助手回复，用于触发交互卡片。", "tool_calls": []}

        manager = SimpleNamespace(
            astream=fake_astream,
            generate_interactive_cards=AsyncMock(return_value=cards),
            reflect_memory=AsyncMock(),
            generate_title=AsyncMock(return_value="标题"),
            session_manager=MagicMock(),
        )

        with patch("api.chat.agent_manager", manager):
            raw_events = []
            async for chunk in event_generator("用户消息", session_id, False):
                raw_events.append(json.loads(chunk.removeprefix("data: ").strip()))

        self.assertEqual([event["type"] for event in raw_events], ["token", "interactive_card", "done"])
        self.assertEqual(raw_events[1]["cards"], cards)
        manager.generate_interactive_cards.assert_awaited_once()
        manager.session_manager.save_message.assert_any_call(session_id, "user", "用户消息")
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "这是一个足够长的助手回复，用于触发交互卡片。", [], cards)

    def test_session_manager_persists_interactive_cards(self):
        session_id = "123e4567-e89b-12d3-a456-426614174000"
        cards = [
            {
                "id": "card_1",
                "type": "choice",
                "title": "请选择",
                "options": [{"id": "opt_1", "label": "A", "prompt": "选择 A"}],
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))
            manager.save_message(session_id, "assistant", "回复", [], cards)
            messages = manager.load_session(session_id)

        self.assertEqual(messages[0]["interactive_cards"], cards)

    async def test_non_streaming_response_includes_cards_and_saves_them(self):
        from api.chat import ChatRequest, chat

        session_id = "123e4567-e89b-12d3-a456-426614174000"
        cards = [
            {
                "id": "card_1",
                "type": "quick_replies",
                "title": "继续",
                "options": [{"id": "opt_1", "label": "总结", "prompt": "请总结。"}],
            }
        ]

        async def fake_astream(message, session):
            yield {"type": "token", "content": "回复内容"}
            yield {"type": "done", "tool_calls": []}

        manager = SimpleNamespace(
            astream=fake_astream,
            generate_interactive_cards=AsyncMock(return_value=cards),
            reflect_memory=AsyncMock(),
            session_manager=MagicMock(load_session=MagicMock(return_value=[])),
        )

        with patch("api.chat.agent_manager", manager):
            result = await chat(ChatRequest(message="用户消息", session_id=session_id, stream=False))

        self.assertEqual(result["interactive_cards"], cards)
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "回复内容", [], cards)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend/`:

```bash
python3 -m unittest tests/test_chat_interactive_cards.py -v
```

Expected: FAIL because cards are not emitted or persisted.

- [ ] **Step 3: Persist cards in session manager**

Change `backend/graph/session_manager.py` `save_message()` signature:

```python
    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        interactive_cards: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
```

After tool calls:

```python
        if interactive_cards:
            message["interactive_cards"] = interactive_cards
```

- [ ] **Step 4: Emit and save cards in streaming chat**

In `backend/api/chat.py`, inside `done` branch, generate cards before saving assistant messages and before yielding `done`:

```python
            assistant_text = "".join(seg.get("content", "") for seg in segments)
            interactive_cards = []
            if assistant_text:
                interactive_cards = await agent_manager.generate_interactive_cards(message, assistant_text)
                if interactive_cards:
                    yield f"data: {json.dumps({'type': 'interactive_card', 'cards': interactive_cards}, ensure_ascii=False)}\n\n"
```

When saving assistant segments, attach cards only to the last assistant segment:

```python
            for index, seg in enumerate(segments):
                cards_for_segment = interactive_cards if index == len(segments) - 1 else None
                agent_manager.session_manager.save_message(
                    session_id,
                    "assistant",
                    seg["content"],
                    seg.get("tool_calls"),
                    cards_for_segment,
                )
```

Keep memory reflection after save.

- [ ] **Step 5: Include cards in non-streaming response**

In non-streaming branch, after `full_content` is complete:

```python
        interactive_cards = []
        if full_content:
            interactive_cards = await agent_manager.generate_interactive_cards(request.message, full_content)
```

Save assistant with cards:

```python
        agent_manager.session_manager.save_message(
            request.session_id, "assistant", full_content, tool_calls, interactive_cards
        )
```

Return cards:

```python
            "interactive_cards": interactive_cards,
```

- [ ] **Step 6: Run tests**

Run from `backend/`:

```bash
python3 -m unittest tests/test_chat_interactive_cards.py tests/test_interactive_cards.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/api/chat.py backend/graph/session_manager.py backend/tests/test_chat_interactive_cards.py
git commit -m "Emit and persist interactive chat cards"
```

---

### Task 4: Frontend Store and API Types

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/store.tsx`

- [ ] **Step 1: Extend API types**

In `frontend/src/lib/api.ts`, add interfaces after `StreamEvent` or before chat API:

```ts
export interface InteractiveCardOption {
  id: string
  label: string
  prompt: string
}

export interface InteractiveCard {
  id: string
  type: 'quick_replies' | 'choice'
  title: string
  description?: string
  options: InteractiveCardOption[]
}
```

Add event type:

```ts
  | 'interactive_card'
```

- [ ] **Step 2: Extend message model and history loading**

In `frontend/src/lib/store.tsx`, import type:

```ts
import { streamChat, getSessions, createSession, deleteSession, getSessionHistory, compressSession, getRAGMode, setRAGMode, type InteractiveCard } from './api'
```

Add to `Message`:

```ts
  interactive_cards?: InteractiveCard[]
```

In `selectSession()` mapping, include:

```ts
        interactive_cards: msg.interactive_cards,
```

- [ ] **Step 3: Handle stream event**

In `sendMessage()` stream event switch, add before `done`:

```ts
          case 'interactive_card':
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, interactive_cards: data.cards || [] }
                : msg
            ))
            break
```

- [ ] **Step 4: Build frontend**

Run from repo root:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/store.tsx
git commit -m "Handle interactive card stream events"
```

---

### Task 5: Frontend Interactive Card UI

**Files:**
- Create: `frontend/src/components/chat/InteractiveCard.tsx`
- Modify: `frontend/src/components/chat/ChatMessage.tsx`

- [ ] **Step 1: Create card component**

Create `frontend/src/components/chat/InteractiveCard.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { MessageSquare, ListChecks } from 'lucide-react'
import { useApp } from '@/lib/store'
import type { InteractiveCard as InteractiveCardType } from '@/lib/api'

interface InteractiveCardProps {
  card: InteractiveCardType
}

export default function InteractiveCard({ card }: InteractiveCardProps) {
  const { sendMessage, isStreaming, currentSessionId } = useApp()
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null)
  const isChoice = card.type === 'choice'

  const handleClick = async (optionId: string, prompt: string) => {
    if (isStreaming || !currentSessionId || !prompt.trim()) return
    setSelectedOptionId(optionId)
    await sendMessage(prompt)
  }

  return (
    <div className="mt-3 rounded-xl border border-apple-border bg-gray-50 p-3">
      <div className="flex items-start gap-2">
        <div className="mt-0.5 text-klein-blue">
          {isChoice ? <ListChecks size={16} /> : <MessageSquare size={16} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-gray-800">{card.title}</div>
          {card.description && (
            <div className="mt-1 text-xs text-gray-500">{card.description}</div>
          )}
          <div className={isChoice ? 'mt-3 space-y-2' : 'mt-3 flex flex-wrap gap-2'}>
            {card.options.map(option => {
              const selected = selectedOptionId === option.id
              return (
                <button
                  key={option.id}
                  onClick={() => handleClick(option.id, option.prompt)}
                  disabled={isStreaming || !currentSessionId}
                  className={
                    isChoice
                      ? `block w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                          selected
                            ? 'border-klein-blue bg-klein-blue/10 text-klein-blue'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-klein-blue/50 hover:text-klein-blue'
                        }`
                      : `rounded-full border px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                          selected
                            ? 'border-klein-blue bg-klein-blue text-white'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-klein-blue/50 hover:text-klein-blue'
                        }`
                  }
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Render cards in chat message**

In `frontend/src/components/chat/ChatMessage.tsx`, add import:

```tsx
import InteractiveCard from './InteractiveCard'
```

After the message bubble `</div>` and before streaming cursor, add:

```tsx
        {!isUser && message.interactive_cards && message.interactive_cards.length > 0 && (
          <div className="w-full">
            {message.interactive_cards.map(card => (
              <InteractiveCard key={card.id} card={card} />
            ))}
          </div>
        )}
```

- [ ] **Step 3: Build frontend**

Run:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/InteractiveCard.tsx frontend/src/components/chat/ChatMessage.tsx
git commit -m "Render interactive chat cards"
```

---

### Task 6: Full Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run backend card tests**

Run from `backend/`:

```bash
python3 -m unittest tests/test_interactive_cards.py tests/test_chat_interactive_cards.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend regression tests**

Run from `backend/`:

```bash
python3 -m unittest tests/test_memory_store.py tests/test_memory_reflection.py tests/test_memory_indexer.py tests/test_memories_api.py tests/test_file_upload_validation.py -v
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run from repo root:

```bash
npm run build --prefix frontend
```

Expected: PASS.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intended source/test files are modified; runtime data such as `backend/memory/memories.jsonl` may remain untracked and should not be committed unless explicitly requested.

- [ ] **Step 5: Commit any final verification fixes**

If verification required small fixes, commit only the relevant source/test files:

```bash
git add <fixed-files>
git commit -m "Complete interactive chat card integration"
```

---

## Self-Review

- Spec coverage: backend generation, SSE event, session persistence, frontend stream handling, historical replay, card rendering, click-to-send, prompt guidance, validation, and failure handling are all covered.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: backend uses `interactive_cards`; frontend `Message` also uses `interactive_cards`; SSE event type is `interactive_card` with `cards` payload.
