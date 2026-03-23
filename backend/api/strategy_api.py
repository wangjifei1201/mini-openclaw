"""
策略分析 API - 分析任务执行策略
"""
from typing import List, Optional

from fastapi import APIRouter
from graph.capability_dispatcher import ExecutionMode, get_capability_dispatcher
from graph.strategy_selector import analyze_task
from pydantic import BaseModel

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """策略分析请求"""

    message: str


class AnalyzeResponse(BaseModel):
    """策略分析响应"""

    strategy: str
    task_type: Optional[str] = None
    target_agent: Optional[str] = None
    confidence: float
    reason: str
    sub_tasks: Optional[List] = None
    # 新增：能力调度信息
    execution_mode: str = "primary_skills"
    use_skills: List[str] = []
    description: str = ""


@router.post("/config/analyze-strategy")
async def analyze_execution_strategy(request: AnalyzeRequest):
    """
    分析任务执行策略

    根据消息内容判断：
    - 使用单Agent还是多Agent协同
    - 如果是多Agent，分发给哪个Domain Agent
    - 使用技能注入还是Domain Agent独立执行

    返回分析结果供前端展示
    """
    # 1. 基础策略分析
    analysis = analyze_task(request.message)

    # 2. 能力调度决策（Skills vs Domain Agent）
    dispatcher = get_capability_dispatcher()
    capability_decision = dispatcher.decide(request.message)

    return {
        "strategy": analysis.strategy.value,
        "task_type": analysis.task_type,
        "target_agent": capability_decision.target_agent or analysis.target_agent,
        "confidence": max(analysis.confidence, capability_decision.confidence),
        "reason": capability_decision.reason or analysis.reason,
        "sub_tasks": analysis.sub_tasks,
        # 新增
        "execution_mode": capability_decision.mode.value,
        "use_skills": capability_decision.use_skills,
        "description": dispatcher._get_description(capability_decision),
    }


@router.get("/config/execution-modes")
async def get_execution_modes():
    """
    获取执行模式说明

    帮助用户理解系统的执行方式
    """
    return {
        "modes": [
            {
                "name": "primary_skills",
                "label": "Primary Agent + 技能注入",
                "description": "轻量级任务，通过将技能知识注入到Primary Agent的System Prompt中执行",
                "examples": ["写作文章", "翻译文档", "简单代码生成", "问答咨询"],
                "when_to_use": "任务简单、不需要专业工具、知识注入即可完成",
            },
            {
                "name": "domain_agent",
                "label": "Domain Agent 独立执行",
                "description": "复杂专业任务，由专门的Domain Agent使用专业工具执行",
                "examples": ["数据分析", "PDF解析", "批量文档处理", "代码执行"],
                "when_to_use": "任务复杂、需要专业工具、需要独立上下文",
            },
            {
                "name": "hybrid",
                "label": "混合模式",
                "description": "跨领域任务，由多个Agent协同执行",
                "examples": ["分析数据并生成报告文档", "解析文档后进行数据分析"],
                "when_to_use": "任务涉及多个专业领域",
            },
        ],
        "domain_agents": [
            {
                "name": "code_agent",
                "capabilities": ["代码生成", "代码审查", "调试", "测试", "重构"],
                "tools": ["python_repl", "terminal", "read_file", "write_file"],
            },
            {
                "name": "research_agent",
                "capabilities": ["信息检索", "PDF解析", "文档提取", "事实核查", "报告生成"],
                "tools": ["fetch_url", "read_file", "write_file", "python_repl", "search_knowledge_base"],
            },
            {
                "name": "creative_agent",
                "capabilities": ["内容创作", "文案写作", "翻译", "文档生成", "创意设计"],
                "tools": ["read_file", "write_file", "python_repl"],
            },
            {
                "name": "data_agent",
                "capabilities": ["Python代码执行", "数据分析", "数据可视化", "表格处理"],
                "tools": ["python_repl", "read_file", "write_file"],
            },
        ],
    }
