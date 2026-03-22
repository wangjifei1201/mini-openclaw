"""
Token统计追踪器 - 记录和分析LLM调用消耗

功能：
1. 记录每次LLM调用的输入/输出Token数
2. 按Agent分类统计
3. 按任务聚合统计
4. 实时计算预估消耗
"""
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数

    中文字符平均约 1.5 token/字符，英文约 0.25 token/word。
    这里使用简化公式：字符数 * 2 / 3，保证至少返回 1。
    """
    if not text:
        return 0
    return max(1, len(text) * 2 // 3)


@dataclass
class TokenRecord:
    """单次Token使用记录"""

    agent: str
    input_tokens: int
    output_tokens: int
    timestamp: float
    task_id: Optional[str] = None
    model: Optional[str] = None


@dataclass
class TaskTokenStats:
    """任务级别Token统计"""

    task_id: str
    llm_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_call_count: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    records: List[TokenRecord] = field(default_factory=list)
    llm_calls_by_agent: Dict[str, int] = field(default_factory=dict)
    tokens_by_agent: Dict[str, Dict[str, int]] = field(default_factory=dict)
    tool_calls_by_name: Dict[str, int] = field(default_factory=dict)
    active_agents: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def elapsed_time(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> Dict:
        """转换为字典格式（用于API返回）"""
        return {
            "taskId": self.task_id,
            "llmCallCount": self.llm_call_count,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "toolCallCount": self.tool_call_count,
            "startTime": self.start_time,
            "elapsedTime": self.elapsed_time,
            "llmCallsByAgent": self.llm_calls_by_agent,
            "tokensByAgent": self.tokens_by_agent,
            "toolCallsByName": self.tool_calls_by_name,
            "activeAgents": self.active_agents,
        }


class TokenTracker:
    """
    Token统计追踪器

    使用方式：
    - 全局单例，通过 get_token_tracker() 获取
    - 调用 record_llm_call() 记录LLM调用
    - 调用 record_tool_call() 记录工具调用
    - 调用 get_task_stats() 获取任务统计
    """

    def __init__(self):
        self._lock = Lock()
        self._tasks: Dict[str, TaskTokenStats] = {}
        self._global_records: List[TokenRecord] = []

    def start_task(self, task_id: str) -> None:
        """开始任务追踪"""
        with self._lock:
            if task_id not in self._tasks:
                self._tasks[task_id] = TaskTokenStats(task_id=task_id)

    def end_task(self, task_id: str) -> Optional[TaskTokenStats]:
        """结束任务追踪"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].end_time = time.time()
                return self._tasks[task_id]
        return None

    def record_llm_call(
        self,
        agent: str,
        input_tokens: int,
        output_tokens: int,
        task_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        记录LLM调用

        Args:
            agent: Agent名称
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            task_id: 任务ID（可选）
            model: 模型名称（可选）
        """
        record = TokenRecord(
            agent=agent,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=time.time(),
            task_id=task_id,
            model=model,
        )

        with self._lock:
            self._global_records.append(record)

            # 更新任务统计
            if task_id and task_id in self._tasks:
                task_stats = self._tasks[task_id]
                task_stats.records.append(record)
                task_stats.llm_call_count += 1
                task_stats.input_tokens += input_tokens
                task_stats.output_tokens += output_tokens

                # 按Agent分类统计
                if agent not in task_stats.llm_calls_by_agent:
                    task_stats.llm_calls_by_agent[agent] = 0
                task_stats.llm_calls_by_agent[agent] += 1

                if agent not in task_stats.tokens_by_agent:
                    task_stats.tokens_by_agent[agent] = {"input": 0, "output": 0}
                task_stats.tokens_by_agent[agent]["input"] += input_tokens
                task_stats.tokens_by_agent[agent]["output"] += output_tokens

                # 更新活跃Agent列表
                if agent not in task_stats.active_agents:
                    task_stats.active_agents.append(agent)

    def record_tool_call(
        self,
        tool_name: str,
        task_id: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> None:
        """
        记录工具调用

        Args:
            tool_name: 工具名称
            task_id: 任务ID（可选）
            agent: 调用Agent（可选）
        """
        with self._lock:
            if task_id and task_id in self._tasks:
                task_stats = self._tasks[task_id]
                task_stats.tool_call_count += 1

                if tool_name not in task_stats.tool_calls_by_name:
                    task_stats.tool_calls_by_name[tool_name] = 0
                task_stats.tool_calls_by_name[tool_name] += 1

    def get_task_stats(self, task_id: str) -> Optional[Dict]:
        """获取任务统计"""
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id].to_dict()
        return None

    def get_all_task_stats(self) -> List[Dict]:
        """获取所有任务统计"""
        with self._lock:
            return [stats.to_dict() for stats in self._tasks.values()]

    def clear_task(self, task_id: str) -> None:
        """清除任务统计"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

    def get_global_stats(self) -> Dict:
        """获取全局统计"""
        with self._lock:
            total_input = sum(r.input_tokens for r in self._global_records)
            total_output = sum(r.output_tokens for r in self._global_records)
            return {
                "totalRecords": len(self._global_records),
                "totalInputTokens": total_input,
                "totalOutputTokens": total_output,
                "totalTokens": total_input + total_output,
            }


# 全局单例
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """获取Token追踪器单例"""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker
