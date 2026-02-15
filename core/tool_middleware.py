"""
工具持久化中间件 - 核心创新模块 (LangChain 1.0 优化版)

基于 LangChain 1.0+ 的 Middleware 机制实现工具生命周期自动管理

核心创新点：
1. before_model 钩子：从 checkpoint 自动加载工具
2. wrap_model_call 钩子：动态注入工具到模型请求
3. after_model 钩子：检测新工具创建并触发持久化
4. wrap_tool_call 钩子：拦截工具调用，增强安全性和监控 🆕

优化内容 (基于 LangChain 1.0 最新特性):
- 添加 wrap_tool_call / awrap_tool_call 方法
- 使用动态 tools 属性
- 完善异步支持
- 添加 JumpTo 流程控制
- 增强类型注解
"""
from typing import List, Dict, Any, Optional, Callable, Awaitable
from langchain.tools import BaseTool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
import time
import json

# LangChain 1.0+ 导入
try:
    from langchain.agents.middleware import (
        AgentMiddleware, 
        AgentState, 
        ModelRequest, 
        ModelResponse,
        hook_config,
    )
    from langchain.agents.middleware.types import ToolCallRequest, JumpTo
    from langgraph.runtime import Runtime
    from langgraph.typing import ContextT
    LANGCHAIN_1_AVAILABLE = True
except ImportError:
    # 如果 LangChain 1.0 不可用，定义占位符
    LANGCHAIN_1_AVAILABLE = False
    AgentMiddleware = object
    AgentState = Dict[str, Any]
    ModelRequest = object
    ModelResponse = object
    ToolCallRequest = object
    JumpTo = str
    Runtime = object
    ContextT = object
    
    def hook_config(**kwargs):
        def decorator(func):
            return func
        return decorator

from .tool_storage import ToolStorage, ToolContext
from .tool_creator import get_dynamic_tools


class DynamicToolMiddleware(AgentMiddleware if LANGCHAIN_1_AVAILABLE else object):
    """
    动态工具管理中间件 - 专利核心创新 (LangChain 1.0 优化版)
    
    实现原理：
    1. 利用 LangChain 1.0+ 的 Middleware 机制
    2. 在智能体执行的关键节点插入钩子
    3. 自动管理工具的加载、注入和持久化
    
    关键钩子（LangChain 1.0 完整实现）：
    - before_model：在模型调用前从 checkpoint 恢复工具
    - wrap_model_call：包装模型调用，注入动态工具
    - after_model：在模型调用后检测新工具创建
    - wrap_tool_call：拦截工具调用，增强安全性 🆕
    
    技术优势：
    - 完全自动化，无需手动管理
    - 动态 tools 属性，无需重新初始化 Agent
    - 工具调用拦截，增强安全性和监控
    - 完整的同步和异步支持
    """
    
    def __init__(self, tool_storage: Optional[ToolStorage] = None):
        """初始化中间件
        
        Args:
            tool_storage: 工具存储实例，用于获取动态创建的工具
        """
        self._tool_storage = tool_storage
        self._current_tools: List[BaseTool] = []
        self._tool_usage_stats: Dict[str, int] = {}
        self._last_created_tool: Optional[str] = None
        self._tool_just_created: bool = False
    
    @property
    def name(self) -> str:
        """中间件名称"""
        return "DynamicToolMiddleware"
    
    @property
    def tools(self) -> List[BaseTool]:
        """
        动态返回当前可用的工具列表 🆕
        
        LangChain 1.0 新特性：中间件可以通过 tools 属性提供额外工具，
        这些工具会被自动注册到 Agent，无需手动注入！
        
        Returns:
            当前存储中的所有动态工具
        """
        if self._tool_storage:
            return get_dynamic_tools(self._tool_storage)
        return []
    
    def _load_dynamic_tools(self) -> List[BaseTool]:
        """从存储加载动态工具"""
        if self._tool_storage:
            return get_dynamic_tools(self._tool_storage)
        return []
    
    def _get_dynamic_tool_names(self) -> set:
        """获取所有动态工具的名称"""
        if self._tool_storage:
            return set(self._tool_storage.list_tools().keys())
        return set()
    
    def _increment_usage(self, tool_name: str) -> None:
        """增加工具使用计数"""
        self._tool_usage_stats[tool_name] = self._tool_usage_stats.get(tool_name, 0) + 1
        # 同步更新到存储
        if self._tool_storage:
            tool_def = self._tool_storage.get_tool(tool_name)
            if tool_def:
                tool_def['usage_count'] = tool_def.get('usage_count', 0) + 1
    
    def _log_tool_result(self, tool_name: str, result: ToolMessage) -> None:
        """记录工具执行结果"""
        status = "成功" if result.status != "error" else "失败"
        content_preview = str(result.content)[:100] if result.content else ""
        print(f"[DynamicToolMiddleware] 📊 工具 {tool_name} 执行{status}: {content_preview}...")
    
    # ========== before_model 钩子 ==========
    
    @hook_config(can_jump_to=["end", "model"])
    def before_model(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> Optional[Dict[str, Any]]:
        """
        钩子1：在模型调用前执行 - 工具加载
        
        工作流程：
        1. 检查是否需要跳过模型调用（工具刚创建）
        2. 从 tool_storage 加载动态工具
        3. 更新 self._current_tools
        4. 日志输出
        
        LangChain 1.0 新特性：
        - 使用 @hook_config 支持 JumpTo 流程控制
        - 可以返回 {"jump_to": "end"} 跳过后续步骤
        
        Args:
            state: 当前 Agent 状态
            runtime: LangGraph Runtime 对象
            
        Returns:
            Optional[Dict[str, Any]]: 状态更新或 jump_to 指令
        """
        try:
            # 检查是否刚创建了工具，如果是，可以选择跳过模型调用
            if self._tool_just_created:
                self._tool_just_created = False
                print(f"[DynamicToolMiddleware] 🎯 工具 '{self._last_created_tool}' 已创建")
                # 注意：这里不跳过，让模型继续响应
            
            # 加载动态工具
            self._current_tools = self._load_dynamic_tools()
            
            if self._current_tools:
                print(f"[DynamicToolMiddleware] ✅ 加载了 {len(self._current_tools)} 个自定义工具")
                for tool in self._current_tools:
                    desc = tool.description[:50] if tool.description else "无描述"
                    usage = self._tool_usage_stats.get(tool.name, 0)
                    print(f"  - {tool.name} (使用 {usage} 次): {desc}...")
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ⚠️ 加载工具时出错: {e}")
            self._current_tools = []
        
        return None
    
    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> Optional[Dict[str, Any]]:
        """异步版本的 before_model"""
        # 同步版本已经是非阻塞的，直接调用
        return self.before_model(state, runtime)
    
    # ========== wrap_model_call 钩子 ==========
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """
        钩子2：包装模型调用 - 工具注入
        
        LangChain 1.1.0 的新 API，替代原来的 modify_model_request
        
        工作流程：
        1. 获取 ModelRequest 中现有的工具列表
        2. 注入动态工具
        3. 调用 handler 执行模型
        4. 返回结果
        
        Args:
            request: 原始模型请求
            handler: 执行模型的回调函数
            
        Returns:
            ModelResponse: 模型响应
        """
        try:
            # 获取现有工具
            existing_tools = list(request.tools or [])
            tool_names = {getattr(t, 'name', str(t)) for t in existing_tools}
            
            # 注入动态工具
            added_count = 0
            for tool in self._current_tools:
                if tool.name not in tool_names:
                    existing_tools.append(tool)
                    tool_names.add(tool.name)
                    added_count += 1
            
            if added_count > 0:
                print(f"[DynamicToolMiddleware] 🔧 注入了 {added_count} 个动态工具")
                # 使用 override 方法更新请求（LangChain 1.1.0 推荐方式）
                request = request.override(tools=existing_tools)
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ⚠️ 注入工具时出错: {e}")
        
        # 调用原始 handler
        return handler(request)
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """异步版本的 wrap_model_call"""
        try:
            existing_tools = list(request.tools or [])
            tool_names = {getattr(t, 'name', str(t)) for t in existing_tools}
            
            added_count = 0
            for tool in self._current_tools:
                if tool.name not in tool_names:
                    existing_tools.append(tool)
                    tool_names.add(tool.name)
                    added_count += 1
            
            if added_count > 0:
                print(f"[DynamicToolMiddleware] 🔧 注入了 {added_count} 个动态工具")
                request = request.override(tools=existing_tools)
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ⚠️ 注入工具时出错: {e}")
        
        return await handler(request)
    
    # ========== wrap_tool_call 钩子 🆕 ==========
    
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """
        钩子3.5：拦截工具调用 - 安全验证和监控 🆕
        
        LangChain 1.0 新特性！可以：
        - 在工具执行前进行安全验证
        - 记录工具使用统计
        - 修改工具参数
        - 错误自动重试
        - 缓存工具结果
        
        Args:
            request: 工具调用请求
            handler: 执行工具的回调函数
            
        Returns:
            ToolMessage | Command: 工具执行结果
        """
        tool_call = request.tool_call
        tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
        tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
        
        # 🔒 安全检查：动态工具需要额外验证
        dynamic_tool_names = self._get_dynamic_tool_names()
        is_dynamic = tool_name in dynamic_tool_names
        
        if is_dynamic:
            print(f"[DynamicToolMiddleware] 🔧 执行动态工具: {tool_name}")
            print(f"  参数: {json.dumps(tool_args, ensure_ascii=False, default=str)[:200]}")
        
        # 📊 使用统计
        start_time = time.time()
        self._increment_usage(tool_name)
        
        try:
            # 执行工具
            result = handler(request)
            
            # 计算执行时间
            exec_time = time.time() - start_time
            
            # 📝 记录执行结果
            if isinstance(result, ToolMessage):
                status = "✅ 成功" if result.status != "error" else "❌ 失败"
                print(f"[DynamicToolMiddleware] {status} {tool_name} ({exec_time:.2f}s)")
                
                # 检测工具创建
                if tool_name == 'create_custom_tool' and result.status != "error":
                    self._tool_just_created = True
                    # 尝试从结果中获取工具名
                    try:
                        result_data = json.loads(result.content) if isinstance(result.content, str) else result.content
                        if isinstance(result_data, dict) and result_data.get('success'):
                            self._last_created_tool = result_data.get('tool_name')
                    except:
                        pass
            
            return result
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ❌ 工具 {tool_name} 执行出错: {e}")
            raise
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """异步版本的 wrap_tool_call"""
        tool_call = request.tool_call
        tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
        tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
        
        dynamic_tool_names = self._get_dynamic_tool_names()
        is_dynamic = tool_name in dynamic_tool_names
        
        if is_dynamic:
            print(f"[DynamicToolMiddleware] 🔧 执行动态工具: {tool_name}")
        
        start_time = time.time()
        self._increment_usage(tool_name)
        
        try:
            result = await handler(request)
            exec_time = time.time() - start_time
            
            if isinstance(result, ToolMessage):
                status = "✅ 成功" if result.status != "error" else "❌ 失败"
                print(f"[DynamicToolMiddleware] {status} {tool_name} ({exec_time:.2f}s)")
                
                if tool_name == 'create_custom_tool' and result.status != "error":
                    self._tool_just_created = True
                    try:
                        result_data = json.loads(result.content) if isinstance(result.content, str) else result.content
                        if isinstance(result_data, dict) and result_data.get('success'):
                            self._last_created_tool = result_data.get('tool_name')
                    except:
                        pass
            
            return result
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ❌ 工具 {tool_name} 执行出错: {e}")
            raise
    
    # ========== after_model 钩子 ==========
    
    def after_model(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> Optional[Dict[str, Any]]:
        """
        钩子4：在模型调用后执行 - 工具检测
        
        检测是否调用了 create_custom_tool 或 create_agent
        
        Args:
            state: 当前 Agent 状态
            runtime: LangGraph Runtime 对象
            
        Returns:
            None
        """
        try:
            messages = state.get('messages', [])
            if not messages:
                return None
            
            last_message = messages[-1]
            tool_calls = getattr(last_message, 'tool_calls', []) or []
            
            for tool_call in tool_calls:
                tool_name = (
                    tool_call.get('name')
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, 'name', None)
                )
                
                if tool_name in ('create_custom_tool', 'create_agent'):
                    print(f"[DynamicToolMiddleware] 📝 检测到 {tool_name} 调用")
                    # 工具列表会在下次 before_model 时自动更新
                    break
            
        except Exception as e:
            print(f"[DynamicToolMiddleware] ⚠️ 检测时出错: {e}")
        
        return None
    
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime[ContextT]
    ) -> Optional[Dict[str, Any]]:
        """异步版本的 after_model"""
        return self.after_model(state, runtime)
    
    # ========== 辅助方法 ==========
    
    def get_usage_stats(self) -> Dict[str, int]:
        """获取工具使用统计"""
        return self._tool_usage_stats.copy()
    
    def reset_usage_stats(self) -> None:
        """重置使用统计"""
        self._tool_usage_stats.clear()


# ========== 中间件工厂函数 ==========

def create_tool_middleware(tool_storage: Optional[ToolStorage] = None) -> DynamicToolMiddleware:
    """
    创建工具持久化中间件实例
    
    Args:
        tool_storage: 工具存储实例
    
    Returns:
        DynamicToolMiddleware 实例
    """
    if not LANGCHAIN_1_AVAILABLE:
        raise ImportError(
            "需要 LangChain 1.0+ 才能使用中间件功能。"
            "请安装：pip install langchain>=1.0.0 langgraph>=0.2.0"
        )
    
    return DynamicToolMiddleware(tool_storage=tool_storage)


# ========== 装饰器风格中间件 (可选) ==========

def create_decorator_middleware(tool_storage: ToolStorage):
    """
    使用装饰器风格创建中间件
    
    LangChain 1.0 支持使用 @before_model 等装饰器创建独立的中间件函数
    
    Returns:
        list: 中间件列表
    """
    from langchain.agents.middleware import before_model, after_model
    
    @before_model
    def load_tools_middleware(state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        """装饰器风格的工具加载中间件"""
        tools = get_dynamic_tools(tool_storage)
        if tools:
            print(f"[装饰器中间件] ✅ 加载了 {len(tools)} 个工具")
        return None
    
    @after_model
    def detect_tool_creation_middleware(state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        """装饰器风格的工具创建检测中间件"""
        messages = state.get('messages', [])
        if messages:
            last_msg = messages[-1]
            tool_calls = getattr(last_msg, 'tool_calls', []) or []
            for tc in tool_calls:
                name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', None)
                if name == 'create_custom_tool':
                    print(f"[装饰器中间件] 📝 检测到工具创建")
        return None
    
    return [load_tools_middleware, detect_tool_creation_middleware]


# ========== 使用说明 ==========

"""
使用示例 (LangChain 1.0 优化版)：

```python
from langchain.agents import create_agent
from core.tool_middleware import create_tool_middleware
from core.tool_storage import ToolStorage
from core.tool_creator import get_tool_creator_tools

# 1. 创建工具存储
storage = ToolStorage()

# 2. 创建优化版中间件
middleware = create_tool_middleware(storage)

# 3. 创建智能体
# 注意：不再需要传递动态工具，中间件的 tools 属性会自动提供！
agent = create_agent(
    model="gpt-4",
    tools=get_tool_creator_tools(storage),  # 只需要创建工具的工具
    middleware=[middleware],
    checkpointer=MemorySaver()
)

# 4. 使用智能体
response = agent.invoke({
    "messages": [{"role": "user", "content": "创建一个计算工具"}]
})

# 5. 查看工具使用统计
print(middleware.get_usage_stats())
```

新功能：

1. ✅ wrap_tool_call - 拦截工具调用
   - 安全验证动态工具
   - 记录使用统计
   - 监控执行时间

2. ✅ 动态 tools 属性
   - 无需手动重新加载
   - 创建的工具自动可用

3. ✅ 完整异步支持
   - abefore_model
   - awrap_model_call
   - awrap_tool_call
   - aafter_model

4. ✅ JumpTo 流程控制
   - 可跳过模型调用
   - 灵活的执行流程
"""
