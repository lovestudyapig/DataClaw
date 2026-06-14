"""ReadFileTool — unified file reading with sandbox support."""

from pathlib import Path
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    file_path: str = Field(
        description="Relative path of the file to read (relative to root directory)"
    )


class SandboxedReadFileTool(BaseTool):
    """Generic file reading tool with sandbox support."""
    name: str = "read_file"
    description: str = ""
    args_schema: Type[BaseModel] = ReadFileInput
    root_dir: str = ""

    def _run(self, file_path: str) -> str:
        try:
            root = Path(self.root_dir)
            # Normalize path
            normalized = file_path.replace("\\", "/").lstrip("./")
            full_path = (root / normalized).resolve()

            # Sandbox check
            if not str(full_path).startswith(str(root.resolve())):
                return f"❌ Access denied: path escapes allowed directory"

            if not full_path.exists():
                return f"❌ File not found: {file_path}"

            if not full_path.is_file():
                return f"❌ Not a file: {file_path}"

            content = full_path.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n...[truncated]"
            return content

        except Exception as e:
            return f"❌ Error reading file: {str(e)}"


def create_read_file_tool(base_dir: Path) -> SandboxedReadFileTool:
    """Create tool for reading project files."""
    tool = SandboxedReadFileTool(root_dir=str(base_dir))
    tool.description = (
        "【文件阅读器 - 安全模式】读取项目目录内的文件内容。 "
        "适用于：查看代码文件、配置文件、SKILL.md等。 "
        "特点：① 沙盒保护（只能访问项目内文件）② 自动截断大文件（>10KB）③ 只读操作。 "
        "路径相对于项目根目录，例如：'README.md'、'src/main.py'。 "
        "如需执行复杂命令（grep/管道/创建文件），请使用 terminal 工具。"
    )
    return tool


def create_read_skill_tool(skills_dir: Path) -> SandboxedReadFileTool:
    """Create tool for reading SKILL.md files and skill sub-files."""
    tool = SandboxedReadFileTool(root_dir=str(skills_dir))
    tool.name = "read_skill_file"
    tool.description = (
        "Read any file from an Agent Skill directory (skills/ subfolder). "
        "When you need to execute a skill, first call this tool to read its "
        "SKILL.md definition, then read individual prompt files as instructed. "
        "Input path is relative to skills folder, e.g.:\n"
        "  - 'patent_disclosure/SKILL.md' — skill entry\n"
        "  - 'patent_disclosure/prompts/intake.md' — step instruction\n"
        "  - 'get_weather/SKILL.md' — simple skill\n"
        "This tool supports reading any .md file within a skill directory tree."
    )
    return tool
