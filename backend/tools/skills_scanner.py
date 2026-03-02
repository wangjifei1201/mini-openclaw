"""
技能扫描器 - 扫描 skills 目录并生成 SKILLS_SNAPSHOT.md
"""
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def parse_skill_frontmatter(content: str) -> Optional[Dict[str, str]]:
    """
    解析 SKILL.md 的 YAML frontmatter

    Args:
        content: 文件内容

    Returns:
        包含 name 和 description 的字典，或 None
    """
    if not content.startswith("---"):
        return None

    try:
        # 查找第二个 ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            return None

        frontmatter = content[3:end_idx].strip()
        data = yaml.safe_load(frontmatter)

        if isinstance(data, dict) and "name" in data and "description" in data:
            return {
                "name": str(data["name"]),
                "description": str(data["description"]),
            }
    except Exception:
        pass

    return None


def scan_skills(skills_dir: Path) -> List[Dict[str, str]]:
    """
    扫描技能目录

    Args:
        skills_dir: 技能目录路径

    Returns:
        技能列表 [{"name": ..., "description": ..., "location": ...}, ...]
    """
    skills = []

    if not skills_dir.exists():
        return skills

    # 遍历 skills 目录下的所有子目录
    for skill_folder in skills_dir.iterdir():
        if not skill_folder.is_dir():
            continue

        skill_file = skill_folder / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
            metadata = parse_skill_frontmatter(content)

            if metadata:
                # 使用相对路径
                relative_path = f"./skills/{skill_folder.name}/SKILL.md"
                skills.append(
                    {
                        "name": metadata["name"],
                        "description": metadata["description"],
                        "location": relative_path,
                    }
                )
        except Exception as e:
            print(f"解析技能文件失败 {skill_file}: {e}")

    return skills


def generate_skills_snapshot(skills: List[Dict[str, str]]) -> str:
    """
    生成 SKILLS_SNAPSHOT.md 内容

    Args:
        skills: 技能列表

    Returns:
        XML 格式的技能快照
    """
    if not skills:
        return """<available_skills>
  <!-- 暂无可用技能 -->
</available_skills>
"""

    lines = ["<available_skills>"]
    for skill in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{skill['name']}</name>")
        lines.append(f"    <description>{skill['description']}</description>")
        lines.append(f"    <location>{skill['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")

    return "\n".join(lines)


def scan_and_save_skills(base_dir: Path) -> str:
    """
    扫描技能并保存快照文件

    Args:
        base_dir: 项目根目录（backend/）

    Returns:
        生成的快照内容
    """
    skills_dir = base_dir / "skills"
    skills = scan_skills(skills_dir)
    snapshot = generate_skills_snapshot(skills)

    # 保存到根目录
    snapshot_file = base_dir / "SKILLS_SNAPSHOT.md"
    snapshot_file.write_text(snapshot, encoding="utf-8")

    return snapshot


if __name__ == "__main__":
    # 测试扫描
    import sys

    base_dir = Path(__file__).parent.parent
    snapshot = scan_and_save_skills(base_dir)
    print(snapshot)
