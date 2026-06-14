"""SafeTerminalTool — sandboxed shell execution with command blacklist."""

import subprocess
from pathlib import Path
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


BLACKLISTED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "format c:",
    "del /f /s /q c:",
]


class TerminalInput(BaseModel):
    command: str = Field(description="The shell command to execute")


class SafeTerminalTool(BaseTool):
    name: str = "terminal"
    description: str = (
        "【终端执行器 - 全能模式】在沙盒环境中执行 shell 命令。 "
        "适用于：复杂文件操作（grep/find/awk/管道）、安装依赖、运行脚本、系统命令等。 "
        "特点：① 支持任意 shell 命令和管道 ② 可创建/修改/删除文件 ③ 30秒超时保护。 "
        "注意：简单文件查看建议使用 read_file 工具（更安全、自动截断大文件）。 "
        "危险命令（rm -rf / 等）会被拦截。"
    )
    args_schema: Type[BaseModel] = TerminalInput
    root_dir: str = ""

    def _is_safe(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        for blocked in BLACKLISTED_COMMANDS:
            if blocked in cmd_lower:
                return False
        return True

    def _run(self, command: str) -> str:
        if not self._is_safe(command):
            return f"❌ Command blocked for safety: {command}"
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if not output.strip():
                output = "(command completed with no output)"
            # Truncate very long output
            if len(output) > 5000:
                output = output[:5000] + "\n...[truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "❌ Command timed out (30s limit)"
        except Exception as e:
            return f"❌ Error: {str(e)}"


def create_terminal_tool(base_dir: Path) -> SafeTerminalTool:
    return SafeTerminalTool(root_dir=str(base_dir))
