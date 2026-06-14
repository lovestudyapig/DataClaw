"""Background Loop — OpenClaw 风格的定时任务调度器。

核心设计：
- 一个后台 loop 负责调度
- 每个定时功能 = 一个独立 async 函数
- 添加新任务只需：写函数 → 注册，无需改动原有代码
- 每个任务可以有自己的执行间隔
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Any


class BackgroundTask:
    """定时任务包装器。"""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        interval: float,
        description: str = "",
        *args,
        **kwargs
    ):
        self.name = name
        self.func = func
        self.interval = interval  # 秒
        self.description = description
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.task: asyncio.Task | None = None

    async def run(self):
        """任务执行循环。"""
        while self.running:
            try:
                if asyncio.iscoroutinefunction(self.func):
                    await self.func(*self.args, **self.kwargs)
                else:
                    self.func(*self.args, **self.kwargs)
            except Exception as e:
                print(f"[BackgroundTask:{self.name}] 错误: {e}")

            await asyncio.sleep(self.interval)

    def start(self):
        """启动任务。"""
        self.running = True
        self.task = asyncio.create_task(self.run())
        print(f"[BackgroundTask] 任务 [{self.name}] 已启动 (间隔 {self.interval}s)")

    def stop(self):
        """停止任务。"""
        self.running = False
        if self.task:
            self.task.cancel()
            print(f"[BackgroundTask] 任务 [{self.name}] 已停止")


class BackgroundLoop:
    """OpenClaw 风格的后台定时任务调度器。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.running = False
        self.tasks: dict[str, BackgroundTask] = {}

    # ========================================================================
    # 👇 想加新定时任务，就在下面写一个新的 async 函数
    # ========================================================================

    async def task_check_skills(self):
        """示例任务：每30秒检查技能文件。"""
        skills_dir = self.base_dir / "skills"
        if skills_dir.exists():
            skill_count = len(list(skills_dir.glob("*/SKILL.md")))
            print(f"[定时任务] 当前有 {skill_count} 个技能")

    async def task_auto_save_memory(self):
        """示例任务：每60秒自动保存记忆。"""
        print("[定时任务] 自动保存记忆到磁盘")
        # 可以调用 memory_manager 的保存方法

    # ========================================================================
    # 任务注册与管理
    # ========================================================================

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        interval: float,
        description: str = "",
        *args,
        **kwargs
    ) -> BackgroundTask:
        """注册一个新任务。

        Args:
            name: 任务唯一标识
            func: 任务函数 (可以是 async 或普通函数)
            interval: 执行间隔（秒）
            description: 任务描述
            *args, **kwargs: 传递给函数的参数

        Returns:
            BackgroundTask 实例
        """
        if name in self.tasks:
            print(f"[BackgroundLoop] 任务 [{name}] 已存在，先停止旧任务")
            self.tasks[name].stop()

        task = BackgroundTask(name, func, interval, description, *args, **kwargs)
        self.tasks[name] = task
        return task

    def start(self) -> None:
        """启动所有已注册的任务。"""
        self.running = True
        print("✅ BackgroundLoop 已启动")

        # 👇 内置任务自动注册，用户自定义任务也可在此添加
        self.register("check_skills", self.task_check_skills, 30)
        self.register("auto_save_memory", self.task_auto_save_memory, 60)

        # 👇 从 tasks/ 文件夹动态加载任务
        self._load_tasks_from_folder()

        # 启动所有任务
        for task in self.tasks.values():
            task.start()

    def _load_tasks_from_folder(self) -> None:
        """从 tasks/ 文件夹加载所有任务。"""
        from tasks import scan_tasks

        tasks_dir = self.base_dir / "tasks"
        task_infos = scan_tasks(tasks_dir)

        for task_info in task_infos:
            self.register(
                task_info["name"],
                task_info["func"],
                task_info["interval"],
                task_info.get("description", "")
            )

    def stop(self) -> None:
        """停止所有任务。"""
        self.running = False
        for task in self.tasks.values():
            task.stop()
        print("🛑 BackgroundLoop 已停止")

    def list_tasks(self) -> list[dict]:
        """列出所有任务状态。"""
        return [
            {
                "name": name,
                "running": task.running,
                "interval": task.interval,
                "description": task.description,
            }
            for name, task in self.tasks.items()
        ]


# 使用示例
if __name__ == "__main__":
    async def demo():
        loop = BackgroundLoop(Path("."))

        # 自定义任务示例
        async def my_custom_task():
            print("🔔 自定义任务执行！")

        # 注册自定义任务（每5秒）
        loop.register("my_task", my_custom_task, 5)

        # 启动
        loop.start()

        # 运行20秒
        await asyncio.sleep(20)

        # 停止
        loop.stop()

    asyncio.run(demo())
