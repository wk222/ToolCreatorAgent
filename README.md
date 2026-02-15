<p align="center">
  <img src="https://img.shields.io/badge/LangChain-1.0.0--alpha-blue?style=for-the-badge" alt="LangChain">
  <img src="https://img.shields.io/badge/LangGraph-0.3+-green?style=for-the-badge" alt="LangGraph">
  <img src="https://img.shields.io/badge/License-Apache%202.0-orange?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow?style=for-the-badge" alt="Python">
</p>

# 🧠 ToolCreatorAgent — 自主创造工具和智能体的超级智能体

> 本项目从一个自动化数据分析软件中抽取而来，是一个能够**自主创建工具（Tool）和子智能体（Sub-Agent）**的超级智能体系统，并配备了完整的 Web 前端管理界面。基于 **LangChain 1.0.0 alpha** 版开发。

## ✨ 核心亮点

传统 Agent 只能**使用**预先定义好的工具。**ToolCreatorAgent 能够在运行时自主发明新工具、创建新智能体**——这是一种元编程（Meta-programming）能力：

| 能力层级 | 传统 Agent | ToolCreatorAgent |
|---------|-----------|------------------|
| 使用工具 | ✅ | ✅ |
| **创建工具** | ❌ | ✅ 运行时动态创建 |
| **创建智能体** | ❌ | ✅ 自主创建专门化子智能体 |
| **给子智能体分配工具** | ❌ | ✅ 动态分配 |
| 工具持久化 | ❌ | ✅ 跨会话复用 |
| 智能体持久化 | ❌ | ✅ 跨会话复用 |
| **智能体启用/禁用** | ❌ | ✅ 前端管理 |

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Web Frontend                       │
│  ┌─────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ 会话管理 │  │  流式聊天     │  │ 智能体/工具管理 │  │
│  └─────────┘  └──────────────┘  └────────────────┘  │
└───────────────────────┬─────────────────────────────┘
                        │ SSE Streaming
┌───────────────────────┴─────────────────────────────┐
│              FastAPI Service (7x24)                   │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ 会话 API  │  │ 流式 Chat │  │ Agent/Tool CRUD  │  │
│  └──────────┘  └───────────┘  └──────────────────┘  │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────┐
│            ToolCreatorAgent Core                      │
│  ┌──────────────────────────────────────────────┐    │
│  │         DynamicToolMiddleware                  │    │
│  │  (拦截模型调用 → 注入动态工具 → 跟踪使用)     │    │
│  └──────────────────────────────────────────────┘    │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │
│  │ ToolCreator  │  │ AgentCreator │  │ Delegation │   │
│  │ (创建新工具)  │  │ (创建子智能体)│  │ (任务委派)  │   │
│  └─────────────┘  └─────────────┘  └────────────┘   │
│  ┌─────────────┐  ┌──────────────┐                   │
│  │ ToolStorage  │  │ AgentStorage  │  ← 持久化到磁盘  │
│  └─────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

复制配置模板并填入你的 API Key：

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "llm_config": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-your-api-key-here",
    "model": "gpt-4"
  }
}
```

> 支持任何兼容 OpenAI API 格式的服务（OpenAI、Azure、本地部署等）

### 3. 启动服务

```bash
python service_mode.py
```

打开浏览器访问 **http://localhost:8000** 即可使用。

### 4. 命令行模式（可选）

```bash
python interactive_cli.py
```

## 💡 使用示例

### 创建工具

对话中直接说：

```
> 创建一个计算圆面积的工具，输入半径，返回面积
```

Agent 会自动：
1. 生成 Python 函数代码
2. 创建 LangChain Tool 定义
3. 持久化到磁盘
4. **后续对话自动加载并使用**

### 创建子智能体

```
> 创建一个数据分析师智能体，专门负责数据处理和统计分析
```

Agent 会创建一个具有独立角色和能力的子智能体，可以通过 `delegate_to_agent` 进行任务委派。

### 管理智能体和工具

在 Web 界面右侧面板中：

- **状态 Tab**：查看当前会话的活跃智能体和工具
- **智能体 Tab**：启用/禁用、分配工具、删除
- **工具 Tab**：查看使用统计、删除

## 📁 项目结构

```
ToolCreatorAgent/
├── agent.py                 # 主智能体入口（含流式聊天方法）
├── service_mode.py          # FastAPI 7x24 后台服务
├── interactive_cli.py       # 命令行交互模式
├── config.example.json      # 配置模板
├── requirements.txt         # 依赖列表
├── core/
│   ├── __init__.py
│   ├── tool_creator.py      # 🔧 动态工具创建器
│   ├── tool_storage.py      # 💾 工具持久化存储
│   ├── tool_middleware.py   # ⚡ 动态工具中间件（核心创新）
│   ├── agent_creator.py     # 🤖 子智能体创建器
│   └── agent_storage.py     # 💾 智能体持久化存储
├── static/
│   ├── index.html           # 前端页面
│   ├── style.css            # 暗色主题样式
│   └── app.js               # 前端逻辑（SSE流式 + 管理面板）
├── examples/
│   ├── example1_create_tool.py
│   └── example2_reuse_tool.py
├── demo.py                  # 完整演示脚本
└── demo_agent_creation.py   # 子智能体创建演示
```

## 🔑 核心技术栈

- **LangChain 1.0.0 alpha** — Agent 框架
- **LangGraph** — 状态化 Agent 执行图 + 检查点持久化
- **FastAPI** — 7x24 后台服务 + SSE 流式输出
- **DynamicToolMiddleware** — 核心创新：运行时工具注入中间件

## 🔬 技术细节

### DynamicToolMiddleware

这是整个系统的核心创新。它作为 LangChain 模型调用的拦截层：

1. **拦截模型调用**：在 LLM 被调用之前，自动检测并加载所有动态工具
2. **注入工具定义**：将新创建的工具注入到模型的 `bind_tools` 中
3. **跟踪工具使用**：记录每个工具的调用次数和执行结果
4. **工具创建感知**：当检测到新工具被创建时，立即使其可用

### 子智能体隔离

每个子智能体拥有：
- 独立的工具目录（`agents_workspace/{name}/tools/`）
- 独立的系统提示词
- 可分配的全局工具（通过 `tools` 字段筛选）
- 启用/禁用状态控制

## 📄 License

[Apache License 2.0](LICENSE)

---

<p align="center">
  <strong>🛠️ 不只是使用工具，而是创造工具</strong><br>
  <em>Not just using tools, but creating them.</em>
</p>
