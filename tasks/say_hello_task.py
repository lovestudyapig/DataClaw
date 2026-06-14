"""定时问候任务 — 每10秒说一次"你好"。

任务文件格式：
- name: 任务名称（显示用）
- interval: 执行间隔（秒）
- description: 任务描述
- run(): 任务执行函数（可以是 async 或普通函数）
"""

import asyncio
from datetime import datetime

# 任务元数据
name = "定时问候"
interval = 10  # 每10秒执行
description = "每10秒说一次'你好'"


async def run():
    """任务执行函数。"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[任务:定时问候] {now} - 你好！")
