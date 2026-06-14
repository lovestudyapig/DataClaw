from __future__ import annotations

import asyncio
import atexit
import os
import sys
from pathlib import Path
from typing import Any
# 加载环境变量
from dotenv import load_dotenv

load_dotenv()

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langchain_deepseek import ChatDeepSeek
from langchain_community.chat_models import ChatTongyi

from background_loop import BackgroundLoop
from memory_manager import MemoryManager
from skills_scanner import generate_skills_prompt, scan_skills
from tools import get_all_tools


def load_identity(memory_dir: Path) -> str:
    """加载 IDENTITY.md 作为基础身份设定。"""
    identity_file = memory_dir / "IDENTITY.md"
    if identity_file.exists():
        content = identity_file.read_text(encoding="utf-8")
        # 移除 frontmatter（第一个 # 标题之前的所有内容）
        lines = content.split("\n")
        result = []
        found_title = False
        for line in lines:
            if line.startswith("# "):
                found_title = True
            if found_title:
                result.append(line)
        return "\n".join(result).strip()
    return "你是 CoreClaw，一个拥有工具调用能力的 AI 助手。"


def load_user_memory(memory_dir: Path) -> str:
    """加载 USER.md 和 MEMORY.md 中的用户相关记忆。"""
    sections = []

    # 加载 USER.md
    user_file = memory_dir / "USER.md"
    if user_file.exists():
        content = user_file.read_text(encoding="utf-8")
        # 提取用户偏好和兴趣部分
        lines = content.split("\n")
        for section_title in ["## 使用偏好", "## 兴趣爱好", "## 基本信息"]:
            for i, line in enumerate(lines):
                if line.startswith(section_title):
                    section_content = [line]
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("## "):
                            break
                        section_content.append(lines[j])
                    sections.append("\n".join(section_content))
                    break

    return "\n\n".join(sections) if sections else ""


def load_soul(memory_dir: Path) -> str:
    """加载 SOUL.md 作为性格特征设定。"""
    soul_file = memory_dir / "SOUL.md"
    if soul_file.exists():
        content = soul_file.read_text(encoding="utf-8")
        # 移除 frontmatter（第一个 # 标题之前的所有内容）
        lines = content.split("\n")
        result = []
        found_title = False
        for line in lines:
            if line.startswith("# "):
                found_title = True
            if found_title:
                result.append(line)
        return "\n".join(result).strip()
    return ""


class CoreClawAgent:
    """CoreClaw Agent with tool support and memory management."""

    def __init__(self, base_dir: Path | None = None, model: str | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.tools = get_all_tools(self.base_dir)
        self.work_dir: Path | None = None  # 用户工作目录（可选）

        # 模型路由：根据 MAIN_MODEL 选择 DeepSeek 或 Qwen
        main_model = os.getenv("MAIN_MODEL", "deepseek").strip().lower()

        if main_model == "qwen":
            # 初始化 Qwen (通义千问)
            qwen_api_key = os.getenv("DASHSCOPE_API_KEY")
            qwen_model = model or os.getenv("QWEN_MODEL", "qwen-plus")

            if not qwen_api_key:
                raise ValueError("DASHSCOPE_API_KEY not found in environment")

            self.llm = ChatTongyi(
                model=qwen_model,
                dashscope_api_key=qwen_api_key,
                temperature=0.2,
            )
        else:
            # 初始化模型 (默认 DeepSeek)
            api_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            model_name = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY not found in environment")

            self.llm = ChatDeepSeek(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=0.2,
            )

        # 初始化记忆管理器（传入 LLM 用于主动提取记忆）
        self.memory = MemoryManager(self.base_dir, llm_client=self.llm)
        self.memory.start_watching()

        # 初始化后台定时任务（延迟启动，等事件循环准备好）
        self.bg_loop = BackgroundLoop(self.base_dir)
        self._bg_started = False

        # 加载身份设定（IDENTITY.md）
        identity_content = load_identity(self.memory.memory_dir)

        # 加载性格特征（SOUL.md）
        soul_content = load_soul(self.memory.memory_dir)

        # 加载用户记忆（USER.md）
        user_memory = load_user_memory(self.memory.memory_dir)

        # 加载技能系统
        skills_content = generate_skills_prompt(self.base_dir / "skills")

        # 构建完整 system prompt
        full_system_prompt = identity_content

        # 添加性格特征
        if soul_content:
            full_system_prompt += "\n\n" + soul_content

        # 添加技能系统
        if skills_content:
            full_system_prompt += "\n\n" + skills_content

        # 添加用户特定记忆
        if user_memory:
            full_system_prompt += f"\n\n## 用户档案\n{user_memory}"

        # 创建 Agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=full_system_prompt,
        )

        # 会话历史
        self.messages: list[Any] = []

        # 注册退出清理
        atexit.register(self.close)

    def close(self) -> None:
        """清理资源。"""
        if hasattr(self, 'memory') and self.memory:
            self.memory.close()
        if hasattr(self, 'bg_loop') and self.bg_loop and self._bg_started:
            self.bg_loop.stop()
            self._bg_started = False

    async def chat(self, user_input: str) -> str:
        """发送消息给 Agent 并返回回复。"""
        # 延迟启动后台任务（第一次聊天时）
        if not self._bg_started:
            self.bg_loop.start()
            self._bg_started = True

        user_msg = HumanMessage(content=user_input)
        self.messages.append(user_msg)
        self.memory.log_message(user_msg)

        # 调用 Agent
        response = await self.agent.ainvoke({"messages": self.messages}, config={"recursion_limit": 200})

        # 获取回复消息 (最后一条 AI 消息)
        ai_message = response["messages"][-1]
        self.messages = response["messages"]

        # 记录 AI 回复
        self.memory.log_message(ai_message)

        return ai_message.content

    async def stream_chat(self, user_input: str):
        """流式输出 Agent 的回复。"""
        self.messages.append(HumanMessage(content=user_input))

        async for chunk in self.agent.astream({"messages": self.messages}, config={"recursion_limit": 1000}):
            if "messages" in chunk:
                # 获取最新的 AI 消息内容
                for msg in chunk["messages"]:
                    if hasattr(msg, "content"):
                        yield msg.content

    async def stream_chat_with_events(self, user_input: str):
        """流式输出 Agent 的回复及中间事件（工具调用等）。"""
        if not self._bg_started:
            self.bg_loop.start()
            self._bg_started = True

        user_msg = HumanMessage(content=user_input)
        self.messages.append(user_msg)
        self.memory.log_message(user_msg)

        # 使用 stream_mode="updates" 获取逐步更新
        async for chunk in self.agent.astream(
            {"messages": self.messages},
            config={"recursion_limit": 200},
            stream_mode="updates",
        ):
            for node_name, update in chunk.items():
                if node_name == "agent":
                    # LLM 推理步骤
                    msgs = update.get("messages", [])
                    for msg in msgs:
                        if hasattr(msg, "content") and msg.content:
                            # 检查是否有 tool_calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield {
                                        "type": "tool_call",
                                        "name": tc.get("name", "unknown"),
                                        "args": tc.get("args", {}),
                                        "id": tc.get("id", ""),
                                        "content": msg.content or "",
                                    }
                            else:
                                yield {
                                    "type": "thinking",
                                    "content": msg.content or "",
                                }
                elif node_name == "tools":
                    # 工具执行结果
                    msgs = update.get("messages", [])
                    for msg in msgs:
                        if hasattr(msg, "content") and msg.content:
                            name = getattr(msg, "name", "tool") or "tool"
                            yield {
                                "type": "tool_result",
                                "name": name,
                                "content": str(msg.content)[:500],
                            }

        # 更新完整历史
        full_response = await self.agent.ainvoke(
            {"messages": self.messages},
            config={"recursion_limit": 200},
        )
        ai_message = full_response["messages"][-1]
        self.messages = full_response["messages"]
        self.memory.log_message(ai_message)

        yield {
            "type": "final",
            "content": ai_message.content or "",
        }

    def export_log(self, save_dir: str | None = None) -> str:
        """导出完整对话日志到文件。"""
        import json
        from datetime import datetime

        log_entries = []
        for msg in self.messages:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "type": getattr(msg, "type", msg.__class__.__name__),
            }
            if hasattr(msg, "content"):
                entry["content"] = msg.content
            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                entry["additional_kwargs"] = msg.additional_kwargs
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if hasattr(msg, "name") and msg.name:
                entry["name"] = msg.name
            log_entries.append(entry)

        # 确定保存路径
        if save_dir:
            save_path = Path(save_dir) / f"claw_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            save_path = self.base_dir / f"claw_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps(log_entries, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(save_path)

    def clear_history(self):
        """清除对话历史。"""
        self.messages = []
        print("✅ 对话历史已清除")

    def set_work_dir(self, path: str) -> str:
        """设置工作目录，更新工具沙盒，并通知 Agent。"""
        target = Path(path)

        # 如果已是存在的绝对路径，直接使用
        if target.is_absolute() and target.exists():
            pass
        else:
            # 浏览器只传了文件夹名，在多个常见位置搜索
            name = target.name  # 纯文件夹名
            base_parent = Path(self.base_dir).parent.resolve()
            home = Path.home()
            locations = [
                base_parent / name,              # 项目同级（如 Desktop）
                Path(self.base_dir) / name,       # 项目内部
                home / name,                      # 用户主目录
                home / "Desktop" / name,          # 桌面
                home / "Documents" / name,        # 文档
                home / "Downloads" / name,        # 下载
                Path.cwd() / name,                # 当前工作目录
            ]
            found = None
            for loc in locations:
                resolved = loc.resolve()
                if resolved.exists() and resolved.is_dir():
                    found = resolved
                    break
            if found is None:
                return f"❌ 找不到目录: {path}"
            target = found

        if not target.is_dir():
            return f"❌ 不是目录: {target}"
        if not target.exists():
            return f"❌ 目录不存在: {target}"

        self.work_dir = target.resolve()
        old_base = self.base_dir

        # 更新所有工具 root_dir 到工作目录
        sandbox_attrs = ["root_dir", "base_dir"]
        for tool in self.tools:
            for attr in sandbox_attrs:
                if hasattr(tool, attr) and tool.root_dir:
                    try:
                        setattr(tool, attr, str(target))
                    except Exception:
                        pass

        # 发送系统消息告知 Agent 工作目录变更
        from langchain_core.messages import SystemMessage
        sys_msg = SystemMessage(content=(
            f"## 工作目录变更通知\n\n"
            f"用户已指定工作目录：`{target}`\n\n"
            f"**重要约束（必须遵守）：**\n"
            f"1. 所有文件读取操作**只能**访问 `{target}` 及其子目录下的文件\n"
            f"2. 所有文件写入/下载操作**必须**保存到 `{target}` 目录下\n"
            f"3. 严禁访问 `{target}` 之外的任何文件和目录\n"
            f"4. 如果用户未指定具体路径，默认使用 `{target}` 作为输出目录\n"
            f"5. 你的工作范围限定在此目录内，超出此目录的操作将被拒绝"
        ))
        self.messages.append(sys_msg)

        print(f"[WorkDir] 已设置为: {target}")
        return f"✅ 工作目录已设置为: {target}\n工具沙盒已更新，所有文件操作限制在此目录内。"

    def get_work_dir(self) -> str:
        """获取当前工作目录。"""
        return str(self.work_dir) if self.work_dir else ""


async def interactive_mode(agent: CoreClawAgent):
    """交互式对话模式。"""
    print("=" * 60)
    print("🐾 CoreClaw Agent")
    print("=" * 60)
    # 尝试获取 model_name，如果不存在则回退到 model 或其他属性
    model_name = getattr(agent.llm, 'model_name', None) or getattr(agent.llm, 'model', 'Unknown')
    print(f"模型: {model_name}")
    print(f"工具: {', '.join(t.name for t in agent.tools)}")
    print(f"记忆: {agent.memory.memory_dir}")
    print("\n命令: /quit 退出, /clear 清除历史, /tools 查看工具, /skills 查看技能, /memory 查看记忆, /task 查看任务")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input == "/quit":
                print("👋 再见!")
                break

            if user_input == "/clear":
                agent.clear_history()
                continue

            if user_input == "/tools":
                print("\n🔧 可用工具:")
                for tool in agent.tools:
                    print(f"  • {tool.name}: {tool.description[:60]}...")
                continue

            if user_input == "/skills":
                skills = scan_skills(agent.base_dir / "skills")
                if skills:
                    print(f"\n🎯 已加载 {len(skills)} 个技能:")
                    for skill in skills:
                        print(f"  • {skill['name']}: {skill['description']}")
                    print("\n使用方法: 直接描述你的需求，Agent 会自动调用相应技能")
                else:
                    print("\n📭 暂无技能，在 skills/ 目录下添加 SKILL.md 文件")
                continue

            if user_input == "/memory":
                print("\n🧠 记忆文件:")
                for name, path in agent.memory.get_memory_files().items():
                    exists = "✅" if path.exists() else "❌"
                    print(f"  {exists} {name}: {path}")
                continue

            if user_input == "/task":
                tasks = agent.bg_loop.list_tasks()
                if tasks:
                    print(f"\n⏰ 运行中的任务 ({len(tasks)}个):")
                    for task in tasks:
                        status = "🟢" if task["running"] else "🔴"
                        interval_m = task["interval"] / 60
                        interval_str = f"{int(interval_m)}分钟" if interval_m >= 1 else f"{int(task['interval'])}秒"
                        desc = task.get("description", "")
                        print(f"  {status} {task['name']}: 每{interval_str}")
                        if desc:
                            print(f"     {desc}")
                else:
                    print("\n📭 暂无运行中的任务")
                continue

            print("\n🤖 CoreClaw: ", end="", flush=True)

            response = await agent.chat(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\n👋 再见!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def single_query(agent: CoreClawAgent, query: str) -> str:
    """单次查询模式。"""
    return await agent.chat(query)


def main():
    """主入口。"""
    # 检查环境变量
    main_model = os.getenv("MAIN_MODEL", "deepseek").strip().lower()

    if main_model == "qwen":
        if not os.getenv("DASHSCOPE_API_KEY"):
            print("❌ 错误: DASHSCOPE_API_KEY 未设置")
            print("请在 .env 文件中配置 DASHSCOPE_API_KEY")
            sys.exit(1)
    elif not os.getenv("DEEPSEEK_API_KEY"):
        print("❌ 错误: DEEPSEEK_API_KEY 未设置")
        print("请在 .env 文件中配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    # 创建 Agent
    base_dir = Path(__file__).parent
    agent = CoreClawAgent(base_dir=base_dir)

    # 判断模式
    if len(sys.argv) > 1:
        # 单次查询模式
        query = sys.argv[1]
        result = asyncio.run(single_query(agent, query))
        print(result)
    else:
        # 交互式模式
        asyncio.run(interactive_mode(agent))


if __name__ == "__main__":
    main()



