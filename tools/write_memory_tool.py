"""WriteMemoryTool — 让 Agent 可以主动更新记忆文件。"""

from pathlib import Path
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class WriteMemoryInput(BaseModel):
    """Input schema for write_memory tool."""

    category: str = Field(
        description="记忆类别: preference(偏好), interest(兴趣), project(项目), note(备注)"
    )
    content: str = Field(description="要记录的内容")
    append: bool = Field(
        default=True, description="是否追加到现有内容，False则替换"
    )


class WriteMemoryTool(BaseTool):
    """Tool for writing to memory files."""

    name: str = "write_memory"
    description: str = (
        "Write important information to memory files. "
        "Use this when you learn something important about the user "
        "that should be remembered across sessions. "
        "Examples: user preferences, interests, important facts, decisions."
    )
    args_schema: Type[BaseModel] = WriteMemoryInput
    memory_dir: Path = Path("./memory")

    def _run(self, category: str, content: str, append: bool = True) -> str:
        """Write to the appropriate memory file based on category."""
        try:
            if category == "preference":
                return self._update_user_md("使用偏好", content, append)
            elif category == "interest":
                return self._update_user_md("兴趣爱好", content, append)
            elif category == "project":
                return self._update_user_md("重要项目", content, append)
            elif category == "note":
                return self._update_memory_md(content, append)
            else:
                return f"❌ Unknown category: {category}"
        except Exception as e:
            return f"❌ Error writing memory: {str(e)}"

    def _update_user_md(self, section: str, content: str, append: bool) -> str:
        """Update USER.md file."""
        user_file = self.memory_dir / "USER.md"

        if not user_file.exists():
            # Create default structure
            default_content = f"""# 用户信息

> 由 CoreClaw 自动维护，记录用户的基本信息和偏好。

## 基本信息
- **用户名字**:
- **首次使用日期**:
- **常用语言**: 中文

## 使用偏好

## 兴趣爱好

## 常用命令/习惯

## 重要项目
"""
            user_file.write_text(default_content, encoding="utf-8")

        text = user_file.read_text(encoding="utf-8")

        # Find the section
        lines = text.split("\n")
        section_idx = -1
        next_section_idx = len(lines)

        for i, line in enumerate(lines):
            if line.startswith(f"## {section}"):
                section_idx = i
            elif section_idx >= 0 and line.startswith("## "):
                next_section_idx = i
                break

        if section_idx < 0:
            return f"❌ Section '{section}' not found in USER.md"

        # Insert content
        new_line = f"- {content}"
        if append:
            # Insert before next section
            lines.insert(next_section_idx, new_line)
        else:
            # Replace content between sections
            lines = lines[: section_idx + 1] + [new_line] + lines[next_section_idx:]

        user_file.write_text("\n".join(lines), encoding="utf-8")
        return f"✅ Updated USER.md [{section}]: {content[:50]}..."

    def _update_memory_md(self, content: str, append: bool) -> str:
        """Update MEMORY.md file."""
        memory_file = self.memory_dir / "MEMORY.md"

        if not memory_file.exists():
            memory_file.write_text(
                "# 长期记忆\n\n> 此文件由 CoreClaw 自动维护\n", encoding="utf-8"
            )

        text = memory_file.read_text(encoding="utf-8")

        if append:
            text += f"\n- {content}"
        else:
            # Replace everything after header
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("# ") and i > 0:
                    text = "\n".join(lines[: i + 1]) + f"\n\n- {content}"
                    break
            else:
                text += f"\n- {content}"

        memory_file.write_text(text, encoding="utf-8")
        return f"✅ Updated MEMORY.md: {content[:50]}..."


def create_write_memory_tool(memory_dir: Path) -> WriteMemoryTool:
    """Create a write_memory tool instance."""
    return WriteMemoryTool(memory_dir=memory_dir)
