"""Skills Scanner — 扫描和管理 Agent Skills。"""

from pathlib import Path
from typing import TypedDict


class SkillInfo(TypedDict):
    """技能信息结构。"""

    name: str
    path: str
    description: str


def scan_skills(skills_dir: Path) -> list[SkillInfo]:
    """
    扫描 skills 文件夹，提取所有可用技能。

    Args:
        skills_dir: skills 目录路径

    Returns:
        技能信息列表
    """
    skills = []

    if not skills_dir.exists():
        return skills

    for skill_folder in skills_dir.iterdir():
        if not skill_folder.is_dir():
            continue

        skill_md = skill_folder / "SKILL.md"
        if not skill_md.exists():
            continue

        # 解析 SKILL.md
        content = skill_md.read_text(encoding="utf-8")

        # 提取元数据 (前3行)
        name = skill_folder.name
        description = ""

        for line in content.split("\n")[:5]:
            line = line.strip()
            if line.startswith("name:"):
                name = line.replace("name:", "").strip()
            elif line.startswith("description:"):
                description = line.replace("description:", "").strip()

        skills.append(
            {
                "name": name,
                "path": f"{skill_folder.name}/SKILL.md",
                "description": description,
            }
        )

    return skills


def generate_skills_xml(skills: list[SkillInfo]) -> str:
    """
    生成 XML 格式的技能菜单。

    Args:
        skills: 技能列表

    Returns:
        XML 格式字符串
    """
    if not skills:
        return "<available_skills>No skills found.</available_skills>"

    snapshot = "<available_skills>\n"

    for skill in skills:
        snapshot += f"""  <skill>
    <name>{skill['name']}</name>
    <path>{skill['path']}</path>
    <description>{skill['description']}</description>
  </skill>
"""

    snapshot += "</available_skills>"
    return snapshot


def generate_skills_prompt(skills_dir: Path) -> str:
    """
    生成完整的技能系统提示词。

    Args:
        skills_dir: skills 目录路径

    Returns:
        技能系统提示词
    """
    skills = scan_skills(skills_dir)

    if not skills:
        return ""

    skills_xml = generate_skills_xml(skills)
    print(skills_xml)

    return f"""
## 技能系统 (Agent Skills)

你拥有以下专业技能，定义了你的能力边界：

{skills_xml}

### 技能执行协议 (CRITICAL)

1. **识别技能需求**：当用户请求匹配上述技能时，严禁直接猜测操作步骤
2. **读取技能定义**：第一步**必须**调用 `read_skill_file` 工具，读取对应技能的 `<path>` 文件
3. **严格执行**：按照 SKILL.md 中的步骤指导执行任务
4. **禁止偏离**：不要添加技能文档之外的额外步骤

### 工具说明

- `read_skill_file(path)` - 读取技能目录内的任意文件，path 相对于 skills/ 文件夹。
  例如: `patent_disclosure/SKILL.md`、`patent_disclosure/prompts/intake.md`、`get_weather/SKILL.md`
"""

print(generate_skills_prompt(Path("skills")))
