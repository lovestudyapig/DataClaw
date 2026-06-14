"""Tasks — 定时任务模块。

每个任务是一个独立的 .py 文件，包含：
- name: 任务名称
- interval: 执行间隔（秒）
- run(): 任务执行函数
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable, TypedDict


class TaskInfo(TypedDict):
    """任务信息结构。"""

    name: str
    interval: float
    description: str
    func: Callable


def scan_tasks(tasks_dir: Path) -> list[TaskInfo]:
    """扫描 tasks 文件夹，加载所有可用任务。

    Args:
        tasks_dir: tasks 目录路径

    Returns:
        任务信息列表
    """
    tasks = []

    if not tasks_dir.exists():
        return tasks

    for task_file in tasks_dir.glob("*.py"):
        if task_file.name.startswith("_"):
            continue

        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                task_file.stem, task_file
            )
            if not spec or not spec.loader:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[task_file.stem] = module
            spec.loader.exec_module(module)

            # 检查必需的属性
            if not hasattr(module, "run"):
                print(f"[Tasks] 跳过 {task_file.name}: 缺少 run() 函数")
                continue

            task_info: TaskInfo = {
                "name": getattr(module, "name", task_file.stem),
                "interval": getattr(module, "interval", 60),
                "description": getattr(module, "description", ""),
                "func": module.run,
            }
            tasks.append(task_info)
            print(f"[Tasks] 已加载任务: {task_info['name']} (间隔 {task_info['interval']}s)")

        except Exception as e:
            print(f"[Tasks] 加载 {task_file.name} 失败: {e}")

    return tasks
