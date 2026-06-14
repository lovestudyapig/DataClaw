"""温度预警检查任务 — 每60秒检查一次温度状态并输出告警。

模拟检查温度是否超过热应激阈值，实际可对接传感器API。
"""

import asyncio
from datetime import datetime

# 任务元数据
name = "温度预警检查"
interval = 60  # 每60秒执行
description = "检查温度是否超过热应激阈值(30°C)，输出状态告警"


async def run():
    """任务执行函数：模拟温度检查并输出状态。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 模拟获取当前温度（实际可对接传感器API）
    # 这里模拟夏季白天温度波动
    import random
    simulated_temp = round(28.0 + random.uniform(-1, 3), 1)
    threshold = 30.0
    
    if simulated_temp > threshold:
        level = "⚠️ 高温预警" if simulated_temp > 32 else "🔶 注意"
        print(f"[任务:温度预警] {now} | 当前温度: {simulated_temp}°C | 超过阈值{threshold}°C | {level}")
    else:
        print(f"[任务:温度预警] {now} | 当前温度: {simulated_temp}°C | 正常范围内 ✅")
