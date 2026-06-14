<p align="center">
  <img src="https://img.shields.io/badge/🐾%20Claw-v2.0-1a73e8" alt="Claw">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20Qwen-brightgreen">
</p>

<h1 align="center">🐾 数据分析 Claw — 易扩展的终端智能体</h1>

---

## 🚀 快速使用

### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

### 2️⃣ 配置 API Key

项目根目录的 `.env` 文件已包含配置模板，填入你的 Key 即可：

```env
# 选择模型：deepseek（默认）或 qwen
MAIN_MODEL=deepseek

# DeepSeek 配置
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Qwen（通义千问）配置
DASHSCOPE_API_KEY=sk-你的key
QWEN_MODEL=qwen-plus
```

### 3️⃣ 运行

```bash
# 交互式对话模式
python Claw.py

# 单次查询模式
python Claw.py "帮我分析一下样例数据.xlsx"
```

---

## 🧠 模型切换

在 `.env` 中修改 `MAIN_MODEL` 即可切换：

| 模型 | `MAIN_MODEL` 值 | API Key |
|------|----------------|---------|
| **DeepSeek** | `deepseek`（默认） | `DEEPSEEK_API_KEY` |
| **Qwen 通义千问** | `qwen` | `DASHSCOPE_API_KEY` |

---

## 🔑 API Key 获取

### DeepSeek

| 项目 | 说明 |
|------|------|
| **申请地址** | [https://platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |
| **步骤** | 注册/登录 → 控制台 → API Keys → 创建 → 复制 `sk-...` |
| **费用** | 新用户有免费额度，后续按量计费 |

```env
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_MODEL=deepseek-chat        # 可选: deepseek-chat, deepseek-reasoner
```

### Qwen（通义千问）

| 项目 | 说明 |
|------|------|
| **申请地址** | [https://bailian.console.aliyun.com/](https://bailian.console.aliyun.com/) |
| **步骤** | 登录阿里云 → 百炼控制台 → API-KEY 管理 → 创建 → 复制 `sk-...` |
| **费用** | 新用户有免费额度，按量计费 |

```env
DASHSCOPE_API_KEY=sk-你的key
QWEN_MODEL=qwen-plus                 # 可选: qwen-plus, qwen-turbo, qwen-max
```

---

## 🛠️ 可用工具

| 工具 | 能力 | 说明 |
|------|------|------|
| 💻 **terminal** | 沙盒 Shell 执行 | 文件操作、安装依赖、运行脚本，30s 超时保护，危险命令拦截 |
| 🐍 **python_repl** | Python REPL | 计算、数据处理、代码执行，安全沙箱 |
| 📁 **read_file** | 文件读取（沙盒） | 读取项目内文件，自动截断大文件（>10KB），只读操作 |
| 📖 **read_skill** | 技能文件读取 | 读取 skills/ 目录下的技能定义文件 |
| 🧠 **write_memory** | 记忆写入 | 记录用户偏好、兴趣、项目信息到记忆文件，跨会话持久化 |

---

## 💬 命令行使用方法

### 交互模式

```bash
python Claw.py
```

内置命令：

| 命令 | 功能 |
|------|------|
| `/quit` | 退出 |
| `/clear` | 清除对话历史 |
| `/tools` | 查看可用工具列表 |
| `/skills` | 查看已加载的技能 |
| `/memory` | 查看记忆文件状态 |
| `/task` | 查看运行中的定时任务 |

### 代码集成

```python
from Claw import CoreClawAgent
import asyncio

async def main():
    agent = CoreClawAgent()
    response = await agent.chat("帮我分析一下样例数据.xlsx")
    print(response)

asyncio.run(main())
```

---

## 🎯 内置技能

| 技能 | 功能 |
|------|------|
| 📊 数据分析 | 数据科学：机器学习/统计/深度学习 |

---

<p align="center">
  <b>🐾 Claw — 终端 AI 智能体</b>
</p>
