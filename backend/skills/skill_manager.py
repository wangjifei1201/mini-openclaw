"""
技能管理器 - 技能注册、匹配和加载

技能是可复用的任务处理模板，包含：
- 触发模式（关键词/正则）
- 推荐 Agent
- 所需工具
- 提示模板

灵感来源: oh-my-opencode 的 builtin-skills + skill-mcp 系统
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Skill:
    """技能定义"""

    name: str
    description: str
    trigger_patterns: List[str]  # 触发关键词
    agent: str  # 推荐使用的 Agent
    tools: List[str]  # 所需工具
    prompt_template: str  # 提示模板内容
    priority: int = 100  # 优先级，越小越先匹配
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "trigger_patterns": self.trigger_patterns,
            "agent": self.agent,
            "tools": self.tools,
            "priority": self.priority,
            "enabled": self.enabled,
        }


# 内置技能定义
BUILTIN_SKILLS: List[Skill] = [
    Skill(
        name="data-wizard",
        description="数据分析与可视化专家，处理 CSV/Excel 数据统计、图表生成等任务",
        trigger_patterns=[
            "分析数据",
            "数据分析",
            "统计分析",
            "可视化",
            "图表",
            "CSV",
            "Excel",
            "数据处理",
            "柱状图",
            "折线图",
            "饼图",
            "散点图",
            "data analysis",
            "visualization",
            "chart",
        ],
        agent="data_agent",
        tools=["python_repl", "read_file", "write_file"],
        prompt_template="""你是一位专业的数据分析师。请按照以下步骤处理任务：

1. **数据理解**: 首先读取并理解数据的结构、字段含义和数据量
2. **数据清洗**: 处理缺失值、异常值和数据类型转换
3. **统计分析**: 执行描述性统计、相关性分析等
4. **可视化**: 使用 matplotlib/seaborn 生成清晰的图表
5. **报告**: 用简洁的语言总结分析发现

注意：
- 优先使用 pandas 处理数据
- 图表必须包含标题、轴标签和图例
- 中文显示使用 plt.rcParams['font.sans-serif'] = ['SimHei']
""",
        priority=10,
    ),
    Skill(
        name="doc-master",
        description="文档处理专家，解析 PDF/Word/文本文档，提取关键信息",
        trigger_patterns=[
            "文档",
            "PDF",
            "Word",
            "解析文档",
            "提取",
            "摘要",
            "总结文档",
            "格式转换",
            "document",
            "parse",
            "extract",
            "summary",
        ],
        agent="research_agent",
        tools=["python_repl", "read_file", "write_file"],
        prompt_template="""你是一位专业的文档处理专家。请按照以下步骤处理任务：

1. **文档解析**: 读取并解析文档内容（支持 PDF、Word、纯文本）
2. **结构识别**: 识别文档的标题、段落、表格等结构
3. **信息提取**: 根据用户需求提取关键信息
4. **格式化输出**: 将提取结果格式化为清晰的结构化输出

注意：
- PDF 解析优先使用 PyPDF2 或 pdfplumber
- Word 解析使用 python-docx
- 保持原文关键信息的准确性
""",
        priority=10,
    ),
    Skill(
        name="code-reviewer",
        description="代码审查专家，分析代码质量、安全性和性能",
        trigger_patterns=[
            "代码审查",
            "review",
            "代码质量",
            "代码检查",
            "安全审计",
            "性能分析",
            "code review",
            "审查代码",
            "代码优化建议",
            "审查",
            "代码安全",
        ],
        agent="primary_agent",
        tools=["read_file", "python_repl"],
        prompt_template="""你是一位资深的代码审查专家。请按照以下维度审查代码：

1. **正确性**: 逻辑是否正确，边界条件是否处理
2. **安全性**: 是否存在注入、XSS、敏感信息泄露等安全风险
3. **性能**: 是否存在性能瓶颈，算法复杂度是否合理
4. **可维护性**: 代码结构、命名、注释是否清晰
5. **测试覆盖**: 是否有充分的测试覆盖

输出格式：
- 按严重程度分类（Critical / Warning / Info）
- 每个问题标注具体文件和行号
- 提供改进建议和代码示例
""",
        priority=20,
    ),
    Skill(
        name="web-scraper",
        description="网页抓取专家，从 URL 获取和解析网页内容",
        trigger_patterns=[
            "抓取",
            "爬取",
            "网页",
            "URL",
            "链接",
            "获取网页",
            "下载",
            "fetch",
            "scrape",
            "crawl",
            "web page",
        ],
        agent="primary_agent",
        tools=["fetch_url", "python_repl", "write_file"],
        prompt_template="""你是一位网页抓取专家。请按照以下步骤处理任务：

1. **访问页面**: 使用 fetch_url 工具获取网页内容
2. **内容解析**: 提取用户需要的关键信息
3. **数据整理**: 将提取结果整理为结构化格式
4. **结果输出**: 按用户要求的格式输出

注意：
- 遵守 robots.txt 规范
- 处理编码问题
- 对大量数据做分页处理
""",
        priority=30,
    ),
]


class SkillManager:
    """
    技能管理器

    负责：
    1. 技能注册和管理
    2. 基于消息内容匹配技能
    3. 加载技能提示模板
    4. 从文件系统加载自定义技能
    """

    def __init__(self, base_dir: Path = None):
        self._skills: Dict[str, Skill] = {}
        self._base_dir = base_dir

        # 注册内置技能
        for skill in BUILTIN_SKILLS:
            self.register(skill)

        # 加载自定义技能
        if base_dir:
            self._load_custom_skills(base_dir)

    def register(self, skill: Skill) -> None:
        """注册技能"""
        self._skills[skill.name] = skill

    def unregister(self, skill_name: str) -> bool:
        """注销技能"""
        if skill_name in self._skills:
            del self._skills[skill_name]
            return True
        return False

    def match(self, message: str) -> Optional[Skill]:
        """
        根据消息内容匹配最合适的技能

        Args:
            message: 用户消息

        Returns:
            匹配的技能，无匹配返回 None
        """
        message_lower = message.lower()
        candidates = []

        for skill in self._skills.values():
            if not skill.enabled:
                continue

            match_count = 0
            for pattern in skill.trigger_patterns:
                if pattern.lower() in message_lower:
                    match_count += 1

            if match_count > 0:
                candidates.append((skill, match_count))

        if not candidates:
            return None

        # 按匹配数 * 优先级排序（匹配多 + 优先级高 = 靠前）
        candidates.sort(key=lambda x: (-x[1], x[0].priority))
        return candidates[0][0]

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定技能"""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有技能"""
        return [skill.to_dict() for skill in sorted(self._skills.values(), key=lambda s: s.priority)]

    def get_skill_prompt(self, skill_name: str) -> str:
        """
        获取技能的提示模板

        Args:
            skill_name: 技能名称

        Returns:
            提示模板文本
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return ""
        return skill.prompt_template

    def _load_custom_skills(self, base_dir: Path) -> None:
        """
        从文件系统加载自定义技能

        扫描 skills/builtins/ 目录下的 SKILL.md 文件
        """
        skills_dir = base_dir / "skills" / "builtins"
        if not skills_dir.exists():
            return

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                content = skill_file.read_text(encoding="utf-8")
                skill = self._parse_skill_file(skill_dir.name, content)
                if skill:
                    self.register(skill)
            except Exception as e:
                print(f"[SkillManager] Failed to load skill from {skill_dir}: {e}")

    def _parse_skill_file(self, name: str, content: str) -> Optional[Skill]:
        """
        解析 SKILL.md 文件

        简单格式：
        ---
        description: 技能描述
        agent: agent_name
        tools: tool1, tool2
        triggers: keyword1, keyword2
        ---

        提示模板内容
        """
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        # 解析 frontmatter
        frontmatter = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()

        prompt_template = parts[2].strip()

        return Skill(
            name=name,
            description=frontmatter.get("description", ""),
            trigger_patterns=[t.strip() for t in frontmatter.get("triggers", "").split(",") if t.strip()],
            agent=frontmatter.get("agent", "primary_agent"),
            tools=[t.strip() for t in frontmatter.get("tools", "").split(",") if t.strip()],
            prompt_template=prompt_template,
            priority=int(frontmatter.get("priority", "100")),
        )


# 全局单例
_skill_manager: Optional[SkillManager] = None


def init_skill_manager(base_dir: Path) -> SkillManager:
    """初始化技能管理器"""
    global _skill_manager
    _skill_manager = SkillManager(base_dir)
    return _skill_manager


def get_skill_manager() -> Optional[SkillManager]:
    """获取技能管理器单例"""
    return _skill_manager
