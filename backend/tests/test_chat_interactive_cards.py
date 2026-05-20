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
                raw_events.append(json.loads(chunk[len("data: "):].strip()))

        self.assertEqual([event["type"] for event in raw_events], ["token", "interactive_card", "done"])
        self.assertEqual(raw_events[1]["cards"], cards)
        manager.generate_interactive_cards.assert_awaited_once_with("用户消息", "这是一个足够长的助手回复，用于触发交互卡片。")
        manager.session_manager.save_message.assert_any_call(session_id, "user", "用户消息")
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "这是一个足够长的助手回复，用于触发交互卡片。", [], cards)

    async def test_event_generator_continues_when_interactive_card_generation_raises(self):
        from api.chat import event_generator

        session_id = "123e4567-e89b-12d3-a456-426614174000"

        async def fake_astream(message, session):
            yield {"type": "token", "content": "回复内容"}
            yield {"type": "done", "content": "回复内容", "tool_calls": []}

        manager = SimpleNamespace(
            astream=fake_astream,
            generate_interactive_cards=AsyncMock(side_effect=RuntimeError("card failure")),
            reflect_memory=AsyncMock(),
            generate_title=AsyncMock(return_value="标题"),
            session_manager=MagicMock(),
        )

        with patch("api.chat.agent_manager", manager):
            raw_events = []
            async for chunk in event_generator("用户消息", session_id, False):
                raw_events.append(json.loads(chunk[len("data: "):].strip()))

        self.assertEqual([event["type"] for event in raw_events], ["token", "done"])
        self.assertNotIn("interactive_card", [event["type"] for event in raw_events])
        manager.session_manager.save_message.assert_any_call(session_id, "user", "用户消息")
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "回复内容", [], [])

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
        manager.generate_interactive_cards.assert_awaited_once_with("用户消息", "回复内容")
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "回复内容", [], cards)

    async def test_non_streaming_response_continues_when_interactive_card_generation_raises(self):
        from api.chat import ChatRequest, chat

        session_id = "123e4567-e89b-12d3-a456-426614174000"

        async def fake_astream(message, session):
            yield {"type": "token", "content": "回复内容"}
            yield {"type": "done", "tool_calls": []}

        manager = SimpleNamespace(
            astream=fake_astream,
            generate_interactive_cards=AsyncMock(side_effect=RuntimeError("card failure")),
            reflect_memory=AsyncMock(),
            session_manager=MagicMock(load_session=MagicMock(return_value=[])),
        )

        with patch("api.chat.agent_manager", manager):
            result = await chat(ChatRequest(message="用户消息", session_id=session_id, stream=False))

        self.assertEqual(result["content"], "回复内容")
        self.assertEqual(result["interactive_cards"], [])
        manager.session_manager.save_message.assert_any_call(session_id, "assistant", "回复内容", [], [])


if __name__ == "__main__":
    unittest.main()
