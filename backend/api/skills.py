"""
技能 API - 获取可用技能列表
"""
from pathlib import Path
from fastapi import APIRouter

from tools.skills_scanner import scan_skills

router = APIRouter()

# 后端根目录
BASE_DIR = Path(__file__).parent.parent.absolute()


@router.get("/skills")
async def get_skills():
    """
    获取所有可用技能列表
    
    Returns:
        skills: 技能列表，每个技能包含 name, description, location
    """
    skills_dir = BASE_DIR / "skills"
    skills = scan_skills(skills_dir)
    
    return {"skills": skills}
