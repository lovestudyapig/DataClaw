"""Python REPL Tool — wraps LangChain experimental PythonREPLTool."""

from langchain_core.tools import BaseTool
from langchain_experimental.tools import PythonREPLTool


def create_python_repl_tool() -> BaseTool:
    tool = PythonREPLTool()
    tool.name = "python_repl"
    tool.description = (
        "Execute Python code in an interactive REPL environment. "
        "Use this for calculations, data processing, running scripts, "
        "and any task that benefits from programmatic execution. "
        "Input should be valid Python code. "
        "Use print() to see output."
    )
    return tool
