"""
并行任务执行器 - 分析依赖关系，自动并行化 TODO 执行

核心逻辑：
1. 分析任务间的依赖关系（同一 Agent 的任务有顺序依赖）
2. 将无依赖的任务分组为可并行组
3. 使用 asyncio.gather 并行执行
4. 合并并行结果，按序产出 SSE 事件

灵感来源: oh-my-opencode 的 background-task + delegate-task 并行模式
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, List, Optional, Set


@dataclass
class ParallelGroup:
    """可并行执行的任务组"""

    todo_indices: List[int]
    group_type: str  # "parallel" or "sequential"


@dataclass
class ParallelResult:
    """单个并行任务的执行结果"""

    todo_index: int
    todo_id: str
    agent: str
    content: str = ""
    tool_calls: List[Dict] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)


class ParallelExecutor:
    """
    并行任务执行器

    分析 ExecutionPlan 中 TODO 的依赖关系，
    将无依赖的 TODO 自动并行化执行，提升效率。

    依赖规则：
    - 同一 Agent 的多个 TODO 必须串行（Agent 上下文依赖）
    - 不同 Agent 的 TODO 可以并行
    - primary_agent 的聚合类 TODO 必须在依赖的 domain agent TODO 之后执行
    """

    # 聚合类关键词 - 这些 TODO 通常需要等待前置 TODO 结果
    _AGGREGATION_KEYWORDS = [
        "汇总",
        "总结",
        "报告",
        "生成报告",
        "输出",
        "整合",
        "summarize",
        "aggregate",
        "report",
        "output",
        "combine",
    ]

    def analyze_dependencies(self, todos: List[Dict[str, Any]]) -> List[ParallelGroup]:
        """
        分析 TODO 列表的依赖关系，返回执行分组

        Args:
            todos: TODO 列表，每项包含 {"id", "content", "agent"}

        Returns:
            并行分组列表，按执行顺序排列
        """
        if not todos:
            return []

        n = len(todos)

        # 构建依赖图
        # deps[i] = set of indices that todo[i] depends on
        deps: List[Set[int]] = [set() for _ in range(n)]

        # 规则1: 同一 Agent 的 TODO 按顺序依赖
        agent_last: Dict[str, int] = {}
        for i, todo in enumerate(todos):
            agent = todo.get("agent", "primary_agent")
            if agent in agent_last:
                deps[i].add(agent_last[agent])
            agent_last[agent] = i

        # 规则2: 聚合类 TODO 依赖同一任务中所有前置 domain agent TODO
        for i, todo in enumerate(todos):
            content = todo.get("content", "").lower()
            is_aggregation = any(kw in content for kw in self._AGGREGATION_KEYWORDS)
            if is_aggregation:
                for j in range(i):
                    agent_j = todos[j].get("agent", "primary_agent")
                    if agent_j != "primary_agent":
                        deps[i].add(j)

        # 拓扑分层 - 每层内的 TODO 可以并行执行
        groups: List[ParallelGroup] = []
        completed: Set[int] = set()

        while len(completed) < n:
            # 找出当前所有依赖已满足的 TODO
            ready = []
            for i in range(n):
                if i not in completed and deps[i].issubset(completed):
                    ready.append(i)

            if not ready:
                # 循环依赖兜底，强制取第一个未完成的
                for i in range(n):
                    if i not in completed:
                        ready.append(i)
                        break

            if len(ready) == 1:
                groups.append(ParallelGroup(todo_indices=ready, group_type="sequential"))
            else:
                groups.append(ParallelGroup(todo_indices=ready, group_type="parallel"))

            completed.update(ready)

        return groups

    async def execute_parallel_group(
        self,
        group: ParallelGroup,
        todos: List[Dict[str, Any]],
        execute_fn: Callable,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行一个并行组

        Args:
            group: 并行分组
            todos: 完整 TODO 列表
            execute_fn: 单个 TODO 的执行函数，签名:
                async def execute_fn(todo, index) -> AsyncGenerator[Dict, None]

        Yields:
            SSE 事件
        """
        if group.group_type == "sequential" or len(group.todo_indices) == 1:
            # 串行执行
            for idx in group.todo_indices:
                async for event in execute_fn(todos[idx], idx):
                    yield event
        else:
            # 并行执行 - 使用 Queue 实现实时流式输出
            yield {
                "type": "parallel_start",
                "group_indices": group.todo_indices,
                "agents": [todos[i].get("agent", "primary_agent") for i in group.todo_indices],
            }

            queue: asyncio.Queue = asyncio.Queue()
            _SENTINEL = object()

            # 每个并行任务的执行结果跟踪
            results_tracker: Dict[int, ParallelResult] = {}

            async def _stream_to_queue(todo: Dict, idx: int) -> None:
                """将单个 TODO 的事件实时推送到共享队列"""
                result = ParallelResult(
                    todo_index=idx,
                    todo_id=todo.get("id", ""),
                    agent=todo.get("agent", "primary_agent"),
                )
                try:
                    async for event in execute_fn(todo, idx):
                        await queue.put(event)
                        if event.get("type") == "token":
                            result.content += event.get("content", "")
                        elif event.get("type") == "tool_end":
                            result.tool_calls.append(
                                {
                                    "tool": event.get("tool", ""),
                                    "input": event.get("input", ""),
                                    "output": event.get("output", ""),
                                }
                            )
                except Exception as e:
                    result.success = False
                    result.error = str(e)
                    await queue.put({"type": "error", "error": str(e), "todo_index": idx})
                results_tracker[idx] = result

            async def _run_all() -> None:
                """并行执行所有任务，完成后放入哨兵信号"""
                tasks = [_stream_to_queue(todos[idx], idx) for idx in group.todo_indices]
                await asyncio.gather(*tasks)
                await queue.put(_SENTINEL)

            # 启动并行生产者
            producer = asyncio.create_task(_run_all())

            # 实时消费并 yield 事件
            while True:
                event = await queue.get()
                if event is _SENTINEL:
                    break
                yield event

            # 确保生产者已完成
            await producer

            yield {
                "type": "parallel_end",
                "group_indices": group.todo_indices,
                "results": [
                    {
                        "todo_index": results_tracker[idx].todo_index,
                        "agent": results_tracker[idx].agent,
                        "success": results_tracker[idx].success,
                        "error": results_tracker[idx].error,
                    }
                    for idx in group.todo_indices
                    if idx in results_tracker
                ],
            }


# 全局单例
_parallel_executor: Optional[ParallelExecutor] = None


def get_parallel_executor() -> ParallelExecutor:
    """获取并行执行器单例"""
    global _parallel_executor
    if _parallel_executor is None:
        _parallel_executor = ParallelExecutor()
    return _parallel_executor
