"""Memory Manager — 管理聊天记录和长期记忆。

功能:
1. 按日期保存聊天记录到 memory/logs/
2. 监听新记忆，自动提取偏好/决策到 MEMORY.md
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class MemoryEncoder(json.JSONEncoder):
    """处理 LangChain 消息的 JSON 编码器。"""

    def default(self, obj: Any) -> Any:
        # 处理 LangChain 消息对象
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        # 处理有 content 属性的消息对象
        if hasattr(obj, "content"):
            return {
                "_type": obj.__class__.__name__,
                "content": obj.content,
                "type": getattr(obj, "type", "unknown"),
            }
        # 处理普通对象
        if hasattr(obj, "__dict__"):
            return {
                "_type": obj.__class__.__name__,
                "__dict__": obj.__dict__,
            }
        return super().default(obj)


class ChatLogger:
    """按日期记录聊天记录。"""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: str | None = None
        self._current_file: Path | None = None
        self._buffer: list[dict] = []
        self._lock = threading.Lock()

    def _get_today_file(self) -> Path:
        """获取今天的日志文件路径。"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._current_file = self.logs_dir / f"{today}.jsonl"
            # 如果有缓冲数据，先写入旧文件
            if self._buffer:
                self._flush()
        return self._current_file

    def _flush(self) -> None:
        """将缓冲数据写入文件。"""
        if not self._buffer or not self._current_file:
            return
        with open(self._current_file, "a", encoding="utf-8") as f:
            for record in self._buffer:
                f.write(json.dumps(record, cls=MemoryEncoder, ensure_ascii=False) + "\n")
        self._buffer = []

    def log_message(self, message: BaseMessage | dict) -> None:
        """记录一条消息。"""
        with self._lock:
            # 确保文件路径已初始化
            self._get_today_file()

            record = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
            }
            self._buffer.append(record)
            # 每条都写入，确保不丢失
            self._flush()

    def close(self) -> None:
        """关闭日志，写入剩余数据。"""
        with self._lock:
            self._flush()

    def get_today_messages(self) -> list[dict]:
        """获取今天的所有消息。"""
        file_path = self._get_today_file()
        if not file_path.exists():
            return []
        messages = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages


class MemoryWatcher(FileSystemEventHandler):
    """监听 memory/logs/ 目录，提取新记忆。"""

    def __init__(self, memory_dir: Path, llm_client: Any | None = None):
        self.memory_dir = memory_dir
        self.logs_dir = memory_dir / "logs"
        self.memory_file = memory_dir / "MEMORY.md"
        self.user_file = memory_dir / "USER.md"
        self.llm_client = llm_client
        self._processed_files: set[str] = set()
        self._lock = threading.Lock()

    def on_modified(self, event) -> None:
        """文件修改时触发。"""
        if event.is_directory:
            return
        if event.src_path.endswith(".jsonl"):
            self._process_log_file(event.src_path)

    def on_created(self, event) -> None:
        """文件创建时触发。"""
        if event.is_directory:
            return
        if event.src_path.endswith(".jsonl"):
            self._process_log_file(event.src_path)

    def _process_log_file(self, file_path: str) -> None:
        """处理日志文件，提取新记忆。"""
        try:
            with self._lock:
                # 读取文件的新行
                last_pos_key = f"{file_path}:pos"
                last_pos = getattr(self, last_pos_key, 0)

                with open(file_path, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    new_pos = f.tell()

                if not new_lines:
                    return

                setattr(self, last_pos_key, new_pos)

                # 解析新消息
                new_messages = []
                for line in new_lines:
                    line = line.strip()
                    if line:
                        try:
                            new_messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

                if new_messages:
                    self._extract_memories(new_messages)

        except Exception as e:
            print(f"[MemoryWatcher] 处理日志文件出错: {e}")

    def _extract_memories(self, messages: list[dict]) -> None:
        """从消息中提取记忆并更新 MEMORY.md。"""
        # 只提取用户消息（AI的回复和工具调用不提取）
        user_messages = [
            msg for msg in messages
            if self._is_user_message(msg)
        ]

        if not user_messages or not self.llm_client:
            return

        # 合并最近的用户消息
        contents = []
        for msg in user_messages:
            content = self._get_message_content(msg)
            if content and len(content) > 5:  # 过滤太短的
                contents.append(content)

        if not contents:
            return

        combined_content = "\n---\n".join(contents)

        # 用 LLM 分析是否有值得记忆的内容
        try:
            memory_items = self._analyze_with_llm(combined_content)
            if memory_items:
                self._update_memory_file(memory_items)
        except Exception as e:
            print(f"[Memory] LLM分析出错: {e}")

    def _is_user_message(self, msg: dict) -> bool:
        """判断是否是用户消息。"""
        message = msg.get("message", {})
        if isinstance(message, dict):
            msg_type = message.get("type", "")
            role = message.get("role", "")
            return msg_type == "human" or role == "user" or msg_type == "user"
        return False

    def _analyze_with_llm(self, content: str) -> list[dict]:
        """用 LLM 分析内容，提取值得记忆的信息。"""
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = f"""分析以下用户对话内容，提取值得长期记忆的信息。

用户对话内容：
{content}

请提取以下类型的信息（如果没有则返回空数组）：
1. 用户偏好（喜欢/不喜欢/偏好）
2. 重要决策或约定
3. 用户身份信息（姓名、职业等）
4. 用户习惯或常用操作

以 JSON 数组格式返回，每项包含 type 和 content：
[
  {{"type": "preference|identity|decision|habit", "content": "提取的记忆内容"}}
]

注意：
- 只返回真正重要的信息，过滤闲聊内容
- 用第三人称客观描述
- 内容简洁，一句话概括
- 如果没有值得记忆的内容，返回空数组 []
"""

        messages = [
            SystemMessage(content="你是一个记忆提取助手。分析对话内容，只提取真正重要的长期记忆。"),
            HumanMessage(content=prompt)
        ]

        response = self.llm_client.invoke(messages)
        result_text = response.content if hasattr(response, "content") else str(response)

        # 解析 JSON
        import json
        import re

        # 尝试从文本中提取 JSON
        json_match = re.search(r'\[[\s\S]*\]', result_text)
        if json_match:
            try:
                items = json.loads(json_match.group())
                # 添加时间戳
                timestamp = datetime.now().isoformat()
                for item in items:
                    item["timestamp"] = timestamp
                return items
            except json.JSONDecodeError:
                pass

        return []

    def _get_message_content(self, msg: dict) -> str:
        """从消息记录中提取内容。"""
        message = msg.get("message", {})
        if isinstance(message, dict):
            return message.get("content", "") or ""
        return str(message)

    def _is_preference_statement(self, content: str) -> bool:
        """判断是否是偏好表述。"""
        preference_patterns = [
            r"我.*喜欢",
            r"我.*讨厌",
            r"我.*偏好",
            r"我.*希望",
            r"我.*想要",
            r"我.*(想|要)",
            r"我更",
            r"请用",
            r"不要",
            r"总是",
            r"从不",
            r"prefer",
            r"like to",
            r"don't want",
            r"always",
            r"never",
        ]
        for pattern in preference_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _is_important_decision(self, content: str) -> bool:
        """判断是否是重要决策。"""
        decision_patterns = [
            r"决定",
            r"确定",
            r"约定",
            r"规则是",
            r"架构",
            r"方案",
            r"使用.*作为",
            r"选择",
            r"decided",
            r"agreed",
            r"conclusion",
            r"final",
            r"architecture",
            r"we will use",
            r"let's use",
        ]
        for pattern in decision_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _update_memory_file(self, new_memories: list[dict]) -> None:
        """更新 MEMORY.md 文件。"""
        try:
            # 读取现有内容
            if self.memory_file.exists():
                content = self.memory_file.read_text(encoding="utf-8")
            else:
                content = "# 长期记忆\n\n"

            # 添加新记忆
            additions = []
            for mem in new_memories:
                timestamp = mem.get("timestamp", "")[:10]  # 只取日期部分
                mem_content = mem.get("content", "")
                # 截断过长的内容
                if len(mem_content) > 200:
                    mem_content = mem_content[:200] + "..."

                entry = f"\n- [{timestamp}] ({mem['type']}) {mem_content}"
                additions.append(entry)

            # 在文件末尾追加（在最后的 ``` 之前）
            if additions:
                # 找到合适的位置插入
                lines = content.split("\n")
                insert_idx = len(lines)

                # 找到 ## 用户偏好 或 ## 重要事项 的位置
                for i, line in enumerate(lines):
                    if line.startswith("## ") and ("偏好" in line or "事项" in line):
                        insert_idx = i + 1
                        # 找到下一个 ## 或文件末尾
                        for j in range(i + 1, len(lines)):
                            if lines[j].startswith("## "):
                                insert_idx = j
                                break
                            insert_idx = j + 1
                        break

                # 插入新记忆
                for entry in additions:
                    lines.insert(insert_idx, entry)
                    insert_idx += 1

                # 写回文件
                self.memory_file.write_text("\n".join(lines), encoding="utf-8")
                print(f"[Memory] 已更新 {len(additions)} 条记忆到 MEMORY.md")

        except Exception as e:
            print(f"[Memory] 更新 MEMORY.md 出错: {e}")


class MemoryManager:
    """记忆管理器主类。"""

    def __init__(self, base_dir: Path, llm_client: Any | None = None):
        self.base_dir = base_dir
        self.memory_dir = base_dir / "memory"
        self.logs_dir = self.memory_dir / "logs"
        self.llm_client = llm_client

        # 创建目录
        self.memory_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        # 初始化组件
        self.chat_logger = ChatLogger(self.logs_dir)
        self.memory_watcher = MemoryWatcher(self.memory_dir, llm_client)

        # 文件系统观察器
        self.observer: Observer | None = None

    def start_watching(self) -> None:
        """启动文件监听。"""
        if self.observer is not None:
            return

        self.observer = Observer()
        self.observer.schedule(self.memory_watcher, str(self.logs_dir), recursive=False)
        self.observer.start()
        print(f"[Memory] 开始监听 {self.logs_dir}")

    def stop_watching(self) -> None:
        """停止文件监听。"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("[Memory] 停止监听")

    def log_message(self, message: BaseMessage | dict) -> None:
        """记录消息。"""
        self.chat_logger.log_message(message)

    def close(self) -> None:
        """关闭管理器。"""
        self.chat_logger.close()
        self.stop_watching()

    def get_memory_files(self) -> dict[str, Path]:
        """获取所有记忆文件路径。"""
        return {
            "memory": self.memory_dir / "MEMORY.md",
            "user": self.memory_dir / "USER.md",
            "identity": self.memory_dir / "IDENTITY.md",
            "soul": self.memory_dir / "SOUL.md",
        }
