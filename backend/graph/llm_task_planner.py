"""
LLM Task Planner - LLM-driven intelligent task dispatch

Replaces hardcoded keyword-to-agent mappings with a single LLM call
that dynamically reads agent capabilities and generates execution plans.
"""
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class PlannedTodo:
    """LLM-planned todo step"""

    content: str
    agent_name: str


@dataclass
class ExecutionPlan:
    """LLM-generated execution plan"""

    strategy: str  # "single" or "multi"
    todos: List[PlannedTodo] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0
    source: str = "llm"  # "llm" or "fallback"


# Capability cache
_capabilities_cache: Optional[str] = None
_capabilities_cache_time: float = 0
_CACHE_TTL = 60  # seconds


def collect_agent_capabilities(coordinator, base_dir: Path) -> str:
    """
    Collect available agent capabilities from coordinator registry + workspace files.

    Args:
        coordinator: CoordinationManager instance
        base_dir: Project root directory

    Returns:
        Compact text summary of agent capabilities
    """
    global _capabilities_cache, _capabilities_cache_time

    now = time.time()
    if _capabilities_cache and (now - _capabilities_cache_time) < _CACHE_TTL:
        return _capabilities_cache

    lines = []
    agents = coordinator.get_available_agents()

    for name, info in agents.items():
        agent_type = info.get("type", "unknown")
        skills = info.get("skills", [])

        # Build header
        header = f"[{name}] type={agent_type}, skills=[{','.join(skills)}]"

        # Read IDENTITY.md for capability description (first 300 chars)
        capability_desc = ""
        identity_paths = [
            base_dir / "workspace" / "universal_agents" / name / "IDENTITY.md",
            base_dir / "workspace" / "domain_agents" / name / "IDENTITY.md",
            base_dir / "workspace" / name / "IDENTITY.md",
        ]
        for identity_path in identity_paths:
            if identity_path.exists():
                try:
                    content = identity_path.read_text(encoding="utf-8")
                    # Extract capability section or use first 300 chars
                    capability_desc = content[:300].strip()
                    if len(content) > 300:
                        capability_desc += "..."
                except Exception:
                    pass
                break

        if capability_desc:
            lines.append(f"{header}\n{capability_desc}")
        else:
            lines.append(header)

    result = "\n\n".join(lines)
    _capabilities_cache = result
    _capabilities_cache_time = now
    return result


def _build_planner_prompt(capabilities_text: str) -> str:
    """Build the system prompt for the LLM planner."""
    return f"""You are a task planner. Based on the user message and available agents, decide the execution strategy.

## Available Agents
{capabilities_text}

## Rules
1. Simple chat/QA/translation/writing/greeting -> strategy=single, todos=[]
2. Tasks needing specialized tools (data analysis, document processing, etc.) -> strategy=multi, generate todos
3. Each todo step specifies the most suitable agent_name
4. primary_agent handles general tasks and result aggregation
5. Domain agents handle tasks requiring their specialized tools
6. ONLY use agent names listed above
7. Keep todos concise (2-4 steps typically)

## Output (strict JSON, no other text)
{{"strategy":"single or multi","reason":"one sentence in Chinese","confidence":0.0-1.0,"todos":[{{"content":"step description","agent_name":"agent_name"}}]}}

When strategy=single, todos must be an empty array []."""


def _parse_llm_response(text: str, available_agents: Dict[str, Any]) -> Optional[ExecutionPlan]:
    """
    Parse LLM response into ExecutionPlan with multi-layer extraction.

    Args:
        text: Raw LLM response text
        available_agents: Dict of available agent names -> info

    Returns:
        ExecutionPlan if parsing succeeds, None otherwise
    """
    if not text:
        return None

    # Strip <think>...</think> tags (some models output thinking process)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Layer 1: Direct JSON parse
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Layer 2: Regex extract outermost JSON object
    if parsed is None:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                parsed = json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass

    # Layer 3: Extract from markdown code block
    if parsed is None:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass

    if not parsed or not isinstance(parsed, dict):
        return None

    # Validate strategy
    strategy = parsed.get("strategy", "")
    if strategy not in ("single", "multi"):
        return None

    # Parse todos
    todos = []
    raw_todos = parsed.get("todos", [])
    if isinstance(raw_todos, list):
        for item in raw_todos:
            if not isinstance(item, dict):
                continue
            content = item.get("content", "")
            agent_name = item.get("agent_name", "primary_agent")
            if not content:
                continue
            # Replace unknown agent with primary_agent
            if agent_name not in available_agents:
                agent_name = "primary_agent"
            todos.append(PlannedTodo(content=content, agent_name=agent_name))

    return ExecutionPlan(
        strategy=strategy,
        todos=todos,
        reason=parsed.get("reason", ""),
        confidence=float(parsed.get("confidence", 0.5)),
        source="llm",
    )


def _fallback_plan(message: str) -> ExecutionPlan:
    """
    Generate a fallback plan using existing keyword-based logic.

    Reuses StrategySelector and TaskExecutor templates when LLM planning fails.
    """
    from graph.strategy_selector import ExecutionStrategy, get_strategy_selector
    from graph.task_executor import TaskExecutor

    try:
        selector = get_strategy_selector()
        analysis = selector.analyze(message)

        if analysis.strategy == ExecutionStrategy.MULTI_AGENT:
            # Use task templates to generate todos
            executor = TaskExecutor()
            task_type = executor._analyze_task_type(message)
            template = executor.TASK_TEMPLATES.get(task_type, executor.TASK_TEMPLATES["general"])

            todos = [PlannedTodo(content=item["content"], agent_name=item["agent"]) for item in template]

            return ExecutionPlan(
                strategy="multi",
                todos=todos,
                reason=analysis.reason or "Fallback: keyword-based analysis",
                confidence=analysis.confidence,
                source="fallback",
            )
    except Exception:
        pass

    # Ultimate fallback: single agent
    return ExecutionPlan(
        strategy="single",
        todos=[],
        reason="Fallback: default to single agent",
        confidence=0.5,
        source="fallback",
    )


class LLMTaskPlanner:
    """
    LLM-driven task planner.

    Collects agent capabilities dynamically and uses a single LLM call
    to generate an execution plan for the incoming user message.
    """

    def __init__(self, llm, coordinator, base_dir: Path):
        self.llm = llm
        self.coordinator = coordinator
        self.base_dir = base_dir

    async def plan_execution(self, message: str) -> ExecutionPlan:
        """
        Generate an execution plan for the user message using LLM.

        Args:
            message: User's raw message

        Returns:
            ExecutionPlan with strategy, todos, and metadata
        """
        try:
            # Collect agent capabilities
            capabilities_text = collect_agent_capabilities(self.coordinator, self.base_dir)

            # Build prompt
            system_prompt = _build_planner_prompt(capabilities_text)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message),
            ]

            # Call LLM (non-streaming, with timeout)
            response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=10)

            # Extract text from response
            response_text = ""
            if hasattr(response, "content"):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response

            # Parse response
            available_agents = self.coordinator.get_available_agents()
            plan = _parse_llm_response(response_text, available_agents)

            if plan:
                return plan

            # Parse failed, fallback
            print(f"[LLMTaskPlanner] Parse failed, using fallback. Raw: {response_text[:200]}")
            return _fallback_plan(message)

        except asyncio.TimeoutError:
            print("[LLMTaskPlanner] LLM call timed out, using fallback")
            return _fallback_plan(message)
        except Exception as e:
            print(f"[LLMTaskPlanner] Error: {e}, using fallback")
            return _fallback_plan(message)


# ============ Module singleton ============

_task_planner: Optional[LLMTaskPlanner] = None


def init_task_planner(llm, coordinator, base_dir: Path) -> LLMTaskPlanner:
    """Initialize the LLM task planner singleton."""
    global _task_planner
    _task_planner = LLMTaskPlanner(llm, coordinator, base_dir)
    return _task_planner


def get_task_planner() -> Optional[LLMTaskPlanner]:
    """Get the LLM task planner singleton."""
    return _task_planner
