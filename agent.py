"""
具有自主工具创建和智能体创建能力的智能体系统

主程序：整合所有核心模块，提供简洁的API

核心能力：
1. 工具创建（元编程）：智能体自主创建工具
2. 智能体创建（元元编程）：智能体自主创建子智能体
"""
from typing import List, Dict, Any, Optional
from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver  # 升级为 SQLite 持久化
from langchain_openai import ChatOpenAI
import sqlite3

from core import (
    # 工具创建相关
    ToolStorage,
    ToolContext,
    get_tool_creator_tools,
    get_dynamic_tools,
    DynamicToolMiddleware,
    # 智能体创建相关
    AgentStorage,
    AgentDefinition,
    get_agent_creator_tools,
)


class ToolCreatorAgent:
    """
    具有自主工具创建和智能体创建能力的智能体
    
    特点：
    1. 能够根据需求自主创建工具（元编程）
    2. 能够根据需求自主创建子智能体（元元编程）
    3. 工具和智能体自动持久化到文件系统
    4. 跨会话自动恢复和使用
    5. 基于 LangChain 1.0 标准实现
    
    使用示例：
    ```python
    agent = ToolCreatorAgent(model="gpt-4", thread_id="session-1")
    
    # 创建工具
    response = agent.chat("创建一个计算圆面积的工具")
    
    # 使用工具 (持久化保存)
    response = agent.chat("用这个工具计算半径为5的圆的面积")
    
    # 创建子智能体 (拥有独立文件夹)
    response = agent.chat("创建一个数据分析师智能体")
    
    # 为子智能体创建专属工具 (保存到子智能体文件夹)
    response = agent.chat("为数据分析师创建一个数据清洗工具")
    
    # 委派任务给子智能体
    response = agent.chat("让数据分析师分析这份销售数据")
    ```
    """
    
    def __init__(
        self,
        model: str = "gpt-4",
        thread_id: str = "default",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        enable_agent_creation: bool = True  # 新增：是否启用智能体创建
    ):
        """
        初始化智能体
        
        Args:
            model: 模型名称（如 "gpt-4", "gpt-3.5-turbo"）
            thread_id: 会话ID，用于持久化
            api_key: API密钥（可选，默认从环境变量读取）
            base_url: API地址（可选）
            temperature: 温度参数
            enable_agent_creation: 是否启用智能体创建能力
        """
        self.model_name = model
        self.thread_id = thread_id
        self.temperature = temperature
        self.enable_agent_creation = enable_agent_creation
        
        # 创建工具存储 (启用磁盘持久化)
        self.storage = ToolStorage(base_dir="global_tools")
        
        # 创建智能体存储 (启用磁盘持久化)
        self.agent_storage = AgentStorage(base_dir="agents_workspace")
        
        # 保存API配置用于创建子智能体
        self._api_key = api_key
        self._base_url = base_url
        
        # 创建模型
        model_kwargs = {
            "model": model,
            "temperature": temperature
        }
        if api_key:
            model_kwargs["api_key"] = api_key
        if base_url:
            model_kwargs["base_url"] = base_url
        
        self.llm = ChatOpenAI(**model_kwargs)
        
        # 创建持久化 checkpoint (用于 7x24 小时运行)
        db_path = "checkpoints.sqlite"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(conn)
        
        # 创建中间件（传入工具存储）
        self.middleware = DynamicToolMiddleware(tool_storage=self.storage)
        
        # 初始化智能体
        self._initialize_agent()
        
        print(f"✅ 智能体已初始化")
        print(f"   模型: {model}")
        print(f"   会话ID: {thread_id}")
        print(f"   存储: global_tools/, agents_workspace/")
        print(f"   功能: 自主工具创建 + 智能体创建 + 目录级持久化")
    
    def _create_llm(self, model: str = None, temperature: float = None):
        """创建LLM实例的工厂方法（用于子智能体）"""
        kwargs = {
            "model": model or self.model_name,
            "temperature": temperature if temperature is not None else self.temperature
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return ChatOpenAI(**kwargs)
    
    def _initialize_agent(self):
        """初始化智能体"""
        # 获取工具创建器工具 (传入 agent_storage 以支持为智能体创建工具)
        creator_tools = get_tool_creator_tools(
            storage=self.storage,
            agent_storage=self.agent_storage
        )
        
        # 获取智能体创建器工具
        if self.enable_agent_creation:
            agent_tools = get_agent_creator_tools(
                agent_storage=self.agent_storage,
                tool_storage=self.storage,
                llm_factory=self._create_llm
            )
            creator_tools.extend(agent_tools)
        
        # 系统提示（升级版：包含智能体创建和专属工具能力）
        system_prompt = """你是一个具有**自主工具创建和智能体创建能力**的超级智能助手。

## 🎯 核心能力

### 一、工具创建能力 🔧
1. **create_custom_tool** - 创建自定义工具
   - 可以创建到全局工具库（默认）
   - 可以创建到**指定智能体的专属工具库**（使用 `target_agent` 参数）
2. **list_custom_tools** - 查看已创建的工具
3. 直接调用已创建的工具

### 二、智能体创建能力 🤖
1. **create_agent** - 创建专门化的子智能体（会自动创建专属文件夹）
2. **delegate_to_agent** - 将任务委派给子智能体执行
   - 子智能体拥有自己的**专属文件夹**和**专属工具库**
3. **list_agents** - 查看已创建的智能体
4. **remove_agent** - 删除不需要的智能体

---

## 🔧 工具创建详解

### 如何创建工具？
**调用 create_custom_tool 工具**

核心参数：
- `tool_name`: 英文+下划线
- `description`: 功能描述
- `code`: Python 代码
- `target_agent`: **(重要)** 如果你想为某个智能体创建专属工具，请填写该智能体名称。如果留空，则创建为全局工具。

### 示例：为数据分析师创建专属工具
用户："给 data_analyst 创建一个数据清洗工具"

调用 create_custom_tool：
```
tool_name: "clean_data"
description: "清洗数据，处理缺失值"
parameters: [...]
code: "..."
target_agent: "data_analyst"  <-- 指定目标智能体
```

---

## 🤖 智能体创建详解

### 如何创建智能体？
**调用 create_agent 工具**

系统会自动在 `agents_workspace/` 下创建该智能体的专属目录，用于存放其配置和专属工具。

---

## 🔄 工作流程示例

1. **创建团队**：
   - "创建一个名为 data_analyst 的数据分析师"
   - "创建一个名为 report_writer 的报告撰写员"

2. **赋予能力（创建专属工具）**：
   - "为 data_analyst 创建一个计算增长率的工具" (设置 target_agent="data_analyst")
   - "为 report_writer 创建一个生成Markdown表格的工具" (设置 target_agent="report_writer")

3. **执行任务**：
   - "让 data_analyst 分析这些数据..." (它会使用它的专属工具)
   - "让 report_writer 根据分析结果写报告..."

记住：**合理利用专属工具库，让每个智能体各司其职，保持整洁！**
"""
        
        # 获取已创建的动态工具 (全局工具)
        dynamic_tools = get_dynamic_tools(self.storage)
        all_tools = creator_tools + dynamic_tools
        
        # 更新中间件的工具存储引用
        self.middleware._tool_storage = self.storage
        
        # 创建智能体（适配 LangChain 1.1.0 API）
        self.agent = create_agent(
            model=self.llm,
            tools=all_tools,
            system_prompt=system_prompt,
            middleware=[self.middleware],
            checkpointer=self.checkpointer
        )
    
    def chat(self, message: str) -> str:
        """
        与智能体对话
        """
        try:
            # 记录对话前的工具数量
            tools_before = len(self.storage.tools)
            
            # 构建配置（包含 thread_id 和 recursion_limit）
            config = {
                "configurable": {
                    "thread_id": self.thread_id
                },
                "recursion_limit": 100  # 支持长周期自主运行
            }
            
            # 调用智能体
            response = self.agent.invoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config
            )
            
            # 提取回复
            messages = response.get("messages", [])
            last_message = messages[-1] if messages else None
            
            # 检测是否创建了新工具 (仅检测全局工具变化)
            tools_after = len(self.storage.tools)
            
            if tools_after > tools_before:
                # 获取最新创建的工具名
                new_tool_name = self.middleware._last_created_tool or "未知"
                print(f"[INFO] ✨ 新全局工具创建成功: {new_tool_name}")
                
                # 重新初始化智能体以注册新工具
                self._initialize_agent()
                print(f"[INFO] 🔄 Agent 已更新，新工具可用")
            
            if last_message:
                return last_message.content
            else:
                return "（无回复）"
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] 对话出错:\n{error_trace}")
            return f"❌ 错误: {str(e)}"
    
    def chat_stream(self, message: str):
        """
        流式对话 — 返回一个生成器，逐步 yield 中间过程和最终结果
        
        每个 yield 的对象格式:
        {"type": "step", "content": "...", "icon": "🔧"}  — 中间步骤
        {"type": "done", "content": "...", "agents": [...], "tools": [...]}  — 最终结果
        {"type": "error", "content": "..."}  — 错误
        """
        import io
        import sys
        import threading
        import queue
        import time as _time
        
        step_queue = queue.Queue()
        final_result = [None]
        error_result = [None]
        
        # 拦截 print 输出，将其转换为中间步骤事件
        class PrintCapture:
            def __init__(self, original, q):
                self.original = original
                self.q = q
            def write(self, text):
                self.original.write(text)
                text = text.strip()
                if text and len(text) > 2:
                    # 解析 print 输出中的标记
                    icon = "📋"
                    if "[DynamicToolMiddleware]" in text:
                        text = text.replace("[DynamicToolMiddleware] ", "")
                        if "✅" in text: icon = "✅"
                        elif "🔧" in text: icon = "🔧"
                        elif "🎯" in text: icon = "🎯"
                        elif "📊" in text: icon = "📊"
                        elif "📝" in text: icon = "📝"
                        elif "❌" in text: icon = "❌"
                        elif "⚠️" in text: icon = "⚠️"
                    elif "[INFO]" in text:
                        text = text.replace("[INFO] ", "")
                        icon = "ℹ️"
                    elif text.startswith("  -"):
                        icon = "  "
                    else:
                        return  # 忽略其他非标记输出
                    self.q.put({"type": "step", "content": text, "icon": icon})
            def flush(self):
                self.original.flush()
        
        def run_agent():
            old_stdout = sys.stdout
            sys.stdout = PrintCapture(old_stdout, step_queue)
            try:
                result = self.chat(message)
                final_result[0] = result
            except Exception as e:
                error_result[0] = str(e)
            finally:
                sys.stdout = old_stdout
                step_queue.put(None)  # 信号完成
        
        # 在后台线程运行 Agent
        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()
        
        # 逐步 yield 中间事件
        while True:
            try:
                event = step_queue.get(timeout=0.5)
                if event is None:
                    break
                yield event
            except queue.Empty:
                if not thread.is_alive():
                    break
                # 发送心跳防止超时
                yield {"type": "heartbeat"}
        
        # yield 最终结果
        if error_result[0]:
            yield {"type": "error", "content": f"❌ 错误: {error_result[0]}"}
        else:
            yield {
                "type": "done",
                "content": final_result[0] or "（无回复）",
                "agents": list(self.list_agents().keys()),
                "tools": list(self.list_tools().keys())
            }
    
    def list_tools(self) -> Dict[str, str]:
        """列出当前已创建的工具"""
        return self.storage.list_tools()
    
    def get_tool_usage_stats(self) -> Dict[str, int]:
        """获取工具使用统计"""
        return self.middleware.get_usage_stats()
    
    def list_agents(self) -> Dict[str, str]:
        """列出当前已创建的子智能体"""
        return self.agent_storage.list_agents()
    
    def get_agent_details(self) -> List[Dict]:
        """获取所有子智能体的详细信息"""
        details = []
        for name, agent_def in self.agent_storage.agents.items():
            details.append(agent_def.to_dict())
        return details
    
    def export_tools(self, filepath: str):
        """导出工具库到文件"""
        self.storage.export_to_json(filepath)
    
    def export_agents(self, filepath: str):
        """导出智能体库到文件"""
        self.agent_storage.export_to_json(filepath)


def create_tool_creator_agent(
    model: str = "gpt-4",
    thread_id: str = "default",
    **kwargs
) -> ToolCreatorAgent:
    """工厂函数：创建智能体实例"""
    return ToolCreatorAgent(
        model=model,
        thread_id=thread_id,
        **kwargs
    )


if __name__ == "__main__":
    import json
    import os
    
    # 加载配置
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            llm_config = config.get('llm_config', {})
            api_key = llm_config.get('api_key')
            base_url = llm_config.get('api_base')
            model = llm_config.get('model', 'gpt-4')
    except Exception:
        api_key = None
        base_url = None
        model = "gpt-4"

    # 简单测试
    print("=" * 60)
    print("具有自主工具创建和智能体创建能力的智能体系统 v3.0 (Directory Based)")
    print("=" * 60)
    
    agent = create_tool_creator_agent(
        model=model,
        thread_id="test-session-dir",
        api_key=api_key,
        base_url=base_url
    )
    
    print("\n" + "=" * 40)
    print("测试1：创建智能体")
    print("=" * 40)
    response = agent.chat("创建一个数学专家智能体(name: math_expert)，擅长数值计算")
    print(f"回复: {response}")
    
    print("\n" + "=" * 40)
    print("测试2：为智能体创建专属工具")
    print("=" * 40)
    response = agent.chat("""
    为 math_expert 创建一个计算阶乘的工具。
    target_agent: math_expert
    tool_name: calculate_factorial
    code: 
    import math
    result = math.factorial(int(n))
    """)
    print(f"回复: {response}")
    
    print("\n" + "=" * 40)
    print("测试3：委派任务（使用专属工具）")
    print("=" * 40)
    response = agent.chat("让 math_expert 计算 5 的阶乘")
    print(f"回复: {response}")

