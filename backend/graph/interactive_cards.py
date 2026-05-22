"""
Interactive chat card generation and validation.
"""
import json
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
UNSAFE_PROMPT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"<[^>]+>",
        r"\[[^\]]+\]\([^)]*\)",
        r"\b(?:system|developer|assistant)\s*:",
        r"ignore\s+(?:previous|all|above)\s+instructions?",
    )
]

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


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_safe_prompt(prompt: str) -> bool:
    return not any(pattern.search(prompt) for pattern in UNSAFE_PROMPT_PATTERNS)


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
        title = _clean_text(raw_card.get("title"))
        description = _clean_text(raw_card.get("description"))
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
            label = _clean_text(raw_option.get("label"))
            prompt = _clean_text(raw_option.get("prompt"))
            if not label or not prompt:
                continue
            if len(label) > MAX_LABEL_LENGTH or len(prompt) > MAX_PROMPT_LENGTH:
                continue
            if not _is_safe_prompt(prompt):
                continue
            valid_options.append(
                {
                    "id": _clean_text(raw_option.get("id")) or f"opt_{uuid.uuid4().hex[:8]}",
                    "label": label,
                    "prompt": prompt,
                }
            )

        if not valid_options:
            continue

        card = {
            "id": _clean_text(raw_card.get("id")) or f"card_{uuid.uuid4().hex[:8]}",
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
