"""
能力调度器 - 统一管理技能(Skills)和Domain Agent的选择

架构设计：
1. Skills是"知识注入"：轻量级，适合Primary Agent直接使用
2. Domain Agent是"独立执行单元"：重量级，适合复杂专业任务

调度策略：
- 简单任务 → Primary Agent + Skills
- 复杂任务 → Domain Agent（Domain Agent内部也可使用Skills）
"""
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import get_multi_agent_mode, BASE_DIR


class ExecutionMode(str, Enum):
    """执行模式"""
    PRIMARY_WITH_SKILLS = "primary_skills"   # Primary Agent + 技能注入
    DOMAIN_AGENT = "domain_agent"            # Domain Agent 独立执行
    HYBRID = "hybrid"                        # 混合模式


@dataclass
class CapabilityDecision:
    """能力调度决策"""
    mode: ExecutionMode
    use_skills: List[str]                    # 需要注入的技能
    target_agent: Optional[str] = None       # 目标Domain Agent
    reason: str = ""
    confidence: float = 0.0


class CapabilityDispatcher:
    """
    能力调度器
    
    统一决策是使用Skills还是Domain Agent
    
    设计原则：
    1. Skills = 知识片段，轻量级注入到Prompt
    2. Domain Agent = 独立执行单元，有自己的上下文和工具
    
    调度逻辑：
    - 任务复杂度低 + 有对应Skill → Primary Agent + Skill注入
    - 任务复杂度高 + 需要专业工具 → Domain Agent
    - 跨领域任务 → 多Domain Agent协同
    """
    
    # Domain Agent专属能力（这些必须走Domain Agent）
    DOMAIN_AGENT_EXCLUSIVE = {
        "data_agent": [
            "python执行", "数据分析", "pandas", "numpy", 
            "数据可视化", "matplotlib", "图表生成",
            "大规模数据处理", "复杂计算"
        ],
        "doc_agent": [
            "pdf解析", "word处理", "文档格式转换",
            "批量文档处理", "文档对比"
        ],
    }
    
    # Skills适用场景（轻量级知识注入即可）
    SKILL_PREFERRED = [
        "写作", "翻译", "简单代码生成", "解释",
        "格式化", "总结", "简单查询", "问答"
    ]
    
    # 复杂任务特征（需要Domain Agent）
    COMPLEX_TASK_INDICATORS = [
        r"批量.*", r"大规模.*", r"复杂.*",
        r"多步骤.*", r"需要.*工具", r"执行.*代码",
        r"处理.*数据集", r"分析.*报表", r"生成.*图表"
    ]
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or BASE_DIR
        self.skills_dir = self.base_dir / "skills"
        self._available_skills = self._scan_skills()
    
    def _scan_skills(self) -> Dict[str, Dict]:
        """扫描可用技能"""
        skills = {}
        if not self.skills_dir.exists():
            return skills
        
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    # 解析技能信息
                    content = skill_file.read_text(encoding="utf-8")
                    name = skill_dir.name
                    skills[name] = {
                        "path": str(skill_file.relative_to(self.base_dir)),
                        "keywords": self._extract_keywords(content),
                        "category": self._extract_category(content),
                    }
        
        return skills
    
    def _extract_keywords(self, content: str) -> List[str]:
        """从技能文件中提取关键词"""
        keywords = []
        # 简单提取：寻找常见关键词
        patterns = [
            r"适用[场景情况][:：]\s*(.+?)(?:\n|$)",
            r"关键词[:：]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                keywords.extend([k.strip() for k in match.group(1).split(",")])
        return keywords
    
    def _extract_category(self, content: str) -> str:
        """提取技能类别"""
        if "pdf" in content.lower() or "文档" in content:
            return "document"
        if "数据" in content or "分析" in content:
            return "data"
        return "general"
    
    def decide(self, message: str, available_tools: List[str] = None) -> CapabilityDecision:
        """
        决策执行方式
        
        Args:
            message: 用户消息
            available_tools: 可用工具列表
            
        Returns:
            CapabilityDecision: 调度决策
        """
        message_lower = message.lower()
        
        # 1. 检查是否需要Domain Agent专属能力
        for agent, keywords in self.DOMAIN_AGENT_EXCLUSIVE.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return CapabilityDecision(
                        mode=ExecutionMode.DOMAIN_AGENT,
                        use_skills=[],
                        target_agent=agent,
                        reason=f"需要{agent}专属能力：{keyword}",
                        confidence=0.9
                    )
        
        # 2. 检查是否为复杂任务
        for pattern in self.COMPLEX_TASK_INDICATORS:
            if re.search(pattern, message):
                # 判断需要哪种Agent
                if any(k in message_lower for k in ["数据", "分析", "计算", "图表"]):
                    return CapabilityDecision(
                        mode=ExecutionMode.DOMAIN_AGENT,
                        use_skills=[],
                        target_agent="data_agent",
                        reason="复杂数据处理任务，需要专业工具",
                        confidence=0.85
                    )
                if any(k in message_lower for k in ["文档", "pdf", "word", "批量"]):
                    return CapabilityDecision(
                        mode=ExecutionMode.DOMAIN_AGENT,
                        use_skills=[],
                        target_agent="doc_agent",
                        reason="复杂文档处理任务，需要专业工具",
                        confidence=0.85
                    )
        
        # 3. 检查是否有匹配的Skill（轻量级任务）
        matched_skills = []
        for skill_name, skill_info in self._available_skills.items():
            for keyword in skill_info.get("keywords", []):
                if keyword.lower() in message_lower:
                    matched_skills.append(skill_name)
                    break
        
        # 4. 检查是否适合Skills处理
        for keyword in self.SKILL_PREFERRED:
            if keyword in message_lower:
                return CapabilityDecision(
                    mode=ExecutionMode.PRIMARY_WITH_SKILLS,
                    use_skills=matched_skills,
                    reason=f"轻量级任务，通过技能注入即可完成",
                    confidence=0.8
                )
        
        # 5. 默认：Primary Agent + 可能的Skills
        return CapabilityDecision(
            mode=ExecutionMode.PRIMARY_WITH_SKILLS,
            use_skills=matched_skills,
            reason="通用任务，由Primary Agent处理",
            confidence=0.6
        )
    
    def get_execution_plan(self, message: str) -> Dict:
        """
        获取执行计划（供前端展示）
        
        Returns:
            执行计划详情
        """
        decision = self.decide(message)
        
        return {
            "mode": decision.mode.value,
            "use_skills": decision.use_skills,
            "target_agent": decision.target_agent,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "description": self._get_description(decision),
        }
    
    def _get_description(self, decision: CapabilityDecision) -> str:
        """获取执行方式描述"""
        if decision.mode == ExecutionMode.DOMAIN_AGENT:
            return f"将由 {decision.target_agent} 独立执行，该Agent拥有专业工具和独立上下文"
        elif decision.mode == ExecutionMode.PRIMARY_WITH_SKILLS:
            if decision.use_skills:
                return f"由 Primary Agent 执行，并注入以下技能知识：{', '.join(decision.use_skills)}"
            return "由 Primary Agent 直接执行"
        else:
            return "混合模式执行"


# 全局单例
_capability_dispatcher: Optional[CapabilityDispatcher] = None


def get_capability_dispatcher() -> CapabilityDispatcher:
    """获取能力调度器单例"""
    global _capability_dispatcher
    if _capability_dispatcher is None:
        _capability_dispatcher = CapabilityDispatcher()
    return _capability_dispatcher


def decide_execution(message: str) -> CapabilityDecision:
    """决策执行方式（便捷函数）"""
    return get_capability_dispatcher().decide(message)