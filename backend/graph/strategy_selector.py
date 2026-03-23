"""
策略选择器 - 决定使用单Agent还是多Agent协同执行
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from config import get_multi_agent_mode


class ExecutionStrategy(str, Enum):
    """执行策略枚举"""

    SINGLE_AGENT = "single"  # 单Agent执行
    MULTI_AGENT = "multi"  # 多Agent协同


@dataclass
class TaskAnalysis:
    """任务分析结果"""

    strategy: ExecutionStrategy
    task_type: Optional[str] = None
    target_agent: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    sub_tasks: Optional[List[Dict]] = None


class StrategySelector:
    """
    策略选择器

    根据任务特征决定执行策略：
    - 单Agent：简单任务，不需要跨领域协作
    - 多Agent：复杂任务，需要拆分和协同
    """

    # 多Agent任务关键词
    MULTI_AGENT_KEYWORDS = {
        "data_processing": [
            "数据分析",
            "统计分析",
            "数据清洗",
            "数据处理",
            "csv",
            "excel",
            "表格",
            "数据可视化",
            "图表生成",
            "计算",
            "统计",
            "平均值",
            "总和",
            "趋势分析",
        ],
        "code_task": [
            "代码生成",
            "编写代码",
            "代码审查",
            "代码调试",
            "bug修复",
            "单元测试",
            "重构",
            "code review",
            "实现功能",
            "编程",
            "开发",
            "debug",
        ],
        "research_task": ["调研", "搜索", "查询", "检索", "资料收集", "网络搜索", "事实核查", "信息提取", "文档解析", "pdf分析", "word处理", "解析文档"],
        "creative_task": ["撰写文档", "写作", "翻译", "文案", "内容创作", "报告撰写", "方案设计", "润色", "文档生成", "copywriting"],
    }

    # 复杂任务特征（需要多Agent）
    COMPLEX_TASK_PATTERNS = [
        r"先.*再.*",  # 先...再...（多步骤）
        r"然后.*最后.*",  # 然后...最后...
        r"同时.*",  # 同时处理
        r"分别.*",  # 分别处理
        r"多个.*",  # 多个文件/任务
        r"批量.*",  # 批量处理
        r"对比.*",  # 对比分析
        r"整合.*",  # 整合多个来源
        r"汇总.*",  # 汇总结果
    ]

    # 简单任务特征（单Agent即可）
    SIMPLE_TASK_PATTERNS = [
        r"你好",
        r"介绍一下",
        r"什么是",
        r"解释一下",
        r"帮我写.*代码",
        r"生成.*",
        r"翻译",
        r"简单.*",
        r"快速.*",
        r"只需要.*",
    ]

    def __init__(self):
        self.multi_agent_mode = get_multi_agent_mode()

    def analyze(self, message: str) -> TaskAnalysis:
        """
        分析任务并选择执行策略

        Args:
            message: 用户消息

        Returns:
            TaskAnalysis: 任务分析结果
        """
        # 检查多Agent模式是否开启
        if not self.multi_agent_mode:
            return TaskAnalysis(strategy=ExecutionStrategy.SINGLE_AGENT, reason="多Agent模式未开启，使用单Agent执行")

        message_lower = message.lower()

        # 1. 检查是否为简单任务
        for pattern in self.SIMPLE_TASK_PATTERNS:
            if re.search(pattern, message):
                return TaskAnalysis(strategy=ExecutionStrategy.SINGLE_AGENT, confidence=0.8, reason="简单任务，单Agent即可完成")

        # 2. 检查是否为复杂任务（多步骤）
        for pattern in self.COMPLEX_TASK_PATTERNS:
            if re.search(pattern, message):
                return TaskAnalysis(strategy=ExecutionStrategy.MULTI_AGENT, confidence=0.9, reason="复杂多步骤任务，需要多Agent协同")

        # 3. 检查任务类型关键词
        detected_types = []
        for task_type, keywords in self.MULTI_AGENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    detected_types.append(task_type)
                    break

        if len(detected_types) == 0:
            # 没有检测到特定领域任务
            return TaskAnalysis(strategy=ExecutionStrategy.SINGLE_AGENT, confidence=0.6, reason="通用任务，单Agent执行")

        if len(detected_types) == 1:
            # 单一领域任务
            task_type = detected_types[0]
            target_agent = self._get_target_agent(task_type)
            return TaskAnalysis(
                strategy=ExecutionStrategy.MULTI_AGENT,
                task_type=task_type,
                target_agent=target_agent,
                confidence=0.8,
                reason=f"检测到{task_type}任务，分发给{target_agent}",
            )

        # 多领域任务
        sub_tasks = []
        for task_type in detected_types:
            target_agent = self._get_target_agent(task_type)
            sub_tasks.append(
                {
                    "task_type": task_type,
                    "target_agent": target_agent,
                }
            )

        return TaskAnalysis(
            strategy=ExecutionStrategy.MULTI_AGENT,
            task_type="mixed",
            confidence=0.9,
            reason=f"跨领域任务，需要{len(detected_types)}个Agent协同",
            sub_tasks=sub_tasks,
        )

    def _get_target_agent(self, task_type: str) -> str:
        """根据任务类型获取目标Agent"""
        mapping = {
            "data_processing": "data_agent",
            "data_analysis": "data_agent",
            "code_task": "code_agent",
            "code_generation": "code_agent",
            "research_task": "research_agent",
            "web_research": "research_agent",
            "creative_task": "creative_agent",
            "content_writing": "creative_agent",
        }
        return mapping.get(task_type, "primary_agent")

    def should_dispatch_to_domain_agent(self, message: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        判断是否需要分发给Domain Agent

        Returns:
            (need_dispatch, target_agent, task_type)
        """
        analysis = self.analyze(message)

        if analysis.strategy == ExecutionStrategy.MULTI_AGENT and analysis.target_agent:
            return True, analysis.target_agent, analysis.task_type

        return False, None, None


# 全局单例
_strategy_selector: Optional[StrategySelector] = None


def get_strategy_selector() -> StrategySelector:
    """获取策略选择器单例"""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = StrategySelector()
    return _strategy_selector


def analyze_task(message: str) -> TaskAnalysis:
    """分析任务（便捷函数）"""
    return get_strategy_selector().analyze(message)
