"""
技能系统 - 可复用的任务模板与工具链

提供技能匹配、加载和执行能力。
"""

from skills.skill_manager import (
    Skill,
    SkillManager,
    get_skill_manager,
    init_skill_manager,
)

__all__ = [
    "Skill",
    "SkillManager",
    "get_skill_manager",
    "init_skill_manager",
]
